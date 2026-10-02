import unittest
import numpy as np
from huntmaps_gui import vegetation_screen as veg
from huntmaps_gui import first_person as fp

class VegetationScreen(unittest.TestCase):
    def test_support_duplicates_classes_missing_ground(self):
        ground=np.full((601,601),100.);ground[300,310]=np.nan
        pts=[]
        # Four distinct returns in cell [1,0,1] relative to ground.
        for dx in [.1,.2,.3,.4]:pts.append([1+dx,.1,101.1,1])
        pts.extend([pts[0]]*10)
        for x,cls in [(3,2),(4,6),(5,9),(6,17),(7,7),(8,18),(10,1)]:
            for dx in [.1,.2,.3,.4]:pts.append([x+dx,.1,101.1,cls])
        pts.append([12,.1,105,1])
        centres,kinds,counts,n=veg.cells(np.array(pts),ground,100.)
        self.assertEqual(len(centres),1);self.assertEqual(counts[0],4);self.assertEqual(kinds[0],1)
        self.assertEqual(centres[0,0],1.5);self.assertEqual(centres[0,2],-.5)
    def test_classified_support_and_cap(self):
        ground=np.zeros((601,601));p=np.array([[1+d,.1,1.1,4] for d in [.1,.2,.3,.4]])
        c,k,n,_=veg.cells(p,ground,0)
        self.assertEqual(k[0],0)
        from unittest.mock import patch
        with patch.object(veg,'MAX_CELLS',0):
            with self.assertRaisesRegex(ValueError,'No cells were silently discarded'):veg.cells(p,ground,0)
    def test_foreground_above_below_and_behind(self):
        c=np.array([[5,1,0]],dtype=np.float32)
        self.assertAlmostEqual(veg.intersect(c,[0,1,0],[10,1,0],1)[0],.45)
        for end in [[10,3,0],[10,-3,0],[-10,1,0]]:
            self.assertIsNone(veg.intersect(c,[0,end[1],0],end,1)[0])
    def test_inside_endpoints_and_parallel_grazing(self):
        c=np.array([[0,1,0],[10,1,0]],dtype=np.float32)
        hit=veg.intersect(c,[0,1,0],[10,1,0],1)
        self.assertEqual(hit[0],0);self.assertTrue(hit[2]);self.assertTrue(hit[3])
        self.assertIsNotNone(veg.intersect(c,[-1,1,.5],[11,1,.5],1)[0])
        self.assertIsNone(veg.intersect(c,[-1,1,.51],[11,1,.51],1)[0])
    def test_scenario_monotonicity_and_no_clear_claim(self):
        c=np.array([[5,1,.7],[8,1,0]],dtype=np.float32)
        r=veg.evaluate(c,[0,1,0],[10,1,0],10,100,'medium',True)
        counts=[r['scenarios'][n]['intersected_cells'] for n in veg.SCENARIOS]
        self.assertEqual(counts,sorted(counts));self.assertTrue(r['unknown_ground'])
        self.assertEqual(r['scenarios']['medium']['first_intersection']['line_m'],101)
        empty=veg.evaluate(np.empty((0,3)),[0,1,0],[10,1,0],10,0,'medium')
        self.assertEqual(empty['scenarios']['medium']['result'],'no modeled intersection')
    def test_independent_face_intersections(self):
        # Independent reference: enumerate face crossings and test the other axes.
        rng=np.random.default_rng(54)
        for _ in range(100):
            centre=rng.uniform(-3,3,3).astype(np.float32);start=rng.uniform(-5,5,3);end=rng.uniform(-5,5,3);side=1.5
            low=centre.astype(float)-side/2;high=centre.astype(float)+side/2;delta=end-start;hits=[]
            if np.all((start>=low)&(start<=high)):hits.append(0.)
            for axis in range(3):
                for face in [low[axis],high[axis]]:
                    t=(face-start[axis])/delta[axis];point=start+t*delta
                    if 0<=t<=1 and np.all(point>=low-1e-10) and np.all(point<=high+1e-10):hits.append(t)
            actual=veg.intersect(np.array([centre]),start,end,side)[0]
            if hits:self.assertAlmostEqual(actual,min(hits))
            else:self.assertIsNone(actual)
    def test_profile_compatibility_and_scope(self):
        from unittest.mock import patch
        from pathlib import Path
        meta=dict(fine_observer_available=True,ground_m=0,vegetation={})
        with patch.object(fp,'candidate'),patch.object(fp,'bundle',return_value=(Path('/tmp'),meta)),patch.object(Path,'stat') as st,patch.object(fp,'grid',return_value=(np.zeros((601,601)),1,-300,300)):
            st.return_value.st_mtime_ns=0
            body=dict(east_m=20,north_m=0)
            original=fp.profile(fp.RUN,'A0075',body)
            self.assertNotIn('vegetation',original)
            screened=fp.profile(fp.RUN,'A0075',dict(body,vegetation_scenario='medium'))
            self.assertEqual({k:v for k,v in screened.items() if k!='vegetation'},original)
            self.assertEqual(screened['vegetation']['status'],'unavailable')
            for value in ['bad',[],{}]:
                with self.assertRaises(ValueError):fp.profile(fp.RUN,'A0075',dict(body,vegetation_scenario=value))
            distant=fp.profile(fp.RUN,'A0075',dict(east_m=400,north_m=0,vegetation_scenario='medium'))
            self.assertEqual(distant['vegetation']['status'],'unavailable')
