import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const base=process.env.HUNTMAPS_URL,out=process.env.HUNTMAPS_SCREENSHOTS;
if(!base||!out)throw Error('Use isolated pack acceptance or ./gui/check');
fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.HUNTMAPS_BROWSER||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader']});
const page=await browser.newPage({viewport:{width:1500,height:1050}}),errors=[],external=[];
page.setDefaultTimeout(60000);page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',r=>{
 const u=r.request().url();
 if(u.startsWith(base)||u.startsWith('blob:')||u.startsWith('data:'))return r.continue();
 external.push(u);return r.abort();
});
await page.addInitScript(()=>{localStorage.setItem('huntmaps-online-imagery','off');localStorage.setItem('huntmaps-connection-mode','all');});
const headers={'X-HuntMaps':'local'};
async function json(r){assert.equal(r.status(),200,await r.text());return r.json();}
async function waitJob(j){for(let i=0;i<1800;i++){const v=await json(await page.request.get(base+'/api/jobs/'+j.id));if(v.status==='complete')return v;assert.ok(['running','cancelling'].includes(v.status),JSON.stringify(v));await page.waitForTimeout(200);}throw Error('job timeout');}
try{
 await page.goto(base);
 await page.getByRole('button',{name:'New scouting area',exact:true}).click();
 const selector=page.getByLabel('Hunting unit',{exact:true});await selector.locator('option').filter({hasText:'Colorado GMU 54'}).waitFor({state:'attached'});
 const pack=await json(await page.request.get(base+'/api/unit-packs'));const unit=pack.units.find(u=>u.unit_id==='co-gmu54');assert.equal(unit.status,'ready');
 await selector.selectOption('co-gmu54/'+unit.version);
 await page.waitForFunction(()=>document.querySelector('.map')?.dataset.unitPackReady==='true');
 await page.screenshot({path:out+'/unit-selection-desktop.png'});
 await page.setViewportSize({width:900,height:950});await page.screenshot({path:out+'/unit-selection-900.png'});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 // Hold a real context reply across a unit → custom switch. The late reply
 // must not resurrect the old unit outline/relief or clear habitat preferences.
 const habitat=page.getByLabel('Habitat preference',{exact:true});
 await habitat.selectOption('fall-mixed');
 await selector.selectOption('');
 let release, reached=false;const held=new Promise(r=>release=r);
 await page.route('**/api/unit-packs/co-gmu54/'+unit.version,async route=>{const response=await route.fetch();reached=true;await held;await route.fulfill({response});});
 await selector.selectOption('co-gmu54/'+unit.version);
 for(let n=0;n<200&&!reached;n++)await page.waitForTimeout(20);
 assert.ok(reached,'Held actual pack context response reached the test');
 await selector.selectOption('');release();
 await page.waitForTimeout(200);
 assert.equal(await page.locator('.map').getAttribute('data-unit-pack'),null);
 assert.equal(await habitat.inputValue(),'fall-mixed');
 await page.unroute('**/api/unit-packs/co-gmu54/'+unit.version);
 await selector.selectOption('co-gmu54/'+unit.version);
 await page.waitForFunction(()=>document.querySelector('.map')?.dataset.unitPackReady==='true');
 await habitat.selectOption('off');
 await page.setViewportSize({width:1500,height:1050});
 const outcomes=process.env.HUNTMAPS_PACK_ACCEPTANCE?JSON.parse(fs.readFileSync(process.env.HUNTMAPS_PACK_ACCEPTANCE,'utf8')):null;
 let run,cid;
 if(outcomes){run=outcomes[0].run;cid=outcomes[0].candidate;}
 else {
  // Release journey uses a new area and the real pack, never a prepared-run replay.
  const area={type:'Polygon',coordinates:[[[-107.158,38.572],[-107.153,38.572],[-107.153,38.577],[-107.158,38.577],[-107.158,38.572]]]};
  const response=await page.request.post(base+'/api/imports',{headers,multipart:{file:{name:'unit-browser-area.geojson',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({type:'Feature',properties:{},geometry:area}))}}});const imported=await json(response);
  run='pack-browser-'+Date.now();
  const prepared=await json(await page.request.post(base+'/api/plans',{headers,data:{name:run,import_id:imported.id,polygon:'1',unit_id:unit.unit_id,pack_version:unit.version,candidate_count:12,recommendation_count:12,radius_m:1828.8,include_network:true,access_sampling:{network_ids:[],kinds:['roads','trails'],distance_m:804.672,height_m:null},max_download_mb:10,estimate_first:false}}));await waitJob(prepared);
  const plan=await json(await page.request.get(base+'/api/plans/'+prepared.plan));assert.equal(plan.acquisition.estimated_bytes,0);assert.equal(plan.sources_ready,true);
  await waitJob(await json(await page.request.post(base+'/api/plans/'+prepared.plan+'/start',{headers,data:{download:false,review_signature:plan.review_signature}})));
  const r=await json(await page.request.get(base+'/api/runs/'+run));cid=r.candidates[0].id;
 }
 await page.reload();await page.getByRole('button',{name:'Open existing work',exact:true}).click();
 await page.getByLabel('Run selector').selectOption(run);
 await page.locator('.candidate').first().waitFor();
 await page.locator('.coverage-loading').waitFor({state:'hidden',timeout:90000});
 await page.screenshot({path:out+'/pack-results-desktop.png'});
 await page.getByRole('button',{name:'+ New area',exact:true}).click();
 await selector.selectOption('co-gmu54/'+unit.version);await selector.selectOption('');
 await page.getByRole('button',{name:'Back to review',exact:true}).click();
 assert.equal(await page.getByLabel('Run selector').inputValue(),run);
 // Confirmed workflow + actual renderer in the decisive acceptance server.
 if(outcomes){
  await page.locator('.workflow-stages button').filter({hasText:'Inspect'}).click();
  await page.getByRole('button',{name:/Open prepared view|Inspect current setup/}).click();
  await page.waitForFunction(()=>JSON.parse(document.querySelector('.fp-scene')?.getAttribute('data-camera')||'{}').loaded===true);
  // Direct scene metadata is also read independently; the service journey has
  // asserted approach/view/confirmation gates and exact observer coordinates.
  const scene=await json(await page.request.get(base+'/api/runs/'+run+'/first-person/'+cid));assert.equal(scene.fidelity,'terrain');assert.equal(scene.status,'ready');
  await page.screenshot({path:out+'/pack-confirmed-desktop.png'});
  await page.getByRole('button',{name:'Return to map',exact:true}).click();
 }
 await page.setViewportSize({width:900,height:950});await page.screenshot({path:out+'/pack-results-900.png'});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
 // Separate optional-display test: the real pack must still offer default-on
 // satellite context, render it above relief, and fall back without a core error.
 // Controlled colored tiles test composition; they are not source-pack data.
 const satellite=await browser.newPage({viewport:{width:1500,height:1050}});
 satellite.setDefaultTimeout(60000);satellite.on('pageerror',e=>errors.push(e.message));
 const tile=Buffer.from(await satellite.evaluate(()=>{
  const c=document.createElement('canvas');c.width=c.height=256;
  const ctx=c.getContext('2d');ctx.fillStyle='#158c54';ctx.fillRect(0,0,256,256);
  return c.toDataURL().split(',')[1];
 }),'base64');
 let tileRequests=0,failTiles=false;
 await satellite.route('**/*',r=>{
  const u=r.request().url();
  if(u.startsWith('https://basemap.nationalmap.gov/')){
   tileRequests++;return failTiles?r.abort():r.fulfill({contentType:'image/png',body:tile});
  }
  if(u.startsWith(base)||u.startsWith('blob:')||u.startsWith('data:'))return r.continue();
  return r.abort();
 });
 const greenFraction=async()=>{
  const shot=await satellite.locator('.maplibregl-canvas').screenshot();
  return satellite.evaluate(async encoded=>{
   const img=await createImageBitmap(await(await fetch('data:image/png;base64,'+encoded)).blob());
   const c=document.createElement('canvas');c.width=img.width;c.height=img.height;
   const ctx=c.getContext('2d');ctx.drawImage(img,0,0);const d=ctx.getImageData(0,0,c.width,c.height).data;
   let green=0;for(let i=0;i<d.length;i+=4)if(Math.abs(d[i]-21)<4&&Math.abs(d[i+1]-140)<4&&Math.abs(d[i+2]-84)<4)green++;
   return green/(d.length/4);
  },shot.toString('base64'));
 };
 await satellite.goto(base);await satellite.getByRole('button',{name:'New scouting area',exact:true}).click();
 await satellite.getByLabel('Hunting unit',{exact:true}).selectOption('co-gmu54/'+unit.version);
 await satellite.waitForFunction(()=>document.querySelector('.map')?.dataset.unitPackReady==='true');
 await satellite.locator('.layers > summary').click();
 const imagery=satellite.getByLabel('Online imagery — fill gaps',{exact:true});
 assert.equal(await imagery.isChecked(),true,'Satellite remains enabled by default with a prepared unit');
 await satellite.waitForFunction(()=>JSON.parse(document.querySelector('.map')?.dataset.mapState||'{}').loaded===true);
 const rendered=await greenFraction();assert.ok(rendered>.2,'Satellite tiles render above local relief: '+rendered);
 const trailPixels=await satellite.locator('.maplibregl-canvas').screenshot().then(shot=>satellite.evaluate(async encoded=>{
  const img=await createImageBitmap(await(await fetch('data:image/png;base64,'+encoded)).blob());
  const c=document.createElement('canvas');c.width=img.width;c.height=img.height;
  const ctx=c.getContext('2d');ctx.drawImage(img,0,0);const d=ctx.getImageData(0,0,c.width,c.height).data;
  let count=0;for(let i=0;i<d.length;i+=4)if(Math.abs(d[i]-102)<10&&Math.abs(d[i+1]-225)<10&&Math.abs(d[i+2]-188)<10)count++;
  return count;
 },shot.toString('base64')));
 assert.ok(trailPixels>50,'Actual GMU trail pixels remain above opaque satellite imagery: '+trailPixels);
 assert.ok(tileRequests>0);await satellite.screenshot({path:out+'/pack-online-context.png'});
 await imagery.uncheck();
 await satellite.waitForTimeout(250);
 assert.ok(await greenFraction()<.01,'Disabling satellite reveals local relief');
 const disabledRequests=tileRequests;
 await satellite.getByLabel('Hunting unit',{exact:true}).selectOption('');
 await satellite.getByLabel('Hunting unit',{exact:true}).selectOption('co-gmu54/'+unit.version);
 await satellite.waitForFunction(()=>document.querySelector('.map')?.dataset.unitPackReady==='true');
 assert.equal(await imagery.isChecked(),false);assert.equal(tileRequests,disabledRequests);
 failTiles=true;await imagery.check();
 await satellite.getByText('Online imagery could not load.',{exact:false}).waitFor();
 assert.equal(await satellite.getByRole('alert').count(),0);
 assert.equal(await satellite.locator('.map').getAttribute('data-unit-pack-ready'),'true');
 assert.ok(await greenFraction()<.01);await satellite.screenshot({path:out+'/pack-online-fallback.png'});
 failTiles=false;await satellite.getByRole('button',{name:'Retry online imagery',exact:true}).click();
 await satellite.waitForFunction(()=>JSON.parse(document.querySelector('.map')?.dataset.mapState||'{}').loaded===true);
 assert.ok(await greenFraction()>.2);assert.equal(await satellite.getByRole('button',{name:'Retry online imagery',exact:true}).count(),0);
 assert.deepEqual(errors,[]);await satellite.close();
 fs.writeFileSync(out+'/unit-pack-results.json',JSON.stringify({run,cid,errors,external,realPack:unit.version,satellite:{renderedFraction:rendered,tileRequests,toggle:true,fallback:true,retry:true}},null,2));
}finally{await browser.close();}
