"""Working coordinate/mask transactions against real cached Soap Creek sources."""
import copy,json,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from osgeo import gdal
from fastapi.testclient import TestClient
from huntmaps_gui import working_waypoints as w,server,manual_observers as manual
from huntmaps_gui.catalog import Run
from huntmaps_gui.config import AppConfig, configured
from huntmaps_gui.jobs import Jobs,write,ACTIVE

RUN='soap-creek-decision-review-v2'
BODY=dict(observer_east_m=1,observer_north_m=-2,name='A0075 working',notes='Inspect foreground')

class WorkingWaypoints(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.configured=configured(AppConfig(state_dir=self.root));self.configured.__enter__();self.jobs=Jobs()
    def tearDown(self):self.jobs.shutdown();self.configured.__exit__(None,None,None);self.tmp.cleanup()
    def wait(self,ident):
        end=time.monotonic()+15
        while time.monotonic()<end:
            j=next(j for j in self.jobs.list() if j['id']==ident)
            if j['status'] not in ACTIVE:return j
            time.sleep(.05)
        self.fail('Bounded job did not finish')
    def update(self,body=BODY):
        response=w.start(RUN,'A0075',body,self.jobs)
        if response['status']=='running':
            j=self.wait(response['job']['id']);self.assertEqual(j['status'],'complete',j.get('logs'))
        return w.snapshot(RUN,self.jobs)['overrides']['A0075']
    def synthetic_pending(self,command,proposal=None):
        j=self.jobs.start([sys.executable,'-u','-c',command],'waypoint-update',name=RUN)
        folder=w.home(RUN);data=w.state(folder);old=data['overrides']['A0075']
        data['pending']['A0075']=dict(job_id=j['id'],proposal=proposal or copy.deepcopy(old),revision=old['revision'],status='running');write(folder/'state.json',data)
        return j
    def test_real_mask_area_alignment_clipping_and_no_scores(self):
        point=self.update();r=w.DisplayRun(RUN,self.jobs);mask,check=r.mask('A0075');ds=gdal.Open(str(r.visibility_path('A0075')))
        self.assertEqual(ds.GetGeoTransform(),r.dem.GetGeoTransform());self.assertTrue(ds.GetSpatialRef().IsSame(r.dem.GetSpatialRef()));self.assertEqual(ds.GetRasterBand(1).GetNoDataValue(),255)
        target=gdal.Open(str(r.analysis/'target.tif')).ReadAsArray()==1;self.assertFalse(np.any(mask&~target))
        self.assertAlmostEqual(mask.sum()*100/1e6,point['metrics']['raw_km2']);self.assertNotIn('baseline_score',point['metrics'])
        p=r.candidate('A0075',True);self.assertEqual(p['longitude'],point['longitude']);self.assertEqual(p['original_analysis']['longitude'],Run(RUN).candidate('A0075')['longitude']);self.assertNotEqual(p['longitude'],p['original_analysis']['longitude'])
        self.assertEqual(r.sectors('A0075')['features'],[])
    def test_repeat_cache_restore_and_review_do_not_duplicate(self):
        point=self.update();count=len(self.jobs.list());again=w.start(RUN,'A0075',BODY,self.jobs)
        self.assertTrue(again['cached']);self.assertEqual(len(self.jobs.list()),count);self.assertEqual(len(w.snapshot(RUN,self.jobs)['overrides']),1)
        edit=w.review(RUN,'A0075',dict(name='Edited',notes='Question',status='keep'),self.jobs);self.assertEqual(edit['longitude'],point['longitude']);self.assertEqual(edit['revision'],point['revision'])
        w.restore(RUN,'A0075',self.jobs);self.assertEqual(w.snapshot(RUN,self.jobs)['overrides'],{});self.assertEqual(w.DisplayRun(RUN,self.jobs).candidate('A0075')['longitude'],Run(RUN).candidate('A0075')['longitude'])
    def test_legacy_manual_waypoint_keeps_identity_and_gets_own_mask(self):
        with configured(AppConfig(state_dir=self.root)):
            old=manual.create(RUN,dict(BODY,anchor='A0075'))
            before=manual.records(RUN)
            response=w.start(RUN,old['id'],dict(BODY,observer_east_m=2),self.jobs)
            self.assertEqual(self.wait(response['job']['id'])['status'],'complete')
            p=w.snapshot(RUN,self.jobs)['overrides'][old['id']]
            self.assertEqual(p['id'],old['id']);self.assertEqual(p['east_m'],2)
            r=w.DisplayRun(RUN,self.jobs);self.assertGreater(r.mask(old['id'])[0].sum(),0)
            self.assertEqual(manual.records(RUN),before)
            w.restore(RUN,old['id'],self.jobs)
            self.assertEqual(r.base.candidate('A0075')['id'],'A0075')
            self.assertEqual(w.DisplayRun(RUN,self.jobs).candidate(old['id']),old)
    def test_failure_and_cancel_keep_prior_location_and_partial_files(self):
        before=self.update()
        j=self.synthetic_pending("print('STAGE Synthetic validation');print('GUI JOB: synthetic failure');raise SystemExit(2)")
        self.assertEqual(self.wait(j['id'])['status'],'failed');snap=w.snapshot(RUN,self.jobs);self.assertEqual(snap['overrides']['A0075'],before);self.assertEqual(snap['pending']['A0075']['status'],'failed')
        j=self.synthetic_pending("import time;print('STAGE Synthetic bounded calculation',flush=True);time.sleep(30)")
        partial=w.home(RUN)/'partials'/'synthetic-partial';partial.mkdir(parents=True);(partial/'trace.txt').write_text('partial retained')
        self.jobs.cancel(j['id']);self.assertEqual(self.wait(j['id'])['status'],'cancelled');self.assertEqual(w.snapshot(RUN,self.jobs)['overrides']['A0075'],before);self.assertTrue((partial/'trace.txt').exists())
    def test_restart_and_late_completion_cannot_publish_restored_point(self):
        before=self.update();j=self.synthetic_pending("import time;print('STAGE Synthetic calculation',flush=True);time.sleep(30)")
        replacement=Jobs(self.root);self.assertEqual(self.wait(j['id'])['status'],'interrupted');self.assertEqual(w.snapshot(RUN,replacement)['overrides']['A0075'],before)
        w.restore(RUN,'A0075',replacement)
        # Even a later completion record is no longer a pending publication token.
        path=self.root/'jobs'/(j['id']+'.json');record=json.loads(path.read_text());record['status']='complete';write(path,record)
        self.assertEqual(w.snapshot(RUN,replacement)['overrides'],{});replacement.shutdown()
    def test_busy_invalid_and_tampered_masks_rejected(self):
        self.update();j=self.jobs.start([sys.executable,'-c','import time;time.sleep(30)'],'synthetic')
        with self.assertRaisesRegex(ValueError,'Another job'):w.start(RUN,'A0075',BODY,self.jobs)
        self.jobs.cancel(j['id']);self.wait(j['id'])
        with self.assertRaises(ValueError):w.start(RUN,'A0075',dict(BODY,observer_east_m=20),self.jobs)
        path=w.DisplayRun(RUN,self.jobs).visibility_path('A0075');path.write_bytes(b'tampered')
        with self.assertRaises(ValueError):w.DisplayRun(RUN,self.jobs).mask('A0075')
    def test_api_guards_exports_historical_read_and_restoration(self):
        with configured(AppConfig(state_dir=self.root)):
            with TestClient(server.create_app(AppConfig(state_dir=self.root))) as client:
                url='/api/runs/'+RUN;headers={'X-HuntMaps':'local'}
                self.assertEqual(client.post(url+'/working-waypoints/A0075',json=BODY).status_code,403)
                response=client.post(url+'/working-waypoints/A0075',json=BODY,headers=headers);self.assertEqual(response.status_code,200);j=response.json()['job'];self.assertEqual(self.wait(j['id'])['status'],'complete')
                p=client.get(url+'/working-waypoints').json()['overrides']['A0075']
                self.assertEqual(client.get(url+'/candidates/A0075').json()['longitude'],Run(RUN).candidate('A0075')['longitude'])
                self.assertEqual(client.get(url+'/working-candidates/A0075').json()['longitude'],p['longitude'])
                import xml.etree.ElementTree as ET
                for fmt in ['gpx','kml']:
                    doc=ET.fromstring(client.get(url+'/export/'+fmt,params={'ids':'A0075,V010'}).content)
                    if fmt=='gpx':coords=(float(doc[0].attrib['lon']),float(doc[0].attrib['lat']))
                    else:coords=tuple(map(float,doc.findall('.//{*}coordinates')[0].text.split(',')[:2]))
                    self.assertEqual(coords,(p['longitude'],p['latitude']))
                self.assertEqual(client.delete(url+'/working-waypoints/A0075',headers=headers).status_code,200)
                self.assertEqual(client.get(url+'/working-waypoints').json()['overrides'],{})
