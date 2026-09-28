import copy
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from glassing import comparison_models as m
from glassing.compare import score,random_baseline


class ComparisonTests(unittest.TestCase):
    def setUp(self):self.c=json.loads(Path('configs/comparison.json').read_text())
    def test_background_and_season_hypotheses(self):
        zeros=np.zeros(3);ones=np.ones(3)
        h=m.habitat(zeros,zeros,zeros,'summer',.25)
        np.testing.assert_allclose(h,.25)
        self.assertTrue(np.all(m.habitat(ones,ones,ones,'winter',.25)<=1))
        np.testing.assert_array_equal(m.habitat(zeros,zeros,zeros,'background',.25),ones)
        with self.assertRaises(ValueError):m.habitat(zeros,zeros,zeros,floor=0)
    def test_distance_tasks_and_budget(self):
        distances=np.array([100,500,1000,2000])
        curves=[m.distance_response(distances,self.c,task=x) for x in ['detect','classify','judge']]
        self.assertTrue(np.all(curves[0]>=curves[1]));self.assertTrue(np.all(curves[1]>=curves[2]))
        self.assertTrue(np.all(np.diff(curves[0])<=0))
        self.assertAlmostEqual(m.inspection_fraction(3,30,.02),.2)
        self.assertEqual(m.inspection_fraction(.2,30,.02),1)
    def test_perspective_and_glare_geometry(self):
        gx=np.array([.5]);zero=np.array([0.]);one=np.array([100.])
        self.assertGreater(m.perspective(gx,zero,-one,zero,zero,0)[0],m.perspective(gx,zero,one,zero,zero,0)[0])
        az,el=np.radians([110,15]);dx=one*np.sin(az)*np.cos(el);dy=one*np.cos(az)*np.cos(el);dz=one*np.sin(el)
        facing=m.sunlight(zero,zero,dx,dy,dz,'morning',self.c)
        away=m.sunlight(zero,zero,-dx,-dy,-dz,'morning',self.c)
        self.assertLess(facing[0],away[0])
        np.testing.assert_array_equal(m.sunlight(zero,zero,dx,dy,dz,'none',self.c),[1])
    def test_canopy_endpoints_and_foreground_are_separate(self):
        a=np.zeros((61,61),dtype='float32');tree=np.zeros_like(a);gt=(300000,10,0,4400000,0,-10)
        def ray(height=.8):return m.canopy_ray(a,tree,gt,(30,10),(30,50),1.7,height,0,15)
        tree[:,30]=.8;self.assertTrue(ray()['blocked']);self.assertFalse(ray()['foreground'])
        self.assertFalse(ray(40)['blocked'])
        tree[:]=0;tree[:,11]=.8;self.assertTrue(ray()['foreground']);self.assertFalse(ray()['blocked'])
        tree[:]=0;tree[:,50]=.8;self.assertFalse(ray()['blocked']) # endpoint never moved to treetops
        tree[:,30]=np.nan;self.assertTrue(ray()['unknown'])
    def test_switches_collapse_to_raw(self):
        z=np.zeros(4);o=np.ones(4)
        comp=dict(total=.0004,d=o*100,dx=o*100,dy=z,dz=z,gx=z,gy=z,tree=z,shrub=z,herb=z,
                  summer=z,winter=z,search=o,perspective=o,uncertain=np.zeros(4,bool),actionable=np.zeros(4,bool),
                  foreground_cover_mean=0,foreground_unknown_fraction=0,stress={})
        c=dict(self.c,arm='glass',features={k:False for k in self.c['features']})
        self.assertAlmostEqual(score(comp,c,10)['score'],.0004)
        # Removing target eligibility reduces planimetric cell area, never erases terrain.
        comp={k:(v[:2] if isinstance(v,np.ndarray) else v) for k,v in comp.items()}
        self.assertAlmostEqual(score(comp,c,10)['score'],.0002)
    def test_access_and_expert_provenance(self):
        pref=dict(self.c['preferences'],require_verified_access=True)
        self.assertEqual(m.eligible_points([{'id':'A'}],pref,{}),[])
        self.assertEqual(m.eligible_points([{'id':'A'}],self.c['preferences'],{'A':{'reachable':'denied'}}),[])
        self.assertEqual(len(m.eligible_points([{'id':'A'}],pref,{'A':{'reachable':'verified','evidence':'reviewed route'}})),1)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'experts.csv';p.write_text('id,longitude,latitude\nE,-107,38\n')
            with self.assertRaisesRegex(ValueError,'expert_id'):m.import_experts(p,(300000,10,0,4400000,0,-10),np.ones((2,2),bool),32613)
    def test_random_is_score_blind_and_reproducible(self):
        points=[{'id':str(i),'x':i%2,'y':i//2} for i in range(4)]
        scores={k:{str(i):float(i) for i in range(4)} for k in ['M1_raw','M2_habitat','M3_glass']}
        a=random_baseline(self.c,points,scores)
        for v in scores.values():
            for k in v:v[k]=-v[k]
        b=random_baseline(self.c,points,scores)
        self.assertEqual(a['replicates'],b['replicates'])

if __name__=='__main__':unittest.main()
