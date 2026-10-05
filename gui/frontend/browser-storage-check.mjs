import {chromium} from 'playwright';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const base=process.env.HUNTMAPS_URL,out=process.env.HUNTMAPS_SCREENSHOTS;
if(!base||!out)throw Error('Run through gui/check');
fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.HUNTMAPS_BROWSER||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader']});
let page;
try {
  page=await browser.newPage({viewport:{width:1450,height:1050}});page.setDefaultTimeout(45000);
  await page.addInitScript(()=>localStorage.setItem('huntmaps-online-imagery','off'));
  await page.route('**/*',route=>route.request().url().startsWith(base)||route.request().url().startsWith('blob:')?route.continue():route.abort());
  const api=base+'/api/runs/soap-creek-decision-review-v2';
  const headers={'X-HuntMaps':'local'};
  await page.request.put(api+'/annotations/A0075',{headers,data:{status:'keep',notes:'Storage recovery verification'}});
  await page.goto(base);await page.getByRole('button',{name:'Activity',exact:true}).click();
  const panel=page.locator('.storage-panel');if (!(await page.locator('.activity-drawer').isVisible())) await page.getByRole('button',{name:'Activity',exact:true}).click(); await panel.locator('summary').first().click();
  await panel.getByRole('button',{name:'Back up GUI records',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.storage-panel [role="status"]')?.textContent.includes('backup'));
  const key=JSON.parse(await panel.locator('[role="status"]').innerText()).backup;
  await panel.locator('summary').filter({hasText:'Reset notes and waypoints'}).click();
  assert.equal(await panel.getByRole('button',{name:'Reset GUI records',exact:true}).isDisabled(),true);
  await page.getByLabel('Reset confirmation',{exact:true}).fill('RESET GUI RECORDS');
  await panel.getByRole('button',{name:'Reset GUI records',exact:true}).click();
  await page.waitForFunction(()=>!document.querySelector('.storage-panel')?.hasAttribute('open'));
  assert.deepEqual(await (await page.request.get(api+'/annotations')).json(),{});
  if (!(await page.locator('.activity-drawer').isVisible())) await page.getByRole('button',{name:'Activity',exact:true}).click(); await panel.locator('summary').first().click();await page.getByLabel('Record backup',{exact:true}).selectOption(key);
  await panel.getByRole('button',{name:'Restore selected backup',exact:true}).click();
  await page.waitForFunction(()=>!document.querySelector('.storage-panel')?.hasAttribute('open'));
  assert.equal((await (await page.request.get(api+'/annotations')).json()).A0075.notes,'Storage recovery verification');
  if (!(await page.locator('.activity-drawer').isVisible())) await page.getByRole('button',{name:'Activity',exact:true}).click(); await panel.locator('summary').first().click();
  await panel.getByRole('button',{name:'Preview cache cleanup',exact:true}).click();
  await panel.getByRole('button',{name:'Clean previewed cache',exact:true}).waitFor();
  // Keep the viewer idle while previewing; regenerating tiles legitimately invalidates a preview.
  const value=await (await page.request.post(base+'/api/storage/cache/preview',{headers,data:{}})).json();
  const cleaned=await page.request.post(base+'/api/storage/cache/cleanup',{headers,data:{token:value.token}});
  assert.equal(cleaned.status(),200);
  const meta=await (await page.request.get(api+'/first-person/A0075')).json();assert.equal(meta.status,'ready');
  assert.equal((await (await page.request.get(api+'/annotations')).json()).A0075.notes,'Storage recovery verification');
  await page.screenshot({path:out+'/storage-desktop.png',fullPage:true});
  await page.setViewportSize({width:900,height:800});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:out+'/storage-900.png',fullPage:true});
  fs.writeFileSync(out+'/storage.json',JSON.stringify({backup:key,reclaimed:await cleaned.json(),recordsRestored:true,retainedSceneReady:true},null,2));
  console.log('Storage backup, reset, restoration and cleanup verified:',out);
} catch(error) {
  await page?.screenshot({path:out+'/failure.png',fullPage:true});throw error;
} finally {await browser.close()}
