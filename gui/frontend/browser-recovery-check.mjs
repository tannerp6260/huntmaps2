import {chromium} from 'playwright';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const base=process.env.HUNTMAPS_URL,out=process.env.HUNTMAPS_SCREENSHOTS;
if(!base||!out)throw Error('Run through gui/recovery_check.py');
fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.HUNTMAPS_BROWSER||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader']});
const page=await browser.newPage({viewport:{width:1500,height:1050}}), errors=[];
page.on('pageerror',e=>errors.push(e.message));
await page.addInitScript(()=>localStorage.setItem('huntmaps-online-imagery','off'));
await page.route('**/*',r=>r.request().url().startsWith(base)||r.request().url().startsWith('blob:')?r.continue():r.abort());
const jobs=async()=>await (await page.request.get(base+'/api/jobs')).json();
const waitJob=async status=>{
 for(let i=0;i<600;i++){
  const list=await jobs();
  const found=list.find(j=>j.name==='browser-recovery'&&j.kind==='baseline'&&j.status===status);
  if(found)return found;
  await page.waitForTimeout(200);
 }
 throw Error('Expected baseline '+status+': '+JSON.stringify(await jobs()));
};
try{
 await page.goto(base);
 await page.getByRole('button',{name:'+ New baseline run',exact:true}).click();
 await page.getByRole('button',{name:'Import file',exact:true}).click();
 await page.getByLabel('Import observer polygon').setInputFiles(process.env.HUNTMAPS_IMPORT_FILE);
 await page.getByLabel('New run name',{exact:true}).fill('browser-recovery');
 await page.getByLabel('View radius',{exact:true}).selectOption('500');
 await page.getByLabel('Search effort',{exact:true}).selectOption('600');
 await page.getByLabel('Setups recommended',{exact:true}).fill('10');
 await page.getByRole('button',{name:'Review downloads',exact:true}).click();
 await page.getByRole('button',{name:'Generate setups',exact:true}).waitFor({timeout:30000});
 await page.getByRole('button',{name:'Generate setups',exact:true}).click();
 const failed=await waitJob('failed');
 assert.match(failed.error,/Injected post-download/);
 assert.equal(failed.failed_stage,'score');
 const plan=await (await page.request.get(base+'/api/plans/'+failed.plan)).json();
 assert.equal(plan.acquisition.estimated_bytes,0);
 assert.ok(plan.acquisition.already_cached_bytes>0);
 await page.reload();
 await page.getByText('Job history and recovery',{exact:true}).click();
 await page.locator('summary').filter({hasText:'Analysis jobs'}).click();
 const card=page.locator('.job').filter({hasText:'Injected post-download'});
 await card.getByRole('button',{name:'Review / resume plan',exact:true}).click();
 await page.getByRole('button',{name:'Generate setups',exact:true}).waitFor();
 await page.screenshot({path:out+'/01-cached-recovery-desktop.png',fullPage:true});
 const [started]=await Promise.all([
  page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith('/start')),
  page.getByRole('button',{name:'Generate setups',exact:true}).click()
 ]);
 assert.ok(started.ok(),await started.text());
 await page.reload();
 await waitJob('complete');
 const response=await page.request.get(base+'/api/runs/browser-recovery');
 assert.ok(response.ok(),await response.text());
 const run=await response.json();
 assert.equal(run.recommendation_ids.length,10);
 assert.ok(run.search_summary.sampling.spacing_m<150);
 await page.getByLabel('Run selector').selectOption('browser-recovery');
 await page.getByText(/Evaluated .* locations/).waitFor();
 await page.setViewportSize({width:900,height:900});
 await page.locator('.coverage-status').filter({hasText:'Coverage ready'}).waitFor({timeout:60000});
 await page.locator('.inspector').getByText('Loading setup...',{exact:true}).waitFor({state:'hidden'});
 await page.screenshot({path:out+'/02-search-complete-900.png',fullPage:true});
 assert.deepEqual(errors,[]);
 fs.writeFileSync(out+'/results.json',JSON.stringify({errors,failedStage:failed.failed_stage,search:run.search_summary},null,2));
 console.log('Actual browser Thorough search, cached recovery and reload verified',out);
}finally{await browser.close();}
