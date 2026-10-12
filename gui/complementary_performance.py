"""Read-only real-area coverage benchmarks in disposable GUI state, no downloads."""

import argparse
import json
import os
from pathlib import Path
import resource
import statistics
import subprocess
import sys
import tempfile
import time


def sample(run, state):
    from huntmaps_gui.config import AppConfig, configured, SOURCE
    from huntmaps_gui import complementary as c
    from unittest.mock import patch

    config = AppConfig(source_dir=SOURCE, workspace=SOURCE, state_dir=Path(state))
    Path(state).mkdir(parents=True, exist_ok=True)
    with configured(config), patch(
        "urllib.request.urlopen", side_effect=AssertionError("No acquisition allowed")
    ):
        samples = []
        for count, label in [
            (5, "cold"),
            (5, "warm"),
            (3, "resize-3"),
            (4, "resize-4"),
            (5, "warm-return"),
        ]:
            start = time.perf_counter()
            value = c.calculate(run, count)
            elapsed = time.perf_counter() - start
            samples.append(
                dict(
                    label=label,
                    count=count,
                    wall_s=elapsed,
                    compute_s=value["elapsed_s"],
                    cached=value["cached"],
                    combined_cells=value["combined_cells"],
                    evaluated_count=value["evaluated_count"],
                    eligible_count=value["eligible_count"],
                    packed_cache_bytes=value["cache_bytes"],
                    ids=[p["id"] for p in value["suggestions"]],
                )
            )
        # Independently compare exported analytical cells and marginal areas.
        import numpy as np
        from osgeo import gdal

        context = c.Context(run, "", None)
        union = np.zeros(context.shape, bool)
        for contribution in value["suggestions"]:
            mask = context.run.mask(contribution["id"])[0] & context.filtered.matching
            assert int((mask & ~union).sum()) == contribution["additional_cells"]
            assert int(mask.sum()) == contribution["total_cells"]
            union |= mask
        assert int(union.sum()) == value["combined_cells"]
        combined = gdal.Open(str(c.folder(value["id"]) / "combined.tif"))
        assert np.array_equal(combined.GetRasterBand(4).ReadAsArray() > 0, union)
        return dict(
            run=run,
            grid=list(context.shape),
            samples=samples,
            peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
            verified_exact_union=True,
            network_bytes=0,
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample")
    parser.add_argument("--state")
    parser.add_argument("--out")
    args = parser.parse_args()
    if args.sample:
        print(json.dumps(sample(args.sample, args.state)))
        return
    root = Path(tempfile.mkdtemp(prefix="huntmaps-complementary-performance-"))
    results = []
    for run in ("soap-creek-v1", "scouting-2026-10-10v4"):
        repeats = []
        for i in range(3):
            state = root / f"{run}-{i}"
            env = dict(
                os.environ,
                OPENBLAS_NUM_THREADS="1",
                OMP_NUM_THREADS="1",
                PYTHONDONTWRITEBYTECODE="1",
            )
            response = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gui.complementary_performance",
                    "--sample",
                    run,
                    "--state",
                    str(state),
                ],
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if response.returncode:
                raise RuntimeError(response.stdout + response.stderr)
            repeats.append(json.loads(response.stdout))
        medians = {
            label: statistics.median(
                next(s["wall_s"] for s in repeat["samples"] if s["label"] == label)
                for repeat in repeats
            )
            for label in ("cold", "warm", "resize-3", "resize-4", "warm-return")
        }
        results.append(dict(run=run, repeats=repeats, median_wall_s=medians))
    report = dict(
        artifacts=str(root),
        cold_definition="New process, empty application display/packed caches; OS page cache unchanged",
        results=results,
    )
    output = Path(args.out) if args.out else root / "results.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                output=str(output),
                runs=[dict(run=r["run"], medians=r["median_wall_s"]) for r in results],
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
