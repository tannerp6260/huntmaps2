"""Expanded normal search, nearby evidence and recovery without owner-data writes."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import numpy as np
from huntmaps_gui.search import nearby_cover, rank
from huntmaps_gui.requests import Preparation

ROOT = Path(__file__).resolve().parents[1]


class SearchTests(unittest.TestCase):
    def test_cover_categories_unknown_edges_and_separate_shrubs(self):
        tree = np.zeros((11, 11))
        shrub = np.full_like(tree, 0.7)
        point = dict(row=5, col=5)
        gt = (0, 10, 0, 0, 0, -10)
        result = nearby_cover(tree, shrub, gt, point)
        self.assertEqual(result["foreground_category"], "low mapped tree cover")
        self.assertAlmostEqual(result["foreground_shrub_mean"], 0.7)
        tree[:] = 0.8
        self.assertEqual(
            nearby_cover(tree, shrub, gt, point)["foreground_category"],
            "other known cover",
        )
        tree[:] = np.nan
        self.assertEqual(
            nearby_cover(tree, shrub, gt, point)["foreground_category"],
            "insufficient coverage",
        )
        tree[:] = 0
        self.assertEqual(
            nearby_cover(tree, shrub, gt, dict(row=0, col=0))["foreground_category"],
            "insufficient coverage",
        )
        rows = [
            dict(id="dense", raw_km2=10, foreground_category="other known cover"),
            dict(id="clear", raw_km2=1, foreground_category="low mapped tree cover"),
            dict(id="unknown", raw_km2=20, foreground_category="insufficient coverage"),
        ]
        self.assertEqual([p["id"] for p in rank(rows)], ["clear", "dense", "unknown"])

    def test_payload_budgets(self):
        value = dict(name="test", import_id="a" * 32, polygon="all")
        self.assertEqual(
            Preparation(**value, candidate_count=5000).candidate_count, 5000
        )
        with self.assertRaises(ValueError):
            Preparation(**value, candidate_count=5001)
        with self.assertRaises(ValueError):
            Preparation(**value, tree_threshold_percent=101)

    def test_api_records_search_and_rejects_excess_recommendations(self):
        from fastapi.testclient import TestClient
        from huntmaps_gui.server import create_app
        from huntmaps_gui.config import AppConfig, configured
        from huntmaps_gui.storage import write
        from unittest.mock import patch

        with tempfile.TemporaryDirectory(prefix="huntmaps-search-api-") as folder:
            root = Path(folder)
            config = AppConfig(state_dir=root / "state", workspace=root)
            app = create_app(config)
            self.addCleanup(app.state.jobs.shutdown)
            with configured(config):
                polygon = root / "observer.geojson"
                polygon.write_text(
                    json.dumps(
                        dict(
                            type="Polygon",
                            coordinates=[
                                [
                                    [-108, 38],
                                    [-107.99, 38],
                                    [-107.99, 38.01],
                                    [-108, 38.01],
                                    [-108, 38],
                                ]
                            ],
                        )
                    )
                )
                ident = "a" * 32
                write(
                    root / "state/imports" / ident / "import.json",
                    dict(path=str(polygon), choices=[dict(number="1")]),
                )
                client = TestClient(app)
                payload = dict(
                    name="new-search",
                    import_id=ident,
                    polygon="1",
                    candidate_count=600,
                    recommendation_count=12,
                    nearby_radius_m=60,
                    tree_threshold_percent=15,
                )
                with patch.object(
                    app.state.jobs, "start", return_value={"id": "test"}
                ) as start:
                    response = client.post(
                        "/api/plans", headers={"X-HuntMaps": "local"}, json=payload
                    )
                    self.assertEqual(response.status_code, 200, response.text)
                    plan = start.call_args.args[0][-1]
                    record = json.loads(
                        (root / "state/plans" / (plan + ".json")).read_text()
                    )
                    saved = json.loads(Path(record["config"]).read_text())
                    self.assertEqual(saved["candidate_count"], 600)
                    self.assertEqual(
                        saved["search"],
                        dict(
                            version=1,
                            ranking_version=2,
                            target_filters=__import__(
                                "huntmaps_gui.target_filters", fromlist=["validate"]
                            ).validate(),
                            avoid_dense_vegetation=False,
                            recommendation_count=12,
                            recommendation_separation_m=150,
                            nearby_radius_m=60,
                            tree_threshold_percent=15,
                        ),
                    )
                    payload.update(
                        name="bad-search", candidate_count=12, recommendation_count=20
                    )
                    response = client.post(
                        "/api/plans", headers={"X-HuntMaps": "local"}, json=payload
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(start.call_count, 1)

    def test_complete_search_reproducibility_manual_coordinates_and_checkpoint(self):
        with tempfile.TemporaryDirectory(prefix="huntmaps-search-") as directory:
            root = Path(directory)
            for name in ["glassing", "configs"]:
                shutil.copytree(
                    ROOT / name,
                    root / name,
                    ignore=shutil.ignore_patterns("__pycache__"),
                )
            env = dict(
                os.environ,
                PYTHONPATH=str(ROOT),
                HUNTMAPS_STATE_DIR=str(root / "state"),
                HUNTMAPS_WORKSPACE=str(root),
                PYTHONDONTWRITEBYTECODE="1",
                HUNTMAPS_PROGRESS_FILE=str(root / "search.progress"),
            )

            def run(*args):
                p = subprocess.run(
                    [sys.executable, *args],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                self.assertEqual(p.returncode, 0, p.stdout + "\n" + p.stderr)
                return p

            run(
                "-c",
                "from glassing.transfer_fixture import create; create('fixture.json','fixture')",
            )
            config = json.loads((root / "fixture.json").read_text())
            config.update(
                normal_scouting=True, candidate_count=48, work="results/search-analysis"
            )
            config["search"] = dict(
                version=1,
                ranking_version=2,
                target_filters=dict(
                    elevation_m=[2100, 2150],
                    tree_percent=[0, 15],
                    shrub_percent=[20, 30],
                ),
                avoid_dense_vegetation=False,
                recommendation_count=5,
                nearby_radius_m=30,
                tree_threshold_percent=10,
            )
            (root / "fixture.json").write_text(json.dumps(config))
            run(
                "-c",
                """from glassing import transfer
