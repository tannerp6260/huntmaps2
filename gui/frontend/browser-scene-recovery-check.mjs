import {openExisting} from './browser-startup.mjs';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const base=process.env.HUNTMAPS_URL,out=process.env.HUNTMAPS_SCREENSHOTS;
if(!base || !out || !process.env.HUNTMAPS_STATE_DIR?.startsWith('/tmp/'))throw Error('Use ./gui/check');
fs.mkdirSync(out,{recursive:true});
execFileSync(path.resolve('../../.venv/bin/python'),['-m','huntmaps_gui.owner_worker','run','--area','workflow-fixture/observer.geojson','--source-config','workflow-fixture.json','--name','scene-recovery-fixture'],{cwd:process.env.HUNTMAPS_WORKSPACE,stdio:'pipe'});
const browser=await chromium.launch({executablePath:process.env.HUNTMAPS_BROWSER||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader']});
const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));
await page.addInitScript(()=>localStorage.setItem('huntmaps-online-imagery','off'));
await page.route('**/*',route=>route.request().url().startsWith(base)||route.request().url().startsWith('blob:')?route.continue():route.abort());
try {
 await openExisting(page,base);
 await page.getByLabel('Run selector').selectOption('soap-creek-decision-review-v2');
 await page.getByLabel('Select A0075',{exact:true}).click();
 await page.getByRole('button',{name:'View',exact:true}).click();
 const dialog=page.getByRole('dialog',{name:'First-person modeled view',exact:true});
 await dialog.locator('.fp-scene').waitFor();
 assert.equal(await dialog.getByText('Details and settings',{exact:true}).count(),1,'Technical controls belong in a collapsed disclosure');
 assert.equal(await dialog.getByRole('button',{name:'Improve detail',exact:true}).count(),0);
 assert.equal(await dialog.getByRole('button',{name:'Reload scene',exact:true}).count(),0);
 assert.equal(await dialog.getByRole('button',{name:'Review terrain-only scene · no new transfer',exact:true}).count(),0);
 assert.equal(await dialog.getByLabel('First-person setup').count(),1);
 await page.waitForFunction(()=>{const s=JSON.parse(document.querySelector('.fp-scene')?.getAttribute('data-camera')||'{}');return s.loaded&&s.imageryPending===0;});
 await page.screenshot({path:out+'/compact-view.png',fullPage:true});
 console.log('Compact first-person controls passed');
 await dialog.getByRole('button',{name:'Return to map',exact:true}).click();
 // Retry opening reloads saved assets; it must not create a plan or preparation job.
 let retryJobs=0,failAsset=true;
 const countRetryJobs=r=>{if(r.method()==='POST'&&r.url().includes('/api/first-person/plans'))retryJobs++;};
 page.on('request',countRetryJobs);
 await page.route('**/first-person/A0075/assets/fine-vertices.bin?*',route=>failAsset?route.fulfill({status:503,body:'Controlled asset failure'}):route.continue());
 await page.getByRole('button',{name:'View',exact:true}).click();
 await dialog.getByRole('button',{name:'Retry opening view',exact:true}).waitFor();
 assert.equal(await dialog.getByText('Detailed terrain',{exact:true}).count(),1,'A loading failure must retain detailed scene identity');
 failAsset=false;
 await dialog.getByRole('button',{name:'Retry opening view',exact:true}).click();
 await page.waitForFunction(()=>JSON.parse(document.querySelector('.fp-scene')?.getAttribute('data-camera')||'{}').loaded===true);
 assert.equal(retryJobs,0,'Opening retry cannot rebuild or download');
 page.off('request',countRetryJobs);
 for(const width of [900,450]){
  await page.setViewportSize({width,height:900});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No page overflow at '+width);
  assert.ok(await dialog.evaluate(el=>el.scrollWidth<=el.clientWidth+1),'No dialog overflow at '+width);
  await page.screenshot({path:out+'/compact-view-'+width+'.png',fullPage:true});
 }
 await page.setViewportSize({width:1500,height:1000});
 await dialog.getByRole('button',{name:'Return to map',exact:true}).click();
 const run='scene-recovery-fixture',runData=await (await page.request.get(base+'/api/runs/'+run)).json();
 const fallbackCid=runData.candidates[1].id;
 let policy='failed',basicRequests=0,basicStarts=0,bestRequests=0;
 const fakeId='9'.repeat(32),fakePlan='8'.repeat(32);
 const fakeJob=()=>({id:fakeId,plan:fakePlan,kind:'first-person-prepare',status:policy==='basic-fails'?'failed':policy,started:1,elapsed_s:1,stage:'Controlled detailed preparation',error:policy==='failed'?'Controlled dense-ground failure':null});
 await page.route(base+'/api/first-person/plans',route=>{
  const body=route.request().postDataJSON();
  if(body.fidelity==='terrain'){
   basicRequests++;
   if(policy==='basic-fails')return route.fulfill({json:{...fakeJob(),id:'6'.repeat(32),plan:'7'.repeat(32),kind:'first-person-plan',status:'failed'}});
   return route.continue();
  }
  bestRequests++;return route.fulfill({json:fakeJob()});
 });
 await page.route(base+'/api/first-person/plans/'+fakePlan,route=>route.fulfill({json:{id:fakePlan,run_id:run,candidates:[fallbackCid],fidelity:'best',prepared:true,download_cap_bytes:10000000,estimated_new_bytes:0,remaining_new_bytes:0,review_signature:'fixture',sources:[{key:'fixture',cached:true,bytes:1,title:'Controlled source'}],errors:[]}}));
 await page.route(base+'/api/jobs',async route=>{const response=await route.fetch();const jobs=await response.json();await route.fulfill({json:[...jobs,fakeJob()]});});
 await page.route(base+'/api/jobs/'+fakeId,route=>route.fulfill({json:fakeJob()}));
 page.on('request',r=>{if(r.method()==='POST'&&r.url().includes('/api/first-person/plans/')&&r.url().endsWith('/start')){assert.equal(r.postDataJSON().download,false,'Automatic basic preparation cannot download');basicStarts++;}});
 await page.getByLabel('Run selector').selectOption(run);
 await page.getByLabel('Saved neighborhood').selectOption('all');
 await page.getByLabel('Select '+fallbackCid,{exact:true}).click();
 await page.getByRole('button',{name:'View',exact:true}).click();
 await page.waitForFunction(cid=>{const e=document.querySelector('.fp-scene');const data=JSON.parse(e?.getAttribute('data-camera')||'{}');return data.loaded&&data.candidate===cid;},fallbackCid,{timeout:60000});
 assert.equal(basicRequests,1);assert.equal(basicStarts,1);
 await page.getByText('Showing basic terrain; lidar ground and vegetation are unavailable.',{exact:false}).waitFor();
 await page.screenshot({path:out+'/automatic-basic-fallback.png',fullPage:true});
 await page.waitForTimeout(1500);assert.equal(basicRequests,1,'No fallback loop');
 const meta=await (await page.request.get(base+'/api/runs/'+run+'/first-person/'+fallbackCid)).json();
 assert.equal(meta.fine_observer_available,false);
 await dialog.getByText('Details and settings',{exact:true}).click();
 await dialog.getByText('Detailed preparation failed: Controlled dense-ground failure',{exact:true}).waitFor();
 assert.equal(await dialog.getByText('Detailed preparation log',{exact:true}).count(),1,'Fallback must retain the failed detailed job diagnostics');
 await page.getByRole('button',{name:'Return to map',exact:true}).click();
 // Cancelled preparation must not start a basic fallback.
 policy='cancelled';
 const cancelCid=runData.candidates[2].id;
 await page.unroute(base+'/api/first-person/plans/'+fakePlan);
 await page.route(base+'/api/first-person/plans/'+fakePlan,route=>route.fulfill({json:{id:fakePlan,run_id:run,candidates:[cancelCid],fidelity:'best',prepared:true,download_cap_bytes:10000000,estimated_new_bytes:0,remaining_new_bytes:0,sources:[],errors:[]}}));
 await page.getByLabel('Select '+cancelCid,{exact:true}).click();await page.getByRole('button',{name:'View',exact:true}).click();
 await page.waitForTimeout(2000);assert.equal(basicRequests,1,'Cancellation must not trigger fallback');
 await page.getByRole('button',{name:'Return to map',exact:true}).click();
 // A failed basic fallback cannot recursively schedule more jobs.
 policy='basic-fails';const failedCid=runData.candidates[3].id;
 await page.unroute(base+'/api/first-person/plans/'+fakePlan);
 await page.route(base+'/api/first-person/plans/'+fakePlan,route=>route.fulfill({json:{id:fakePlan,run_id:run,candidates:[failedCid],fidelity:'best',prepared:true,download_cap_bytes:10000000,estimated_new_bytes:0,remaining_new_bytes:0,sources:[],errors:[]}}));
 await page.route(base+'/api/first-person/plans/'+'7'.repeat(32),route=>route.fulfill({json:{id:'7'.repeat(32),run_id:run,candidates:[failedCid],fidelity:'terrain',prepared:false,download_cap_bytes:10000000,estimated_new_bytes:0,sources:[],errors:[]}}));
 const failedBasic=()=>({...fakeJob(),id:'6'.repeat(32),plan:'7'.repeat(32),kind:'first-person-plan',status:'failed'});
 await page.route(base+'/api/jobs/'+'6'.repeat(32),route=>route.fulfill({json:failedBasic()}));
 await page.unroute(base+'/api/jobs');
 await page.route(base+'/api/jobs',async route=>{const response=await route.fetch();await route.fulfill({json:[...await response.json(),fakeJob(),...(basicRequests>1?[failedBasic()]:[])]});});
 await page.getByLabel('Select '+failedCid,{exact:true}).click();await page.getByRole('button',{name:'View',exact:true}).click();
 await page.getByText('Basic terrain could not be prepared either.',{exact:false}).waitFor();
 const count=basicRequests;await page.waitForTimeout(1500);assert.equal(basicRequests,count);assert.equal(count,2);
 await page.getByRole('button',{name:'Return to map',exact:true}).click();
 // A source reply arriving after the dialog closes cannot start a fallback.
 policy='failed';const staleCid=runData.candidates[4].id;
 let release,entered;const gate=new Promise(r=>release=r),arrived=new Promise(r=>entered=r);
 await page.unroute(base+'/api/first-person/plans');
 await page.route(base+'/api/first-person/plans',async route=>{entered();await gate;await route.fulfill({json:fakeJob()});});
 await page.getByLabel('Select '+staleCid,{exact:true}).click();await page.getByRole('button',{name:'View',exact:true}).click();await arrived;
 await page.getByRole('button',{name:'Return to map',exact:true}).click();release();await page.waitForTimeout(2000);assert.equal(basicRequests,count);
 assert.deepEqual(errors,[]);
 fs.writeFileSync(out+'/results.json',JSON.stringify({basicRequests,basicStarts,bestRequests,errors,cancellationStoppedFallback:true,failedBasicDidNotLoop:true,closedDialogIgnoredReply:true,openingRetryCreatedNoJobs:retryJobs===0,narrowWidths:[900,450],retainedDetailedFailure:true},null,2));
 console.log('Automatic real basic fallback, cancellation, basic failure and stale-response policy passed');
} catch(error){await page.screenshot({path:out+'/failure.png',fullPage:true});throw error;}
finally{await browser.close();}
