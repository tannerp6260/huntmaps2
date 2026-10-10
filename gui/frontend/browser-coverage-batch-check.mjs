import {chromium} from 'playwright';
import fs from 'node:fs';
import assert from 'node:assert/strict';
import ts from 'typescript';
import * as maplibre from 'maplibre-gl';
const base=process.env.HUNTMAPS_URL,out=process.env.HUNTMAPS_SCREENSHOTS;
if(!base||!out)throw Error('Run through ./gui/check');
fs.mkdirSync(out,{recursive:true});
// Exercise pause/resume with no provider or browser timing dependency.
const code=ts.transpileModule(fs.readFileSync('src/coverage-cache.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText.replace(/import.*from ['"]maplibre-gl['"];/, 'const {MercatorCoordinate}=globalThis.__coverageMaplibre;');
globalThis.__coverageMaplibre=maplibre;
const helper=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
for(const [width,height] of [[1902,862],[3840,2160]])for(const bearing of [0,45,90]){
 const tasks=helper.coverageTasks([{id:'large',longitude:-107,latitude:38}],width,height,undefined,bearing,[170,50]);
 assert.ok(tasks[0].tiles.length>0&&tasks[0].tiles.length<=3*512,'Current and 4K viewports must prepare within bounded tile counts');
}
const originalFetch=globalThis.fetch, originalWindow=globalThis.window;
globalThis.window={setTimeout:(f,ms)=>setTimeout(f,Math.min(ms,2))};
let pause=true,fetches=0;const states=[];
globalThis.fetch=async()=>{fetches++;return {ok:true,arrayBuffer:async()=>new ArrayBuffer(1)}};
try {
 const fake={getContainer:()=>({clientWidth:200,clientHeight:300}),isMoving:()=>false,getBearing:()=>0,getPadding:()=>({left:0,right:0,top:0,bottom:0})};
 const points=[{id:'fixture',longitude:-107,latitude:38}];
 const stop=helper.prepareCoverage(fake,'fixture',points,{},undefined,v=>states.push(v),undefined,()=>pause);
 assert.equal(states.at(-1).phase,'paused');assert.equal(fetches,0,'Paused owner jobs must not request tiles');
 pause=false;
 while(states.at(-1).phase!=='ready')await new Promise(resolve=>setTimeout(resolve,5));
 assert.equal(states.at(-1).completed,1);assert.ok(fetches>0);
 stop();
 pause=true;const stopped=[];
 const cancel=helper.prepareCoverage(fake,'fixture',points,{},undefined,v=>stopped.push(v),undefined,()=>pause);
 const before=fetches;cancel();pause=false;await new Promise(resolve=>setTimeout(resolve,10));
 assert.equal(fetches,before,'Cancellation must stop a paused batch');assert.equal(stopped.at(-1).phase,'cancelled');
} finally {globalThis.fetch=originalFetch;globalThis.window=originalWindow;delete globalThis.__coverageMaplibre;}
const browser=await chromium.launch({executablePath:process.env.HUNTMAPS_BROWSER||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader']});
const page=await browser.newPage({viewport:{width:1500,height:1050},reducedMotion:'reduce'}),errors=[],background=[];
page.on('pageerror',e=>errors.push(e.message));
await page.addInitScript(()=>localStorage.setItem('huntmaps-online-imagery','off'));
let fail=false,inflight=0,maximum=0;
await page.route('**/*',async route=>{
 const request=route.request();
 if(!request.url().startsWith(base)&&!request.url().startsWith('blob:'))return route.abort();
 if(request.headers()['x-huntmaps-prefetch']!=='true')return route.continue();
 background.push(request.url());inflight++;maximum=Math.max(maximum,inflight);
 try {
   await new Promise(resolve=>setTimeout(resolve,35));
   if(fail){fail=false;await route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({detail:'Synthetic preparation failure'})});}
   else await route.continue();
 } finally {inflight--;}
});
try {
 await page.goto(base);await page.getByLabel('Run selector').selectOption('search-fixture');
 await page.locator('.coverage-status').filter({hasText:'Coverage ready'}).waitFor({timeout:60000});
 await page.getByLabel('Saved neighborhood').selectOption('all');
 const order=await page.locator('.candidate-select strong').allTextContents();
 const selected=await page.locator('.candidate-select[aria-pressed="true"] strong').textContent();
 const expected=order.slice(Math.max(0,order.indexOf(selected)),Math.max(0,order.indexOf(selected))+10);
 assert.equal(await page.getByLabel('Coverage batch size').inputValue(),'10');
 await page.getByRole('button',{name:'Prepare coverage',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('.coverage-preparation small')?.textContent.match(/^[1-9]/));
 await page.getByRole('button',{name:'Cancel preparation',exact:true}).click();
 await page.locator('.coverage-preparation[data-phase="cancelled"]').waitFor();
 const completed=background.slice(0,-1);
 while(inflight)await new Promise(resolve=>setTimeout(resolve,10));
 fail=true;
 await page.getByRole('button',{name:'Resume preparation',exact:true}).click();
 await page.locator('.coverage-preparation[data-phase="error"]').waitFor();
 await page.getByText('Synthetic preparation failure',{exact:true}).waitFor();
 const start=Date.now();
 await page.getByRole('button',{name:'Resume preparation',exact:true}).click();
 await page.locator('.coverage-preparation[data-phase="ready"]').waitFor({timeout:180000});
 const batchMs=Date.now()-start;
 assert.deepEqual([...new Set(background.map(url=>url.split('/visible/')[1].split('/')[0]))],expected,'Prepare follows displayed ranking including current setup');
 for(const url of completed)assert.equal(background.filter(v=>v===url).length,1,'Completed immutable tiles must survive cancel/retry');
 assert.equal(maximum,1,'Only one background tile is requested at a time');
 assert.ok(JSON.parse(await page.locator('.map').getAttribute('data-coverage-cache')).length<=8);
 await page.screenshot({path:out+'/batch-desktop.png',fullPage:true});
 await page.setViewportSize({width:1902,height:862});
 await page.getByLabel('Coverage batch size').selectOption('5');
 await page.getByRole('button',{name:'Prepare coverage',exact:true}).click();
 await page.locator('.coverage-preparation[data-phase="ready"]').waitFor({timeout:180000});
 await page.screenshot({path:out+'/batch-current-window.png',fullPage:true});
 await page.setViewportSize({width:900,height:900});
 await page.screenshot({path:out+'/batch-900.png',fullPage:true});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.getByLabel('Coverage batch size').selectOption('5');
 await page.getByRole('button',{name:'Prepare coverage',exact:true}).focus();
 await page.keyboard.press('Enter');
 await page.locator('.coverage-preparation[data-phase="preparing"]').waitFor();
 await page.getByLabel('Setup order').selectOption('engine');
 await page.locator('.coverage-preparation').waitFor({state:'hidden'});
 assert.deepEqual(errors,[]);
 fs.writeFileSync(out+'/results.json',JSON.stringify({batchMs,expected,maximum,requests:background.length,errors},null,2));
 console.log('Explicit ranked batches, bounded requests, cancellation/resume, error retry, ranking invalidation and narrow layout verified');
} catch(e){await page.screenshot({path:out+'/failure.png',fullPage:true});fs.writeFileSync(out+'/failure.txt',await page.locator('body').innerText());throw e;} finally {await browser.close();}
