"""Bounded offline engineering journey through the live GUI job API, never a hunting area."""
import json,sys,time,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from glassing.transfer_fixture import create
from huntmaps_gui.catalog import ROOT,STATE,read
from huntmaps_gui.jobs import write
client=httpx.Client(base_url='http://127.0.0.1:8765/api',headers={'X-HuntMaps':'local'},timeout=30)
ident=uuid.uuid4().hex;folder=STATE/'fixtures'/ident;folder.mkdir(parents=True);config=folder/'fixture.json';create(str(config),str(folder/'sources'))
c=read(config);c.update(normal_scouting=True,manual_points=None);write(config,c)
name='synthetic-gui-'+ident[:8];p=dict(id=ident,name=name,area=str(folder/'sources/observer.geojson'),polygon='1',config=str(config),max_download_mb=600,prepared=False);write(STATE/'plans'/(ident+'.json'),p)
seen=[]
def post(path,body=None):
 r=client.post(path,json=body or {});r.raise_for_status();return r.json()
def wait(j,expected):
 for _ in range(300):
  record=next(r for r in client.get('/jobs').json() if r['id']==j['id'])
  seen.append(dict(id=j['id'],status=record['status'],stage=record['stage'],elapsed_s=record['elapsed_s']))
  if record['status'] not in ['running','cancelling']:
   assert record['status']==expected,record
   return record
  time.sleep(.1)
 raise RuntimeError('Job exceeded test deadline')
# Source validation failure is real: descriptor hash is deliberately invalid in this fixture only.
c['data']['dem']['sha256']='invalid synthetic test hash';write(config,c)
bad=post('/plans/'+ident+'/prepare');wait(bad,'failed')
c=read(config);from glassing.acquire import digest
c['data']['dem']['sha256']=digest(c['data']['dem']['path']);write(config,c)
partial=ROOT/'results'/name/'scouting.json'
if partial.exists():
 fixed=read(partial);fixed['data']['dem']=c['data']['dem'];write(partial,fixed)
prepared=post('/plans/'+ident+'/prepare');wait(prepared,'complete')
plan=client.get('/plans/'+ident).json();assert plan['sources_ready'] and plan['acquisition']['estimated_bytes']==0
cancelled=post('/plans/'+ident+'/start',{'download':False})
# Allow the real wrapper to emit an actual stage, then cancel its full process group.
for _ in range(60):
 current=next(j for j in client.get('/jobs').json() if j['id']==cancelled['id'])
 if 'STAGE ' in current['logs']:break
 time.sleep(.02)
post('/jobs/'+cancelled['id']+'/cancel');wait(cancelled,'cancelled')
complete=post('/plans/'+ident+'/start',{'download':False});finished=wait(complete,'complete')
assert (ROOT/'results'/name/'manifest.json').exists()
assert any(r['id']==name for r in client.get('/runs').json())
assert 'STAGE Baseline report and GIS exports complete' in finished['logs']
write(STATE/'verification/jobs.json',dict(name=name,plan=ident,failure=bad['id'],prepare=prepared['id'],cancel=cancelled['id'],complete=complete['id'],observations=seen))
print('Real offline baseline journey, failure, cancellation, resume and discovery passed:',name)
