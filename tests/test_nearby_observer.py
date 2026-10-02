import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from shapely.geometry import mapping,box
from huntmaps_gui import first_person as fp,manual_observers as manual

class FakeRun:
    def __init__(self,ident):
        self.points={'A0075':dict(x=0,y=0)}
        self.ll=lambda x,y:(x,y)
    def candidate(self,cid):
        if cid!='A0075':raise ValueError('Unknown candidate')
        return dict(longitude=0,latitude=0)
    def boundary(self):return dict(features=[dict(geometry=mapping(box(-8,-8,8,8)))])

class NearbyObservers(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name)
        rows,cols=np.indices((41,41));self.a=100+cols*.2+rows*.1
        np.savez(self.folder/'fine.npz',heights=self.a,res=1,x0=-20,y0=20)
        self.meta=dict(ground_m=106,fine_observer_available=True,key='test',hashes={'fine.npz':'unused'})
        self.patches=[patch.object(fp,'Run',FakeRun),patch.object(manual,'Run',FakeRun),patch.object(fp,'bundle',return_value=(self.folder,self.meta)),patch.object(manual,'STATE',self.folder)]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()
    def pose(self,x,y):return fp.observer(fp.RUN,'A0075',dict(observer_east_m=x,observer_north_m=y))
    def test_support_and_exact_render_triangle(self):
        pose=self.pose(1.25,-2.4)
        vertices,indices=fp.mesh(self.a,1,-20,20,106,300)
        for tri in vertices[indices]:
            weights=np.linalg.solve(np.vstack((tri[:,0],-tri[:,2],np.ones(3))),[1.25,-2.4,1])
            if np.all(weights>=-1e-9):
                self.assertAlmostEqual(float(weights@tri[:,1]),pose['scene_y_m'],places=6);break
        else:self.fail('Missing rendered triangle')
        self.assertEqual(pose['longitude'],1.25)
        self.assertEqual(pose['latitude'],-2.4)
    def test_reject_offsets_and_boundary(self):
        for x,y in [(10,0),(float('nan'),0),(0,float('inf')),(8.1,0)]:
            with self.assertRaises(ValueError):self.pose(x,y)
        for body in [{},{'observer_east_m':1},{'observer_east_m':True,'observer_north_m':0}]:
            with self.assertRaises(ValueError):fp.observer(fp.RUN,'A0075',body)
    def test_unknown_ground_rejected_not_snapped(self):
        self.a[19:22,19:22]=np.nan
        np.savez(self.folder/'fine.npz',heights=self.a,res=1,x0=-20,y0=20)
        with self.assertRaisesRegex(ValueError,'unknown'):self.pose(.25,.25)
    def test_translated_profile_endpoints_and_anchor_curvature(self):
        pose=self.pose(1.25,-2.4);path=self.folder/'fine.npz';a,res,x0,y0=fp.scene_grid(str(path),path.stat().st_mtime_ns,106)
        p=fp.moved_profile(a,res,x0,y0,pose,15,4,1.7,.8,106)
        self.assertAlmostEqual(p['distance_m'],np.hypot(15-1.25,4+2.4))
        self.assertAlmostEqual(p['points'][0]['line_m'],pose['ground_m']+1.7)
        self.assertAlmostEqual(p['points'][-1]['line_m'],float(fp.sample(a,res,x0,y0,np.array(15),np.array(4)))+106+.8)
        self.assertFalse(p['unknown'])
    def test_manual_store_coordinates_immutable_review_edit(self):
        p=manual.create(fp.RUN,dict(anchor='A0075',observer_east_m=1.25,observer_north_m=-2.4,name='Test <observer>',notes='Field question'))
        self.assertEqual(p['status'],'needs inspection');self.assertNotIn('metrics',p)
        q=manual.update(fp.RUN,p['id'],dict(name='Renamed',notes='Updated',status='keep',longitude=99))
        self.assertEqual(q['longitude'],1.25);self.assertEqual(q['scene_key'],'test')
        self.assertEqual(manual.records(fp.RUN)[p['id']],q)
        manual.delete(fp.RUN,p['id']);self.assertEqual(manual.records(fp.RUN),{})
    def test_invalid_fields_do_not_persist(self):
        for name,notes in [('', ''),('x'*101,''),('okay',3)]:
            with self.assertRaises(ValueError):manual.create(fp.RUN,dict(anchor='A0075',observer_east_m=1,observer_north_m=0,name=name,notes=notes))
        self.assertEqual(manual.records(fp.RUN),{})
    def test_paired_profile_offsets_and_distant_unavailable(self):
        body=dict(east_m=350,north_m=0,observer_east_m=1,observer_north_m=0)
        p=fp.profile(fp.RUN,'A0075',body)
        self.assertEqual(p['status'],'unavailable');self.assertEqual(p['points'],[])
        del body['observer_north_m']
        with self.assertRaises(ValueError):fp.profile(fp.RUN,'A0075',body)
    def test_profile_cannot_bridge_missing_rendered_triangles(self):
        self.a[:,26:28]=np.nan
        np.savez(self.folder/'fine.npz',heights=self.a,res=1,x0=-20,y0=20)
        pose=self.pose(1,0);path=self.folder/'fine.npz';a,res,x0,y0=fp.scene_grid(str(path),path.stat().st_mtime_ns,106)
        p=fp.moved_profile(a,res,x0,y0,pose,15,0,1.7,.8,106)
        self.assertTrue(p['unknown']);self.assertEqual(p['result'],'incomplete data')
    def test_local_api_guards_exact_mixed_exports_and_explicit_delete(self):
        from fastapi.testclient import TestClient
        from huntmaps_gui import server
        import xml.etree.ElementTree as ET
        with patch.object(server,'STATE',self.folder),patch.object(server,'Jobs'):
            with TestClient(server.create_app()) as client:
                url='/api/runs/'+fp.RUN+'/manual-observers';body=dict(anchor='A0075',observer_east_m=1.25,observer_north_m=-2.4,name='<Field & observer>',notes='Check brush')
                self.assertEqual(client.post(url,json=body).status_code,403)
                headers={'X-HuntMaps':'local'}
                self.assertEqual(client.post(url,json=body,headers=dict(headers,Origin='https://other')).status_code,403)
                response=client.post(url,json=body,headers=headers);self.assertEqual(response.status_code,200);p=response.json()
                for fmt in ['gpx','kml']:
                    r=client.get('/api/runs/'+fp.RUN+'/export/'+fmt,params=dict(ids='A0075,'+p['id']));self.assertEqual(r.status_code,200);root=ET.fromstring(r.content)
                    if fmt=='gpx':
                        point=root.findall('{*}wpt')[-1];coords=float(point.attrib['lon']),float(point.attrib['lat']);name=point.find('{*}name').text
                    else:
                        point=root.findall('.//{*}Placemark')[-1];coords=tuple(map(float,point.find('.//{*}coordinates').text.split(',')[:2]));name=point.find('{*}name').text
                    self.assertEqual(coords,(1.25,-2.4));self.assertEqual(name,body['name'])
                self.assertEqual(client.get('/api/runs/'+fp.RUN+'/export/gpx',params=dict(ids='manual-unknown')).status_code,400)
                self.assertEqual(client.put(url+'/'+p['id'],json=dict(name='Changed',notes='New question',status='keep',longitude=99),headers=headers).json()['longitude'],1.25)
                self.assertEqual(client.delete(url+'/'+p['id'],headers=headers).status_code,200)
                self.assertEqual(client.get(url).json(),[])
