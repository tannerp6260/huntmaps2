import { openExisting, reloadExisting } from './browser-startup.mjs';
import { chromium } from 'playwright';
import fs from 'node:fs';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const base=process.env.HUNTMAPS_URL,out=process.env.HUNTMAPS_SCREENSHOTS;
if(!base||!out)throw Error('Run through ./gui/check');
fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.HUNTMAPS_BROWSER||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader']});
const page=await browser.newPage({viewport:{width:1500,height:1050},reducedMotion:'reduce'}),errors=[],tiles=[],responses=[];
page.on('pageerror',e=>errors.push(e.message));
page.on('request',r=>{if(r.url().includes('/collection-tiles/'))tiles.push(r.url());});
await page.addInitScript(()=>localStorage.setItem('huntmaps-online-imagery','off'));
const cdp=await page.context().newCDPSession(page);await cdp.send('Network.enable');
let hits=0;cdp.on('Network.requestServedFromCache',()=>hits++);
const api=async(path,body)=>{
 const r=body===undefined?await page.request.get(base+'/api'+path):await page.request.post(base+'/api'+path,{headers:{'X-HuntMaps':'local'},data:body});
 assert.ok(r.ok(),await r.text());return r.json();
};
const decide=async(run,cid,action)=>{
 const state=await api(`/runs/${run}/workflow`),point=await api(`/runs/${run}/workflow-point/${cid}`);
 const response=await page.request.put(`${base}/api/runs/${run}/workflow/${cid}`,{headers:{'X-HuntMaps':'local'},data:{revision:state.revision,point,action}});
 assert.ok(response.ok(),await response.text());return response.json();
};
const result=async(action)=>{
 const response=page.waitForResponse(r=>r.url().endsWith('/complementary')&&r.status()===200);
 const start=Date.now();await action();const r=await response,value=await r.json();
 await page.locator('.collection-total').waitFor();
 await page.waitForFunction(id=>document.querySelector('.map')?.dataset.coverageCache?.includes(id),value.id);
 responses.push({count:value.count,run:value.run_id,ms:Date.now()-start,serverSeconds:value.elapsed_s});
 return value;
};
const ready=()=>page.locator('.coverage-status').filter({hasText:'Coverage ready'}).waitFor({timeout:60000});
try {
 await openExisting(page, base);await page.getByLabel('Run selector').selectOption('collection-fixture');
 await page.getByLabel('Recommendation mode').waitFor({timeout:60000});
 const initial=await api('/runs/collection-fixture/workflow');
 const originalRun=await api('/runs/collection-fixture');
 let value=await result(()=>page.getByLabel('Recommendation mode').selectOption('complementary'));
 assert.equal(value.count,5);assert.ok(value.suggestions.length>0);
 assert.deepEqual((await api('/runs/collection-fixture/workflow')),initial,'Computing must preserve decisions');
 assert.deepEqual(await page.locator('.collection-suggestion b').allTextContents(),value.suggestions.map(p=>p.id));
 const selected=value.suggestions[0].id;
 await page.getByRole('button',{name:'Preview contribution '+selected,exact:true}).click();await ready();
 const canvasPath=out+'/collection-canvas.png';await page.locator('.maplibregl-canvas').screenshot({path:canvasPath});
 const python=fileURLToPath(new URL('../../.venv/bin/python',import.meta.url));
 const pixels=JSON.parse(execFileSync(python,['-c',"import sys,json; import numpy as np; from PIL import Image; a=np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype('int16'); print(json.dumps({'pink':int(((a[:,:,0]>a[:,:,1]+25)&(a[:,:,0]>a[:,:,2]+15)).sum()),'cyan':int(((a[:,:,2]>a[:,:,0]+40)&(a[:,:,1]>a[:,:,0]+35)&(a[:,:,2]>105)).sum())}))",canvasPath],{encoding:'utf8'}));
 assert.ok(pixels.pink>1500,'Actual incremental coverage pixels must be visible');
 assert.ok(pixels.cyan>1500,'Actual combined coverage pixels must be visible');
 const preparationStart=Date.now();
 if (await page.locator('.coverage-options').getAttribute('open') === null) await page.locator('.coverage-options > summary').click();
 await page.getByRole('button',{name:'Prepare coverage',exact:true}).click();
 await page.locator('.coverage-preparation[data-phase="ready"]').waitFor({timeout:180000});
 const preparationMs=Date.now()-preparationStart;
 assert.ok(tiles.some(u=>u.includes('/combined/')));
 assert.ok(value.suggestions.every(p=>tiles.some(u=>u.includes('/additional-'+p.id+'/'))));
 assert.ok(JSON.parse(await page.locator('.map').getAttribute('data-coverage-cache')).length<=8);
 const next=value.suggestions.at(-1).id,beforeTiles=tiles.length;
 await page.getByRole('button',{name:'Preview contribution '+next,exact:true}).click();await ready();
 await page.getByRole('button',{name:'Preview contribution '+selected,exact:true}).click();await ready();
 const reviewExtraRequests=tiles.length-beforeTiles;
 value=await result(()=>page.getByLabel('Complementary collection size').selectOption('3'));
 assert.equal(value.count,3);assert.ok(value.suggestions.length<=3);
 await ready();await page.screenshot({path:out+'/collection-desktop.png',fullPage:true});
 await page.getByRole('button',{name:'Add suggestions to shortlist',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('.complementary-views')?.textContent.includes('Your shortlist already fills'));
 const added=await api('/runs/collection-fixture/workflow');
 assert.ok(value.suggestions.every(p=>added.points[p.id].shortlisted));
 for(const [id,point] of Object.entries(added.points))
  assert.equal(!!point.confirmed,!!initial.points[id]?.confirmed,'Shortlisting must preserve prior confirmation and never confirm a new setup');
 const retained=structuredClone(added.points);
 value=await result(()=>page.getByLabel('Complementary collection size').selectOption('5'));
 assert.equal(value.kept.length,3);assert.ok(value.suggestions.length<=2);
 assert.deepEqual((await api('/runs/collection-fixture/workflow')).points,retained);
 if (await page.locator('.coverage-options').getAttribute('open') === null) await page.locator('.coverage-options > summary').click();
 await page.getByRole('button',{name:'Prepare coverage',exact:true}).click();
 await page.locator('.coverage-preparation[data-phase="ready"]').waitFor({timeout:180000});
 await page.locator('.coverage-preparation').getByText('5/5 setups',{exact:false}).waitFor();
 assert.ok(tiles.filter(u=>u.includes('/collection-tiles/'+value.id+'/additional-')).every(u=>value.suggestions.some(p=>u.includes('/additional-'+p.id+'/'))),'Retained positions have combined coverage, not fabricated contribution layers');
 // Dismiss and restore through real workflow endpoints. The API invalidates the old seal.
 if(value.suggestions.length){
  const cid=value.suggestions[0].id;await decide('collection-fixture',cid,'dismiss');
  const dismissed=await api('/runs/collection-fixture/complementary',{count:5,profile:value.profile});
  assert.ok(!dismissed.suggestions.some(p=>p.id===cid));
  const stale=await page.request.post(`${base}/api/runs/collection-fixture/complementary/${value.id}/add`,{headers:{'X-HuntMaps':'local'}});
  assert.equal(stale.status(),400);
  await decide('collection-fixture',cid,'restore');
  const restored=await api('/runs/collection-fixture/complementary',{count:5,profile:value.profile});
  assert.notEqual(restored.id,dismissed.id);
  await page.waitForFunction(id=>document.querySelector('.map')?.dataset.coverageCache?.includes(id),restored.id);
  await ready();
 }
 await page.setViewportSize({width:900,height:900});
 if(await page.getByRole('button',{name:'Setups',exact:true}).isVisible())await page.getByRole('button',{name:'Setups',exact:true}).click();
 await ready();await page.screenshot({path:out+'/collection-900.png',fullPage:true});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 // Controlled delays still use the actual backend response; no invented recommendations.
 let delayedResolve,release;const delayed=new Promise(r=>delayedResolve=r),gate=new Promise(r=>release=r);
 await page.route('**/api/runs/collection-fixture/complementary',async route=>{
  const body=route.request().postDataJSON();
  if(body.count!==4)return route.continue();
  const response=await route.fetch();delayedResolve();await gate;
  try{await route.fulfill({response});}catch{} // aborted old UI request
 });
 await page.getByLabel('Complementary collection size').selectOption('4');await delayed;
 await page.getByLabel('Complementary collection size').selectOption('3');
 await page.waitForFunction(()=>document.querySelector('.complementary-views')?.textContent.includes('Your shortlist already fills'));
 release();await page.waitForTimeout(300);
 assert.equal(await page.getByLabel('Complementary collection size').inputValue(),'3');
 assert.equal(await page.locator('.collection-suggestion').count(),0,'Late size-4 reply must not replace size-3 result');
 // A held response must also be unable to update changed criteria.
 await page.unroute('**/api/runs/collection-fixture/complementary');
 let filterResolve,releaseFilter,heldFilterOnce=false;const filterHeld=new Promise(r=>filterResolve=r),filterGate=new Promise(r=>releaseFilter=r);
 await page.route('**/api/runs/collection-fixture/complementary',async route=>{
  if(route.request().postDataJSON().count!==4||heldFilterOnce)return route.continue();
  heldFilterOnce=true;
  const response=await route.fetch();filterResolve();await filterGate;try{await route.fulfill({response});}catch{}
 });
 await page.getByLabel('Complementary collection size').selectOption('4');await filterHeld;
 await page.getByRole('button',{name:/Terrain & access filters/}).click();
 await page.getByLabel('Minimum Elevation range (feet)',{exact:true}).fill('20000');
 await page.getByLabel('Maximum Elevation range (feet)',{exact:true}).fill('21000');
 await page.getByRole('button',{name:'Apply review filters',exact:true}).click();
 await page.getByRole('button',{name:'← All setups',exact:true}).click();
 await page.getByText('No further eligible position adds matching terrain',{exact:false}).waitFor();
 releaseFilter();await page.waitForTimeout(300);
 assert.equal(await page.locator('.collection-suggestion').count(),0,'Old filter reply must not replace zero matching coverage');
 assert.ok((await page.locator('.collection-total').textContent()).includes('0.000'));
 // A held response must also be unable to update a different run.
 let secondResolve,releaseSecond;const second=new Promise(r=>secondResolve=r),secondGate=new Promise(r=>releaseSecond=r);
 await page.unroute('**/api/runs/collection-fixture/complementary');
 await page.route('**/api/runs/collection-fixture/complementary',async route=>{const response=await route.fetch();secondResolve();await secondGate;try{await route.fulfill({response});}catch{}});
 await page.getByLabel('Complementary collection size').selectOption('5');await second;
 await page.getByLabel('Run selector').selectOption('workflow-fixture');releaseSecond();
 await page.getByLabel('Recommendation mode').waitFor();await page.waitForTimeout(300);
 assert.equal(await page.locator('.collection-total').count(),0);
 assert.equal(await page.getByLabel('Recommendation mode').inputValue(),'individual');
 assert.deepEqual((await api('/runs/collection-fixture')).recommendation_ids,originalRun.recommendation_ids,'Individual ranking remains unchanged');
 // Measure interaction during a cold collection request on available saved real terrain.
 let realInteraction=null;
 const runs=await api('/runs');
 const realRun=runs.find(r=>r.id==='scouting-2026-10-10v4');
 if(realRun){
  await page.unroute('**/api/runs/collection-fixture/complementary');
  await page.setViewportSize({width:1500,height:1050});
  await page.getByLabel('Run selector').selectOption(realRun.id);
  await page.getByLabel('Recommendation mode').waitFor();
  await page.locator('.selected-setup').getByText('matching terrain',{exact:true}).waitFor({timeout:60000});
  await ready();
  await page.evaluate(()=>{window.__coverageFrames=[];window.__coverageSampling=true;const sample=t=>{window.__coverageFrames.push(t);if(window.__coverageSampling)requestAnimationFrame(sample)};requestAnimationFrame(sample)});
  const response=page.waitForResponse(r=>r.url().endsWith('/complementary')&&r.status()===200);
  const start=Date.now();await page.getByLabel('Recommendation mode').selectOption('complementary');
  const clickStart=Date.now();await page.getByRole('button',{name:'Zoom in',exact:true}).click();const zoomClickMs=Date.now()-clickStart;
  const value=await (await response).json();
  await page.locator('.collection-total').waitFor();await ready();
  const frames=await page.evaluate(()=>{window.__coverageSampling=false;return window.__coverageFrames});
  assert.ok(frames.length>2,'Browser must continue rendering through the real calculation');
  realInteraction={run:realRun.id,evaluated:value.evaluated_count,serverSeconds:value.elapsed_s,responseMs:Date.now()-start,zoomClickMs,renderedFrames:frames.length,maximumFrameGapMs:Math.max(...frames.slice(1).map((t,i)=>t-frames[i]))};
  await page.screenshot({path:out+'/real-collection-desktop.png',fullPage:true});
 }
 assert.deepEqual(errors,[]);
 fs.writeFileSync(out+'/results.json',JSON.stringify({responses,preparationMs,reviewExtraRequests,cacheHits:hits,tiles:tiles.length,pixels,errors,realInteraction,actualBackend:true},null,2));
 console.log('Actual backend collection, contributions, map pixels, prepared review, explicit additions, dismissal/restoration, stale size/run responses and narrow layout verified');
}catch(e){await page.screenshot({path:out+'/failure.png',fullPage:true});fs.writeFileSync(out+'/failure.txt',await page.locator('body').innerText());throw e;}finally{await browser.close();}
