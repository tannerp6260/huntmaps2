"""GUI adapter integration checks against saved real results and isolated job fixtures."""
import io,json,math,os,signal,subprocess,sys,tempfile,time,unittest,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from osgeo import gdal
from huntmaps_gui.catalog import ROOT,STATE,Run
from huntmaps_gui.tiles import tile,sources
from huntmaps_gui.jobs import Jobs,write
from huntmaps_gui.server import create_app

class GuiTests(unittest.TestCase):
 def test_real_visibility_alignment_cover_and_tiles(self):
  r=Run('soap-creek-decision-review-v2')
  self.assertEqual(r.groups['West'][:3],['A0075','V010','V008'])
  for ident,area in [('A0075',1.2567),('V010',1.3155),('V008',1.2937)]:
   p=r.candidate(ident,True);self.assertAlmostEqual(p['alignment']['mapped_km2'],area,places=9)
   m,check=r.mask(ident);self.assertFalse(np.any(m&~(gdal.Open(str(r.analysis/'target.tif')).ReadAsArray()==1)))
   metrics=p['metrics'];self.assertAlmostEqual(sum(metrics[k] for k in ['tree_lt10_km2','tree_10to40_km2','tree_ge40_km2','tree_unknown_km2']),area,places=9)
   classes_path,_=sources(r,'classes',ident,0);class_ds=gdal.Open(str(classes_path[0]));self.assertEqual((class_ds.GetRasterBand(4).ReadAsArray()>0).sum(),int(m.sum()))
   paths,_=sources(r,'visible',ident,0);rgba=gdal.Open(str(paths[0]));self.assertEqual(rgba.GetGeoTransform(),r.dem.GetGeoTransform());self.assertTrue(rgba.GetSpatialRef().IsSame(r.dem.GetSpatialRef()));self.assertEqual(int((rgba.GetRasterBand(4).ReadAsArray()>0).sum()),int(m.sum()))
   x,y=p['longitude'],p['latitude'];z=15;tx=int((x+180)/360*2**z);ty=int((1-math.asinh(math.tan(math.radians(y)))/math.pi)/2*2**z)
   data=tile(r,'visible',ident,z,tx,ty);self.assertEqual(Image.open(io.BytesIO(data)).size,(256,256))
   # Tile center and alpha must match independent coordinate transforms into source cells.
   from glassing.transfer import project
   half=20037508.342789244;size=2*half/2**z;merc=project(3857,r.config['epsg']);gt=r.dem.GetGeoTransform();a=np.array(Image.open(io.BytesIO(data)))
   for rr,cc in [(40,40),(90,180),(120,120),(220,70)]:
    xx,yy=merc(-half+(tx+(cc+.5)/256)*size,half-(ty+(rr+.5)/256)*size);col=int((xx-gt[0])/gt[1]);row=int((yy-gt[3])/gt[5]);expected=m[row,col] if 0<=row<m.shape[0] and 0<=col<m.shape[1] else False
    self.assertEqual(a[rr,cc,3]>0,bool(expected))

 def test_exports_import_and_mutation_guards(self):
  client=TestClient(create_app());ids=['A0075','V010','V008'];r=Run('soap-creek-decision-review-v2')
  for fmt in ['gpx','kml']:
   response=client.get('/api/runs/'+r.id+'/export/'+fmt,params={'ids':','.join(ids)});self.assertEqual(response.status_code,200);root=ET.fromstring(response.content)
   if fmt=='gpx':coords=[(float(w.attrib['lon']),float(w.attrib['lat'])) for w in root]
   else:coords=[tuple(map(float,w.text.split(',')[:2])) for w in root.findall('.//{*}coordinates')]
   for ident,xy in zip(ids,coords):
    p=r.candidate(ident);self.assertEqual(xy,(p['longitude'],p['latitude']))
  body={'status':'keep','notes':'test'};url='/api/runs/'+r.id+'/annotations/A0075'
  self.assertEqual(client.put(url,json=body).status_code,403)
  self.assertEqual(client.put(url,json=body,headers={'X-HuntMaps':'local','Origin':'https://other.invalid'}).status_code,403)
  original=(ROOT/'inputs/test.kml').read_bytes()
  response=client.post('/api/imports',files={'file':('area.kml',(ROOT/'inputs/test.kml').read_bytes(),'application/xml')},headers={'X-HuntMaps':'local'});self.assertEqual(response.status_code,200);self.assertTrue(response.json()['choices'])
  self.assertEqual(Path(response.json()['path']).read_bytes(),original)
  self.assertEqual(original,(ROOT/'inputs/test.kml').read_bytes())
  tile_response=client.get('/api/runs/'+r.id+'/tiles/visible/A0075/15/6615/12559.png');self.assertEqual(tile_response.status_code,200);self.assertEqual(tile_response.headers['content-type'],'image/png')
  self.assertEqual(client.get('/api/runs/'+r.id+'/tiles/visible/A0075/24/0/0.png').status_code,400)
  self.assertEqual(client.get('/api/runs/'+r.id+'/export/gpx',params={'ids':'not-a-point'}).status_code,400)

 def test_job_success_failure_cancel_restart_and_serialization(self):
  state=Path(tempfile.mkdtemp(prefix='huntmaps-jobs-'));jobs=Jobs(state)
  def wait(j):
   for _ in range(100):
    value=next(v for v in jobs.list() if v['id']==j['id'])
    if value['status'] not in ['running','cancelling']:return value
    time.sleep(.05)
   self.fail('Job did not terminate')
  good=jobs.start([sys.executable,'-u','-c','print("STAGE fixture computation"); print("fixture done")'],'synthetic');self.assertEqual(wait(good)['status'],'complete')
  bad=jobs.start([sys.executable,'-u','-c','print("STAGE fixture source validation"); raise ValueError("synthetic missing DEM")'],'synthetic');self.assertEqual(wait(bad)['status'],'failed')
  long=jobs.start([sys.executable,'-u','-c','import time;print("STAGE bounded synthetic hold");time.sleep(15)'],'synthetic')
  with self.assertRaisesRegex(ValueError,'Another job'):jobs.start([sys.executable,'-c','pass'],'synthetic')
  time.sleep(.15);self.assertEqual(jobs.list()[0]['stage'],'bounded synthetic hold');jobs.cancel(long['id']);self.assertEqual(wait(long)['status'],'cancelled')
  write(state/'jobs'/'interrupted.json',dict(id='interrupted',status='running',started=time.time(),stage='old job',kind='synthetic'))
  recovered=Jobs(state);self.assertEqual(next(j for j in recovered.list() if j['id']=='interrupted')['status'],'interrupted')

 def test_cancellation_kills_descendants_that_ignore_term(self):
  state=Path(tempfile.mkdtemp(prefix='huntmaps-kill-'));jobs=Jobs(state);pidfile=state/'child.pid'
  child="import os,signal,time;from pathlib import Path;signal.signal(signal.SIGTERM,signal.SIG_IGN);Path("+repr(str(pidfile))+").write_text(str(os.getpid()));time.sleep(15)"
  parent="import subprocess,sys,time;subprocess.Popen([sys.executable,'-c',"+repr(child)+"]);print('STAGE synthetic child running',flush=True);time.sleep(15)"
  j=jobs.start([sys.executable,'-u','-c',parent],'synthetic')
  for _ in range(100):
   if pidfile.exists():break
   time.sleep(.02)
  self.assertTrue(pidfile.exists());pid=int(pidfile.read_text());jobs.cancel(j['id'])
  for _ in range(100):
   if jobs.list()[0]['status']=='cancelled':break
   time.sleep(.02)
  self.assertEqual(jobs.list()[0]['status'],'cancelled')
  stat=Path(f'/proc/{pid}/stat')
  for _ in range(100):
   if not stat.exists() or stat.read_text().rsplit(')',1)[1].split()[0]=='Z':break
   time.sleep(.02)
  self.assertTrue(not stat.exists() or stat.read_text().rsplit(')',1)[1].split()[0]=='Z')
  jobs.shutdown()

if __name__=='__main__':unittest.main()
