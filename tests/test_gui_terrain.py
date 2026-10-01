"""Display terrain encoding, source coverage and separate drawn-area validation."""
import io,json,math,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from PIL import Image
from osgeo import gdal,osr
from fastapi.testclient import TestClient
from huntmaps_gui.catalog import Run,STATE
from huntmaps_gui.server import create_app
from huntmaps_gui.terrain import metadata,elevation_tile

def decode(data):
    a=np.array(Image.open(io.BytesIO(data))).astype('float64');return a[:,:,0]*256+a[:,:,1]+a[:,:,2]/256-32768

class TerrainTests(unittest.TestCase):
    def test_real_dem_encoding_and_api(self):
        r=Run('soap-creek-decision-review-v2');info=metadata(r);self.assertTrue(info['available']);self.assertEqual(info['exaggeration'],1)
        p=r.candidate('A0075');z=info['maxzoom'];x=int((p['longitude']+180)/360*2**z);y=int((1-math.asinh(math.tan(math.radians(p['latitude'])))/math.pi)/2*2**z)
        values=decode(elevation_tile(r,z,x,y));self.assertGreater(float(values.max()-values.min()),50);self.assertGreater(float(values.min()),1000)
        half=20037508.342789244;size=2*half/2**z
        # Independent nearest source checks allow bilinear variation by comparing
        # interpolation against the four bracketing cells, not another warp.
        from glassing.transfer import project
        transform=project(3857,r.config['epsg']);gt=r.dem.GetGeoTransform();a=r.dem.ReadAsArray()
        for row,col in [(100,100),(120,170),(190,190)]:
            xx,yy=transform(-half+(x+(col+.5)/256)*size,half-(y+(row+.5)/256)*size);cx=(xx-gt[0])/gt[1]-.5;cy=(yy-gt[3])/gt[5]-.5;cc,rr=math.floor(cx),math.floor(cy)
            patch=a[rr:rr+2,cc:cc+2];self.assertGreaterEqual(values[row,col],float(patch.min())-.02);self.assertLessEqual(values[row,col],float(patch.max())+.02)
        with TestClient(create_app()) as client:
            self.assertTrue(client.get('/api/runs/'+r.id+'/terrain').json()['available'])
            self.assertEqual(client.get(f'/api/runs/{r.id}/terrain/{z}/{x}/{y}.png').content,elevation_tile(r,z,x,y))
            self.assertEqual(client.get('/api/runs/'+r.id+'/terrain/24/0/0.png').status_code,400)

    def test_plane_seams_edge_padding_and_nodata_rejection(self):
        folder=Path(tempfile.mkdtemp(prefix='huntmaps-terrain-'));path=folder/'plane.tif';z,x,y=14,7000,6000;half=20037508.342789244;size=2*half/2**z;cell=size/256
        ds=gdal.GetDriverByName('GTiff').Create(str(path),512,256,1,gdal.GDT_Float32);gt=(-half+x*size,cell,0,half-y*size,0,-cell);ds.SetGeoTransform(gt);s=osr.SpatialReference();s.ImportFromEPSG(3857);ds.SetProjection(s.ExportToWkt())
        yy,xx=np.indices((256,512));plane=1000+xx*.5+yy*.25;ds.GetRasterBand(1).WriteArray(plane);ds.GetRasterBand(1).SetNoDataValue(-9999);ds.FlushCache();ds=None;ds=gdal.Open(str(path))
        r=SimpleNamespace(dem=ds,dem_path=path);a=decode(elevation_tile(r,z,x,y));b=decode(elevation_tile(r,z,x+1,y));np.testing.assert_allclose(a,plane[:,:256],atol=.005);np.testing.assert_allclose(b,plane[:,256:],atol=.005);np.testing.assert_allclose(b[:,0]-a[:,-1],.5,atol=.005)
        coarse=decode(elevation_tile(r,z-1,x//2,y//2));self.assertTrue(np.isfinite(coarse).all());self.assertGreaterEqual(coarse.min(),1000);self.assertLessEqual(coarse.max(),plane.max())
        plane[100,100]=-9999;ds=None;ds=gdal.Open(str(path),gdal.GA_Update);ds.GetRasterBand(1).WriteArray(plane);ds.FlushCache();ds=None;r.dem=gdal.Open(str(path));self.assertFalse(metadata(r)['available'])
        with self.assertRaisesRegex(ValueError,'complete'):elevation_tile(r,z,x,y)

    def test_drawn_practice_geometry_is_separate_and_preserved(self):
        feature=dict(type='Feature',properties={'name':'Practice boundary'},geometry=dict(type='Polygon',coordinates=[[[-107.31,38.68],[-107.30,38.68],[-107.30,38.69],[-107.31,38.68]]]))
        data=json.dumps(feature).encode();headers={'X-HuntMaps':'local'}
        with TestClient(create_app()) as client:
            response=client.post('/api/imports?practice=true',files={'file':('drawing.geojson',data,'application/geo+json')},headers=headers);self.assertEqual(response.status_code,200);item=response.json();self.assertIn('practice-areas',item['path']);self.assertEqual(Path(item['path']).read_bytes(),data);self.assertEqual(item['choices'][0]['geometry'],feature['geometry']);self.assertFalse((STATE/'imports'/item['id']).exists())
            denied=client.post('/api/plans',json={'name':'practice-must-not-run','import_id':item['id'],'polygon':'1'},headers=headers);self.assertEqual(denied.status_code,400)
            feature['geometry']['coordinates']=[[[-107.31,38.68],[-107.30,38.69],[-107.31,38.69],[-107.30,38.68],[-107.31,38.68]]]
            response=client.post('/api/imports?practice=true',files={'file':('invalid.geojson',json.dumps(feature).encode(),'application/geo+json')},headers=headers);self.assertEqual(response.status_code,400);self.assertIn('Invalid polygon',response.json()['detail'])
