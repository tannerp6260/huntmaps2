import { chromium } from 'playwright';
import fs from 'node:fs';
import assert from 'node:assert/strict';
import ts from 'typescript';
const base=process.env.HUNTMAPS_URL,out=process.env.HUNTMAPS_SCREENSHOTS;
if(!base||!out)throw Error('Run through ./gui/check');
fs.mkdirSync(out,{recursive:true});
for(const name of ['units','decimal-input']) {
 const code=ts.transpileModule(fs.readFileSync(`src/${name}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext}}).outputText;
 const mod=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
 if(name==='units') {assert.equal(mod.area(2.589988110336),'1.000 mi²');assert.equal(mod.yards(1609.344),'1,760 yd'.replace(',',''));assert.equal(mod.feet(304.8),'1000 ft');}
 else {assert.equal(mod.decimalValue('.'),null);assert.equal(mod.decimalValue('.75'),.75);assert.equal(mod.decimalValue(''),null);assert.equal(mod.decimalValue('NaN'),null);}
}
const browser=await chromium.launch({executablePath:process.env.HUNTMAPS_BROWSER||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader']});
const page=await browser.newPage({viewport:{width:1500,height:1050}}),errors=[],requests=[];
page.on('pageerror',e=>errors.push(e.message));
page.on('request',r=>{if(r.request){} if(r.method()==='POST'&&r.url().endsWith('/approaches'))requests.push(r.postDataJSON());});
await page.addInitScript(()=>localStorage.setItem('huntmaps-online-imagery','off'));
await page.route('**/*',r=>r.request().url().startsWith(base)||r.request().url().startsWith('blob:')?r.continue():r.abort());
const api=base+'/api/runs/workflow-fixture',headers={'X-HuntMaps':'local'};
async function decide(cid,action,extra={}) {
 const state=await(await page.request.get(api+'/workflow')).json();
 const point=state.points[cid]?.point||await(await page.request.get(api+'/workflow-point/'+cid)).json();
 const r=await page.request.put(api+'/workflow/'+cid,{headers,data:{revision:state.revision,point,action,...extra}});assert.equal(r.status(),200,await r.text());
}
async function review() {return(await page.request.get(api+'/approach-review')).json();}
try {
 await page.goto(base);await page.getByLabel('Run selector').selectOption('workflow-fixture');
 const run=await(await page.request.get(api)).json();
 const existing=await(await page.request.get(api+'/approaches')).json();
 const ids=run.candidates.filter(p=>p.id!=='A0001'&&!existing.some(s=>s.scenario.points.some(q=>q.id===p.id))).slice(0,2).map(p=>p.id);
 assert.equal(ids.length,2);
 const before=await(await page.request.get(api+'/workflow')).json();
 for(const [cid,p] of Object.entries(before.points))if(p.shortlisted&&cid!=='A0001'&&!ids.includes(cid))await decide(cid,'remove');
 for(const cid of ids)await decide(cid,'shortlist');
 const saved=await(await page.request.get(api+'/approaches')).json();
 const prior=saved.find(s=>s.results?.results.some(r=>r.point.id==='A0001'&&r.alternatives.length));assert.ok(prior);
 const seedState=await(await page.request.get(api+'/workflow')).json(),seedReview=await review();
 const seed={...prior.scenario,scenario:prior.scenario.id,alternative:0,attempted:true,boundary_confirmed:true};
 const seeded=await page.request.put(api+'/approach-review',{headers,data:{revision:seedReview.revision,workflow_revision:seedState.revision,ids:['A0001',...ids],active_point:'A0001',point:seedState.points.A0001.point,draft:seed}});assert.equal(seeded.status(),200,await seeded.text());
 await decide('A0001','approach',{scenario:prior.scenario.id,alternative:0});
 const points=run.candidates;
 const xs=points.map(p=>p.longitude),ys=points.map(p=>p.latitude);
 const x0=Math.min(...xs)-.003,x1=Math.max(...xs)+.003,y0=Math.min(...ys)-.003,y1=Math.max(...ys)+.003;
 const area={type:'Polygon',coordinates:[[[x0,y0],[x1,y0],[x1,y1],[x0,y1],[x0,y0]]]};
 const state=await(await page.request.get(api+'/workflow')).json(),old=await review();
 const first=ids[0];
 const d={...prior.scenario,travel_area:area,maximum_slope_deg:60,scenario:null,alternative:0,attempted:false,boundary_confirmed:true,point:state.points[first].point};
 const res=await page.request.put(api+'/approach-review',{headers,data:{revision:old.revision,workflow_revision:state.revision,ids:['A0001',...ids],active_point:first,point:state.points[first].point,draft:d}});assert.equal(res.status(),200,await res.text());
 await page.reload();await page.getByLabel('Run selector').selectOption('workflow-fixture');await page.getByRole('button',{name:/2 · Compare approaches/}).click();
 await page.getByLabel('Focused approach spot').waitFor();assert.equal(await page.getByLabel('Focused approach spot').inputValue(),first);
 await page.getByRole('button',{name:'Use this approach & next spot',exact:true}).waitFor({timeout:60000});
 assert.equal(requests.length,1,'Uncomputed focused point starts one automatic comparison');
 assert.deepEqual(requests[0].ids,[first]);
 await page.waitForFunction(ids=>{const s=JSON.parse(document.querySelector('.map').dataset.mapState||'{}');return s.loaded&&JSON.stringify(s.candidateIds?.sort())===JSON.stringify(ids.sort());},['A0001',...ids],{timeout:60000});
 const mapBox=await page.locator('.map').boundingBox();
 const pixels=await page.locator('.map').getAttribute('data-map-state').then(v=>JSON.parse(v).candidatePixels);
 const marker=pixels.find(p=>p.id==='A0001'&&p.x>10&&p.y>10&&p.x<mapBox.width-10&&p.y<mapBox.height-10);
 assert.ok(marker,'Another shortlisted point should be visible on this fixture map');
 await page.mouse.click(mapBox.x+marker.x,mapBox.y+marker.y);
 await page.waitForFunction(()=>document.querySelector('[aria-label="Focused approach spot"]')?.value==='A0001');
 await page.getByLabel('Focused approach spot').selectOption(first);
 await page.getByRole('button',{name:'3D terrain',exact:true}).click();
 await page.waitForFunction(ids=>{const s=JSON.parse(document.querySelector('.map').dataset.mapState||'{}');return s.loaded&&s.terrain&&JSON.stringify(s.candidateIds?.sort())===JSON.stringify(ids.sort());},['A0001',...ids],{timeout:60000});
 await page.getByRole('button',{name:'2D',exact:true}).click();
 const active=await page.getByLabel('Focused approach spot').inputValue();
 await page.getByRole('button',{name:'Show this alternative on map',exact:true}).click();
 assert.equal(await page.getByLabel('Focused approach spot').inputValue(),active);
 await page.waitForFunction(()=>{const b=Array.from(document.querySelectorAll('.approach-controls button')).find(b=>b.textContent.includes('Use this approach'));return b&&!b.disabled;});
 await page.getByText('More options · pinned departure and preferences',{exact:true}).click();
 await page.getByLabel('Approach tree weight').fill('4');
 assert.equal(await page.getByLabel('Approach tree weight').inputValue(),'4');
 const recalculated=page.waitForResponse(r=>r.url()===api+'/approaches'&&r.request().method()==='POST'&&r.request().postDataJSON().weights.tree===4);
 await page.getByRole('button',{name:'Recalculate approaches for '+first,exact:true}).click();
 const recalculation=await recalculated;assert.equal(recalculation.status(),200,await recalculation.text());
 await page.waitForFunction(()=>{const b=Array.from(document.querySelectorAll('.approach-controls button')).find(b=>b.textContent.includes('Use this approach'));return b&&!b.disabled;},undefined,{timeout:60000});
 await page.getByRole('button',{name:'Use this approach & next spot',exact:true}).waitFor();
 await page.reload();await page.getByLabel('Run selector').selectOption('workflow-fixture');await page.getByRole('button',{name:/2 · Compare approaches/}).click();
 await page.getByText('More options · pinned departure and preferences',{exact:true}).click();
 assert.equal(await page.getByLabel('Approach tree weight').inputValue(),'4','Reload restores individual preferences');
 assert.equal(requests.length,2,'Reload must not compute again');
 await page.getByRole('button',{name:'Use this approach & next spot',exact:true}).click();
 await page.waitForFunction(cid=>document.querySelector('[aria-label="Focused approach spot"]')?.value===cid,ids[1]);
 await page.getByRole('button',{name:'Dismiss spot & next',exact:true}).click();
 await page.waitForFunction(()=>!Array.from(document.querySelectorAll('.workflow-stages button')).find(b=>b.textContent.includes('3 ·')).disabled);
 await page.screenshot({path:out+'/guided-desktop.png',fullPage:true});
 await page.setViewportSize({width:900,height:900});await page.screenshot({path:out+'/guided-900.png',fullPage:true});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.getByRole('button',{name:'Undo',exact:true}).click();
 await page.waitForFunction(()=>Array.from(document.querySelectorAll('.workflow-stages button')).find(b=>b.textContent.includes('3 ·')).disabled);
 // Keep the remainder of the suite's original single-point fixture intact.
 for(const cid of ids)await decide(cid,'remove');
 await page.getByRole('button',{name:'+ New baseline run',exact:true}).click();
 await page.getByRole('button',{name:'Import file',exact:true}).click();await page.getByLabel('Import observer polygon').setInputFiles(process.env.HUNTMAPS_WORKSPACE+'/workflow-fixture/observer.geojson');
 await page.getByText('More options · sampling restrictions',{exact:true}).click();await page.getByText('Observer access sampling and network acquisition',{exact:true}).click();
 const input=page.getByLabel('Maximum distance from a road or trail (yards)');await input.fill('');await input.pressSequentially('.');assert.equal(await input.inputValue(),'.');
 assert.equal(await page.getByRole('button',{name:'Review downloads',exact:true}).isDisabled(),true);
 await input.pressSequentially('75');assert.equal(await input.inputValue(),'.75');assert.equal(await page.getByRole('button',{name:'Review downloads',exact:true}).isDisabled(),false);
 assert.deepEqual(errors,[]);fs.writeFileSync(out+'/results.json',JSON.stringify({errors,requests,session:await review()},null,2));
 console.log('Imperial known answers, raw decimal keystrokes, isolated automatic comparisons, preferences/reload, next/dismiss/Undo and queue gate verified');
} catch(e) {await page.screenshot({path:out+'/failure.png',fullPage:true});fs.writeFileSync(out+'/failure.txt',await page.locator('body').innerText());fs.writeFileSync(out+'/requests.json',JSON.stringify(requests,null,2));throw e;} finally {await browser.close();}
