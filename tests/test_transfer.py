import json,tempfile,unittest,copy
from pathlib import Path
from shapely.geometry import box,mapping,Point
from shapely.ops import transform
from glassing.transfer import manual,polygon,project,read,intake,candidates,work
from glassing.acquire import dump

class TransferChecks(unittest.TestCase):
    def test_unsnapped_import_all_formats_and_rejects(self):
        area=box(450000,4200000,451000,4201000);lo,la=project(32612,4326)(450103.25,4200202.75)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'p.csv').write_text(f'id,longitude,latitude,note\nmy point,{lo},{la},original rationale\n');(p/'p.gpx').write_text(f'<gpx xmlns="http://www.topografix.com/GPX/1/1"><wpt lon="{lo}" lat="{la}"><name>my point</name></wpt></gpx>');dump(p/'p.geojson',dict(type='FeatureCollection',features=[dict(type='Feature',properties={'id':'my point'},geometry=mapping(Point(lo,la)))]))
            for ext in ['csv','gpx','geojson']:
                rows=manual(p/('p.'+ext),32612,area,{'selector':'fixture'})
                self.assertEqual(rows[0]['longitude'],lo);self.assertEqual(rows[0]['latitude'],la);self.assertAlmostEqual(rows[0]['x'],450103.25,places=5);self.assertEqual(rows[0]['original_id'],'my point')
            with self.assertRaises(ValueError):manual(p/'p.csv',32612,box(0,0,100,100),{})
            (p/'p.csv').write_text('id,longitude,latitude\nx,4200000,450000\n')
            with self.assertRaises(ValueError):manual(p/'p.csv',32612,area,{})
    def test_domain_separation_no_silent_crop(self):
        c=read('configs/transfer.fixture.json')
        with tempfile.TemporaryDirectory() as d:
            c['work']=d;r=intake(c);g={k:__import__('shapely.geometry',fromlist=['shape']).shape(v) for k,v in r['geometry'].items()}
            self.assertGreater(g['target'].area,g['observer'].area);self.assertTrue(g['terrain_halo'].covers(g['target']));self.assertTrue(g['access_extent'].covers(g['terrain_halo']))
            c['target_limit']='runs/transfer_fixture_inputs/target_limit.geojson';r2=intake(c);self.assertEqual(r['geometry']['terrain_halo'],r2['geometry']['terrain_halo']);self.assertLess(r2['target_area_km2'],r['target_area_km2'])
    def test_independent_automatic_pool_and_manual_export(self):
        c=read('configs/transfer.fixture.json');r=Path(c['work']);p=read(r/'pool.json');auto=[v for v in p if v['group']=='automated'];self.assertEqual(len(auto),24);self.assertFalse(any('manual' in str(v['provenance']) for v in auto))
        checks=read(r/'export_checks.json');self.assertEqual(checks['manual_count'],2);self.assertLessEqual(checks['automated_count'],5);self.assertTrue(checks['manual_coordinates_unchanged'])
        overlap=read(r/'overlap.json');self.assertEqual(len(overlap),21)
        for row in overlap:
            self.assertTrue(row['jaccard'] is None or 0<=row['jaccard']<=1)
        self.assertTrue(read(r/'refinement.json')['primary_pool_unchanged'])
    def test_preserved_output_path_rejected(self):
        c=read('configs/transfer.template.json');c['work']='runs/scouting'
        with self.assertRaises(ValueError):work(c)
    def test_manual_edits_do_not_change_automatic_candidates(self):
        import shutil
        from glassing.acquire import digest
        c=read('configs/transfer.fixture.json');old=Path(c['work'])
        with tempfile.TemporaryDirectory() as d:
            dst=Path(d)
            for name in ['dem.tif','target.tif','observer.tif','manual_import.json','prepared.json','core_config.json']:shutil.copyfile(old/name,dst/name)
            dump(dst/'transfer_owner.json',dict(component='glassing.transfer',input_kind='synthetic_fixture'))
            bc=read(dst/'core_config.json');bc['work']=str(dst);dump(dst/'core_config.json',bc);meta=read(dst/'prepared.json');meta['config']=bc;dump(dst/'prepared.json',meta);c['work']=str(dst)
            candidates(c);first=[p for p in read(dst/'pool.json') if p['group']=='automated'];manuals=read(dst/'manual_import.json');manuals[0]['x']+=1;dump(dst/'manual_import.json',manuals);candidates(c);second=[p for p in read(dst/'pool.json') if p['group']=='automated'];self.assertEqual(first,second)
    def test_known_empty_season_layer_is_not_missing_data(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'empty.geojson';dump(p,dict(type='FeatureCollection',features=[]))
            self.assertTrue(polygon(p,32612,allow_empty=True).is_empty)
            with self.assertRaises(ValueError):polygon(p,32612)
    def test_portable_access_uses_configured_entry_and_terrain(self):
        import shutil
        import numpy as np
        from glassing import core
        from glassing.acquire import digest,srs
        from glassing.transfer_access import run
        from shapely.geometry import LineString
        c=read('configs/transfer.fixture.json');old=Path(c['work'])
        with tempfile.TemporaryDirectory() as d:
            dst=Path(d);c['work']=d
            dump(dst/'transfer_owner.json',dict(component='glassing.transfer',input_kind='synthetic_fixture'))
            for name in ['target.tif','observer.tif','prepared.json','core_config.json']:shutil.copyfile(old/name,dst/name)
            bc=read(dst/'core_config.json');bc['work']=d;dump(dst/'core_config.json',bc)
            from osgeo import gdal
            src=gdal.Open(str(old/'dem.tif'));core.write_raster(dst/'dem.tif',np.full((src.RasterYSize,src.RasterXSize),2100,dtype='float32'),src.GetGeoTransform(),src.GetProjection(),-9999)
            meta=read(dst/'prepared.json');meta['config']=bc;meta['dem_sha256']=digest(dst/'dem.tif');dump(dst/'prepared.json',meta)
            dump(dst/'leading.json',[dict(id='M0001',original_id='fixture manual',group='manual',x=450300.,y=4200300.)])
            def spec(name,geom,props):
                path=dst/name;dump(path,dict(type='FeatureCollection',features=[dict(type='Feature',properties=props,geometry=mapping(transform(project(32612,4326),geom)))]));return dict(path=str(path),sha256=digest(path),provider='synthetic test')
            c['access']['entries']=spec('entries.geojson',Point(450100,4200100),dict(id='ENTRY_X',evidence='synthetic fixture, not a real entry'))
            c['access']['routes']=[spec('routes.geojson',LineString([(450100,4200100),(450250,4200250)]),dict(id='route_x',name='fixture'))]
            c['access']['offtrail_allowed']=spec('allowed.geojson',box(450000,4200000,450600,4200600),{})
            run(c);r=read(dst/'approaches.json')['fixture manual'];self.assertEqual(r['entry'],'ENTRY_X');self.assertTrue(r['dem_profile_complete']);self.assertAlmostEqual(r['roundtrip_gain_ft'],0);self.assertGreater(r['roundtrip_miles'],0)