from huntmaps_gui import search
from unittest.mock import patch
c=transfer.read('fixture.json');transfer.prepare(c);search.candidates(c)
original=transfer.evaluate
calls=0
def interrupted(*args):
 global calls
 calls+=1
 if calls==2:raise ValueError('synthetic interruption')
 return original(*args)
with patch.object(transfer,'evaluate',side_effect=interrupted):
 try:search.score(c)
 except ValueError as error:assert str(error)=='synthetic interruption'
 else:raise AssertionError('Expected interruption')
assert len(transfer.read('results/search-analysis/search-checkpoint.json')['rows'])==20
""",
            )
            progress = json.loads((root / "search.progress").read_text())
            self.assertEqual(progress["completed"], 20)
            self.assertGreater(progress["remaining_s"], 0)
            run("-m", "huntmaps_gui.search_worker", "--config", "fixture.json")
            analysis = root / "results/search-analysis"
            scores = json.loads((analysis / "scores.json").read_text())
            recommendations = json.loads(
                (analysis / "recommendations.json").read_text()
            )
            self.assertEqual(
                len(scores), 50
            )  # 48 automated evaluations plus two manual inputs
            self.assertEqual(
                len({(p["row"], p["col"]) for p in scores if p["group"] != "manual"}),
                48,
            )
            self.assertTrue(all(0 <= p["matching_km2"] <= p["raw_km2"] for p in scores))
            self.assertTrue(any(p["matching_km2"] < p["raw_km2"] for p in scores))
            from huntmaps_gui.search import spread_recommendations

            self.assertEqual(
                recommendations["ids"],
                [p["id"] for p in spread_recommendations(scores, 5, 0)],
            )
            self.assertEqual(len(recommendations["ids"]), 5)
            self.assertTrue(any(p["group"] == "refinement" for p in scores))
            manual = json.loads((analysis / "manual_import.json").read_text())
            self.assertEqual(
                [(p["x"], p["y"]) for p in scores if p["group"] == "manual"],
                [(p["x"], p["y"]) for p in manual],
            )
            # Dense mapped cover excludes automated standing points, but never
            # changes or drops the user's exact manual coordinates.
            clearing = dict(
                config,
                work="results/clearing-search",
                search=dict(config["search"], avoid_dense_vegetation=True),
            )
            (root / "clearing.json").write_text(json.dumps(clearing))
            run("-m", "huntmaps_gui.search_worker", "--config", "clearing.json")
            cleared = json.loads(
                (root / "results/clearing-search/scores.json").read_text()
            )
            self.assertEqual(
                [(p["x"], p["y"]) for p in cleared], [(p["x"], p["y"]) for p in manual]
            )
            self.assertTrue(all(not p["standing_eligible"] for p in cleared))
            packet = root / "results/clearing-search"
            checks = json.loads((packet / "export_checks.json").read_text())
            self.assertTrue(checks["passed"])
            self.assertEqual(checks["manual_count"], 2)
            self.assertEqual(checks["automated_count"], 0)
            recovery = json.loads((packet / "comparison_review.json").read_text())[
                "recovery"
            ]
            self.assertTrue(all(p["nearest_automated"] is None for p in recovery))
            self.assertGreater((packet / "review_packet.pdf").stat().st_size, 1000)
            self.assertEqual(
                json.loads(
                    (root / "results/clearing-search/recommendations.json").read_text()
                )["ids"],
                [],
            )
            before = (analysis / "scores.json").read_bytes()
            run("-m", "huntmaps_gui.search_worker", "--config", "fixture.json")
            self.assertEqual((analysis / "scores.json").read_bytes(), before)
            metrics = json.loads((analysis / "search-metrics.json").read_text())
            print("Expanded search fixture metrics:", json.dumps(metrics))
            run(
                "-c",
                """from pathlib import Path
