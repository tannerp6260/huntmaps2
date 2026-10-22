import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const base = process.env.HUNTMAPS_URL, out = process.env.HUNTMAPS_SCREENSHOTS;
if (!base || !out) throw Error('Use gui.check');
fs.mkdirSync(out, {recursive:true});
const browser = await chromium.launch({executablePath:process.env.HUNTMAPS_BROWSER || '/usr/bin/google-chrome', headless:true, args:['--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader']});
const page = await browser.newPage({viewport:{width:1500,height:1050}});
page.setDefaultTimeout(60000);
const errors=[], requests=[];
page.on('pageerror',e=>errors.push(e.message));
page.on('request',r=>{if(r.url().endsWith('/api/roadless-overlay'))requests.push(r.postDataJSON());});
const tile = Buffer.from(await page.evaluate(()=>{const c=document.createElement('canvas');c.width=c.height=256;const x=c.getContext('2d');x.fillStyle='#158c54';x.fillRect(0,0,256,256);return c.toDataURL().split(',')[1];}),'base64');
await page.route('**/*',r=>{
 const url=r.request().url();
 if(url.startsWith('https://basemap.nationalmap.gov/'))return r.fulfill({contentType:'image/png',body:tile});
 return url.startsWith(base)||/^(blob:|data:)/.test(url)?r.continue():r.abort();
});
async function ready(miles){await page.waitForFunction(m=>{const v=JSON.parse(document.querySelector('.map')?.dataset.roadless||'{}');return v.status==='ready'&&Math.abs(v.distance_m-m*1609.344)<.01;},miles);}
async function pixels(opacity){
 const shot=await page.locator('.maplibregl-canvas').screenshot();
 return page.evaluate(async ({encoded,opacity})=>{
  const bitmap=await createImageBitmap(await(await fetch('data:image/png;base64,'+encoded)).blob());
  const c=document.createElement('canvas');c.width=bitmap.width;c.height=bitmap.height;
  const ctx=c.getContext('2d');ctx.drawImage(bitmap,0,0);const d=ctx.getImageData(0,0,c.width,c.height).data;
  const color=[21*(1-opacity)+197*opacity,140*(1-opacity)+141*opacity,84*(1-opacity)+242*opacity];
  let count=0;for(let i=0;i<d.length;i+=4)if(color.every((v,n)=>Math.abs(d[i+n]-v)<5))count++;
  return count;
 },{encoded:shot.toString('base64'),opacity});
}
try {
 await page.goto(base);
 await page.getByRole('button',{name:'New scouting area',exact:true}).click();
 const catalog=await(await page.request.get(base+'/api/unit-packs')).json();
 const unit=catalog.units.find(u=>u.unit_id==='co-gmu54');assert.ok(unit);
 const selector=page.getByLabel('Hunting unit',{exact:true});
 await selector.selectOption(unit.unit_id+'/'+unit.version);
 await page.waitForFunction(()=>document.querySelector('.map')?.dataset.unitPackReady==='true');
 await page.locator('.layers > summary').click();
 const toggle=page.getByLabel('Roadless distance overlay',{exact:true});
 assert.equal(await toggle.isChecked(),false);
 await toggle.check();await ready(1);
 await page.waitForFunction(()=>JSON.parse(document.querySelector('.map')?.dataset.mapState||'{}').loaded===true);
 assert.ok(await pixels(.3)>500,'Transparent purple shading is visible above opaque imagery');
 await page.screenshot({path:out+'/roadless-desktop.png'});
 const distance=page.getByLabel('Minimum road distance (miles)',{exact:true});
 await distance.fill('2');await ready(2);
 const opacity=page.getByLabel('Roadless overlay opacity',{exact:true});
 await opacity.fill('0.6');await page.waitForTimeout(300);
 assert.ok(await pixels(.6)>500,'Opacity changes actual rendered pixels');
 await page.setViewportSize({width:900,height:950});await ready(2);
 await page.screenshot({path:out+'/roadless-900.png'});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.reload();await page.getByRole('button',{name:'New scouting area',exact:true}).click();
 await page.getByLabel('Hunting unit',{exact:true}).selectOption(unit.unit_id+'/'+unit.version);
 await page.locator('.layers > summary').click();await ready(2);
 assert.equal(await toggle.isChecked(),true);assert.equal(await distance.inputValue(),'2');assert.equal(await opacity.inputValue(),'0.6');
 await distance.fill('');assert.equal(await distance.getAttribute('aria-invalid'),'true');
 await page.waitForFunction(()=>!document.querySelector('.map')?.dataset.roadless);
 await distance.fill('1');await ready(1);
 await toggle.uncheck();await page.waitForFunction(()=>!document.querySelector('.map')?.dataset.roadless);
 assert.equal(await page.getByLabel('Minimum road distance (miles)').count(),0);
 assert.equal(await pixels(.6),0,'Toggle removes shading');
 await toggle.check();await ready(1);
 // Empty custom-area inventories must not shade the map as roadless.
 await selector.selectOption('');
 await page.getByText('Road-source coverage is insufficient here.',{exact:false}).waitFor();
 assert.equal(JSON.parse(await page.locator('.map').getAttribute('data-roadless')).features,0);
 assert.deepEqual(errors,[]);
 fs.writeFileSync(out+'/results.json',JSON.stringify({errors,requests,realPack:unit.version,transparentPixels:true,reload:true,unknownCoverage:true},null,2));
} catch(e) {
 await page.screenshot({path:out+'/failure.png',fullPage:true});
 fs.writeFileSync(out+'/failure.txt',await page.locator('body').innerText());throw e;
} finally {await browser.close();}
