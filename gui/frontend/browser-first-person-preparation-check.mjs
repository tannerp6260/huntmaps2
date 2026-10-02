import {chromium} from 'playwright';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const base=process.env.HUNTMAPS_URL||'http://127.0.0.1:8765',out=process.env.HUNTMAPS_SCREENSHOTS||'/tmp/huntmaps-first-person';
const browser=await chromium.launch({executablePath:process.env.HUNTMAPS_BROWSER||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader']});
try{
 const page=await browser.newPage({viewport:{width:1450,height:1050}});page.setDefaultTimeout(45000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>localStorage.setItem('huntmaps-online-imagery','off'));
 await page.goto(base);await page.getByLabel('Select A0031',{exact:true}).click();await page.getByRole('button',{name:'View from this setup',exact:true}).click();
 const oldPlan=await page.evaluate(()=>localStorage.getItem('huntmaps-first-person-plan'));
 await page.locator('summary').filter({hasText:'Prepare local fine terrain and lidar'}).click();await page.getByRole('button',{name:'Check source plan',exact:true}).click();
 await page.waitForFunction(old=>localStorage.getItem('huntmaps-first-person-plan')!==old,oldPlan);
 await page.getByRole('button',{name:'Prepare using cached sources only',exact:true}).waitFor();await page.waitForFunction(()=>!document.querySelector('.fp-preparation button:last-of-type')?.disabled);
 const pid=await page.evaluate(()=>localStorage.getItem('huntmaps-first-person-plan'));
 const plan=await (await page.request.get(base+'/api/first-person/plans/'+pid)).json();assert.equal(plan.estimated_new_bytes,0);assert.ok(plan.sources.every(s=>s.cached));
 assert.equal(await page.getByLabel('Allow this plan’s source downloads within 500 MB',{exact:true}).isChecked(),false);
 await page.screenshot({path:out+'/06-acquisition-plan.png',fullPage:true});
 await page.getByRole('button',{name:'Prepare using cached sources only',exact:true}).click();
 let job;
 for(let attempt=0;attempt<60;attempt++){
  const jobs=await (await page.request.get(base+'/api/jobs')).json();job=jobs.find(j=>j.plan===pid&&j.kind==='first-person-prepare');
  if(job?.status==='complete'&&job.logs.includes('cached bundle verified and reused'))break;
  if(job?.status==='failed')throw new Error(job.logs);
  await page.waitForTimeout(1000);
 }
 assert.equal(job?.status,'complete');assert.match(job.logs,/cached bundle verified and reused/);
 await page.locator('.fp-job details').evaluate(el=>el.open=true);
 await page.locator('.fp-job pre').filter({hasText:'cached bundle verified and reused'}).waitFor();
 await page.screenshot({path:out+'/07-preparation-complete.png',fullPage:true});assert.deepEqual(errors,[]);
 fs.writeFileSync(out+'/preparation-results.json',JSON.stringify({plan,job,errors},null,2));console.log('Actual GUI source plan and cached-only preparation verified:',pid);
}finally{await browser.close()}