import hashlib
from glassing import transfer
from huntmaps_gui import search_worker
import sys
root=Path('results/search-analysis')
checkpoint=root/'search-checkpoint.json'
original=checkpoint.read_bytes()
stale=transfer.read(checkpoint);stale['identity']['algorithm']='outdated'
transfer.dump(checkpoint,stale)
before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
sys.argv=['search_worker','--config','fixture.json']
try:search_worker.main()
except ValueError as error:assert 'checkpoint is incompatible' in str(error)
else:raise AssertionError('Incompatible checkpoint must be rejected')
after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
assert before==after
checkpoint.write_bytes(original)
""",
            )
            run(
                "-m",
                "huntmaps_gui.owner_worker",
                "run",
                "--area",
                "fixture/observer.geojson",
                "--manual",
                "fixture/manual.geojson",
                "--source-config",
                "fixture.json",
                "--name",
                "gui-search",
            )
            run("-m", "glassing.owner", "verify", "--name", "gui-search")
            capped = dict(config, work="results/capped-search", disk_bytes=1000)
            (root / "capped.json").write_text(json.dumps(capped))
            failed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "huntmaps_gui.search_worker",
                    "--config",
                    "capped.json",
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(failed.returncode, 2)
            self.assertIn("Search output limit reached", failed.stdout)
            self.assertEqual(
                json.loads(
                    (root / "results/capped-search/search-checkpoint.json").read_text()
                )["rows"],
                [],
            )
            self.assertFalse((root / "results/capped-search/scores.json").exists())
            self.assertEqual(
                len(
                    json.loads(
                        (
                            root / "results/gui-search/analysis/recommendations.json"
                        ).read_text()
                    )["ids"]
                ),
                5,
            )


if __name__ == "__main__":
    unittest.main()
