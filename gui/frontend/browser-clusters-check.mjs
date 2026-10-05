if(!process.env.HUNTMAPS_URL||!process.env.HUNTMAPS_SCREENSHOTS)throw Error('Run through ./gui/check with an isolated server and screenshot directory');
import {chromium} from 'playwright';
import fs from 'node:fs';
import assert from 'node:assert/strict';
import * as THREE from 'three';
const base=process.env.HUNTMAPS_URL,out=process.env.HUNTMAPS_SCREENSHOTS;fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.HUNTMAPS_BROWSER||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader']});
try{
 const page=await browser.newPage({viewport:{width:1900,height:1050}});page.setDefaultTimeout(60000);const errors=[],external=[];page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(r.url().startsWith('http')&&!r.url().startsWith(base))external.push(r.url())});
 await page.addInitScript(()=>localStorage.setItem('huntmaps-online-imagery','off'));await page.route('**/*',r=>r.request().url().startsWith(base)||r.request().url().startsWith('blob:')?r.continue():r.abort());
 const api=base+'/api/runs/soap-creek-decision-review-v2';
 const annotations=await (await page.request.get(api+'/annotations')).text(),jobs=await (await page.request.get(base+'/api/jobs')).json();
 const currentMeta=await (await page.request.get(api+'/first-person/A0075')).json();
 const legacy=JSON.parse(fs.readFileSync((process.env.HUNTMAPS_SCENE_SOURCE||'../../.gui/first-person')+'/bundles/'+currentMeta.reused_base_bundle+'/scene.json','utf8'));
 const legacyRoute=route=>route.fulfill({json:{...legacy,key:currentMeta.key,initial_bearing_deg:currentMeta.initial_bearing_deg,initial_facing_note:currentMeta.initial_facing_note}});
 await page.route(api+'/first-person/A0075',legacyRoute);
 await page.goto(base);await page.getByLabel('Select A0075',{exact:true}).click();await page.getByRole('button',{name:'View',exact:true}).click();
 const loaded=cid=>page.waitForFunction(cid=>{const s=JSON.parse(document.querySelector('.fp-scene')?.getAttribute('data-camera')||'{}');return s.candidate===cid&&s.loaded&&s.imageryPending===0},cid);
 const state=async()=>JSON.parse(await page.locator('.fp-scene').getAttribute('data-camera'));
 await loaded('A0075');await page.getByLabel('First-person heading',{exact:true}).fill('187');await page.getByLabel('First-person look angle',{exact:true}).fill('-16');
 await page.waitForFunction(()=>{const s=JSON.parse(document.querySelector('.fp-scene').getAttribute('data-camera'));return s.loaded&&s.heading===187&&s.look===-16});
 await page.locator('.fp-scene').scrollIntoViewIfNeeded();await page.locator('.fp-scene').screenshot({path:out+'/A0075-before-clumps-120m.png'});
 await page.getByRole('button',{name:'Return to map',exact:true}).click();await page.unroute(api+'/first-person/A0075',legacyRoute);await page.getByRole('button',{name:'View',exact:true}).click();
 await loaded('A0075');assert.equal((await state()).vegetationRadius,120);
 const evidence={};
 for(const cid of ['A0075','V010','V008','A0031']){
  await page.getByLabel('First-person setup',{exact:true}).selectOption(cid);await loaded(cid);
  const meta=await (await page.request.get(api+'/first-person/'+cid)).json();evidence[cid]={ranges:{}};assert.equal(meta.version,6);assert.ok(meta.vegetation.neighbor_supported_cell_count>0);
  const camera=await state(),info=meta.vegetation.meshes['120'];assert.equal(camera.vegetationScenario,'dense');assert.equal(camera.vegetationTriangles,info.scenarios.dense.triangle_count);assert.ok(camera.vegetationTriangles<=500000);assert.equal(camera.geometryIdentifier,'rounded-cell-union-v2');assert.ok(camera.rawPointRadiusMax<=120);evidence[cid].ranges[120]={dense:{cells:camera.vegetationCells,triangles:camera.vegetationTriangles,step:camera.samplingInterval}};
  await page.waitForTimeout(1000);const before=await state();await page.waitForTimeout(1000);const after=await state();assert.equal(after.draws,before.draws);evidence[cid].idleDraws=after.draws-before.draws;
  await page.getByLabel('First-person heading',{exact:true}).fill('187');await page.getByLabel('First-person look angle',{exact:true}).fill('-16');await page.waitForFunction(()=>{const s=JSON.parse(document.querySelector('.fp-scene').getAttribute('data-camera'));return s.loaded&&s.heading===187&&s.look===-16});
  await page.locator('.fp-scene').scrollIntoViewIfNeeded();await page.locator('.fp-scene').screenshot({path:out+'/'+cid+'-clusters-120m.png'});
 }
 await page.getByLabel('First-person setup',{exact:true}).selectOption('A0075');await loaded('A0075');
 const profile=await (await page.request.post(api+'/first-person/A0075/profile',{headers:{'X-HuntMaps':'local'},data:{east_m:0,north_m:-120,vegetation_scenario:'medium',vegetation_radius_m:30}})).json();
 assert.equal(profile.vegetation.evaluated_radius_m,30);assert.equal(profile.vegetation.geometry_identifier,'rounded-cell-union-v2');assert.equal(profile.vegetation.farther_vegetation_unevaluated,true);
 const map=page.getByLabel('Choose inspection target on plan map',{exact:true});await map.scrollIntoViewIfNeeded();const b=await map.boundingBox();await page.mouse.click(b.x+b.width*.5,b.y+b.height*.69);await page.locator('.fp-vegetation table').waitFor();assert.equal(await page.locator('.fp-vegetation tbody tr').count(),3);
 // Exercise a measured nearby target and verify UI/profile mesh identity.
 const current=await (await page.request.get(api+'/first-person/A0075')).json();const raw=await (await page.request.get(api+'/first-person/A0075/assets/'+current.vegetation.centres_file)).body();const centres=new Float32Array(raw.buffer.slice(raw.byteOffset,raw.byteOffset+raw.byteLength));
 let chosen,chosenTarget;for(let i=0;i<centres.length;i+=3){const d=Math.hypot(centres[i],centres[i+2]);if(d<20||d>90)continue;const response=await page.request.post(api+'/first-person/A0075/profile',{headers:{'X-HuntMaps':'local'},data:{east_m:centres[i],north_m:-centres[i+2],vegetation_scenario:'medium',vegetation_radius_m:120}});const p=await response.json();if(p.vegetation?.status==='evaluated'&&p.vegetation.scenarios.medium.first_intersection&&!p.vegetation.scenarios.medium.observer_inside){chosen=p;chosenTarget={east_m:centres[i],north_m:-centres[i+2]};break}}
 assert.ok(chosen,'Real target must intersect the displayed experimental surface');evidence.realIntersection=chosen.vegetation;
 const endpoint=chosen.points.at(-1),startPoint=new THREE.Vector3(0,1.7,0),endPoint=new THREE.Vector3(chosenTarget.east_m,endpoint.line_m-current.ground_m,-chosenTarget.north_m),length=startPoint.distanceTo(endPoint);
 for(const scenario of ['sparse','medium','dense']){
  const entry=current.vegetation.meshes['120'].scenarios[scenario];
  const read=async(name,Type)=>{const b=await (await page.request.get(api+'/first-person/A0075/assets/'+name)).body();return new Type(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength))};
  const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(await read(entry.vertices_file,Float32Array),3));geometry.setIndex(new THREE.BufferAttribute(await read(entry.indices_file,Uint32Array),1));
  const mesh=new THREE.Mesh(geometry,new THREE.MeshBasicMaterial({side:THREE.DoubleSide})),ray=new THREE.Raycaster(startPoint,endPoint.clone().sub(startPoint).normalize(),0,length);
  const hits=ray.intersectObject(mesh),result=chosen.vegetation.scenarios[scenario];
  if(!result.observer_inside){assert.equal(hits.length>0,!!result.first_intersection);if(hits.length)assert.ok(Math.abs(hits[0].distance/length*chosen.distance_m-result.first_intersection.distance_m)<1e-4)}
  geometry.dispose();mesh.material.dispose();
 }
 evidence.threeRaycasterAgreement=true;
 const start=Date.now();await page.getByLabel('First-person heading',{exact:true}).fill('200');await page.waitForFunction(()=>JSON.parse(document.querySelector('.fp-scene').getAttribute('data-camera')).heading===200);const latencyMs=Date.now()-start;assert.ok(latencyMs<2000);
 await page.getByLabel('Inferred vegetation',{exact:true}).uncheck();await page.waitForFunction(()=>!JSON.parse(document.querySelector('.fp-scene').getAttribute('data-camera')).vegetationVisible);await page.getByLabel('Inferred vegetation',{exact:true}).check();
 await page.setViewportSize({width:900,height:800});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:out+'/small-screen.png',fullPage:true});
 assert.deepEqual(errors,[]);assert.deepEqual(external,[]);assert.equal(await (await page.request.get(api+'/annotations')).text(),annotations);assert.equal((await (await page.request.get(base+'/api/jobs')).json()).length,jobs.length);
 fs.writeFileSync(out+'/results.json',JSON.stringify({evidence,latencyMs,profile,errors,external},null,2));console.log('Connected foliage: all four scenes, four Dense 120 m meshes, profiles, offline, budgets and zero idle draws verified');
}finally{await browser.close()}
