// Explicit service fixture for specialist journeys. This seeds decisions; it does
// not assert that a browser rendered the scene. browser-workflow-check tests that.
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
export async function workflowFixture(request, base) {
 if (!process.env.HUNTMAPS_STATE_DIR?.startsWith('/tmp/huntmaps-check-')) throw Error('Fixture requires isolated release runner');
 const headers={'X-HuntMaps':'local'}, api=base+'/api/runs/workflow-fixture';
 async function json(response) { assert.equal(response.status(),200,await response.text()); return response.json(); }
 async function idle(id) {
  for(let n=0;n<600;n++) {
   const jobs=await json(await request.get(base+'/api/jobs'));
   if (id) {
    const job=jobs.find(j=>j.id===id);
    if(job && !['running','cancelling'].includes(job.status)) {assert.equal(job.status,'complete',JSON.stringify(job));return;}
   } else if(!jobs.some(j=>['running','cancelling'].includes(j.status))) return;
   await new Promise(r=>setTimeout(r,100));
  }
  throw Error('Fixture job timeout');
 }
 await idle();
 // Each newly focused spot resolves complete road AND trail query coverage.
 // Importing one unbounded line is intentionally insufficient for that contract.
 const inventories=JSON.parse(execFileSync(fileURLToPath(new URL('../../.venv/bin/python',import.meta.url)),['-c',`
import json
from pathlib import Path
from huntmaps_gui.config import current
from huntmaps_gui.catalog import Run
from gui.connectivity_fixture import sources
assert current().state_dir.resolve().is_relative_to(Path('/tmp'))
r=Run('workflow-fixture')
assert r.config.get('input_kind')=='synthetic_fixture'
print(json.dumps(sources(r,r.candidate('A0001'))))
`],{cwd:fileURLToPath(new URL('../../',import.meta.url)),encoding:'utf8'}));
 const point=await json(await request.get(api+'/workflow-point/A0001'));
 async function decide(cid,action,extra={}) {
  const state=await json(await request.get(api+'/workflow'));
  const p=await json(await request.get(api+'/workflow-point/'+cid));
  return json(await request.put(api+'/workflow/'+cid,{headers,data:{action,point:p,revision:state.revision,...extra}}));
 }
 const before=await json(await request.get(api+'/workflow'));
 for(const [cid,p] of Object.entries(before.points)) if(cid!=='A0001'&&p.shortlisted)await decide(cid,'remove');
 await decide('A0001','shortlist');
 let scenarios=await json(await request.get(api+'/approaches'));
 let prior=scenarios.find(s=>!s.stale&&s.results?.results.some(r=>r.point.id==='A0001'&&r.alternatives.length));
 if(!prior) {
  const lon=point.longitude, lat=point.latitude;
  const body={ids:['A0001'],network_ids:inventories,travel_area:{type:'Polygon',coordinates:[[[lon-.002,lat-.002],[lon+.002,lat-.002],[lon+.002,lat+.002],[lon-.002,lat+.002],[lon-.002,lat-.002]]]},maximum_slope_deg:35};
  const submitted=await json(await request.post(api+'/approaches',{headers,data:body}));
  await idle(submitted.job.id);
  prior=await json(await request.get(base+'/api/approaches/'+submitted.scenario.id));
 }
 const state=await json(await request.get(api+'/workflow')), review=await json(await request.get(api+'/approach-review'));
 await json(await request.put(api+'/approach-review',{headers,data:{revision:review?.revision ?? 0,workflow_revision:state.revision,ids:['A0001'],active_point:'A0001',point,draft:{...prior.scenario,scenario:prior.scenario.id,alternative:0,attempted:true,boundary_confirmed:true}}}));
 await decide('A0001','approach',{scenario:prior.scenario.id,alternative:0});
 let scene=await json(await request.get(api+'/first-person/A0001'));
 if(scene.status!=='ready') {
  const job=await json(await request.post(base+'/api/first-person/plans',{headers,data:{run_id:'workflow-fixture',ids:['A0001'],fidelity:'terrain'}}));
  await idle(job.id);
  const plan=await json(await request.get(base+'/api/first-person/plans/'+job.plan));
  const prepared=await json(await request.post(base+'/api/first-person/plans/'+job.plan+'/start',{headers,data:{download:false,review_signature:plan.review_signature}}));
  await idle(prepared.id);
  scene=await json(await request.get(api+'/first-person/A0001'));
  assert.equal(scene.status,'ready');
 }
 await decide('A0001','viewed',{scene:scene.key});
 await decide('A0001','confirm');
 return {point,scene,scenario:prior.scenario};
}
