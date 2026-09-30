"""Actual crash/restart test, using only an isolated synthetic plan. Stop the GUI first."""
import json,os,signal,subprocess,sys,time,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from glassing.transfer_fixture import create
from huntmaps_gui.catalog import ROOT,STATE,read
from huntmaps_gui.jobs import write
client=httpx.Client(base_url='http://127.0.0.1:8765/api',headers={'X-HuntMaps':'local'},timeout=10)
logpath=STATE/'verification/restart-server.log';logpath.parent.mkdir(parents=True,exist_ok=True);log=logpath.open('wb')
def launch():
 proc=subprocess.Popen([str(ROOT/'huntmaps-gui'),'--no-browser'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
 for _ in range(100):
  if proc.poll() is not None:raise RuntimeError('Could not start dedicated test server; stop the GUI first')
  try:
   if client.get('/runs').status_code==200:return proc
  except httpx.HTTPError:pass
  time.sleep(.1)
 raise RuntimeError('Startup deadline exceeded')
def post(path,body=None):
 r=client.post(path,json=body or {});r.raise_for_status();return r.json()
def job(ident):return next(j for j in client.get('/jobs').json() if j['id']==ident)
proc=None
try:
 ident=uuid.uuid4().hex;folder=STATE/'fixtures'/ident;folder.mkdir(parents=True);config=folder/'fixture.json';create(str(config),str(folder/'sources'));c=read(config);c.update(normal_scouting=True,manual_points=None);write(config,c)
 name='synthetic-restart-'+ident[:8];p=dict(id=ident,name=name,area=str(folder/'sources/observer.geojson'),polygon='1',config=str(config),max_download_mb=600,prepared=False);write(STATE/'plans'/(ident+'.json'),p)
 proc=launch();j=post('/plans/'+ident+'/prepare')
 for _ in range(200):
  current=job(j['id'])
  if current['status'] not in ['running','cancelling']:break
  time.sleep(.1)
 assert current['status']=='complete',current
 running=post('/plans/'+ident+'/start',{'download':False})
 for _ in range(100):
  before=job(running['id'])
  if 'STAGE ' in before['logs']:break
  time.sleep(.02)
 assert before['status']=='running'
 proc.kill();proc.wait(timeout=5);time.sleep(.1)
 proc=launch();after=job(running['id']);assert after['status']=='interrupted',after
 worker=Path(f'/proc/{running["pid"]}/stat')
 for _ in range(100):
  if not worker.exists() or worker.read_text().rsplit(')',1)[1].split()[0]=='Z':break
  time.sleep(.02)
 assert not worker.exists() or worker.read_text().rsplit(')',1)[1].split()[0]=='Z','Surviving worker after recovery'
 write(STATE/'verification/restart.json',dict(name=name,plan=ident,before=before,after=after,worker_stopped=True))
 print('Actual server crash/restart marks unfinished job interrupted and stops its worker:',name)
finally:
 if proc and proc.poll() is None:proc.terminate();proc.wait(timeout=10)
 client.close();log.close()
