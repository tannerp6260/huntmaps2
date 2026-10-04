import { chromium } from 'playwright';
import fs from 'node:fs';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const base=process.env.HUNTMAPS_URL,out=process.env.HUNTMAPS_SCREENSHOTS, state=process.env.HUNTMAPS_STATE_DIR;
if (!base || !out || !state) throw Error('Run through ./gui/check');
fs.mkdirSync(out,{recursive:true});
const project=fileURLToPath(new URL('../../',import.meta.url));
const python=fileURLToPath(new URL('../../.venv/bin/python',import.meta.url));
const browser=await chromium.launch({executablePath:process.env.HUNTMAPS_BROWSER||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader']});
const page=await browser.newPage({viewport:{width:1500,height:1050}}), errors=[];
page.on('pageerror',e=>errors.push(e.message));
await page.addInitScript(()=>localStorage.setItem('huntmaps-online-imagery','off'));
const headers={'X-HuntMaps':'local'};
try {
  // No routing during this section: test actual browser cache, not intercepted responses.
  await page.goto(base);await page.getByLabel('Run selector').selectOption('workflow-fixture');
  const sceneUrl='/api/runs/workflow-fixture/first-person/A0001';
  const before=await (await page.request.get(base+sceneUrl)).json();
  assert.equal(before.status,'ready');
  const asset='context-vertices.bin';
  const hash=async url=>page.evaluate(async url=>{const r=await fetch(url);const a=await r.arrayBuffer();return [...new Uint8Array(await crypto.subtle.digest('SHA-256',a))].map(x=>x.toString(16).padStart(2,'0')).join('');},url);
  assert.equal(await hash(sceneUrl+'/assets/'+asset+'?scene_key='+before.key),before.hashes[asset]);
  const replacement=JSON.parse(execFileSync(python,['-c',`
import json,shutil,hashlib
from pathlib import Path
import numpy as np
from huntmaps_gui import first_person as fp
from huntmaps_gui.storage import write,read_json
folder,meta=fp.bundle('A0001','workflow-fixture')
key='f'*32;target=Path(${JSON.stringify(state)})/'first-person/bundles'/key
shutil.copytree(folder,target,dirs_exist_ok=True)
p=target/'context-vertices.bin'
a=np.frombuffer(p.read_bytes(),dtype=np.float32).copy();a[0]+=7;p.write_bytes(a.tobytes())
meta=dict(meta,key=key,hashes=dict(meta['hashes']));meta['hashes']['context-vertices.bin']=hashlib.sha256(p.read_bytes()).hexdigest()
write(target/'scene.json',meta);write(fp.ready_path('workflow-fixture','A0001'),dict(key=key))
print(json.dumps(dict(key=key,sha256=meta['hashes']['context-vertices.bin'])))
`],{encoding:'utf8',cwd:project}));
  assert.notEqual(replacement.sha256,before.hashes[asset]);
  assert.equal(await hash(sceneUrl+'/assets/'+asset+'?scene_key='+replacement.key),replacement.sha256);
  // An old viewing signature must not attest to the replacement scene.
  const workflow=await (await page.request.get(base+'/api/runs/workflow-fixture/workflow')).json();
  const point=workflow.points.A0001.point;
  const stale=await page.request.put(base+'/api/runs/workflow-fixture/workflow/A0001',{headers,data:{action:'viewed',revision:workflow.revision,point,scene:before.key}});
  assert.equal(stale.status(),400);
  // Restore original pointer for subsequent journeys, keeping both immutable bundles.
  execFileSync(python,['-c',`from huntmaps_gui import first_person as fp; from huntmaps_gui.storage import write; write(fp.ready_path('workflow-fixture','A0001'),dict(key=${JSON.stringify(before.key)}))`],{cwd:project});
  await page.getByRole('button',{name:'+ New baseline run',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Draw on map',exact:true}).count(),0);
  assert.equal(await page.getByRole('button',{name:'Draw boundary',exact:true}).count(),1);
  await page.getByText('How we find places to glass',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Help: effort',exact:true}).click();
  await page.getByRole('tooltip').filter({hasText:'How many possible standing'}).waitFor();
  await page.keyboard.press('Escape');
  await page.getByText('More options · sampling restrictions',{exact:true}).click();
  await page.getByText('Observer access sampling and network acquisition',{exact:true}).click();
  const proximity=page.getByLabel('Only look near mapped roads or trails',{exact:true});
  assert.equal(await proximity.isChecked(),true);
  const distance=page.getByLabel('Maximum distance from a road or trail (miles)');
  await distance.fill('0.25');assert.equal(await distance.getAttribute('type'),'text');
  const label=proximity.locator('..'), rect=await label.boundingBox(), panel=await page.locator('.inspector').boundingBox();
  if (panel.x+panel.width-8>rect.x+rect.width+8) await page.mouse.click(panel.x+panel.width-8,rect.y+rect.height/2);
  assert.equal(await proximity.isChecked(),true,'Empty space must not toggle checkbox');
  await page.screenshot({path:out+'/01-settings-desktop.png',fullPage:true});
  await page.setViewportSize({width:900,height:900});await page.screenshot({path:out+'/02-settings-900.png',fullPage:true});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  // Archive has real durable state but leaves analysis bytes accessible.
  await page.getByRole('button',{name:'Manage saved results',exact:true}).click();
  const manager=page.getByRole('dialog',{name:'Manage saved results'});
  await manager.getByLabel('Managed run').selectOption('search-fixture');
  await manager.getByRole('button',{name:'Archive',exact:true}).click();
  await manager.getByRole('button',{name:'Unarchive',exact:true}).waitFor();
  assert.ok((await (await page.request.get(base+'/api/run-management')).json()).find(r=>r.id==='search-fixture').archived);
  await manager.getByRole('button',{name:'Unarchive',exact:true}).click();
  await manager.getByRole('button',{name:'Review permanent deletion',exact:true}).click();
  await manager.getByRole('button',{name:'Permanently delete these results',exact:true}).waitFor();
  await page.screenshot({path:out+'/03-deletion-review-900.png',fullPage:true});
  await manager.getByRole('button',{name:'Close',exact:true}).click();
  assert.equal((await page.request.get(base+'/api/runs/search-fixture')).status(),200);
  assert.deepEqual(errors,[]);
  fs.writeFileSync(out+'/results.json',JSON.stringify({errors,before:before.key,replacement,staleViewingStatus:stale.status()},null,2));
  console.log('Immutable browser assets, stale viewing gate, concise help, drawing action, proximity hitbox and archived/deletion review verified');
} finally { await browser.close(); }
