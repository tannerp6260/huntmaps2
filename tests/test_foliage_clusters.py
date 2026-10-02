import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from huntmaps_gui.config import AppConfig, configured
import numpy as np
from huntmaps_gui import foliage_clusters as c,vegetation_screen as v,first_person as fp

class Clusters(unittest.TestCase):
    def test_neighbor_support_nonrecursive_duplicates_unknown(self):
        ground=np.zeros((601,601));points=[]
        # strong at x0 and2; weak1 has two strong neighbors; weak3 only one.
        for x,n in [(0,4),(2,4),(1,2),(3,3),(4,2),(5,1),(15,3)]:
            points.extend([[x+.1+i*.1,.1,1.1,1] for i in range(n)])
        points.extend([points[0]]*20)
        legacy=v.cells(np.array(points),ground,0)[0]
        centres,kinds,counts,_=v.cells(np.array(points),ground,0,True)
        np.testing.assert_array_equal(legacy[:,0],[.5,2.5]);np.testing.assert_array_equal(centres[:,0],[.5,1.5,2.5]);np.testing.assert_array_equal(counts,[4,2,4])
        ground[299:301,301:303]=np.nan
        centres=v.cells(np.array(points),ground,0,True)[0]
        self.assertNotIn(1.5,centres[:,0])
        classified=np.array([[.1+i*.1,.1,1.1,4] for i in range(4)])
        self.assertEqual(v.cells(classified,np.zeros((601,601)),0,True)[1][0],0)
    def mesh(self,centres,side=1.5,step=.5):
        a,f=c.surface(np.array(centres,float),side,step);t=a[f].astype(float)
        return a,f,(t,t.min(axis=1),t.max(axis=1))
    def test_union_seams_watertight_gap_and_determinism(self):
        a,f,mesh=self.mesh([[7.5,.5,.5],[8.5,.5,.5],[15.5,.5,.5]])
        edges=np.sort(np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1)
        _,counts=np.unique(edges,axis=0,return_counts=True)
        np.testing.assert_array_equal(counts,np.full(len(counts),2))
        self.assertTrue(c.inside(mesh,[8,.5,.5]));self.assertFalse(c.inside(mesh,[12,.5,.5]))
        self.assertIsNone(c.intersect(mesh,[12,-3,.5],[12,3,.5])[0])
        b,g,_=self.mesh([[7.5,.5,.5],[8.5,.5,.5],[15.5,.5,.5]])
        np.testing.assert_array_equal(a,b);np.testing.assert_array_equal(f,g)
    def test_dense_contact_and_tile_corner_regression(self):
        rng=np.random.default_rng(187)
        keys=np.array(list(np.ndindex(5,4,5)))+np.array([6,-2,6])
        centres=keys[rng.random(len(keys))<.55]+.5
        centres=np.vstack([centres,[1.5,1.5,1.5]])
        for side in v.SCENARIOS.values():
            for step in c.STEPS:
                a,f,_=self.mesh(centres,side,step)
                edges=np.sort(np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1)
                _,n=np.unique(edges,axis=0,return_counts=True)
                self.assertTrue(np.all(n==2),(side,step,int((n!=2).sum())))
    def test_independent_triangle_ray_and_inside(self):
        a,f,mesh=self.mesh([[.5,.5,.5],[1.5,.5,.5]])
        self.assertEqual(c.intersect(mesh,[.5,.5,.5],[4,.5,.5])[0],0)
        self.assertTrue(c.intersect(mesh,[-3,.5,.5],[.5,.5,.5])[3])
        rng=np.random.default_rng(54)
        for _ in range(50):
            start=np.array([-3.,*rng.uniform(-1,2,2)]);end=np.array([4.,*rng.uniform(-1,2,2)]);d=end-start;hits=[]
            for face in f:
                x,y,z=a[face].astype(float);e1=y-x;e2=z-x;h=np.cross(d,e2);det=np.dot(e1,h)
                if abs(det)<1e-12:continue
                s=start-x;u=np.dot(s,h)/det;q=np.cross(s,e1);w=np.dot(d,q)/det;t=np.dot(e2,q)/det
                if 0<=u<=1 and 0<=w and u+w<=1 and 0<=t<=1:hits.append(t)
            actual=c.intersect(mesh,start,end)[0]
            if hits:self.assertAlmostEqual(actual,min(hits),places=6)
            else:self.assertIsNone(actual)
    def test_nested_scenarios_coarsening_and_empty(self):
        centres=np.array([[.5,.5,.5],[1.5,.5,.5]])
        meshes=[self.mesh(centres,side)[2] for side in v.SCENARIOS.values()]
        for y in np.linspace(-.5,1.5,25):
            hits=[c.intersect(m,[-3,y,.5],[4,y,.5])[0] is not None for m in meshes]
            self.assertEqual(hits,sorted(hits))
        for step in c.STEPS:
            _,f,_=self.mesh([[.5,.5,.5]],1,step);self.assertGreater(len(f),0)
        with patch.object(c,'surface',side_effect=[c.BudgetError('budget')]+[(np.zeros((1,3)),np.zeros((1,3),dtype=int))]*3):
            step,_,n=c.build_range(centres,30);self.assertEqual(step,.5);self.assertEqual(n,2)
        with self.assertRaises(c.BudgetError):c.build_range(centres,30,cap=0)
        with self.assertRaises(ValueError):c.build_range(centres,True)
        step,meshes,n=c.build_range(np.empty((0,3)),30);self.assertEqual(n,0)
    def test_cluster_job_failure_cancel_restart_preserves_prior(self):
        import sys,time
        from huntmaps_gui.jobs import Jobs
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);prior=root/'ready.json';prior.write_text('prior validated scene')
            jobs=Jobs(root)
            prefix="import numpy as np; from pathlib import Path; from huntmaps_gui import foliage_clusters as c; print('STAGE Building bounded synthetic foliage',flush=True); "
            failed=jobs.start([sys.executable,'-u','-c',prefix+"c.surface(np.array([[.5,.5,.5]]),1.5,.5,cap=0)"],'first-person-cluster-fixture')
            def wait(ident,statuses):
                until=time.monotonic()+10
                while time.monotonic()<until:
                    j=next(x for x in jobs.list() if x['id']==ident)
                    if j['status'] in statuses:return j
                    time.sleep(.02)
                self.fail('Synthetic cluster job did not finish')
            self.assertEqual(wait(failed['id'],{'failed'})['status'],'failed')
            partial=root/'partial.bin'
            code=prefix+"v,f=c.surface(np.array([[.5,.5,.5]]),1.5,.5); v.tofile("+repr(str(partial))+"); print('STAGE Synthetic mesh saved; awaiting cancellation',flush=True); import time; time.sleep(60)"
            job=jobs.start([sys.executable,'-u','-c',code],'first-person-cluster-fixture')
            until=time.monotonic()+10
            while not partial.exists() and time.monotonic()<until:time.sleep(.02)
            self.assertTrue(partial.exists());jobs.cancel(job['id']);self.assertEqual(wait(job['id'],{'cancelled'})['status'],'cancelled')
            restarted=jobs.start([sys.executable,'-u','-c',code],'first-person-cluster-fixture')
            second=Jobs(root)
            self.assertEqual(next(j for j in second.list() if j['id']==restarted['id'])['status'],'interrupted')
            # Join the old wait thread before asserting durable interrupted status.
            jobs.process.wait(timeout=5);time.sleep(.05)
            self.assertEqual(next(j for j in second.list() if j['id']==restarted['id'])['status'],'interrupted')
            self.assertEqual(prior.read_text(),'prior validated scene');self.assertTrue(partial.exists())
            jobs.shutdown();second.shutdown()
    def test_asset_references_and_screening_scope(self):
        with tempfile.TemporaryDirectory() as folder,configured(AppConfig(state_dir=Path(folder))):
            base='a'*32;target=Path(folder)/'first-person/bundles'/base;target.mkdir(parents=True)
            a,f,_=self.mesh([[5.5,.5,.5]])
            a.tofile(target/'v.bin');f.tofile(target/'i.bin')
            entry=dict(vertices_file='v.bin',indices_file='i.bin')
            meta=dict(hashes={'v.bin':'hash','i.bin':'hash'},asset_bundles={'v.bin':base,'i.bin':base},vegetation=dict(meshes={'30':dict(sampling_interval_m=.5,cell_count=1,scenarios={n:entry for n in v.SCENARIOS})}))
            r=c.evaluate(Path(folder),meta,[0,.5,.5],[120,.5,.5],120,100,'medium',False,30,fp.asset_path)
            self.assertTrue(r['farther_vegetation_unevaluated']);self.assertEqual(r['included_cell_count'],1)
            self.assertAlmostEqual(r['scenarios']['medium']['first_intersection']['line_m'],100.5)
            for name in ['../v.bin','missing.bin']:
                with self.assertRaises(ValueError):fp.asset_path(Path(folder),meta,name)
            meta['asset_bundles']['v.bin']='../outside'
            with self.assertRaises(ValueError):fp.asset_path(Path(folder),meta,'v.bin')

if __name__=='__main__':unittest.main()
