if(!process.env.HUNTMAPS_URL||!process.env.HUNTMAPS_SCREENSHOTS)throw Error('Run through ./gui/check with an isolated server and screenshot directory');
import {chromium} from 'playwright';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const base=process.env.HUNTMAPS_URL,out=process.env.HUNTMAPS_SCREENSHOTS;fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.HUNTMAPS_BROWSER||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader']});
try{
 const page=await browser.newPage({viewport:{width:1450,height:1050}});page.setDefaultTimeout(45000);const errors=[],mutations=[],external=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(['POST','PUT','DELETE'].includes(r.method()))mutations.push(r.url());if(r.url().startsWith('http')&&!r.url().startsWith(base))external.push(r.url())});
 await page.addInitScript(()=>localStorage.setItem('huntmaps-online-imagery','off'));await page.route('**/*',r=>r.request().url().startsWith(base)||r.request().url().startsWith('blob:')?r.continue():r.abort());
 const api=base+'/api/runs/soap-creek-decision-review-v2';
 const annotations=await (await page.request.get(api+'/annotations')).text(),jobs=await (await page.request.get(base+'/api/jobs')).json();
 const loaded=()=>page.waitForFunction(()=>{const s=JSON.parse(document.querySelector('.fp-scene')?.getAttribute('data-camera')||'{}');return s.loaded&&s.imageryPending===0});
 await page.goto(base);await page.getByLabel('Select A0031',{exact:true}).click();await page.getByRole('button',{name:'View',exact:true}).click();await loaded();assert.equal(await page.getByLabel('Measured above-ground returns',{exact:true}).isChecked(),false);assert.equal(await page.getByLabel('Inferred vegetation',{exact:true}).isChecked(),true);
 const meta=await (await page.request.get(api+'/first-person/A0031')).json();assert.ok(meta.fine_observer_available);
 let state=JSON.parse(await page.locator('.fp-scene').getAttribute('data-camera'));assert.equal(state.eye_m,1.7);assert.equal(state.east_m,0);assert.equal(state.north_m,0);assert.equal(state.ground_m,meta.fine_ground_m);assert.equal(state.vegetationSide,2);assert.equal(state.vegetationCells,meta.vegetation.nearby_counts['120']);assert.equal(state.vegetationVisible,true);
 await page.screenshot({path:out+'/01-eye-height-ground.png',fullPage:true});
 await page.getByLabel('First-person eye height',{exact:true}).fill('2.2');await page.getByLabel('First-person heading',{exact:true}).fill('135');await page.getByLabel('First-person look angle',{exact:true}).fill('-10');
 await page.waitForFunction(()=>JSON.parse(document.querySelector('.fp-scene').getAttribute('data-camera')).eye_m===2.2);
 await page.getByRole('dialog').getByText('Sources, coverage and technical details',{exact:true}).click();await page.getByLabel('Measured above-ground returns',{exact:true}).check();await page.waitForFunction(()=>JSON.parse(document.querySelector('.fp-scene').getAttribute('data-camera')).points>0);await page.screenshot({path:out+'/02-measured-points.png',fullPage:true});
 await page.getByLabel('Measured above-ground returns',{exact:true}).uncheck();await page.screenshot({path:out+'/03-draped-imagery.png',fullPage:true});assert.equal(await page.getByLabel('Cached imagery texture',{exact:true}).count(),0);
 await page.getByRole('dialog').getByRole('button',{name:'Reset view',exact:true}).click();await loaded();assert.equal(JSON.parse(await page.locator('.fp-scene').getAttribute('data-camera')).imageryFailed,false);
 assert.equal(await page.getByLabel('Vegetation screening assumption',{exact:true}).count(),0);
 await page.getByLabel('Inferred vegetation',{exact:true}).uncheck();await page.waitForFunction(()=>!JSON.parse(document.querySelector('.fp-scene').getAttribute('data-camera')).vegetationVisible);await page.screenshot({path:out+'/08-foliage-off.png',fullPage:true});
 await page.getByLabel('Inferred vegetation',{exact:true}).check();await page.waitForFunction(()=>JSON.parse(document.querySelector('.fp-scene').getAttribute('data-camera')).vegetationVisible);await page.screenshot({path:out+'/09-foliage-on.png',fullPage:true});
 const map=page.getByLabel('Choose inspection target on plan map',{exact:true});await map.scrollIntoViewIfNeeded();let b=await map.boundingBox();await page.mouse.click(b.x+b.width*.65,b.y+b.height*.5);await page.locator('.fp-profile').waitFor();await page.locator('.fp-vegetation table').waitFor();assert.equal(await page.locator('.fp-vegetation tbody tr').count(),3);await page.getByLabel('Inspection target height',{exact:true}).fill('2.5');await page.waitForTimeout(700);await page.screenshot({path:out+'/04-terrain-profile.png',fullPage:true});
 await page.getByLabel('Inspection map radius',{exact:true}).selectOption('2000');await map.scrollIntoViewIfNeeded();b=await map.boundingBox();await page.mouse.click(b.x+b.width*.65,b.y+b.height*.5);await page.getByText('Separate baseline-only profile; both endpoints use baseline ground',{exact:false}).waitFor();await page.getByText('Vegetation screening requires fine observer ground and a target within 300 m.',{exact:true}).waitFor();
 const scene=page.locator('.fp-scene');await scene.scrollIntoViewIfNeeded();await scene.focus();await page.keyboard.press('ArrowRight');const start=Date.now();await page.getByLabel('First-person heading',{exact:true}).fill('200');await page.waitForFunction(()=>JSON.parse(document.querySelector('.fp-scene').getAttribute('data-camera')).heading===200);const interactionMs=Date.now()-start;assert.ok(interactionMs<2000);
 await page.setViewportSize({width:900,height:800});await page.screenshot({path:out+'/05-smaller-screen.png',fullPage:true});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await scene.evaluate(el=>el.querySelector('canvas').dispatchEvent(new Event('webglcontextlost',{cancelable:true,bubbles:true})));await page.getByText('Graphics context lost.',{exact:false}).waitFor();
 await page.getByRole('button',{name:'Return to map',exact:true}).click();await page.getByRole('button',{name:'View',exact:true}).click();await loaded();
 for(const cid of ['A0075','V010','V008']){
  await page.getByLabel('First-person setup',{exact:true}).selectOption(cid);const m=await (await page.request.get(api+'/first-person/'+cid)).json();
  if(m.status==='ready'){await page.waitForFunction(cid=>JSON.parse(document.querySelector('.fp-scene')?.getAttribute('data-camera')||'{}').candidate===cid,cid);await loaded();assert.ok(await scene.isVisible());const camera=JSON.parse(await scene.getAttribute('data-camera'));assert.equal(camera.ground_m,m.fine_ground_m);assert.equal(camera.east_m,0);assert.equal(camera.north_m,0);await page.screenshot({path:out+'/'+cid+'-view.png',fullPage:true});
   await page.getByLabel('Inferred vegetation',{exact:true}).uncheck();await page.waitForFunction(()=>!JSON.parse(document.querySelector('.fp-scene').getAttribute('data-camera')).vegetationVisible);await page.screenshot({path:out+'/'+cid+'-foliage-off.png',fullPage:true});await page.getByLabel('Inferred vegetation',{exact:true}).check();await page.waitForFunction(()=>JSON.parse(document.querySelector('.fp-scene').getAttribute('data-camera')).vegetationVisible)}else await page.getByText('No fine scene has been prepared yet.',{exact:false}).waitFor();
 }
 // Failed photographs retain usable terrain and the profile; no checkbox is needed.
 await page.getByRole('button',{name:'Return to map',exact:true}).click();
 await page.route('**/assets/*imagery.png*',r=>r.abort());
 await page.getByRole('button',{name:'View',exact:true}).click();await loaded();
 await page.getByText('Some imagery unavailable; shaded terrain retained.',{exact:true}).waitFor();
 assert.ok(JSON.parse(await scene.getAttribute('data-camera')).triangles>0);
 assert.equal(await (await page.request.get(api+'/annotations')).text(),annotations);assert.equal((await (await page.request.get(base+'/api/jobs')).json()).length,jobs.length);assert.ok(mutations.every(u=>u===base+'/api/speed-probe' || u.endsWith('/profile') || u.includes('/workflow/')));assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
 fs.writeFileSync(out+'/results.json',JSON.stringify({errors,external,mutations,interactionMs,metadata:meta,annotationsUnchanged:true,jobsUnchanged:true},null,2));console.log('First-person camera, points, texture, profiles, offline, keyboard, resizing, switching and context failure verified:',out);
}finally{await browser.close()}
