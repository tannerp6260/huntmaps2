import tempfile
from pathlib import Path
import unittest
import numpy as np
from osgeo import gdal
from glassing.core import write_raster,validate,viewshed,score_mask,profile_clearance
from glassing.acquire import srs


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def dem(self,a,res=10,epsg=32613):
        return write_raster(self.root/'dem.tif',a.astype('float32'),(300000,res,0,4400000,0,-res),srs(epsg).ExportToWkt(),-9999)
    def run_view(self,a,eye=1.7,target=.8,res=10):
        ds=self.dem(a,res);gt=ds.GetGeoTransform()
        r=len(a)//2;col=r-20
        x=gt[0]+(col+.5)*res;y=gt[3]+(r+.5)*gt[5]
        v=viewshed(ds,self.root/'v.tif',x,y,250,eye,target,0)
        return ds,v,r,col,x,y
    def cell(self,v,ds,r,col):
        gt=ds.GetGeoTransform();vg=v.GetGeoTransform()
        return v.ReadAsArray()[r-int(round((vg[3]-gt[3])/gt[5])),col-int(round((vg[0]-gt[0])/gt[1]))]
    def test_flat_and_area_resolution(self):
        areas=[]
        for res in [10,20]:
            n=201 if res==10 else 101
            ds=self.dem(np.zeros((n,n)),res);gt=ds.GetGeoTransform()
            x=gt[0]+(n//2+.5)*res;y=gt[3]-(n//2+.5)*res
            v=viewshed(ds,self.root/'flat.tif',x,y,500,1.7,.8,0)
            total,bands,mask=score_mask(v,gt,(n,n),np.ones((n,n),bool),x,y,500)
            self.assertAlmostEqual(total,np.pi*.5**2,delta=.015)
            self.assertAlmostEqual(total,sum(bands))
            areas.append(total)
        self.assertLess(abs(areas[0]-areas[1])/areas[0],.02)
    def test_ridge_heights_and_independent_ray(self):
        a=np.zeros((121,121));a[:,50:53]=10
        ds,v,r,col,x,y=self.run_view(a)
        self.assertEqual(self.cell(v,ds,r,64),0)
        self.assertEqual(self.cell(v,ds,r,45),1)
        p={'row':r,'col':col}
        self.assertLess(profile_clearance(a,ds.GetGeoTransform(),p,r,64,1.7,.8,0),0)
        self.assertGreater(profile_clearance(a,ds.GetGeoTransform(),p,r,45,1.7,.8,0),0)
        ds,v,*_=self.run_view(a,eye=40);self.assertEqual(self.cell(v,ds,r,64),1)
        ds,v,*_=self.run_view(a,target=40);self.assertEqual(self.cell(v,ds,r,64),1)
    def test_excluded_targets_keep_obstruction(self):
        a=np.zeros((121,121));a[:,50:53]=10
        ds,v,r,col,x,y=self.run_view(a)
        mask=np.ones(a.shape,bool);mask[:,50:53]=False
        before=ds.ReadAsArray().copy()
        total,_,_=score_mask(v,ds.GetGeoTransform(),a.shape,mask,x,y,250)
        self.assertTrue(np.array_equal(before,ds.ReadAsArray()))
        self.assertEqual(self.cell(v,ds,r,64),0)
        self.assertGreater(total,0)
    def test_explicit_curvature_changes_zero_height_flat_visibility(self):
        ds=self.dem(np.zeros((201,201)));gt=ds.GetGeoTransform()
        x=gt[0]+1005;y=gt[3]-1005
        flat=viewshed(ds,self.root/'flat.tif',x,y,500,0,0,0).ReadAsArray()
        curved=viewshed(ds,self.root/'curved.tif',x,y,500,0,0,1).ReadAsArray()
        self.assertGreater(np.count_nonzero(flat==1),np.count_nonzero(curved==1))

    def test_nodata_and_coordinate_units_fail(self):
        a=np.zeros((121,121));a[60,60]=-9999
        with self.assertRaisesRegex(ValueError,'NoData'):validate(self.dem(a))
        a[60,60]=np.nan
        with self.assertRaisesRegex(ValueError,'NoData'):validate(self.dem(a))
        with self.assertRaisesRegex(ValueError,'projected metric'):validate(self.dem(np.zeros((121,121)),epsg=4326))
        with self.assertRaisesRegex(ValueError,'projected metric'):validate(self.dem(np.zeros((121,121)),epsg=2232))
        ds=self.dem(np.zeros((121,121)))
        with self.assertRaisesRegex(ValueError,'Vertical units'):validate(ds,'feet')
        with self.assertRaisesRegex(ValueError,'outside terrain'):viewshed(ds,self.root/'bad.tif',-107,38,100,1,0,0)
        with self.assertRaisesRegex(ValueError,'halo'):viewshed(ds,self.root/'bad.tif',300005,4399995,100,1,0,0)

if __name__=='__main__':unittest.main()
