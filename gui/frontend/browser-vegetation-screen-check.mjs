import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const base=process.env.HUNTMAPS_URL||'http://127.0.0.1:8765',out=process.env.HUNTMAPS_SCREENSHOTS||'/tmp/huntmaps-first-person';
const browser=await chromium.launch({executablePath:process.env.HUNTMAPS_BROWSER||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader']});
try{
 const page=await browser.newPage({viewport:{width:1900,height:1050}});page.setDefaultTimeout(45000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>localStorage.setItem('huntmaps-online-imagery','off'));
 await page.route('**/*',r=>r.request().url().startsWith(base)||r.request().url().startsWith('blob:')?r.continue():r.abort());
 await page.goto(base);await page.getByLabel('Select A0075',{exact:true}).click();await page.getByRole('button',{name:'View',exact:true}).click();
 const state=()=>JSON.parse(document.querySelector('.fp-scene')?.getAttribute('data-camera')||'{}');
 await page.waitForFunction(()=>{const s=JSON.parse(document.querySelector('.fp-scene')?.getAttribute('data-camera')||'{}');return s.loaded&&s.imageryPending===0});
 await page.getByLabel('First-person heading',{exact:true}).fill('187');await page.getByLabel('First-person look angle',{exact:true}).fill('-16');
 await page.waitForFunction(()=>{const s=JSON.parse(document.querySelector('.fp-scene').getAttribute('data-camera'));return s.heading===187&&s.look===-16});

 const scene=page.locator('.fp-scene');await scene.scrollIntoViewIfNeeded();
 const on=await scene.screenshot({path:out+'/A0075-heading187-foliage-on.png'});
 await page.getByLabel('Inferred vegetation',{exact:true}).uncheck();await page.waitForFunction(()=>!JSON.parse(document.querySelector('.fp-scene').getAttribute('data-camera')).vegetationVisible);
 const off=await scene.screenshot({path:out+'/A0075-heading187-foliage-off.png'});assert.notDeepEqual(on,off);
 await page.getByLabel('Inferred vegetation',{exact:true}).check();
 const meta=await (await page.request.get(base+'/api/runs/soap-creek-decision-review-v2/first-person/A0075')).json();
 const raw=await (await page.request.get(base+'/api/runs/soap-creek-decision-review-v2/first-person/A0075/assets/'+meta.vegetation.centres_file)).body();
 let index=0;while(Math.hypot(raw.readFloatLE(index*12),raw.readFloatLE(index*12+8))>120)index++;const centre=[raw.readFloatLE(index*12),raw.readFloatLE(index*12+4),raw.readFloatLE(index*12+8)];const actual=JSON.parse(await scene.getAttribute('data-camera'));assert.deepEqual(actual.vegetationFirstCentre,centre);assert.equal(actual.vegetationCells,meta.vegetation.nearby_counts['120']);
 // Expand to120 m for this known inspection example, then verify the purple marker.

 let target,result;
 for(const bearing of [187,200,220,240,255,280,310,340,20,60,100,140]){
  const a=bearing*Math.PI/180;target={east_m:120*Math.sin(a),north_m:120*Math.cos(a),vegetation_scenario:'dense',vegetation_radius_m:120};
  result=await (await page.request.post(base+'/api/runs/soap-creek-decision-review-v2/first-person/A0075/profile',{headers:{'X-HuntMaps':'local'},data:target})).json();
  if(result.vegetation?.scenarios.dense.first_intersection)break;
 }
 assert.ok(result.vegetation.scenarios.dense.first_intersection);
 const map=page.getByLabel('Choose inspection target on plan map',{exact:true});await map.scrollIntoViewIfNeeded();const b=await map.boundingBox();
 await page.mouse.click(b.x+(200+target.east_m/300*190)/400*b.width,b.y+(200-target.north_m/300*190)/400*b.height);
 await page.locator('.fp-profile circle[fill="#8052ad"]').waitFor();await page.locator('.fp-vegetation table').waitFor();
 await page.screenshot({path:out+'/A0075-vegetation-inspection.png',fullPage:true});assert.deepEqual(errors,[]);
 fs.writeFileSync(out+'/vegetation-results.json',JSON.stringify({geometryMatches:true,visibleImageChanged:true,errors,exampleTarget:target,exampleProfile:result},null,2));
 console.log('Measured foliage rendering, matching geometry and purple inspection marker verified');
}finally{await browser.close()}
