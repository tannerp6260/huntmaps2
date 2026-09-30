import unittest
import numpy as np
from glassing.vegetation_rays import ray
class VegetationRays(unittest.TestCase):
 def test_partitioned_ground_endpoint_geometry(self):
    z=np.zeros((5,25));h=z.copy();o=(2,3);t=(2,23)
    def check():return ray(z,h,10,o,t,eye=2,deer=2,curvature=0)
    self.assertFalse(any(check()[k] for k in ['observer','intermediate','target','unknown','terrain']))
    h[2,1]=30;self.assertFalse(check()['observer']) # behind observer
    h[2,5]=3;self.assertTrue(check()['observer']);self.assertFalse(check()['intermediate']);h[2,5]=0
    h[2,12]=1;self.assertFalse(check()['intermediate']);h[2,12]=3;self.assertTrue(check()['intermediate']);h[2,12]=0
    h[2,23]=4;self.assertTrue(check()['target']);self.assertEqual(check()['ground_target'],2);h[2,23]=0
    h[2,12]=np.nan;self.assertTrue(check()['unknown']);self.assertFalse(check()['intermediate'])
 def test_raised_ground_and_endpoint_cells(self):
    z=np.full((3,12),100.);h=np.zeros_like(z);h[1,1]=20
    r=ray(z,h,10,(1,1),(1,10),eye=1.7,deer=.8,curvature=0)
    self.assertEqual(r['ground_start'],101.7);self.assertEqual(r['ground_target'],100.8);self.assertFalse(r['observer']);self.assertEqual(r['observer_cell_height'],20)

 def test_directional_cover_excludes_opposite_sectors(self):
    from glassing.vegetation_experiment import directional
    a=np.zeros((41,41));a[15:26,10:19]=.8
    p=dict(row=20,col=20,x=205,y=205)
    d=directional(p,a,(0,10,0,410,0,-10),[[10,60]])
    east=next(v for v in d if v['start']==90);west=next(v for v in d if v['start']==270)
    self.assertEqual(east['mean_tree'],0);self.assertGreater(west['mean_tree'],0)

 def test_unknown_search_bounds_and_area_partition(self):
    from glassing.vegetation_experiment import summarize,read
    a=np.full((20,20),.05);shrub=a.copy();a[5,5]=np.nan
    p=dict(id='fixture',row=10,col=10,x=105,y=95)
    c=read('configs/transfer.template.json');c['radius_m']=500
    lock=read('configs/transfer_model.lock.json');indices=np.arange(400)
    row,_=summarize(p,indices,a,shrub,(0,10,0,200,0,-10),a.shape,c,lock,[[10,60],[60,120]],[.2,.4])
    self.assertAlmostEqual(row['raw_km2'],.04);self.assertAlmostEqual(row['cover_unknown_km2'],.0001)
    self.assertLessEqual(row['unknown_low'],row['target_heuristic']);self.assertLessEqual(row['target_heuristic'],row['unknown_high'])
