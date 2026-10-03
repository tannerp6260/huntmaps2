"""Regressions for small-area search and cache changes after failed analysis."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import shutil
import threading
import functools
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RecoveryRegressions(unittest.TestCase):
    def test_thorough_small_boundary(self):
        with tempfile.TemporaryDirectory() as folder:
            shutil.copytree(ROOT / "configs", Path(folder) / "configs")
            script = """
from glassing.transfer_fixture import create
from glassing import transfer
from huntmaps_gui import search
create('fixture.json','fixture')
c=transfer.read('fixture.json')
c.update(normal_scouting=True,candidate_count=600,spacing_m=150,manual_points=None,work='results/new-search')
c['search']=dict(version=1,recommendation_count=10,nearby_radius_m=30,tree_threshold_percent=10)
transfer.prepare(c); search.candidates(c)
p=transfer.read(c['work']+'/pool.json')
assert len(p)==480, len(p)
assert len({(v['row'],v['col']) for v in p})==480
"""
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=folder,
                env=dict(os.environ, PYTHONPATH=str(ROOT)),
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_cache_change_is_not_source_change(self):
        from huntmaps_gui import worker

        approval_inventory = getattr(
            worker, "approval_inventory", lambda config, acquisition: acquisition
        )
        config = dict(
            data=dict(tree=dict(url="https://example.test/tree", path="missing.tif"))
        )
        before = approval_inventory(
            config,
            dict(
                items=[dict(key="tree", url="https://example.test/tree")],
                estimated_bytes=100,
            ),
        )
        config["data"]["tree"].update(
            path="downloaded.tif", sha256="verified", bytes=50
        )
        after = approval_inventory(
            config, dict(items=[], estimated_bytes=0, already_cached_bytes=50)
        )
        self.assertEqual(before, after)

    def test_actual_worker_download_failure_retry(self):
        """Real owner/fetcher/job processes; only provider routing and fault injection are controlled."""
        from huntmaps_gui.config import AppConfig, configured
        from huntmaps_gui.jobs import Jobs, ACTIVE
        from huntmaps_gui.storage import read_json, write
        from huntmaps_gui.downloads import baseline_review_signature
        import time

        with tempfile.TemporaryDirectory(prefix="huntmaps-recovery-") as folder:
            root = Path(folder)
            for name in ["glassing", "configs", "docs", "huntmaps_gui"]:
                (root / name).symlink_to(ROOT / name, target_is_directory=True)
            env = dict(os.environ, PYTHONPATH=str(ROOT))
            subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from glassing.transfer_fixture import create;create('fixture.json','fixture',32613)",
                ],
                cwd=root,
                env=env,
                check=True,
                capture_output=True,
            )
            c = read_json(root / "fixture.json")
            c.update(
                normal_scouting=True, candidate_count=24, spacing_m=150, radius_m=500
            )
            c["data"]["shrub"] = None
            c["search"] = dict(
                version=1,
                recommendation_count=10,
                nearby_radius_m=30,
                tree_threshold_percent=10,
            )
            write(root / "fixture.json", c)

            class Quiet(SimpleHTTPRequestHandler):
                def log_message(self, *args):
                    pass

            http = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                functools.partial(Quiet, directory=str(root / "fixture")),
            )
            thread = threading.Thread(target=http.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(http.server_close)
            self.addCleanup(http.shutdown)
            (root / "sitecustomize.py").write_text(
                f"""
import urllib.request
from pathlib import Path
original = urllib.request.urlopen
def open_response(request,*args,**kwargs):
 url=request.full_url if hasattr(request,'full_url') else str(request)
 if 'geoserver/mrlc_shrub' in url:
  request='http://127.0.0.1:{http.server_port}/shrub.tif'
 elif not url.startswith('http://127.0.0.1:'):
  raise AssertionError('Test attempted an uncontrolled external request: '+url)
 response=original(request,*args,**kwargs)
 marker=Path('injected-transfer-failure')
 if 'geoserver/mrlc_shrub' in url and not marker.exists():
  marker.write_text('controlled interrupted transfer')
  read=response.read
  calls=0
  def interrupted(size=-1):
   nonlocal calls
   calls+=1
   if calls>1:raise TimeoutError('Injected transfer interruption')
   return read(min(size,1024))
  response.read=interrupted
 return response
urllib.request.urlopen=open_response
from huntmaps_gui import search
from pathlib import Path
score=search.score
def fail_once(c):
 marker=Path('injected-failure')
 if not marker.exists():
  marker.write_text('controlled post-download failure')
  raise ValueError('Injected post-download analysis failure')
 return score(c)
