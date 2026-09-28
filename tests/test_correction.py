import itertools,math,unittest
import numpy as np
from shapely.geometry import LineString
from glassing.attention import select,patches,paradox
from glassing.correction_access import graph,witness

class CorrectionTests(unittest.TestCase):
    def test_uniform_paradox_and_optional_patch_monotonicity(self):
        p=paradox();self.assertLess(p['uniform_after'],p['uniform_before']);self.assertEqual(p['selective_before'],p['selective_after'])
        base=[dict(id=i,full_area_km2=.02*(i+1),reward=r) for i,r in enumerate([.1,.6,.2,.9])]
        for budget in [1,3,6,10]:
            before=select(base,budget)['score']
            self.assertGreaterEqual(select(base+[dict(id=5,full_area_km2=.04,reward=.01)],budget)['score'],before)
            raised=[dict(p,reward=p['reward']+.02) for p in base]
            self.assertGreaterEqual(select(raised,budget)['score'],before)
    def test_exact_attention_against_exhaustive_subsets(self):
        pats=[dict(id=i,full_area_km2=a,reward=v) for i,(a,v) in enumerate([(.011,.3),(.022,.8),(.035,.9),(.01,.1)])]
        for budget in [0,.75,1,2.5,4,10]:
            feasible=[]
            for flags in itertools.product([0,1],repeat=4):
                cost=sum(math.ceil((p['full_area_km2']/.02+.5)/.25-1e-9)*.25*f for p,f in zip(pats,flags))
                if cost<=budget:feasible.append(sum(p['reward']*f for p,f in zip(pats,flags)))
            r=select(pats,budget);self.assertAlmostEqual(r['score'],max(feasible));self.assertLessEqual(r['minutes_used'],budget)
            self.assertAlmostEqual(r['score'],sum(p['reward'] for p in pats if p['id'] in r['patch_ids']))
    def test_patch_geometry_area_and_fixed_costs(self):
        ps=patches(np.array([0,1,0]),np.array([10,10,510]),np.array([1,.2,.4]),.0001)
        self.assertEqual(len(ps),48);self.assertAlmostEqual(sum(p['full_area_km2'] for p in ps),math.pi*4)
        self.assertAlmostEqual(ps[0]['reward'],.00012);self.assertAlmostEqual(ps[12]['reward'],.00004)
        larger=patches(np.array([0,1,0,2]),np.array([10,10,510,10]),np.array([1,.2,.4,.1]),.0001)
        self.assertEqual([p['full_area_km2'] for p in ps],[p['full_area_km2'] for p in larger])
        self.assertGreaterEqual(select(larger,30)['score'],select(ps,30)['score'])
    def test_access_gap_is_not_connected(self):
        edges,adj,key=graph([LineString([(0,0),(1,0)]),LineString([(1.1,0),(2,0)])])
        self.assertIsNone(witness(adj,key((0,0)),key((2,0))))
        edges,adj,key=graph([LineString([(0,0),(1,0)]),LineString([(1,0),(2,0)])])
        self.assertEqual(len(witness(adj,key((0,0)),key((2,0)))),2)
