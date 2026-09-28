import json,math,tempfile,unittest
from pathlib import Path
import numpy as np
from shapely.geometry import LineString,Point
from glassing.scout_access import build_network,insert_supported_vertices,shortest,terrain_connector,season_covers


def record(coords,name='SAME',rid='726'):
    return dict(geometry=LineString(coords),name=name,route_id=rid,motor=True)

class ScoutingChecks(unittest.TestCase):
    def test_crossing_is_not_a_junction(self):
        rs=[record([(0,0),(20,0)]),record([(10,-10),(10,10)],'OTHER','1')]
        v,adj,logs,n=build_network(insert_supported_vertices(rs));d,_=shortest(adj,0,rs)
        self.assertEqual(len(d),2);self.assertEqual(logs,[])
    def test_supported_endpoint_to_segment_and_tolerance(self):
        rs=[record([(0,0),(20,0)]),record([(10,3),(10,10)])]
        v,adj,logs,n=build_network(insert_supported_vertices(rs));d,_=shortest(adj,0,rs)
        self.assertEqual(len(d),len(v));self.assertTrue(logs);self.assertTrue(all(l['gap_m']<=5 for l in logs))
        rs=[record([(0,0),(20,0)]),record([(10,5.1),(10,10)])]
        v,adj,logs,n=build_network(insert_supported_vertices(rs));d,_=shortest(adj,0,rs);self.assertLess(len(d),len(v))
    def test_barrier_and_diagonal_corner(self):
        a=np.full((5,5),1000.);ok=np.ones_like(a,dtype=bool);gt=(0,20,0,100,0,-20)
        self.assertIsNotNone(terrain_connector(a,ok,gt,(10,90),(90,10)))
        ok[:,2]=False;self.assertIsNone(terrain_connector(a,ok,gt,(10,90),(90,10)))
        ok=np.eye(5,dtype=bool);self.assertIsNone(terrain_connector(a,ok,gt,(10,90),(90,10)))
    def test_motor_season_and_invalid_source_dates(self):
        hunt=['2026-10-24','2026-11-01'];self.assertTrue(season_covers('07/01-12/31',hunt));self.assertFalse(season_covers('07/01-10/31',hunt));self.assertFalse(season_covers('02/30-12/31',hunt));self.assertFalse(season_covers(None,hunt))
    def test_real_packet_support_and_exports_if_present(self):
        root=Path('runs/scouting')
        if not (root/'export_checks.json').exists():self.skipTest('Run scouting packet for integration evidence')
        from osgeo import gdal,ogr
        from glassing.acquire import srs
        data=json.loads((root/'support.json').read_text())
        baseline={r['id']:r for r in json.loads(Path('runs/gmu54/scores.json').read_text())}
        for i,cases in data.items():
            self.assertAlmostEqual(cases['frozen_pilot']['summary']['raw_visible_km2'],baseline[i]['visible_km2'])
            self.assertEqual(cases['restored_FS']['summary']['terrain_missing_km2'],0)
            p=cases['pilot_FS']['summary'];r=cases['restored_FS']['summary'];self.assertGreaterEqual(r['raw_visible_km2'],p['raw_visible_km2']);self.assertGreaterEqual(r['selective_score']+1e-12,p['selective_score']);self.assertLessEqual(r['target_support_km2'],math.pi*4+.001)
            if (root/(i+'_restored_visible.tif')).exists():
                ds=gdal.Open(str(root/(i+'_restored_visible.tif')));self.assertAlmostEqual(float(ds.ReadAsArray().sum())*abs(ds.GetGeoTransform()[1]*ds.GetGeoTransform()[5])/1e6,r['raw_visible_km2'],places=6)
        checks=json.loads((root/'export_checks.json').read_text());self.assertEqual(checks['opportunities.gpx'],3);self.assertGreater(checks['kml_valid_polygons'],0);self.assertTrue(checks['gpkg_coordinate_readback'])
        ds=ogr.Open(str(root/'scouting.gpkg'))
        layer=ds.GetLayerByName('provisional_FS_targets');f=layer.GetNextFeature();targets=f.GetGeometryRef().Clone()
        for f in ds.GetLayerByName('candidate_review'):
            if f.GetField('id') in ['C0068','C0095','C0049']:self.assertTrue(targets.Intersects(f.GetGeometryRef()))
        for r in json.loads((root/'approach_rows.json').read_text()):
            if 'offtrail_km' in r:
                self.assertEqual(r['offtrail_private_crossing_m'],0);self.assertEqual(r['offtrail_waterbody_intersection_m'],0);self.assertLessEqual(r['offtrail_max_slope_deg'],30)
