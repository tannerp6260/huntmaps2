import { chromium } from 'playwright';
import { openExisting } from './browser-startup.mjs';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const base=process.env.HUNTMAPS_URL,out=process.env.HUNTMAPS_SCREENSHOTS;
if(!base||!out)throw Error('Run through .venv/bin/python -m gui.check');
fs.mkdirSync(out,{recursive:true});
// Delayed history/direct-job responses cannot erase or regress a returned job.
{
 const originalFetch=globalThis.fetch, pending=[];
 globalThis.fetch=(path)=>new Promise(resolve=>pending.push({path,resolve}));
 try{
  const source=fs.readFileSync('src/polling.ts','utf8').replace("import { useSyncExternalStore } from 'react';","const useSyncExternalStore=()=>undefined;");
  const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext}}).outputText;
  const polling=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
  const history=polling.refreshPolling();
  const job={id:'a'.repeat(32),plan:'b'.repeat(32),kind:'approach',status:'running'};
  polling.trackJob(job);pending.shift().resolve({ok:true,json:async()=>[]});await history;
  assert.equal(polling.jobSnapshot()[0].id,job.id);assert.equal(polling.jobSnapshot()[0].elapsed_s,0);
  const old=polling.refreshPolling();assert.ok(pending[0].path.endsWith('/'+job.id));
  polling.trackJob({...job,status:'cancelling'});
  pending.shift().resolve({ok:true,json:async()=>job});await old;
  assert.equal(polling.jobSnapshot()[0].status,'cancelling');
 }finally{globalThis.fetch=originalFetch;}
}
const browser=await chromium.launch({executablePath:process.env.HUNTMAPS_BROWSER||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader']});
const page=await browser.newPage({viewport:{width:1500,height:1050}}),errors=[],timings=[],requests=[];
page.setDefaultTimeout(45000);page.on('pageerror',e=>errors.push(e.message));
await page.addInitScript(()=>{
 localStorage.setItem('huntmaps-online-imagery','off');
 window.guidedFeedback=[];
 document.addEventListener('click',e=>{const b=e.target.closest('button');if(!b||!(/Calculate approaches|Recalculate approaches|Use this approach/.test(b.textContent)))return;
  const start=performance.now();const observer=new MutationObserver(()=>{if(document.body.textContent.includes('Submitting approach calculation')||document.body.textContent.includes('Saving approach')){window.guidedFeedback.push(performance.now()-start);observer.disconnect();}});observer.observe(document.body,{childList:true,characterData:true,subtree:true});
 },true);
});
await page.route('**/*',r=>r.request().url().startsWith(base)||r.request().url().startsWith('blob:')?r.continue():r.abort());
// Browse tiles are independently mocked, with requests beyond analysis bounds permitted.
const transparent=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAQAAAAEACAYAAABccqhmAAABFUlEQVR4nO3BMQEAAADCoPVP7WsIoAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAeAMBPAABPO1TCQAAAABJRU5ErkJggg==','base64');
await page.route('**/api/browsing/transportation/**',r=>{requests.push(r.request().url());return r.fulfill({body:transparent,contentType:'image/png'});});
const run='collection-fixture',url=base+'/api/runs/'+run,headers={'X-HuntMaps':'local'};
async function state(){return(await page.request.get(url+'/workflow')).json();}
async function decide(cid,action){const s=await state();const point=s.points[cid]?.point||await(await page.request.get(url+'/workflow-point/'+cid)).json();const r=await page.request.put(url+'/workflow/'+cid,{headers,data:{action,point,revision:s.revision}});assert.equal(r.status(),200,await r.text());}
async function waitJob(j){for(let i=0;i<180;i++){const response=await page.request.get(base+'/api/jobs/'+j.id);const v=await response.json();if(v.status==='complete')return v;if(!['running','cancelling'].includes(v.status))throw Error(JSON.stringify(v));await page.waitForTimeout(250);}throw Error('job timeout');}
try{
 await openExisting(page,base);await page.getByLabel('Run selector').selectOption(run);
 const result=await(await page.request.get(url)).json();
 const original=await state();for(const [cid,p]of Object.entries(original.points))if(p.shortlisted)await decide(cid,'remove');
 // Complementary per-member decisions and immediate invalidation.
 await page.getByLabel('Recommendation mode').selectOption('complementary');
 await page.locator('.collection-suggestion').first().waitFor();
 const first=await page.locator('.collection-suggestion').first().locator('b').innerText();
 await page.getByRole('button',{name:'Shortlist '+first,exact:true}).click();
 await page.getByText(first+': shortlisted.',{exact:false}).waitFor();
 const toast=page.locator('.decision-toast');await toast.hover();await page.waitForTimeout(8200);assert.ok(await toast.isVisible(),'hover pauses decision expiry');
 await page.mouse.move(0,0);await toast.waitFor({state:'hidden',timeout:9000});
 await page.locator('.collection-suggestion').first().waitFor();
 const dismissed=await page.locator('.collection-suggestion').first().locator('b').innerText();
 let release;const blocked=new Promise(r=>release=r);
 await page.route('**/workflow/'+dismissed,async route=>{await blocked;await route.continue();});
 await page.getByRole('button',{name:'Dismiss '+dismissed,exact:true}).click();
 await page.waitForFunction(cid=>!JSON.parse(document.querySelector('.map').dataset.mapState||'{}').candidateIds?.includes(cid),dismissed);
 assert.equal(await page.locator('.map').evaluate(el=>JSON.parse(el.dataset.coverageCache||'[]').some(id=>id.includes('collection')&&getComputedStyle(el).display==='none')),false);
 release();const undo=page.waitForResponse(r=>r.url()===url+'/workflow/'+dismissed&&r.request().method()==='PUT'&&r.request().postDataJSON()?.action==='undo');await page.getByRole('button',{name:'Undo',exact:true}).click();const restored=await undo;assert.equal(restored.status(),200,await restored.text());await page.unroute('**/workflow/'+dismissed);
 await page.getByLabel('Recommendation mode').selectOption('individual');
 const second=result.candidates.find(p=>p.id!==first&&p.id!==dismissed).id;await decide(second,'shortlist');
 // Reload to obtain the authoritative revision after API seeding.
 await page.reload();await page.getByRole('button',{name:'Open existing work',exact:true}).click();await page.getByLabel('Run selector').selectOption(run);
 await page.getByRole('button',{name:'Plan approaches (2 shortlisted)',exact:true}).click();
 await page.getByRole('button',{name:'Confirm approach search boundary',exact:true}).waitFor();
 assert.ok(await page.getByText('Boundary needs confirmation',{exact:false}).isVisible());
 const focused=await page.getByLabel('Focused approach spot').inputValue();
 const p=result.candidates.find(p=>p.id===focused),line={type:'LineString',coordinates:[[p.longitude-.0006,p.latitude-.002],[p.longitude-.0006,p.latitude+.002]]};
 await page.locator('.approach-sources > summary').click();
 await page.locator('.scouting-tools').getByLabel('Import road trail network',{exact:true}).setInputFiles({name:'guided-network.geojson',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(line))});
 await page.getByRole('button',{name:'Confirm approach search boundary',exact:true}).click();
 await page.locator('.approach-boundary-check[data-ready="true"]').waitFor();
 await page.getByText('More options · pinned departure and preferences',{exact:true}).click();
 const slope=page.getByLabel('Maximum approach slope');assert.equal(await slope.inputValue(),'25');
 await slope.fill('');assert.equal(await slope.inputValue(),'');assert.equal(await page.getByRole('button',{name:'Calculate approaches for '+focused,exact:true}).isDisabled(),true);
 await slope.fill('36');assert.equal(await slope.getAttribute('aria-invalid'),'true');await slope.fill('025');await slope.blur();assert.equal(await slope.inputValue(),'25');assert.equal(await slope.getAttribute('autocomplete'),'off');
 await page.getByLabel('Approach tree weight').fill('4');
 // Hold the submission to verify feedback independently of worker speed.
 await page.route('**/runs/'+run+'/approaches',async r=>{if(r.request().method()==='POST')await new Promise(resolve=>setTimeout(resolve,700));await r.continue();});
 await page.getByRole('button',{name:'Calculate approaches for '+focused,exact:true}).click();
 await page.getByRole('button',{name:'Submitting approach calculation…',exact:true}).waitFor({timeout:200});
 assert.equal(await slope.isDisabled(),true);assert.equal((await page.locator('.approach-controls').innerText()).includes('Approach job complete'),false);
 await page.getByRole('button',{name:'Use this approach & next spot',exact:true}).first().waitFor({timeout:60000});
 assert.ok(await page.locator('.approach-alternative').count()>=1);
 assert.equal(await page.getByRole('button',{name:'Finished',exact:true}).count(),0);
 let failSave=true;
 await page.route('**/workflow/'+focused,async route=>{if(failSave && route.request().postDataJSON()?.action==='approach'){failSave=false;return route.fulfill({status:500,json:{detail:'Injected save failure'}});}return route.continue();});
 await page.getByRole('button',{name:'Use this approach & next spot',exact:true}).first().click();
 await page.getByText('Injected save failure',{exact:false}).waitFor();assert.equal(await page.getByLabel('Focused approach spot').inputValue(),focused);
 await page.getByRole('button',{name:'Use this approach & next spot',exact:true}).first().click();
 await page.unroute('**/workflow/'+focused);
 await page.waitForFunction(id=>document.querySelector('[aria-label="Focused approach spot"]')?.value!==id,focused);
 await page.getByRole('button',{name:'Confirm approach search boundary',exact:true}).waitFor();
 const next=await page.getByLabel('Focused approach spot').inputValue();
 if(await page.getByLabel('Approach tree weight').isVisible()===false)await page.getByText('More options · pinned departure and preferences',{exact:true}).click();
 assert.equal(await page.getByLabel('Approach tree weight').inputValue(),'4','preferences carry to the next unreviewed spot');
 await page.getByRole('button',{name:'Confirm approach search boundary',exact:true}).click();
 // Imported source remains an explicit, selectable override for the second proposal.
 if(!await page.locator('.approach-boundary-check[data-ready="true"]').count()){
  const details=page.locator('.approach-sources');await details.evaluate(el=>el.open=true);const checkbox=details.locator('label').filter({hasText:'guided-network.geojson'}).locator('input');await checkbox.check();
 }
 await page.locator('.approach-boundary-check[data-ready="true"]').waitFor();
 await page.getByRole('button',{name:'Calculate approaches for '+next,exact:true}).click();await page.getByRole('button',{name:'Use this approach & next spot',exact:true}).first().waitFor({timeout:60000});
 await page.getByRole('button',{name:'Use this approach & next spot',exact:true}).first().click();
 await page.getByRole('button',{name:/Open prepared view|Inspect current setup/}).waitFor();
 // Prepare existing terrain for this engineering fixture; no live source acquisition.
 const active=(await state()).points;
 for(const cid of [first,second]){
  const j=await(await page.request.post(base+'/api/first-person/plans',{headers,data:{run_id:run,ids:[cid],fidelity:'terrain'}})).json();await waitJob(j);
  const plan=await(await page.request.get(base+'/api/first-person/plans/'+j.plan)).json();
  const job=await(await page.request.post(base+'/api/first-person/plans/'+j.plan+'/start',{headers,data:{download:true,review_signature:plan.review_signature}})).json();await waitJob(job);
 }
 await page.getByRole('button',{name:/Open prepared view|Inspect current setup/}).click();
 await page.getByRole('dialog',{name:'First-person modeled view',exact:true}).waitFor();
 await page.getByLabel('Inspection map radius',{exact:true}).waitFor();
 await page.waitForFunction(()=>JSON.parse(document.querySelector('.fp-scene')?.getAttribute('data-camera')||'{}').loaded===true);
 const opened=JSON.parse(await page.locator('.fp-scene').getAttribute('data-camera')).candidate;
 assert.ok([first,second].includes(opened),'Opened scene belongs to the shortlisted inspection queue');
 const scene=await(await page.request.get(url+'/first-person/'+opened)).json();
 const expected=result.candidates.find(p=>p.id===opened);
 assert.equal(scene.observer.longitude,expected.longitude);
 assert.equal(scene.observer.latitude,expected.latitude);
 await page.getByRole('heading',{name:'View from '+opened+' Basic terrain',exact:true}).waitFor();
 assert.equal(Number(await page.getByLabel('Inspection map radius').inputValue()),Math.min(914.4,scene.context_radius_m));
 const planMap=page.getByLabel('Choose inspection target on plan map',{exact:true});await planMap.scrollIntoViewIfNeeded();const planBounds=await planMap.boundingBox();await planMap.click({position:{x:planBounds.width*.6,y:planBounds.height*.45}});
 await page.getByText('Horizontal:',{exact:false}).waitFor();
 const targetBefore=await page.locator('.scene-view').getAttribute('data-selected-target');
 const eyeView=page.getByLabel('Look around terrain',{exact:true});await eyeView.scrollIntoViewIfNeeded();
 const viewBounds=await eyeView.boundingBox();await eyeView.click({position:{x:viewBounds.width*.5,y:viewBounds.height*.8}});
 await page.waitForFunction(before=>document.querySelector('.scene-view')?.dataset.selectedTarget!==before,targetBefore);
 const afterClick=await page.locator('.scene-view').getAttribute('data-selected-target');
 const box=await eyeView.boundingBox();await page.mouse.move(box.x+200,box.y+150);await page.mouse.down();await page.mouse.move(box.x+280,box.y+150,{steps:5});await page.mouse.up();
 assert.equal(await page.locator('.scene-view').getAttribute('data-selected-target'),afterClick,'drag rotates without replacing target');

 await page.screenshot({path:out+'/inspect-desktop.png',fullPage:true});
 await page.setViewportSize({width:900,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:out+'/inspect-900.png',fullPage:true});
 await page.getByRole('dialog').getByRole('button',{name:'Confirm setup',exact:true}).click();
 await page.getByLabel('Inspection map radius').waitFor();
 await page.getByRole('dialog').getByRole('button',{name:'Confirm setup',exact:true}).click();
 await page.locator('.collection-export').waitFor();
 const finished=await state();assert.equal(Object.values(finished.points).filter(p=>p.confirmed).length,2);
 timings.push(...await page.evaluate(()=>window.guidedFeedback));assert.ok(timings.length>=2);assert.ok(timings.every(t=>t<200),JSON.stringify(timings));
 assert.ok(requests.length>0);assert.deepEqual(errors,[]);
 fs.writeFileSync(out+'/results.json',JSON.stringify({errors,feedbackMs:timings,browsingTiles:requests.length,workflow:finished},null,2));
 console.log('Guided Find → Approach → Inspect → Save, desktop/900px, source separation and pending feedback verified');
}catch(e){await page.screenshot({path:out+'/failure.png',fullPage:true});fs.writeFileSync(out+'/failure.txt',await page.locator('body').innerText());throw e;}finally{await browser.close();}
