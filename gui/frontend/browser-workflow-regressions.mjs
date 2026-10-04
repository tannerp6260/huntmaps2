import { chromium } from 'playwright';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const base=process.env.HUNTMAPS_URL,out=process.env.HUNTMAPS_SCREENSHOTS;
if (!base||!out) throw Error('Run through ./gui/check');
fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.HUNTMAPS_BROWSER||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader']});
const page=await browser.newPage({viewport:{width:1500,height:1050}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));await page.addInitScript(()=>localStorage.setItem('huntmaps-online-imagery','off'));
await page.route('**/*',r=>r.request().url().startsWith(base)||r.request().url().startsWith('blob:')?r.continue():r.abort());
const headers={'X-HuntMaps':'local'}, run='search-fixture';
const decision=async(cid,action)=>{const v=await (await page.request.get(`${base}/api/runs/${run}/workflow`)).json();const p=await (await page.request.get(`${base}/api/runs/${run}/working-candidates/${cid}`)).json();const point={id:cid,longitude:p.longitude,latitude:p.latitude,revision:p.working_revision};if(!point.revision){const pt=v.points[cid]?.point;if(pt)point.revision=pt.revision;else { // ask a backend shortlist endpoint's exact point snapshot
 const kept=await (await page.request.get(`${base}/api/runs/${run}/kept-points`)).json(); point.revision=kept.find(x=>x.id===cid)?.revision;
 }}
 // Fixture original point identity is the backend digest of its exact lon/lat.
 if (!point.revision) { const bytes=new TextEncoder().encode(JSON.stringify([point.longitude,point.latitude])); // Python digest uses sorted JSON with spaces.
 const text='['+point.longitude+', '+point.latitude+']';point.revision=await page.evaluate(async text=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text)))].map(x=>x.toString(16).padStart(2,'0')).join(''),text); }
 const res=await page.request.put(`${base}/api/runs/${run}/workflow/${cid}`,{headers,data:{action,revision:v.revision,point}});assert.equal(res.status(),200,await res.text());return await res.json();};
try {
 await page.goto(base);await page.getByLabel('Run selector').selectOption(run);await page.getByLabel('Saved neighborhood').selectOption('all');await page.getByLabel('Select A0001',{exact:true}).click();
 const targetBefore=await (await page.request.get(base+'/api/runs/workflow-fixture/annotations')).json();
 await page.getByLabel('Candidate decision').selectOption('keep');await page.getByLabel('Candidate notes').fill('Belongs only to search-fixture');
 let release,enter;const held=new Promise(r=>release=r),entered=new Promise(r=>enter=r);
 await page.route('**/api/runs/search-fixture/annotations/A0001',async route=>{if(route.request().method()==='PUT'){enter();await held;}await route.continue();});
 const reply=page.waitForResponse(r=>r.url().endsWith('/search-fixture/annotations/A0001')&&r.request().method()==='PUT');
 await page.getByRole('button',{name:'Save review',exact:true}).click();await entered;
 await page.getByLabel('Run selector').selectOption('workflow-fixture');await page.getByLabel('Candidate notes').waitFor();
 release();await reply;await page.waitForTimeout(300);
 assert.deepEqual(await (await page.request.get(base+'/api/runs/workflow-fixture/annotations')).json(),targetBefore);
 assert.notEqual(await page.getByLabel('Candidate notes').inputValue(),'Belongs only to search-fixture');
 await page.unroute('**/api/runs/search-fixture/annotations/A0001');
 const data=await (await page.request.get(base+'/api/runs/'+run)).json();const ids=data.candidates.filter(p=>!data.recommendation_ids.includes(p.id)).slice(0,2).map(p=>p.id);
 assert.equal(ids.length,2);
 for(const cid of ids) await decision(cid,'shortlist');
 await page.getByLabel('Run selector').selectOption(run);await page.getByLabel('Saved neighborhood').selectOption('recommended');await page.getByLabel('Find a setup').fill('no-such-setup');
 await page.getByRole('button',{name:/2 · Compare approaches/}).click();
 for(const cid of ids) await page.getByLabel('Select '+cid,{exact:true}).waitFor();
 await page.screenshot({path:out+'/01-independent-stage-list-desktop.png',fullPage:true});
 await page.setViewportSize({width:900,height:900});await page.screenshot({path:out+'/02-approaches-900.png',fullPage:true});
 // Recovery must retrieve the correct scenario, even when lists are still loading.
 const scenarios=await (await page.request.get(base+'/api/runs/workflow-fixture/approaches')).json();assert.ok(scenarios.length);
 const scenario=scenarios[0].scenario;
 await page.route('**/api/jobs',r=>r.fulfill({json:[{id:'a'.repeat(32),kind:'approach',name:'workflow-fixture',plan:scenario.id,status:'failed',stage:'Synthetic approach recovery',error:'Controlled failure',elapsed_s:1}]}));
 await page.getByText('Job history and recovery',{exact:true}).click();await page.locator('details.jobs > summary').click();
 const job=page.locator('.job').filter({hasText:'Synthetic approach recovery'});await job.waitFor({timeout:15000});
 await job.getByRole('button',{name:'Review / resume plan',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('[aria-label="Run selector"]').value==='workflow-fixture');
 await page.waitForFunction(id=>[...document.querySelectorAll('.approach-controls select')].some(s=>s.value===id),scenario.id);
 assert.equal(await page.getByRole('alert').filter({hasText:'Unknown plan'}).count(),0);
 for(const cid of ids) await decision(cid,'remove');
 assert.deepEqual(errors,[]);fs.writeFileSync(out+'/results.json',JSON.stringify({errors,independentPoints:ids,recoveredScenario:scenario.id},null,2));
 console.log('Delayed annotation responses, stage-scoped lists and typed approach recovery verified');
}finally{await browser.close();}
