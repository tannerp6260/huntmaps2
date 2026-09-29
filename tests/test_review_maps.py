import unittest
import numpy as np
from osgeo import gdal
from glassing.acquire import srs
from glassing.review_maps import visible_mask

class ReviewAlignment(unittest.TestCase):
 def test_target_clipping_radius_and_registration(self):
    def raster(w,h,gt):
        d=gdal.GetDriverByName('MEM').Create('',w,h,1,gdal.GDT_Byte);d.SetGeoTransform(gt);d.SetProjection(srs(32613).ExportToWkt());d.GetRasterBand(1).Fill(1);return d
    dem=raster(10,10,(300000,10,0,4290000,0,-10));vs=raster(3,3,(300020,10,0,4289980,0,-10));target=np.ones((10,10),bool);target[3,3]=False
    p=dict(id='fixture',x=300035,y=4289965,raw_km2=.0004)
    m,check=visible_mask(vs,dem,target,p,10)
    self.assertEqual(int(m.sum()),4);self.assertFalse(m[3,3]);self.assertEqual(check['difference_km2'],0)
    vs.SetGeoTransform((300021,10,0,4289980,0,-10))
    with self.assertRaisesRegex(ValueError,'Nonintegral'):visible_mask(vs,dem,target,p,10)
