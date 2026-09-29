"""Regressions from the actual Soap Creek acquisition responses."""
import json,tempfile,unittest
from pathlib import Path
import numpy as np
from osgeo import gdal
from glassing import core
from glassing.acquire import srs,digest,dump
from glassing.owner_data import coverage,covers,normalize_range

class CoverageChecks(unittest.TestCase):
 def test_nodata101_is_unknown_cover_not_missing_geography(self):
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp)/'tree.tif';a=np.full((40,40),25,dtype='float32');a[17:23,17:23]=101
        core.write_raster(p,a,(300000,30,0,4290000,0,-30),srs(32613).ExportToWkt(),101)
        bounds=[300030,4288830,301170,4289970]
        d=coverage(p,bounds,32613,10,True)
        self.assertTrue(d['geographic_coverage']);self.assertEqual(d['unknown_cells'],324)
        self.assertTrue(covers(p,bounds,32613,vegetation=True))
        self.assertFalse(covers(p,bounds,32613)) # obstruction DEM still fails gaps
        self.assertFalse(covers(p,[299990,4288830,301170,4289970],32613,True))
        # Exact same normalization used by transfer.prepare: unknown is -9999, not open.
        w=gdal.Warp('',str(p),format='MEM',dstSRS='EPSG:32613',outputBounds=bounds,xRes=10,yRes=10,resampleAlg='near',outputType=gdal.GDT_Float32,dstNodata=-9999)
        v=w.ReadAsArray();valid=np.isfinite(v)&(v>=0)&(v<=100)
        normalized=np.where(valid,v/100.,-9999)
        self.assertEqual(int((~valid).sum()),324)
        self.assertTrue((normalized[~valid]==-9999).all());self.assertFalse((normalized==0).any())

 def test_agency_crs_and_nested_shell_repair_preserve_raw(self):
    from shapely.geometry import box,MultiPolygon,mapping,shape
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);p=root/'raw.geojson'
        geom=MultiPolygon([box(-108,38,-107,39),box(-107.8,38.2,-107.6,38.4)])
        dump(p,dict(type='FeatureCollection',crs={'type':'name','properties':{'name':'EPSG:4326'}},features=[dict(type='Feature',properties={},geometry=mapping(geom))]))
        h=digest(p);spec=normalize_range(dict(path=str(p),sha256=h),root,'summer');out=json.loads(Path(spec['path']).read_text())
        self.assertEqual(digest(p),h);self.assertNotIn('crs',out);self.assertTrue(shape(out['features'][0]['geometry']).is_valid)
        self.assertEqual(len(spec['geometry_repairs']),1);self.assertEqual(spec['raw_source']['sha256'],h)
        raw=json.loads(p.read_text());raw['crs']['properties']['name']='EPSG:3857';dump(p,raw)
        with self.assertRaisesRegex(ValueError,'Unrecognized range CRS'):normalize_range(dict(path=str(p),sha256=digest(p)),root,'winter')
