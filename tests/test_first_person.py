import io
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from huntmaps_gui import first_person as fp
from huntmaps_gui.config import AppConfig, configured
from huntmaps_gui import first_person_worker as worker

class GroundDiagnostics(unittest.TestCase):
    def grid(self,fn=lambda x,y:0):
        r,c=np.indices((41,41));x=c-20;y=20-r
        return np.broadcast_to(fn(x,y),x.shape).astype(float)
    def test_flat_heights_and_curvature(self):
        a=self.grid()
        p=fp.profile_grid(a,1,-20,20,15,0,1.7,.8)
        self.assertEqual(p['result'],'no obstruction found in this ground model')
        self.assertAlmostEqual(p['points'][0]['line_m'],1.7)
        self.assertAlmostEqual(p['points'][-1]['line_m'],.8-fp.CURVATURE*15**2/(2*fp.EARTH))
        self.assertFalse(p['borderline'])
    def test_rise_and_height_changes(self):
        a=self.grid(lambda x,y:np.where((x>=5)&(x<=7),1.6,0))
        p=fp.profile_grid(a,1,-20,20,15,0,1.7,.8)
        self.assertEqual(p['result'],'modeled ground obstruction')
        self.assertLessEqual(p['first_obstruction']['east_m'],5)
        high=fp.profile_grid(a,1,-20,20,15,0,2.2,2.5)
        self.assertEqual(high['result'],'no obstruction found in this ground model')
    def test_valley_and_hidden_target(self):
        a=self.grid(lambda x,y:np.where((x>=4)&(x<=9),-3,0))
        p=fp.profile_grid(a,1,-20,20,15,0,1.7,.8)
        self.assertEqual(p['result'],'no obstruction found in this ground model')
        a[:,29]=4
        self.assertEqual(fp.profile_grid(a,1,-20,20,15,0,1.7,.8)['result'],'modeled ground obstruction')
    def test_triangle_interpolation_matches_mesh(self):
        a=np.array([[1.,3.],[5.,8.]])
        positions,indices=fp.mesh(a,1,0,1,0,2)
        for x,y in [(.8,.7),(.2,.2),(.4,.6)]:
            z=float(fp.sample(a,1,0,1,np.array([x]),np.array([y]))[0])
            # Independent barycentric solve against rendered triangles.
            for tri in positions[indices]:
                M=np.vstack([tri[:,0],-tri[:,2],np.ones(3)])
                weights=np.linalg.solve(M,np.array([x,y,1]))
                if np.all(weights>=-1e-6):
                    expected=float(weights@tri[:,1])+fp.CURVATURE*(x*x+y*y)/(2*fp.EARTH)
                    self.assertAlmostEqual(z,expected,places=5)
                    break
            else:self.fail('Target not represented by mesh')
    def test_missing_ground_not_bridged(self):
        a=self.grid();a[:,25:28]=np.nan
        p=fp.profile_grid(a,1,-20,20,15,0,1.7,.8)
        self.assertEqual(p['result'],'incomplete data')
        _,faces=fp.mesh(a,1,-20,20,0,30)
        used=set(faces.ravel().tolist())
        self.assertTrue(all((r*41+c) not in used for r in range(41) for c in range(25,28)))
    def test_point_support_no_extrapolation(self):
        r,c=np.indices((15,15));points=np.column_stack([c.ravel()-7,r.ravel()-7,(c*.2+r*.1).ravel(),np.full(225,2)])
        a,s=worker.fine_grid(points)
        self.assertTrue(np.isfinite(a[300,300]))
        self.assertTrue(np.isnan(a[300,320]))
        sparse=np.array([[-10,-10,1,2],[10,-10,1,2],[0,10,1,2]],float)
        a,s=worker.fine_grid(sparse)
        self.assertTrue(np.isnan(a[300,300]))
    def test_off_center_grid_and_rejected_inputs(self):
        a=self.grid(lambda x,y:x*.1+y*.2)
        z=fp.sample(a,1,-20.37,19.63,np.array([0.]),np.array([0.]))[0]
        self.assertAlmostEqual(z,.111,places=7)
        for body in [dict(east_m=math.nan,north_m=0),dict(east_m=10,north_m=0,eye_m=5),dict(east_m=2100,north_m=0)]:
            with patch.object(fp,'candidate',return_value={}):
                with self.assertRaises(ValueError):fp.profile(fp.RUN,'A0075',body)
    def test_cache_integrity_and_plan_ids(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a';p.write_bytes(b'original')
            h=__import__('hashlib').sha256(p.read_bytes()).hexdigest()
            fp.verify_file(p,h);p.write_bytes(b'changed')
            with self.assertRaises(ValueError):fp.verify_file(p,h)
        with self.assertRaises(ValueError):fp.plan('../unsafe')
        with self.assertRaises(ValueError):fp.candidate('another-run','A0075')
    def test_tiled_surface_continuity(self):
        r,c=np.indices((91,91));x=c.ravel()-45;y=r.ravel()-45
        points=np.column_stack([x,y,x*.13+y*.07,np.full(len(x),2)])
        heights,support=worker.fine_grid(points)
        rows,cols=np.mgrid[270:331,270:331]
        expected=(cols-300)*.13+(300-rows)*.07
        np.testing.assert_allclose(heights[270:331,270:331],expected,atol=1e-5)
    def test_parallel_ranges_exact_assembly_and_accounting(self):
        import re
        from unittest.mock import MagicMock
        data=b'12345678'*(1024*1024+1)
        with tempfile.TemporaryDirectory() as d,configured(AppConfig(state_dir=Path(d))):
            folder=Path(d)/'first-person/sources';folder.mkdir(parents=True)
            part=folder/'source.partial';part.write_bytes(data[:100])
            src=dict(key='source.laz',bytes=len(data),url='https://rockyweb.usgs.gov/a.laz',cached=False,title='test')
            def open_range(req,timeout):
                lo,hi=map(int,re.search(r'bytes=(\d+)-(\d+)',req.get_header('Range')).groups())
                stream=io.BytesIO(data[lo:hi+1]);stream.url=src['url'];stream.status=206
                stream.headers={'Content-Range':f'bytes {lo}-{hi}/{len(data)}'}
                return stream
            with patch('urllib.request.urlopen',side_effect=open_range):
                worker.parallel_ranges(src,part,100)
            self.assertEqual(part.read_bytes(),data)
            self.assertEqual(worker.read(folder/'ledger.json')['received_bytes'],len(data)-100)
            self.assertEqual(list(folder.glob('*.range-*')),[])
    def test_job_stages_failure_cancel_restart_and_single_job(self):
        import sys,time,json
        from huntmaps_gui.jobs import Jobs,write
        with tempfile.TemporaryDirectory() as d:
            state=Path(d);jobs=Jobs(state)
            j=jobs.start([sys.executable,'-u','-c','import time;print("STAGE synthetic first-person preparation",flush=True);time.sleep(30)'],'first-person-prepare')
            deadline=time.monotonic()+3
            while 'synthetic' not in jobs.list()[0]['stage'] and time.monotonic()<deadline:time.sleep(.02)
            self.assertIn('synthetic',jobs.list()[0]['stage'])
            with self.assertRaisesRegex(ValueError,'Another job'):jobs.start([sys.executable,'-c','pass'],'first-person-prepare')
            jobs.cancel(j['id'])
            while jobs.list()[0]['status']=='cancelling' and time.monotonic()<deadline:time.sleep(.02)
            self.assertEqual(jobs.list()[0]['status'],'cancelled')
            fail=jobs.start([sys.executable,'-u','-c','print("GUI JOB: synthetic source missing",flush=True);raise SystemExit(2)'],'first-person-prepare')
            deadline=time.monotonic()+3
            while next(v for v in jobs.list() if v['id']==fail['id'])['status']=='running' and time.monotonic()<deadline:time.sleep(.02)
            record=next(v for v in jobs.list() if v['id']==fail['id'])
            self.assertEqual(record['status'],'failed');self.assertIn('synthetic source missing',record['error'])
            write(state/'jobs'/'interrupted.json',dict(id='interrupted',status='running',started=time.time(),kind='first-person-prepare'))
            restarted=Jobs(state)
            self.assertEqual(next(v for v in restarted.list() if v['id']=='interrupted')['status'],'interrupted')
            jobs.shutdown();restarted.shutdown()
    def test_download_budget_and_cached_only(self):
        with tempfile.TemporaryDirectory() as d,configured(AppConfig(state_dir=Path(d))):
            src=dict(key='a.laz',bytes=20,url='https://rockyweb.usgs.gov/a.laz',cached=False,title='test')
            self.assertEqual(worker.acquire(src,False),(None,None))
            folder=Path(d)/'first-person/sources';folder.mkdir(parents=True,exist_ok=True);worker.write(folder/'ledger.json',dict(received_bytes=fp.LIMIT-1))
            stream=io.BytesIO(b'abc');stream.url=src['url'];stream.status=200;stream.headers={}
            with patch('urllib.request.urlopen',return_value=stream):
                with self.assertRaisesRegex(ValueError,'transfer allowance'):worker.acquire(src,True)
            self.assertEqual(worker.read(folder/'ledger.json')['received_bytes'],fp.LIMIT-1)
    def test_resume_requires_range_identity(self):
        with tempfile.TemporaryDirectory() as d,configured(AppConfig(state_dir=Path(d))):
            folder=Path(d)/'first-person/sources';folder.mkdir(parents=True);(folder/'a.partial').write_bytes(b'abc')
            src=dict(key='a.laz',bytes=20,url='https://rockyweb.usgs.gov/a.laz',cached=False,title='test')
            stream=io.BytesIO(b'def');stream.url=src['url'];stream.status=200;stream.headers={}
            with patch('urllib.request.urlopen',return_value=stream):
                with self.assertRaisesRegex(ValueError,'safely resume'):worker.acquire(src,True)
            self.assertEqual((folder/'a.partial').read_bytes(),b'abc')



class PreparationMemory(unittest.TestCase):
    def test_spooled_crop_preserves_order_filters_and_cleanup(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        original_file = tempfile.TemporaryFile
        files = []

        def temporary_file():
            f = original_file()
            files.append(f)
            return f

        vertical = SimpleNamespace(to_wkt=lambda: "NAVD88")
        crs = SimpleNamespace(
            axis_info=[SimpleNamespace(direction="up", unit_conversion_factor=1)],
            is_compound=True,
            sub_crs_list=[vertical],
        )
        chunk = SimpleNamespace(
            x=np.array([10.1, 11.2, 12.3, 13.4, 500.0, 14.5]),
            y=np.full(6, 20.2),
            z=np.array([100.0, 101.0, 102.0, np.nan, 104.0, 105.0]),
            classification=np.array([2, 4, 7, 1, 1, 1]),
            withheld=np.array([False, False, False, False, False, True]),
        )
        reader = MagicMock()
        reader.__enter__.return_value = reader
        reader.header.parse_crs.return_value = crs
        reader.chunk_iterator.side_effect = lambda size: iter([chunk, chunk])
        laspy = SimpleNamespace(
            open=lambda *a, **kw: reader, LazBackend=SimpleNamespace(Lazrs=1)
        )
        transformer = SimpleNamespace(transform=lambda x, y: (x, y))
        pyproj = SimpleNamespace(
            Transformer=SimpleNamespace(from_crs=lambda *a, **kw: transformer)
        )
        run = SimpleNamespace(
            points={"X": {"x": 10.0, "y": 20.0}}, config={"epsg": 32613}
        )
        sources = [
            ({"candidates": ["X"]}, Path("a.laz"), "a"),
            ({"candidates": ["other"]}, Path("ignored.laz"), "b"),
        ]
        expected = np.tile(
            np.column_stack(
                [
                    chunk.x[:2] - 10.0,
                    chunk.y[:2] - 20.0,
                    chunk.z[:2],
                    chunk.classification[:2],
                ]
            ),
            (2, 1),
        )
        with patch.object(worker, "deps", return_value=(laspy, pyproj)), patch.object(
            worker.tempfile, "TemporaryFile", side_effect=temporary_file
        ):
            points, vref, hist = worker.crop_points(run, "X", sources)
            np.testing.assert_array_equal(points, expected)
            self.assertEqual(points.dtype, np.float64)
            self.assertEqual((vref, hist), ("NAVD88", {"2": 2, "4": 2}))
            self.assertTrue(files[-1].closed)
            reader.chunk_iterator.side_effect = MemoryError("decoder allocation")
            with self.assertRaises(MemoryError):
                worker.crop_points(run, "X", sources)
            self.assertTrue(files[-1].closed)
            empty, _, hist = worker.crop_points(run, "X", [])
            self.assertEqual(empty.shape, (0, 4))
            self.assertEqual(hist, {})

    def test_baseline_window_matches_native_crop_and_edges(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from osgeo import gdal

        dem = gdal.GetDriverByName("MEM").Create("", 137, 127, 1, gdal.GDT_Float32)
        gt = (123.25, 37.5, 0.0, 6543.75, 0.0, -37.5)
        dem.SetGeoTransform(gt)
        data = np.arange(137 * 127, dtype=np.float32).reshape(127, 137)
        data[10, 10] = -9999
        data[11, 11] = np.nan
        dem.GetRasterBand(1).SetNoDataValue(-9999)
        dem.GetRasterBand(1).WriteArray(data)
        read = MagicMock(side_effect=dem.ReadAsArray)
        proxy = SimpleNamespace(
            RasterXSize=137,
            RasterYSize=127,
            GetGeoTransform=dem.GetGeoTransform,
            GetRasterBand=dem.GetRasterBand,
            ReadAsArray=read,
        )
        r, c = np.indices(data.shape)
        for x, y in [
            (2500.0, 4000.0),
            (gt[0] + 18.75, gt[3] - 18.75),
            (gt[0] - 2001.25, gt[3] + 2001.25),
        ]:
            with self.subTest(observer=(x, y)):
                xx = gt[0] + (c + 0.5) * gt[1] - x
                yy = gt[3] + (r + 0.5) * gt[5] - y
                rr, cc = np.where((abs(xx) <= 2020) & (abs(yy) <= 2020))
                lo, hi, left, right = rr.min(), rr.max() + 1, cc.min(), cc.max() + 1
                expected = np.where(np.isfinite(data) & (data != -9999), data, np.nan)[
                    lo:hi, left:right
                ]
                actual, res, x0, y0 = worker.baseline_grid(
                    SimpleNamespace(dem=proxy, points={"X": {"x": x, "y": y}}), "X"
                )
                np.testing.assert_array_equal(actual, expected)
                self.assertEqual((res, x0, y0), (37.5, xx[lo, left], yy[lo, left]))
                self.assertEqual(read.call_args.args, (left, lo, right - left, hi - lo))
        with self.assertRaisesRegex(ValueError, "no local terrain"):
            worker.baseline_grid(
                SimpleNamespace(
                    dem=proxy, points={"X": {"x": -10000.0, "y": -10000.0}}
                ),
                "X",
            )

    def test_display_global_stride_and_filters_across_batches(self):
        rng = np.random.default_rng(54)
        points = np.column_stack(
            [
                rng.uniform(-310, 310, (1100003, 2)),
                rng.uniform(0, 4, 1100003),
                rng.integers(0, 7, 1100003),
            ]
        )
        ground = np.zeros((601, 601))
        ground[250:270, 290:310] = np.nan
        within = points[np.hypot(points[:, 0], points[:, 1]) <= 300]
        z = fp.sample(ground, 1, -300, 300, within[:, 0], within[:, 1])
        eligible = within[
            (within[:, 3] != 2) & np.isfinite(z) & (within[:, 2] - z > 0.5)
        ]
        step = max(1, math.ceil(len(eligible) / 500000))
        self.assertGreater(step, 1)
        with patch.object(fp, "sample", wraps=fp.sample) as sample:
            display, raw, count, actual_step = worker.display_points(points, ground)
            self.assertTrue(
                all(len(call.args[4]) <= 100000 for call in sample.call_args_list)
            )
        np.testing.assert_array_equal(display, eligible[::step])
        self.assertEqual((raw, count, actual_step), (len(within), len(eligible), step))
        empty, raw, count, step = worker.display_points(np.empty((0, 4)), ground)
        self.assertEqual((empty.shape, raw, count, step), ((0, 4), 0, 0, 1))

    def test_sampling_under_actual_address_limit(self):
        import os, subprocess, sys

        code = """
import mmap, pathlib, resource
import numpy as np
from huntmaps_gui import first_person as fp, first_person_worker as worker
points = np.empty((3698058,4), dtype=np.float64)
points[:] = [0.,0.,1.,1.]
ground = np.zeros((601,601))
limit = 1536*1024**2
resource.setrlimit(resource.RLIMIT_AS, (limit,limit))
size = int(next(line.split()[1] for line in pathlib.Path('/proc/self/status').read_text().splitlines() if line.startswith('VmSize:')))*1024
# Model runtime/decoder reservations while leaving room for the exact output
# and bounded sampling temporaries, under the unchanged production limit.
reservation = mmap.mmap(-1, limit-size-points.nbytes-64*1024**2)
try:
    fp.sample(ground,1,-300,300,points[:,0],points[:,1])
except MemoryError:
    pass
else:
    raise AssertionError('Unbounded reference unexpectedly fit')
actual = worker.above_ground(points,ground)
assert actual.shape == points.shape
assert np.array_equal(actual[0],points[0]) and np.array_equal(actual[-1],points[-1])
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            env=dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1"),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_vegetation_distinct_support_across_sampling_batches(self):
        from huntmaps_gui import vegetation_screen as veg

        count = 200005
        points = np.column_stack(
            [
                np.linspace(1.01, 1.99, count),
                np.full(count, 0.1),
                np.full(count, 1.1),
                np.full(count, 4.0),
            ]
        )
        points[0, 3] = 1
        # A differently classified duplicate must not replace the original
        # return or count toward the four-distinct-return support rule.
        duplicate = points[0].copy()
        duplicate[3] = 4
        points = np.vstack(
            [points, duplicate, [10.0, 0.1, 1.1, 1.0], [2.0, 0.1, 0.4, 1.0]]
        )
        ground = np.zeros((601, 601))
        ground[300, 310] = np.nan
        with patch.object(fp, "sample", wraps=fp.sample) as sample:
            centres, kinds, counts, eligible = veg.cells(points, ground, 0)
            self.assertTrue(
                all(len(call.args[4]) <= 100000 for call in sample.call_args_list)
            )
        np.testing.assert_array_equal(counts, [count])
        np.testing.assert_array_equal(kinds, [1])
        self.assertEqual(eligible, count)
        self.assertEqual(centres.shape, (1, 3))
        self.assertEqual((centres[0, 0], centres[0, 2]), (1.5, -0.5))

    def test_memory_failure_reports_stage(self):
        with self.assertRaisesRegex(
            MemoryError,
            "preparing vegetation support for X.*prior views were retained",
        ) as caught:
            with worker.preparation_stage("X", "preparing vegetation support"):
                raise MemoryError("allocation")
        self.assertIsInstance(caught.exception.__cause__, MemoryError)
        self.assertEqual(str(caught.exception.__cause__), "allocation")


if __name__ == "__main__":
    unittest.main()


class ImageryAndReturns(unittest.TestCase):
    def test_sharp_source_priority_and_nodata(self):
        from osgeo import gdal, osr

        with tempfile.TemporaryDirectory() as tmp:
            ref = osr.SpatialReference()
            ref.ImportFromEPSG(32613)
            images = []
            for name, n, spacing, color in [("coarse", 2, 2, 30), ("fine", 4, 1, 200)]:
                path = str(Path(tmp) / (name + ".tif"))
                ds = gdal.GetDriverByName("GTiff").Create(path, n, n, 4, gdal.GDT_Byte)
                ds.SetGeoTransform((0, spacing, 0, 4, 0, -spacing))
                ds.SetProjection(ref.ExportToWkt())
                for b in range(1, 4):
                    ds.GetRasterBand(b).WriteArray(
                        np.full((n, n), color, dtype=np.uint8)
                    )
                alpha = np.full((n, n), 255, dtype=np.uint8)
                if name == "fine":
                    alpha[0, 0] = 0
                ds.GetRasterBand(4).SetColorInterpretation(gdal.GCI_AlphaBand)
                ds.GetRasterBand(4).WriteArray(alpha)
                ds = None
                images.append(dict(path=path))
            for order in [images, list(reversed(images))]:
                a = worker.imagery_mosaic(order, 32613, [0, 0, 4, 4], 4)
                self.assertEqual(a[1, 1, 0], 200)
                self.assertEqual(a[0, 0, 0], 30)
                self.assertTrue((a[:, :, 3] == 255).all())
            a = worker.imagery_mosaic(images, 32613, [-4, -4, 4, 4], 8)
            self.assertEqual(a[7, 0, 3], 0)

    def test_above_ground_excludes_ground_low_and_unknown(self):
        a = np.full((601, 601), 100.0)
        a[300, 310] = np.nan
        points = np.array(
            [
                [0, 0, 101, 2],
                [0, 0, 100.4, 1],
                [0, 0, 101.2, 1],
                [1, 0, 102, 5],
                [10, 0, 104, 1],
            ],
            dtype=float,
        )
        chosen = worker.above_ground(points, a)
        np.testing.assert_array_equal(chosen, points[[2, 3]])
