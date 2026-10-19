import {chromium} from 'playwright';
import {openExisting,reloadExisting} from './browser-startup.mjs';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
const base=process.env.HUNTMAPS_URL,out=process.env.HUNTMAPS_SCREENSHOTS;
if(!base||!out||!process.env.HUNTMAPS_WORKSPACE)throw Error('Use ./gui/check');
fs.mkdirSync(out,{recursive:true});
const python=path.resolve('../../.venv/bin/python');
const fixture=JSON.parse(execFileSync(python,['-m','gui.habitat_fixture'],{cwd:process.env.HUNTMAPS_WORKSPACE,encoding:'utf8'}).trim().split('\n').at(-1));
const browser=await chromium.launch({executablePath:process.env.HUNTMAPS_BROWSER||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader']});
const page=await browser.newPage({viewport:{width:1500,height:1050}});page.setDefaultTimeout(60000);
const errors=[],requests=[],responses=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push({url:r.url(),method:r.method()}));
await page.addInitScript(run=>{localStorage.setItem('huntmaps-last-area',run);localStorage.setItem('huntmaps-online-imagery','off');},fixture.run);
const get=async p=>{const r=await page.request.get(base+'/api'+p);assert.ok(r.ok(),await r.text());return r.json();};
const waitHabitat=async()=>{await page.getByText('Scoring saved habitat…',{exact:true}).waitFor({state:'hidden'});await page.locator('.candidate-area').filter({hasText:'quality-adjusted acre equivalents'}).first().waitFor();};
const waitOverlay=async()=>{
 await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 await page.waitForFunction(()=>{const m=document.querySelector('.map');return m?.dataset.coverageIdentity?.includes('raster-habitat-')&&m.dataset.coveragePhase==='ready';});
};
try{
 // A recovered screen can carry inherited individual metrics from before a move.
 // Keep actual connection evidence, but deliberately deliver stale original rank fields.
 await page.route(`**/api/runs/${fixture.run}/connectivity-screen`,async route=>{
   const response=await route.fetch(),value=await response.json();
   if(value.recommendation_pool)for(const p of value.recommendation_pool){p.standing_eligible=false;p.matching_km2=0;}
   await route.fulfill({response,json:value});
 });
 await openExisting(page,base,{screenConnections:true});await page.getByLabel('Run selector').selectOption(fixture.run);
 await page.getByLabel('Habitat preference',{exact:true}).waitFor();await waitHabitat();
 assert.equal(await page.getByLabel('Setup order').locator('option:checked').textContent(),'Quality-adjusted area');
 // Actual synthetic network, actual screen service; first habitat leaders excluded by explicit fixture polygons.
 for(let i=0;i<120;i++) {const s=await get(`/runs/${fixture.run}/connectivity-screen`);if(s.status==='complete')break;if(['failed','cancelled'].includes(s.status))throw Error(JSON.stringify(s));await page.waitForTimeout(250);}
 const screen=await get(`/runs/${fixture.run}/connectivity-screen`);assert.equal(screen.status,'complete');
 const sel=await get(`/runs/${fixture.run}/habitat`),value=await get(`/runs/${fixture.run}/habitat/${sel.profile}`);
 assert.ok(fixture.blocked.every(id=>screen.points[id].status!=='connection_found'));
 const allowed=new Set(screen.recommendation_pool.filter(p=>screen.points[p.id]?.status==='connection_found'&&p.group!=='manual'&&p.standing_eligible!==false).map(p=>p.id));
 const expected=value.candidates.filter(p=>allowed.has(p.id)&&p.qualifies&&(p.effective_m2||0)>0).slice(0,screen.recommendation_count).map(p=>p.id);
 assert.ok(expected.length>0);assert.ok(expected.some(id=>!value.recommendation_ids.includes(id)),'Full pool screening must recover alternatives beyond the unscreened top pool');
 await page.waitForFunction(ids=>JSON.stringify([...document.querySelectorAll('.candidate .candidate-topline strong')].map(e=>e.textContent.trim().split(' ')[0]))===JSON.stringify(ids),expected);
 const decisions=await get(`/runs/${fixture.run}/workflow`);
 const beforeScreen=requests.filter(r=>r.method==='POST'&&r.url.includes('connectivity-screen')).length;
 await page.getByLabel('Show all setups',{exact:true}).check();
 await page.waitForFunction(ids=>JSON.stringify([...document.querySelectorAll('.candidate .candidate-topline strong')].map(e=>e.textContent.trim().split(' ')[0]))===JSON.stringify(ids),value.recommendation_ids);
 const selected=value.recommendation_ids[0];await page.getByRole('button',{name:`Select ${selected}`,exact:true}).click();
 await page.getByLabel('Priority-visible habitat overlay',{exact:true}).check();
 await waitOverlay();
 const canvas=out+'/habitat-canvas.png';await page.locator('.maplibregl-canvas').screenshot({path:canvas});
 const pixels=JSON.parse(execFileSync(python,['-c',"from PIL import Image;import numpy as np,json,sys;a=np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype(float);print(json.dumps({'green':int(((a[:,:,1]>a[:,:,0]+30)&(a[:,:,1]>a[:,:,2]+25)).sum())}))",canvas],{encoding:'utf8'}));
 assert.ok(pixels.green>100,'Actual priority raster must render green pixels');
 await page.screenshot({path:out+'/habitat-desktop.png',fullPage:true});
 // Draft survives preference switches; no notes-editor key is tied to rank/profile.
 await page.getByRole('button',{name:'Setup details',exact:true}).click();
 const notes=page.getByLabel('Candidate notes',{exact:true});await notes.waitFor();await notes.fill('Habitat journey unsaved draft');
 await notes.evaluate(n=>window.habitatNotes=n);
 await page.getByRole('button',{name:'← All setups',exact:true}).click();
 await page.getByLabel('Habitat preference',{exact:true}).selectOption('off');
 await page.waitForFunction(()=>!document.querySelector('.candidate-area')?.textContent.includes('quality-adjusted'));
 assert.equal(await page.locator('[id^="raster-habitat"]').count(),0);
 // A habitat-generated run must still offer established recommendations when
 // Show original terrain removes the current review-filter adapter entirely.
 await page.getByRole('button',{name:'Terrain & access filters',exact:false}).click();
 await page.getByRole('button',{name:'Show original terrain',exact:true}).click();
 await page.getByRole('button',{name:'← All setups',exact:true}).click();
 const original=await get(`/runs/${fixture.run}`);
 assert.ok(original.search_summary.established_ids.length);
 assert.notDeepEqual(original.search_summary.established_ids,original.recommendation_ids);
 await page.waitForFunction(ids=>JSON.stringify([...document.querySelectorAll('.candidate .candidate-topline strong')].map(e=>e.textContent.trim().split(' ')[0]))===JSON.stringify(ids),original.search_summary.established_ids);
 await page.getByLabel('Habitat preference',{exact:true}).selectOption('fall-mixed');await waitHabitat();
 await page.getByRole('button',{name:'Setup details',exact:true}).click();await notes.waitFor();assert.equal(await notes.inputValue(),'Habitat journey unsaved draft');assert.ok(await notes.evaluate(n=>n===window.habitatNotes),'Preference changes must preserve the mounted notes editor');await page.getByRole('button',{name:'← All setups',exact:true}).click();
 await reloadExisting(page);await waitHabitat();assert.equal(await page.getByLabel('Habitat preference',{exact:true}).inputValue(),'fall-mixed');
 await page.getByRole('button',{name:'Setup details',exact:true}).click();await notes.waitFor();assert.equal(await notes.inputValue(),'Habitat journey unsaved draft');await page.getByRole('button',{name:'← All setups',exact:true}).click();
 assert.deepEqual(await get(`/runs/${fixture.run}/workflow`),decisions,'Preview and reranking cannot change shortlist/confirmation');
 assert.equal(requests.filter(r=>r.method==='POST'&&r.url.includes('connectivity-screen')).length,beforeScreen,'Habitat switches must not relaunch connectivity');
 // Actual weighted service and UI fields reconcile.
 const collectionReply=page.waitForResponse(r=>r.url().endsWith('/complementary')&&r.ok());
 await page.getByLabel('Recommendation mode').selectOption('complementary');const collection=await (await collectionReply).json();
 await page.locator('.collection-total').filter({hasText:'quality-adjusted acre equivalents'}).waitFor();
 assert.equal(collection.habitat_profile,(await get(`/runs/${fixture.run}/habitat`)).profile);
 assert.ok(Math.abs(collection.suggestions.reduce((n,p)=>n+p.additional_effective_m2,0)-collection.combined_effective_m2)<1e-6);
 await page.getByLabel('Recommendation mode').selectOption('individual');
 // Failure/retry at provider boundary only: scoring uses actual services otherwise.
 let fail=true;
 await page.route(`**/api/runs/${fixture.run}/habitat/*`,async r=>{if(fail&&r.request().method()==='GET'&&!r.request().url().includes('/export')){fail=false;return r.fulfill({status:400,contentType:'application/json',body:'{"detail":"Controlled scoring failure"}'});}return r.continue();});
 await page.getByLabel('Habitat preference',{exact:true}).selectOption('custom');
 await page.getByRole('button',{name:'Retry habitat scoring',exact:true}).waitFor();await page.getByRole('button',{name:'Retry habitat scoring',exact:true}).click();await waitHabitat();
 await page.unroute(`**/api/runs/${fixture.run}/habitat/*`);
 let arrived,release;const held=new Promise(r=>arrived=r),gate=new Promise(r=>release=r);let once=false;
 await page.route(`**/api/runs/${fixture.run}/habitat/*`,async r=>{if(once)return r.continue();once=true;const response=await r.fetch();arrived();await gate;try{await r.fulfill({response});}catch{}});
 await page.getByLabel('Habitat preference',{exact:true}).selectOption('fall-mixed');await held;
 await page.getByLabel('Habitat preference',{exact:true}).selectOption('off');
 await page.waitForFunction(()=>![...document.querySelectorAll('.candidate-area')].some(n=>n.textContent.includes('quality-adjusted')));
 release();await page.waitForTimeout(250);assert.equal(await page.locator('.candidate-area').filter({hasText:'quality-adjusted'}).count(),0,'Late old profile cannot appear under Off');
 await page.unroute(`**/api/runs/${fixture.run}/habitat/*`);await page.getByLabel('Habitat preference',{exact:true}).selectOption('fall-mixed');await waitHabitat();
 await page.getByLabel('Priority-visible habitat overlay',{exact:true}).check();
 await page.setViewportSize({width:900,height:900});
 await waitOverlay();
 const list=await page.locator('.candidate-list').boundingBox(),sidebar=await page.locator('.sidebar').boundingBox();
 assert.ok(list.y+100<sidebar.y+sidebar.height,'Habitat results remain visible at 900px with completed scoring');
 await page.screenshot({path:out+'/habitat-900.png',fullPage:true});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.setViewportSize({width:450,height:450});await waitOverlay();await page.screenshot({path:out+'/habitat-200-percent.png',fullPage:true});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 const runs=await get('/runs');let actualArea=null;
 if(runs.some(r=>r.id==='scouting-2026-10-16222')) {
   actualArea='scouting-2026-10-16222';
   await page.evaluate(run=>localStorage.setItem('huntmaps-connection-mode:'+run,'all'),actualArea);
   await page.setViewportSize({width:1500,height:1050});await page.getByLabel('Run selector').selectOption(actualArea);
   await page.waitForFunction(()=>document.querySelector('select[aria-label="Habitat preference"]')?.value==='off');
   await page.getByLabel('Habitat preference',{exact:true}).selectOption('fall-mixed');await waitHabitat();
   await page.getByLabel('Priority-visible habitat overlay',{exact:true}).check();
   await waitOverlay();
   await page.screenshot({path:out+'/actual-549-desktop.png',fullPage:true});
   await page.setViewportSize({width:900,height:900});await waitOverlay();await page.screenshot({path:out+'/actual-549-900.png',fullPage:true});
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 }
 // UI-boundary fixture only: numerical unknown behavior is independently tested
 // in Python. An unscorable row remains inspectable without a numbered habitat rank.
 await page.setViewportSize({width:1500,height:1050});
 await page.getByLabel('Run selector').selectOption(fixture.run);await waitHabitat();
 const unknownId=value.candidates[0].id;
 await page.route(`**/api/runs/${fixture.run}/habitat/*`,async route=>{
   const response=await route.fetch(),data=await response.json();
   const row=data.candidates?.find(p=>p.id===unknownId);
   if(row)Object.assign(row,{status:'insufficient_data',effective_m2:null,scorable_m2:0,scorable_fraction:0,habitat_unknown_m2:row.matching_m2,high_habitat_m2:0,priority_m2:0,component_effective_m2:{},observation_penalty_m2:0,mean_glassability:null});
   data.recommendation_ids=data.recommendation_ids?.filter(id=>id!==unknownId);
   await route.fulfill({response,json:data});
 });
 await page.getByLabel('Habitat preference',{exact:true}).selectOption('custom');
 await page.getByLabel('Saved neighborhood').selectOption('all');await page.getByLabel('Find a setup').fill(unknownId);
 await page.locator('.candidate-area').filter({hasText:'Insufficient data'}).waitFor();
 assert.equal((await page.locator('.candidate-rank').textContent()).trim(),'—');
 await page.unroute(`**/api/runs/${fixture.run}/habitat/*`);
 assert.deepEqual(errors,[]);fs.writeFileSync(out+'/results.json',JSON.stringify({fixture,expected,collection,pixels,requests,errors,actualArea},null,2));
}catch(e){await page.screenshot({path:out+'/failure.png',fullPage:true});fs.writeFileSync(out+'/failure.txt',await page.locator('body').innerText());throw e;}finally{await browser.close();}
