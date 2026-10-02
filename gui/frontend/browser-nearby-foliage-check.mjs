import {chromium} from 'playwright';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const base=process.env.HUNTMAPS_URL||'http://127.0.0.1:8765',out=process.env.HUNTMAPS_SCREENSHOTS||'/tmp/huntmaps-nearby-foliage';fs.mkdirSync(out,{recursive:true});
const current=await (await fetch(base+'/api/runs/soap-creek-decision-review-v2/first-person/A0075')).json();
if(current.vegetation?.meshes){await import('./browser-clusters-check.mjs');process.exit(0)}
const browser=await chromium.launch({executablePath:process.env.HUNTMAPS_BROWSER||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader']});
try{
 const page=await browser.newPage({viewport:{width:1900,height:1050}});page.setDefaultTimeout(45000);const errors=[],external=[];page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(r.url().startsWith('http')&&!r.url().startsWith(base))external.push(r.url())});
 await page.addInitScript(()=>localStorage.setItem('huntmaps-online-imagery','off'));await page.route('**/*',r=>r.request().url().startsWith(base)||r.request().url().startsWith('blob:')?r.continue():r.abort());
 const api=base+'/api/runs/soap-creek-decision-review-v2';
 const annotations=await (await page.request.get(api+'/annotations')).text(),jobs=await (await page.request.get(base+'/api/jobs')).json();
 await page.goto(base);await page.getByLabel('Select A0075',{exact:true}).click();await page.getByRole('button',{name:'View from this setup',exact:true}).click();
 const loaded=cid=>page.waitForFunction(cid=>{const s=JSON.parse(document.querySelector('.fp-scene')?.getAttribute('data-camera')||'{}');return s.candidate===cid&&s.loaded&&s.imageryPending===0},cid);
 const state=async()=>JSON.parse(await page.locator('.fp-scene').getAttribute('data-camera'));
 await loaded('A0075');assert.equal((await state()).vegetationRadius,120);
 const evidence={};
 for(const cid of ['A0075','V010','V008','A0031']){
  await page.getByLabel('First-person setup',{exact:true}).selectOption(cid);await loaded(cid);
  const meta=await (await page.request.get(api+'/first-person/'+cid)).json();evidence[cid]={counts:{}};
  for(const radius of [30,60,120]){
   await page.getByLabel('Nearby foliage range',{exact:true}).selectOption(String(radius));
   await page.waitForFunction(r=>JSON.parse(document.querySelector('.fp-scene').getAttribute('data-camera')).vegetationRadius===r,radius);
   const s=await state();assert.equal(s.vegetationCells,meta.vegetation.nearby_counts[String(radius)]);assert.equal(s.primitiveTriangles,20);assert.equal(s.geometryIdentifier,'icosahedron-20-v1');assert.ok(s.rawPointRadiusMax<=radius);assert.ok(s.vegetationCells<=25000);evidence[cid].counts[radius]=s.vegetationCells;
  }
  await page.getByLabel('Nearby foliage range',{exact:true}).selectOption('30');await page.waitForFunction(()=>JSON.parse(document.querySelector('.fp-scene').getAttribute('data-camera')).vegetationRadius===30);
  await page.waitForTimeout(1000);const before=await state();await page.waitForTimeout(1000);const after=await state();assert.equal(after.draws,before.draws);evidence[cid].idleDraws=after.draws-before.draws;
 }
 await page.getByLabel('First-person setup',{exact:true}).selectOption('A0075');await loaded('A0075');
 await page.getByLabel('First-person heading',{exact:true}).fill('187');await page.getByLabel('First-person look angle',{exact:true}).fill('-16');
 await page.waitForFunction(()=>{const s=JSON.parse(document.querySelector('.fp-scene').getAttribute('data-camera'));return s.heading===187&&s.look===-16});
 for(const radius of [30,60,120]){
  await page.getByLabel('Nearby foliage range',{exact:true}).selectOption(String(radius));await page.waitForFunction(r=>JSON.parse(document.querySelector('.fp-scene').getAttribute('data-camera')).vegetationRadius===r,radius);
  await page.locator('.fp-scene').scrollIntoViewIfNeeded();await page.locator('.fp-scene').screenshot({path:out+'/A0075-rounded-'+radius+'m.png'});
 }
 await page.getByLabel('Nearby foliage range',{exact:true}).selectOption('30');
 const profile=await (await page.request.post(api+'/first-person/A0075/profile',{headers:{'X-HuntMaps':'local'},data:{east_m:0,north_m:-120,vegetation_scenario:'medium',vegetation_radius_m:30}})).json();
 assert.equal(profile.vegetation.evaluated_radius_m,30);assert.equal(profile.vegetation.geometry_identifier,'icosahedron-20-v1');assert.equal(profile.vegetation.farther_vegetation_unevaluated,true);
 const map=page.getByLabel('Choose inspection target on plan map',{exact:true});await map.scrollIntoViewIfNeeded();const b=await map.boundingBox();await page.mouse.click(b.x+b.width*.5,b.y+b.height*.69);
 await page.getByText('Target extends beyond nearby range; farther vegetation is unevaluated.',{exact:false}).waitFor();
 const start=Date.now();await page.getByLabel('First-person heading',{exact:true}).fill('200');await page.waitForFunction(()=>JSON.parse(document.querySelector('.fp-scene').getAttribute('data-camera')).heading===200);const latencyMs=Date.now()-start;assert.ok(latencyMs<2000);
 await page.screenshot({path:out+'/foreground-inspection.png',fullPage:true});assert.deepEqual(errors,[]);assert.deepEqual(external,[]);assert.equal(await (await page.request.get(api+'/annotations')).text(),annotations);assert.equal((await (await page.request.get(base+'/api/jobs')).json()).length,jobs.length);
 fs.writeFileSync(out+'/results.json',JSON.stringify({evidence,latencyMs,profile,errors,external},null,2));console.log('Nearby range, rounded geometry, scoped screening, offline and zero idle draws verified');
}finally{await browser.close()}