search.score=fail_once
"""
            )
            config = AppConfig(
                source_dir=root, state_dir=root / "state", workspace=root
            )
            ident = "e" * 32
            plan_path = config.state_dir / "plans" / (ident + ".json")
            write(
                plan_path,
                dict(
                    id=ident,
                    name="recovery",
                    area=str(root / "fixture/observer.geojson"),
                    polygon="1",
                    config=str(root / "fixture.json"),
                    max_download_mb=30,
                    prepared=False,
                ),
            )
            from unittest.mock import patch

            with configured(config), patch.dict(
                os.environ, PYTHONPATH=str(root) + os.pathsep + str(ROOT)
            ):
                jobs = Jobs()
                self.addCleanup(jobs.shutdown)

                def execute(action, approval=None):
                    command = [
                        sys.executable,
                        "-u",
                        "-m",
                        "huntmaps_gui.worker",
                        action,
                        ident,
                    ]
                    if approval:
                        command += ["--download", "--review-signature", approval]
                    job = jobs.start(
                        command,
                        "prepare" if action == "prepare" else "baseline",
                        name="recovery",
                        plan=ident,
                    )
                    deadline = time.monotonic() + 90
                    while time.monotonic() < deadline:
                        record = next(j for j in jobs.list() if j["id"] == job["id"])
                        if record["status"] not in ACTIVE:
                            return record
                        time.sleep(0.05)
                    self.fail("Worker timeout")

                prepared = execute("prepare")
                self.assertEqual(prepared["status"], "complete", prepared.get("logs"))
                signature = baseline_review_signature(read_json(plan_path))
                interrupted = execute("run", signature)
                self.assertEqual(
                    interrupted["status"], "failed", interrupted.get("logs")
                )
                self.assertTrue(
                    (
                        root / "results/recovery/downloads/shrub_padded120.tif.partial"
                    ).exists()
                )
                self.assertFalse(
                    (root / "results/recovery/downloads/shrub_padded120.tif").exists()
                )
                self.assertEqual(
                    read_json(config.state_dir / "plans" / (ident + "-transfer.json"))[
                        "received_bytes"
                    ],
                    1024,
                )
                first = execute("run", signature)
                self.assertEqual(first["status"], "failed", first.get("logs"))
                self.assertIn("Injected post-download", first["error"])
                self.assertEqual(first["failed_stage"], "score")
                downloaded = root / "results/recovery/downloads/shrub_padded120.tif"
                self.assertTrue(downloaded.exists())
                ledger = read_json(
                    config.state_dir / "plans" / (ident + "-transfer.json")
                )
                self.assertGreater(ledger["received_bytes"], 0)
                checksum = (
                    __import__("hashlib").sha256(downloaded.read_bytes()).hexdigest()
                )
                original_bytes = downloaded.read_bytes()
                downloaded.write_bytes(b"corrupted cached source")
                corrupt = execute("run", signature)
                self.assertEqual(corrupt["status"], "failed")
                self.assertEqual(
                    corrupt["failure_code"], "source_invalid", corrupt.get("logs")
                )
                downloaded.write_bytes(original_bytes)
                current_path = root / "results/recovery/scouting.json"
                current = read_json(current_path)
                substituted = json.loads(json.dumps(current))
                substituted["data"]["shrub"].update(
                    path=current["data"]["tree"]["path"],
                    sha256=current["data"]["tree"]["sha256"],
                )
                write(current_path, substituted)
                replaced = execute("run", signature)
                self.assertEqual(replaced["status"], "failed")
                self.assertEqual(
                    replaced["failure_code"], "review_required", replaced.get("logs")
                )
                write(current_path, current)
                changed = json.loads(json.dumps(current))
                changed["data"]["shrub"]["url"] += "&changed-request=true"
                write(current_path, changed)
                blocked = execute("run", signature)
                self.assertEqual(blocked["status"], "failed")
                self.assertEqual(blocked["failure_code"], "review_required")
                self.assertIn("plan changed", blocked["error"].lower())
                write(current_path, current)
                second = execute("run", signature)
                self.assertEqual(second["status"], "complete", second.get("logs"))
                self.assertEqual(
                    checksum,
                    __import__("hashlib").sha256(downloaded.read_bytes()).hexdigest(),
                )
                self.assertEqual(
                    ledger,
                    read_json(config.state_dir / "plans" / (ident + "-transfer.json")),
                )
                refreshed = read_json(plan_path)
                self.assertEqual(refreshed["acquisition"]["estimated_bytes"], 0)
                self.assertGreater(refreshed["acquisition"]["already_cached_bytes"], 0)
                self.assertEqual(signature, baseline_review_signature(refreshed))

    def test_boundary_and_effort_matrix(self):
        with tempfile.TemporaryDirectory() as folder:
            shutil.copytree(ROOT / "configs", Path(folder) / "configs")
            script = """
