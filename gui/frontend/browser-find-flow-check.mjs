import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const base = process.env.HUNTMAPS_URL || 'http://127.0.0.1:8765';
const out = process.env.HUNTMAPS_SCREENSHOTS || '/tmp/huntmaps-find-flow';
fs.mkdirSync(out, {recursive:true});
const browser = await chromium.launch({executablePath:process.env.HUNTMAPS_BROWSER || '/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader']});
const geometry = {type:'Polygon',coordinates:[[[-107.3,38.7],[-107.29,38.7],[-107.29,38.71],[-107.3,38.71],[-107.3,38.7]]]};
const errors=[];
async function fixture({estimated=0,blocked=false,preparationError=false}={}) {
  const page=await browser.newPage({viewport:{width:1280,height:900}});
  page.on('pageerror', e=>errors.push(e.message));
  await page.addInitScript(()=>{
    localStorage.setItem('huntmaps-online-imagery','off');
    localStorage.setItem('huntmaps-training-v2',JSON.stringify({notes:{},current:'review',lessons:{review:{lesson:'review',step:'select',paused:false,complete:false}},draft:null}));
  });
  const state={jobs:[],prepared:false,creates:0,starts:0,cancels:0,runLoads:0,refreshRequired:false,refreshes:0,inputs:null,estimated,blocked,preparationError};
  const id='c'.repeat(32);
  const makeJob=(kind,status)=>({id:kind+'-job',plan:id,kind,status,name:state.inputs?.name || 'fixture',stage:kind==='prepare'?'Preparing sources':'Downloading sources',elapsed_s:2});
  const plan=()=>({id,name:state.inputs.name,prepared:state.prepared,source_refresh_required:state.refreshRequired,sources_ready:!estimated,max_download_mb:state.inputs.max_download_mb,review_signature:'checked-signature',include_network:true,access_sampling:state.inputs.access_sampling,
    settings:{radius_m:state.inputs.radius_m,observation_minutes:state.inputs.observation_minutes,candidate_count:state.inputs.candidate_count,search:{recommendation_count:state.inputs.recommendation_count,recommendation_separation_m:state.inputs.recommendation_separation_m,nearby_radius_m:state.inputs.nearby_radius_m,tree_threshold_percent:state.inputs.tree_threshold_percent,target_filters:state.inputs.target_filters,avoid_dense_vegetation:state.inputs.avoid_dense_vegetation}},
    acquisition:{estimated_bytes:state.estimated,already_cached_bytes:100,cached_keys:['dem'],items:[],errors:state.preparationError?['Catalog unavailable']:[],estimate_note:'Controlled source fixture'},storage:{blocked:state.blocked,volumes:[]}});
  await page.route('**/api/**',async route=>{
    const req=route.request(),path=new URL(req.url()).pathname;
    let value={};
    if(path==='/api/runs') value=[{id:'saved-fixture',label:'Saved fixture',experimental:false}];
    else if(path.startsWith('/api/runs/')) {
      state.runLoads++;
      if(path==='/api/runs/saved-fixture') value={id:'saved-fixture',candidates:[],groups:{all:[],review:[]},review_ids:[],bounds:[[-107.3,38.7],[-107.29,38.71]],boundary:{type:'FeatureCollection',features:[]},radius_m:500,imagery:[],warning:'Fixture',synthetic:true};
      else if(path.endsWith('/manual-observers'))value=[];
      else if(path.endsWith('/working-waypoints'))value={overrides:{}};
      else if(path.endsWith('/workflow'))value={revision:'fixture',points:{}};
      else value={};
    }
    else if(path==='/api/jobs') value=state.jobs;
    else if(path.startsWith('/api/jobs/')&&!path.endsWith('/cancel')) value=state.jobs.find(j=>j.id===path.split('/').at(-1))||{};
    else if(path==='/api/networks') value=[];
    else if(path==='/api/imports')value={id:'import-fixture',choices:[{number:'1',name:'Test polygon',geometry}]};
    else if(path==='/api/plans'&&req.method()==='POST') {
      state.creates++; state.inputs=req.postDataJSON();state.jobs=[makeJob('prepare','running')];value=state.jobs[0];
    }
    else if(path===`/api/plans/${id}/start`) {
      state.starts++;assert.equal(req.postDataJSON().review_signature,'checked-signature');assert.equal(req.postDataJSON().download,true);
      state.jobs=[makeJob('baseline','running'),...state.jobs];value=state.jobs[0];
    }
    else if(path===`/api/plans/${id}/prepare`){state.refreshes++;state.refreshRequired=false;state.prepared=false;state.jobs=[makeJob('prepare','running')];value=state.jobs[0];}
    else if(path===`/api/plans/${id}`)value=plan();
    else if(path.endsWith('/cancel')){state.cancels++;state.jobs[0].status='cancelled';value=state.jobs[0];}
    await route.fulfill({json:value});
  });
  await page.route('**/*',r=>r.request().url().startsWith(base)||r.request().url().startsWith('blob:')?r.fallback():r.abort());
  await page.goto(base);
  await page.getByRole('dialog',{name:'Welcome to HuntMaps2',exact:true}).waitFor();
  return {page,state,id,ready:()=>{state.prepared=true;state.jobs[0].status='complete';}};
}
async function intake(page) {
  await page.getByRole('button',{name:'New scouting area',exact:true}).click();
  await page.getByRole('button',{name:'Import file',exact:true}).click();
  await page.getByLabel('Import observer polygon').setInputFiles({name:'area.geojson',mimeType:'application/geo+json',buffer:Buffer.from(JSON.stringify(geometry))});
  await page.getByLabel('New run name').fill('find-flow-test');
  await page.getByRole('button',{name:'Generate setups',exact:true}).waitFor();
}
async function begin(f) {
  await intake(f.page);
  await f.page.getByRole('button',{name:'Generate setups',exact:true}).click();
  await f.page.getByRole('dialog',{name:'Generating setups',exact:true}).waitFor();
  await waitFor(f.page,()=>f.state.creates===1);
  assert.equal(f.state.creates,1);assert.equal(f.state.starts,0);
}
async function waitFor(page,fn){await page.waitForFunction(()=>true);for(let n=0;n<80;n++){if(fn())return;await page.waitForTimeout(100);}throw Error('Expected transition did not happen');}
try {
  const start=await fixture();
  assert.equal(start.state.runLoads,0);
  assert.equal(await start.page.locator('.training-coach').count(),0);
  await start.page.keyboard.press('Escape');
  assert.equal(await start.page.getByRole('dialog',{name:'Welcome to HuntMaps2'}).isVisible(),true);
  await start.page.screenshot({path:out+'/01-startup.png'});
  await start.page.setViewportSize({width:900,height:850});
  assert.equal(await start.page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  assert.equal(await start.page.evaluate(()=>document.querySelector('dialog[open]').contains(document.activeElement)),true);
  await start.page.setViewportSize({width:1280,height:900});
  await intake(start.page);
  assert.equal(start.state.runLoads,0);
  await start.page.getByRole('button',{name:'About Find',exact:true}).click();
  await start.page.getByRole('dialog',{name:'About Find',exact:true}).getByText('Sources and limits',{exact:true}).waitFor();
  await start.page.screenshot({path:out+'/02-about-find.png'});
  await start.page.keyboard.press('Escape');
  assert.equal(await start.page.getByText('How this works',{exact:true}).count(),0);
  await start.page.getByText('Road and trail restrictions',{exact:true}).click();
  await start.page.getByRole('checkbox',{name:'Roads',exact:true}).waitFor();
  assert.equal(await start.page.getByRole('checkbox',{name:'Trails',exact:true}).isChecked(),true);
  await start.page.getByRole('checkbox',{name:'Roads',exact:true}).uncheck();
  await start.page.getByRole('checkbox',{name:'Trails',exact:true}).uncheck();
  await start.page.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>b.textContent.trim()==='Generate setups'&&b.disabled));
  assert.equal(await start.page.getByRole('button',{name:'Generate setups',exact:true}).isDisabled(),true);
  await start.page.reload();await start.page.getByRole('dialog',{name:'Welcome to HuntMaps2',exact:true}).waitFor();
  assert.equal(start.state.runLoads,0);
  await start.page.getByRole('button',{name:'Training',exact:true}).click();
  await start.page.getByRole('dialog',{name:'Learn HuntMaps2'}).waitFor();
  assert.equal(await start.page.getByRole('button',{name:'Start lesson 1',exact:true}).isDisabled(),true);
  assert.equal(await start.page.locator('.training-coach').count(),0);
  await start.page.close();

  const success=await fixture({estimated:1000000});await begin(success);success.ready();await waitFor(success.page,()=>success.state.starts===1);
  await success.page.getByRole('button',{name:'Continue in background',exact:true}).click();
  await success.page.getByRole('button',{name:'Show generation progress',exact:true}).click();
  await success.page.screenshot({path:out+'/03-progress.png'});
  assert.equal(success.state.starts,1);
  success.state.jobs[0].status='failed';success.state.jobs[0].failure_code='provider_failed';success.state.jobs[0].failed_stage='Downloading and validating USGS RCMAP tree-cover service';success.state.jobs[0].error='SCOUT: Approved source acquisition failed: tree: USGS RCMAP tree-cover service returned an error: class java.lang.String cannot be cast to class org.eclipse.emf.ecore.EObject';
  await success.page.getByRole('dialog',{name:'Generating setups',exact:true}).getByRole('button',{name:'Retry',exact:true}).waitFor({timeout:15000});
  const modal=success.page.getByRole('dialog',{name:'Generating setups',exact:true});
  await modal.getByText(/USGS RCMAP tree-cover service returned an error instead of usable data/).waitFor();
  assert.equal(await modal.locator('pre').isVisible(),false);
  await modal.getByText('Technical diagnostics',{exact:true}).click();await modal.locator('pre').getByText(/java.lang.String/).waitFor();
  await success.page.screenshot({path:out+'/04-provider-failure.png'});
  success.state.refreshRequired=true;
  await modal.getByRole('button',{name:'Retry',exact:true}).click();await waitFor(success.page,()=>success.state.refreshes===1);assert.equal(success.state.starts,1);success.ready();await waitFor(success.page,()=>success.state.starts===2);
  success.state.jobs[0].status='complete';await modal.getByRole('button',{name:'Open results',exact:true}).waitFor({timeout:15000});
  await success.page.close();

  for(const opts of [{estimated:1e12},{blocked:true},{preparationError:true}]) {
    const f=await fixture(opts);await begin(f);f.ready();
    await f.page.getByRole('dialog',{name:'Generating setups',exact:true}).getByText(opts.blocked?'Not enough free storage. Review storage before generating setups.':opts.preparationError?'Catalog unavailable':/Estimated download exceeds/, {exact:false}).waitFor();
    assert.equal(f.state.starts,0);await f.page.close();
  }
  const duplicate=await fixture();await intake(duplicate.page);await duplicate.page.getByRole('button',{name:'Generate setups',exact:true}).evaluate(button=>{button.click();button.click();});await waitFor(duplicate.page,()=>duplicate.state.creates===1);duplicate.ready();await waitFor(duplicate.page,()=>duplicate.state.starts===1);await duplicate.page.waitForTimeout(600);assert.equal(duplicate.state.creates,1);assert.equal(duplicate.state.starts,1);await duplicate.page.close();
  const cancel=await fixture();await begin(cancel);await cancel.page.getByRole('dialog',{name:'Generating setups',exact:true}).getByRole('button',{name:'Cancel current job',exact:true}).click();
  await waitFor(cancel.page,()=>cancel.state.cancels===1);cancel.ready();await cancel.page.waitForTimeout(800);assert.equal(cancel.state.starts,0);await cancel.page.close();
  const changed=await fixture();await begin(changed);await changed.page.getByRole('button',{name:'Continue in background',exact:true}).click();await changed.page.getByLabel('View radius',{exact:true}).selectOption('457.2');changed.ready();await changed.page.waitForTimeout(800);assert.equal(changed.state.starts,0);await changed.page.close();
  const invalid=await fixture();await begin(invalid);await invalid.page.getByRole('button',{name:'Continue in background',exact:true}).click();await invalid.page.getByText('Road and trail restrictions',{exact:true}).click();await invalid.page.getByLabel('Maximum distance from a road or trail (yards)').fill('.');await invalid.page.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>b.textContent.trim()==='Generate setups'&&b.disabled));invalid.ready();await invalid.page.waitForTimeout(800);assert.equal(invalid.state.starts,0);await invalid.page.close();
  const reloaded=await fixture();await begin(reloaded);await reloaded.page.reload();await reloaded.page.getByRole('dialog',{name:'Welcome to HuntMaps2',exact:true}).waitFor();reloaded.ready();await reloaded.page.waitForTimeout(800);assert.equal(reloaded.state.starts,0);await reloaded.page.close();
  assert.deepEqual(errors,[]);
  fs.writeFileSync(out+'/find-flow-results.json',JSON.stringify({startup:true,trainingOptIn:true,oneClick:true,providerRecovery:true,limits:true,cancellation:true,staleInputs:true,reload:true,errors},null,2));
  console.log('Startup and one-click Find flow checks passed:',out);
} finally {await browser.close();}
