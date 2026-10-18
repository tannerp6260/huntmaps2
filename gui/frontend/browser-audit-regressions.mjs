import { chooseExisting, openExisting, reloadExisting } from './browser-startup.mjs';
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const base=process.env.HUNTMAPS_URL,out=process.env.HUNTMAPS_SCREENSHOTS;
if (!base || !out || !process.env.HUNTMAPS_STATE_DIR?.startsWith('/tmp/')) throw Error('Use ./gui/check isolated state');
fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.HUNTMAPS_BROWSER||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader']});
const context=await browser.newContext({viewport:{width:1500,height:1000}});
const page=await context.newPage(),errors=[],viewed=[];
page.setDefaultTimeout(30000);
page.on('pageerror',e=>errors.push(e.message));
page.on('request',r=>{if(r.method()==='PUT' && r.url().includes('/workflow/') && r.postDataJSON()?.action==='viewed')viewed.push(r.url());});
await page.addInitScript(()=>localStorage.setItem('huntmaps-online-imagery','off'));
await page.route('**/*',r=>r.request().url().startsWith(base)||r.request().url().startsWith('blob:')?r.continue():r.abort());
const run='soap-creek-decision-review-v2', endpoint=`${base}/api/runs/${run}/annotations/A0075`;
async function details(cid='A0075',target=page) {
 await target.getByLabel('Run selector').selectOption(run);
 await target.getByLabel('Select '+cid,{exact:true}).click();
 await target.getByRole('button',{name:'Setup details',exact:true}).click();
 await target.getByLabel('Candidate notes').waitFor();
}
try {
 await openExisting(page,base);await details();
 await page.getByLabel('Candidate notes').fill('Draft survives candidate navigation');
 await page.getByRole('button',{name:'← All setups',exact:true}).click();await details('V010');
 await page.getByRole('button',{name:'← All setups',exact:true}).click();await details();
 assert.equal(await page.getByLabel('Candidate notes').inputValue(),'Draft survives candidate navigation');
 await reloadExisting(page);await details();
 assert.equal(await page.getByLabel('Candidate notes').inputValue(),'Draft survives candidate navigation');
 let release,entered;const gate=new Promise(r=>release=r),arrived=new Promise(r=>entered=r);
 await page.route(endpoint,async route=>{entered();await gate;await route.continue();});
 const response=page.waitForResponse(r=>r.url()===endpoint && r.request().method()==='PUT');
 await page.getByRole('button',{name:'Save review',exact:true}).click();await arrived;
 assert.equal(await page.getByRole('button',{name:'Save review',exact:true}).isDisabled(),true);
 await page.getByLabel('Candidate notes').fill('Newer draft during save');release();
 assert.equal((await response).status(),200);
 await page.getByText('Saved earlier edit; newer draft is unsaved',{exact:true}).waitFor();
 await page.unroute(endpoint);await reloadExisting(page);await details();
 assert.equal(await page.getByLabel('Candidate notes').inputValue(),'Newer draft during save');
 await page.getByRole('button',{name:'Save review',exact:true}).click();await page.getByText('Saved on this computer',{exact:true}).waitFor();
 assert.equal((await (await page.request.get(`${base}/api/runs/${run}/annotations`)).json()).A0075.notes,'Newer draft during save');
 // A second editor commits against the same revision; the first tab must retain
 // its draft and require an explicit conflict resolution before replacing it.
 const reviews=await (await page.request.get(`${base}/api/runs/${run}/annotations`)).json();
 const other=await page.request.put(endpoint,{headers:{'X-HuntMaps':'local'},data:{...reviews.A0075,notes:'Saved by another editor'}});
 assert.equal(other.status(),200);
 await page.getByLabel('Candidate notes').fill('My retained conflict draft');
 const conflict=page.waitForResponse(r=>r.url()===endpoint&&r.request().method()==='PUT');
 await page.getByRole('button',{name:'Save review',exact:true}).click();assert.equal((await conflict).status(),409);
 await page.getByText('Saved by another editor',{exact:true}).waitFor();
 assert.equal(await page.getByLabel('Candidate notes').inputValue(),'My retained conflict draft');
 await page.getByRole('button',{name:'Keep my draft for the next save',exact:true}).click();
 await page.getByRole('button',{name:'Save review',exact:true}).click();await page.getByText('Saved on this computer',{exact:true}).waitFor();
 assert.equal((await (await page.request.get(`${base}/api/runs/${run}/annotations`)).json()).A0075.notes,'My retained conflict draft');
 // Distinct tabs must retain their own drafts and the revision they started from.
 const otherTab=await page.context().newPage();
 await otherTab.addInitScript(()=>localStorage.setItem('huntmaps-online-imagery','off'));
 await openExisting(otherTab,base);await details('A0075',otherTab);
 await otherTab.getByLabel('Candidate notes').fill('Independent second-tab draft');
 await page.getByLabel('Candidate notes').fill('First-tab draft');
 await reloadExisting(otherTab);await details('A0075',otherTab);
 assert.equal(await otherTab.getByLabel('Candidate notes').inputValue(),'Independent second-tab draft','Reload must retain this tab’s draft, not overwrite it with another tab’s');
 await page.getByRole('button',{name:'Save review',exact:true}).click();await page.getByText('Saved on this computer',{exact:true}).waitFor();
 await reloadExisting(otherTab);await details('A0075',otherTab);
 assert.equal(await otherTab.getByLabel('Candidate notes').inputValue(),'Independent second-tab draft');
 await otherTab.getByText('First-tab draft',{exact:true}).waitFor();
 await otherTab.screenshot({path:out+'/draft-reload-conflict.png',fullPage:true});
 const staleReload=otherTab.waitForResponse(r=>r.url()===endpoint&&r.request().method()==='PUT');
 await otherTab.getByRole('button',{name:'Save review',exact:true}).click();
 assert.equal((await staleReload).status(),409,'Reload must not silently rebase an older draft onto a newer saved revision');
 await otherTab.getByRole('button',{name:'Keep my draft for the next save',exact:true}).click();
 await otherTab.getByRole('button',{name:'Save review',exact:true}).click();await otherTab.getByText('Saved on this computer',{exact:true}).waitFor();
 await otherTab.close();
 // Duplicated tabs inherit sessionStorage; they still need independent draft ownership.
 await reloadExisting(page);await details();
 await page.getByLabel('Candidate notes').fill('Original tab unfinished draft');
 const popupPromise=page.waitForEvent('popup');
 await page.evaluate(url=>window.open(url,'_blank'),base);
 const duplicate=await popupPromise;await chooseExisting(duplicate);await details('A0075',duplicate);
 await duplicate.getByLabel('Candidate notes').fill('Duplicated tab unfinished draft');
 await reloadExisting(page);await details();
 assert.equal(await page.getByLabel('Candidate notes').inputValue(),'Original tab unfinished draft');
 await reloadExisting(duplicate);await details('A0075',duplicate);
 assert.equal(await duplicate.getByLabel('Candidate notes').inputValue(),'Duplicated tab unfinished draft');
 await duplicate.close();
 await page.getByRole('button',{name:'Save review',exact:true}).click();await page.getByText('Saved on this computer',{exact:true}).waitFor();
 // A newly opened tab can explicitly recover an abandoned branch without changing the server.
 const recoveryTab=await context.newPage();await openExisting(recoveryTab,base);await details('A0075',recoveryTab);
 await recoveryTab.getByText(/Other drafts on this computer/).click();
 const abandoned=recoveryTab.locator('.technical > div').filter({hasText:'Duplicated tab unfinished draft'});
 await abandoned.getByRole('button',{name:'Restore this draft',exact:true}).click();
 assert.equal(await recoveryTab.getByLabel('Candidate notes').inputValue(),'Duplicated tab unfinished draft');
 assert.equal((await (await page.request.get(`${base}/api/runs/${run}/annotations`)).json()).A0075.notes,'Original tab unfinished draft');
 await recoveryTab.getByText('Original tab unfinished draft',{exact:true}).waitFor();
 await recoveryTab.screenshot({path:out+'/draft-branch-recovery.png',fullPage:true});
 await recoveryTab.close();
 console.log('Draft navigation, reload, separate/duplicated tabs, explicit recovery and held-save acknowledgement passed');
 // Optional provider failure is scoped and recoverable while local scouting works.
 let transportFailure=true;
 const transportRoute=route=>transportFailure?route.fulfill({status:503,json:{detail:'Controlled optional context failure'}}):route.continue();
 await page.route('**/api/browsing/transportation/**',transportRoute);
 await reloadExisting(page);
 await page.locator('.layers > summary').click();
 await page.getByRole('status').filter({hasText:'General roads/trails unavailable from provider.'}).waitFor();
 assert.equal(await page.getByRole('alert').filter({hasText:'Map layer could not load'}).count(),0);
 transportFailure=false;
 const retry=page.waitForResponse(r=>r.url().includes('/api/browsing/transportation/')&&r.url().includes('retry=')&&r.status()===200);
 await page.getByRole('button',{name:'Retry general roads/trails',exact:true}).click();await retry;
 await page.getByText('USGS general roads and trails · browsing context only',{exact:true}).waitFor();
 await page.unroute('**/api/browsing/transportation/**',transportRoute);
 await page.locator('.layers > summary').click();
 await details();
 // Required foliage failure must never announce a successfully viewed scene.
 const count=viewed.length;
 await page.route('**/assets/cluster-120-dense-vertices.bin*',r=>r.fulfill({status:500,body:'Controlled required asset failure'}));
 await page.getByRole('button',{name:'View',exact:true}).click();
 await page.getByRole('alert').filter({hasText:/cluster-120-dense-vertices|asset|500/}).waitFor();
 await page.waitForTimeout(300);
 assert.equal(viewed.length,count,'Failed required geometry cannot attest inspection');
 assert.equal(JSON.parse(await page.locator('.fp-scene').getAttribute('data-camera')).loaded,false);
 await page.screenshot({path:out+'/required-geometry-failure.png',fullPage:true});
 await page.keyboard.press('Escape');
 assert.match(await page.evaluate(()=>document.activeElement.textContent),/View/,'Scene close restores focus to its trigger');
 console.log('Required foliage failure did not attest viewing');
 // Synthetic list sizes exercise UI costs only, without recomputing or replacing analysis.
 const actual=await (await page.request.get(`${base}/api/runs/${run}`)).json();
 const sample=actual.candidates.find(p=>p.id==='A0075');
 const timings=[];
 for (const size of [150,600,1500,5000]) {
  await page.route(`${base}/api/runs/${run}`,async route=>route.fulfill({json:{...actual,groups:{},review_ids:[],recommendation_ids:[],candidates:Array.from({length:size},(_,i)=>({...sample,id:i===0?'A0075':`PERF${i}`,metrics:{...sample.metrics,raw_km2:sample.metrics.raw_km2/(i+1)}}))}}));
  await reloadExisting(page);await page.getByLabel('Run selector').selectOption(run);await page.getByLabel('Saved neighborhood').selectOption('all');
  await page.getByLabel('Select A0075',{exact:true}).waitFor();
  assert.equal(await page.locator('.candidate-select').count(),size<=250?size:100);
  if(size>250) {
  await page.getByRole('button',{name:'Next setups',exact:true}).click();
  await page.getByLabel('Select PERF100',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Previous setups',exact:true}).click();
  }
  await page.getByLabel('Find a setup').fill('PERF'+(size-1));await page.getByLabel('Select PERF'+(size-1),{exact:true}).waitFor();
  await page.getByLabel('Find a setup').fill('');await page.getByLabel('Select A0075',{exact:true}).click();
  await page.getByRole('button',{name:'Setup details',exact:true}).click();
  assert.equal(await page.locator('.sidebar .candidate-select').count(),0,'Hidden lists must not mount cards');
  const began=performance.now();await page.getByLabel('Candidate notes').pressSequentially('abcdefghijklmnopqrst');
  const typingMs=performance.now()-began;timings.push({size,typingMs});console.log('Candidate UI timing',{size,typingMs});
  assert.ok(typingMs<2000,`Typing must remain interactive with ${size} candidates: ${typingMs}ms`);
  await page.unroute(`${base}/api/runs/${run}`);
 }
 // Read-only saved owner analysis; all GUI state/drafts remain disposable.
 await reloadExisting(page);
 const realRun='scouting-2026-10-16222';
 if(await page.getByLabel('Run selector').locator(`option[value="${realRun}"]`).count()) {
  await page.getByLabel('Run selector').selectOption(realRun);
  await page.getByLabel('Saved neighborhood').selectOption('all');
  await page.locator('.candidate-select').first().click();
  await page.getByRole('button',{name:'Setup details',exact:true}).click();
  await page.getByLabel('Candidate notes').waitFor();
  const realData=await (await page.request.get(`${base}/api/runs/${realRun}`)).json();
  const began=performance.now();await page.getByLabel('Candidate notes').pressSequentially('abcdefghijklmnopqrst');
  timings.push({fixture:'saved-owner-analysis',size:realData.candidates.length,typingMs:performance.now()-began});
  assert.equal(await page.locator('.sidebar .candidate-select').count(),0);
 } else {
  await details();
 }
 await page.setViewportSize({width:900,height:900});await page.getByRole('button',{name:'← All setups',exact:true}).click();
 const bounds=await page.locator('.candidate-list').boundingBox(), sidebar=await page.locator('.sidebar').boundingBox();
 assert.ok(bounds.y+Math.min(bounds.height,100)<sidebar.y+sidebar.height,'Actual results remain visible at 900px');
 await page.screenshot({path:out+'/find-900.png',fullPage:true});
 // A fresh context preserves the 2x scale while Playwright captures full pages.
 const narrow=await browser.newPage({viewport:{width:450,height:450},deviceScaleFactor:2});
 await narrow.addInitScript(()=>localStorage.setItem('huntmaps-online-imagery','off'));
 await openExisting(narrow,base);
 await narrow.locator('.candidate-select').first().waitFor();
 await narrow.getByLabel('Find a setup').scrollIntoViewIfNeeded();
 assert.ok(await narrow.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 const runPicker=await narrow.getByLabel('Run selector').boundingBox();
 assert.ok(runPicker.x>=0 && runPicker.x+runPicker.width<=450,'Area selector remains within the narrow layout');
 const stages=await narrow.locator('.workflow-stages > button').evaluateAll(buttons=>buttons.map(b=>{const r=b.getBoundingClientRect();return {x:r.x,right:r.right,width:r.width};}));
 assert.ok(stages.every((b,i)=>b.width>60 && b.right<=450 && (i===0 || b.x>=stages[i-1].right-1)),'Workflow stages remain separate at 200% effective zoom');
 await narrow.locator('.candidate-select').first().scrollIntoViewIfNeeded();
 await narrow.locator('.candidate-select').first().focus();await narrow.keyboard.press('Enter');
 assert.equal(await narrow.locator('.candidate-select').first().getAttribute('aria-pressed'),'true');
 await narrow.screenshot({path:out+'/find-200-percent.png',fullPage:true});
 await narrow.close();
 assert.deepEqual(errors,[]);
 fs.writeFileSync(out+'/results.json',JSON.stringify({timings,requiredAssetFailureBlocked:true,optionalProviderRecovered:true,draftsRetained:true,errors},null,2));
 console.log('Audit note persistence, save ordering, failed scene readiness, bounded lists and zoom passed',timings);
} catch(error) {await page.screenshot({path:out+'/failure.png',fullPage:true});fs.writeFileSync(out+'/failure.txt',await page.locator('body').innerText());throw error;}
finally {await browser.close();}