from glassing.transfer_fixture import create
from glassing import transfer, core
from huntmaps_gui import search
from shapely.geometry import box, mapping
from shapely.ops import transform, unary_union
create('fixture.json','fixture')
base=transfer.read('fixture.json')
shapes={'compact':box(450000,4200000,450080,4200080),
 'narrow':box(450000,4200000,450020,4200400),
 'irregular':box(450000,4200000,450160,4200060).union(box(450000,4200000,450060,4200160)),
 'fragmented':unary_union([box(450000,4200000,450060,4200060),box(450300,4200300,450360,4200360)])}
for name,area in shapes.items():
 transfer.dump('observer.geojson',dict(type='Polygon' if area.geom_type=='Polygon' else 'MultiPolygon',coordinates=mapping(transform(transfer.project(base['epsg'],4326),area))['coordinates']))
 for budget in [150,600,2000,5000]:
  c=dict(base,normal_scouting=True,manual_points=None,candidate_count=budget,spacing_m=150,observer_polygon='observer.geojson',work=f'results/{name}-{budget}')
  c['search']=dict(version=1,recommendation_count=20,nearby_radius_m=30,tree_threshold_percent=10)
  transfer.prepare(c);search.candidates(c)
  pool=transfer.read(c['work']+'/pool.json')
  grid=core.load_grid(transfer.read(c['work']+'/core_config.json'))
  assert len(pool)==min(int(budget*.8),int(grid[3]['observer'].sum()))
  assert len(pool)==len({(p['row'],p['col']) for p in pool})
  assert all(grid[3]['observer'][p['row'],p['col']] for p in pool)
  before=transfer.read(c['work']+'/pool.json');search.candidates(c)
  assert before==transfer.read(c['work']+'/pool.json')
  if name=='compact' and budget==5000:
   search.score(c)
   summary=transfer.read(c['work']+'/recommendations.json')
   assert summary['unused_budget']>0 and len(summary['ids'])==20
print('Verified 16 boundary/preset combinations and exhausted-budget scoring')
area=box(450000,4200000,450020,4200020)
transfer.dump('tiny.geojson',mapping(transform(transfer.project(base['epsg'],4326),area)))
c=dict(base,normal_scouting=True,manual_points=None,candidate_count=600,observer_polygon='tiny.geojson',work='results/tiny')
c['search']=dict(version=1,recommendation_count=20,nearby_radius_m=30,tree_threshold_percent=10)
search.prepare(c);search.candidates(c);search.score(c)
summary=transfer.read(c['work']+'/recommendations.json')
assert 0<len(summary['ids'])<20
assert len(summary['ids'])==summary['evaluated_count']
c=dict(base,normal_scouting=True,manual_points=None,candidate_count=150,observer_exclusions=['fixture/range.geojson'],work='results/empty')
c['search']=dict(version=1,recommendation_count=20,nearby_radius_m=30,tree_threshold_percent=10)
try:search.prepare(c);search.candidates(c)
except ValueError as error:assert 'No eligible observer cells' in str(error),str(error)
else:raise AssertionError('Empty eligibility must stop before scoring')
"""
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=folder,
                env=dict(os.environ, PYTHONPATH=str(ROOT)),
                capture_output=True,
                text=True,
                timeout=90,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_durable_transfer_ceiling_and_failure_origin(self):
        from unittest.mock import patch
        from huntmaps_gui.storage import write, read_json
        from huntmaps_gui.progress import received
        from huntmaps_gui.failures import summarize

        with tempfile.TemporaryDirectory() as folder:
            ledger = Path(folder) / "transfer.json"
            write(ledger, dict(received_bytes=8, ceiling_bytes=10))
            with patch.dict(
                os.environ,
                HUNTMAPS_TRANSFER_LEDGER=str(ledger),
                HUNTMAPS_PROGRESS_FILE="",
            ):
                received(2, "https://example.test")
                with self.assertRaisesRegex(ValueError, "Cumulative"):
                    received(1, "https://example.test")
            self.assertEqual(read_json(ledger)["received_bytes"], 11)
        failure = summarize(
            [
                "STAGE score",
                "GUI JOB: original analysis failure",
                "ValueError: generic wrapper failure",
            ]
        )
        self.assertIn("original analysis failure", failure["error"])
        self.assertEqual(failure["failed_stage"], "score")


if __name__ == "__main__":
    unittest.main()
