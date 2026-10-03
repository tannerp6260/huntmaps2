const base=process.env.HUNTMAPS_URL||'http://127.0.0.1:8765';
import {chromium} from 'playwright';
import fs from 'node:fs';
const out=process.env.HUNTMAPS_SCREENSHOTS||'/tmp/huntmaps-gui-browser';fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.HUNTMAPS_BROWSER||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader']});const page=await browser.newPage({viewport:{width:1500,height:1050}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto(base);await page.getByRole('button',{name:'+ New baseline run'}).click();await page.getByRole('button',{name:'Import file',exact:true}).click();await page.getByLabel('Import observer polygon').setInputFiles(process.env.HUNTMAPS_IMPORT_FILE||'../../inputs/test.kml');await page.getByLabel('Polygon selection').waitFor();
const name='gui-plan-check-'+Date.now();await page.getByLabel('New run name').fill(name);await page.getByRole('button',{name:'Review downloads',exact:true}).click();await page.getByText(name+' acquisition plan',{exact:true}).waitFor({timeout:90000});
await page.getByText('MB estimated',{exact:false}).first().waitFor({timeout:90000});await page.waitForTimeout(1000);await page.screenshot({path:out+'/07-acquisition-plan.png',fullPage:true});
const plans=await (await page.request.get(base+'/api/jobs')).json();const job=plans.find(j=>j.name===name);const plan=await (await page.request.get(base+'/api/plans/'+job.plan)).json();
if(!plan.prepared)throw Error('Plan never completed');if(await page.getByText("Approve this plan's new downloads within",{exact:false}).locator('input').isChecked())throw Error('Downloads preauthorized unexpectedly');
fs.writeFileSync(out+'/plan-check.json',JSON.stringify({name,job,plan,errors},null,2));
// Inspect the durable synthetic job outcomes in the actual application.
await page.getByRole('button',{name:'Back to review',exact:true}).click();const summary=page.locator('summary').filter({hasText:'Analysis jobs'});await summary.click();await page.waitForTimeout(500);await page.screenshot({path:out+'/08-job-history.png',fullPage:true});
await browser.close();if(errors.length)throw Error(JSON.stringify(errors));console.log('Actual new-run form prepared acquisition plan without downloads:',name,plan.acquisition.estimated_bytes,'bytes');
