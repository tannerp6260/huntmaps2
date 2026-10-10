"""Offline, disposable performance measurements; saved fixtures are read only.

Run with the project's .venv/bin/python. --package can select a snapshot containing
huntmaps_gui for before/after comparisons. No downloads or kernel-cache flushes.
"""

import argparse
import cProfile
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import statistics
import subprocess
import socket
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "task",
        choices=[
            "search",
            "sampling",
            "tiles",
            "approach",
            "scene",
            "scene-lidar",
            "lidar",
            "browser",
            "catalog",
        ],
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--package", type=Path, default=ROOT)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--count", type=int, default=150)
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--browser-cpu-profile", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    sys.path[:0] = [str(args.package.resolve()), str(ROOT)]
    os.environ.update(
        OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", PYTHONDONTWRITEBYTECODE="1"
    )
    from huntmaps_gui.config import AppConfig, configured
    from glassing import core, transfer
    import numpy as np
    from osgeo import gdal

    records = []

    def measure(label, function):
        before = resource.getrusage(resource.RUSAGE_SELF)
        children_before = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = time.perf_counter()
        result = function()
        seconds = time.perf_counter() - start
        after = resource.getrusage(resource.RUSAGE_SELF)
        children_after = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu = after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime
        child_cpu = (
            children_after.ru_utime
            + children_after.ru_stime
            - children_before.ru_utime
            - children_before.ru_stime
        )
        record = dict(
            stage=label,
            wall_s=seconds,
            cpu_s=cpu,
            cpu_percent=100 * (cpu + child_cpu) / seconds,
            child_cpu_s=child_cpu,
            child_peak_rss_mib=children_after.ru_maxrss / 1024,
            peak_rss_mib=after.ru_maxrss / 1024,
        )
        records.append(record)
        print(json.dumps(record), flush=True)
        return result

    config = AppConfig(ROOT, args.output / "state", ROOT)
    profile = cProfile.Profile()
    # Profile once after uninstrumented timing repeats, since profiling distorts
    # Python loop costs substantially. Measurements never include profiler time.
    with configured(config):
        if args.task == "catalog":
            from huntmaps_gui.catalog import Run

            for repeat in range(args.repeats + 1):
                run = measure(
                    "catalog-first" if repeat == 0 else "catalog-warm",
                    lambda: Run("soap-creek-decision-review-v2"),
                )
                values = dict(
                    summary=run.summary(),
                    candidates=[
                        run.candidate(cid, include_mask=True)
                        for cid in ["A0075", "V010", "V008"]
                    ],
                    hashes=run.hashes,
                )
                (args.output / f"outputs-{repeat}.json").write_text(json.dumps(values))
            profile.runcall(Run, "soap-creek-decision-review-v2")
        elif args.task == "search":
            from huntmaps_gui import search

            for repeat in range(args.repeats + 1):
                if repeat == args.repeats:
                    profile.enable()
                c = transfer.read(ROOT / "results/soap-creek-v1/scouting.json")
                c["work"] = str(args.output / f"search-{repeat}")
                c["candidate_count"] = args.count
                c["search"] = dict(
                    version=1,
                    ranking_version=2,
                    target_filters={},
                    avoid_dense_vegetation=False,
                    recommendation_count=20,
                    nearby_radius_m=30,
                    tree_threshold_percent=10,
                )
                measure("prepare", lambda: search.prepare(c))
                measure("candidates", lambda: search.candidates(c))
                measure("score-cold", lambda: search.score(c))
                measure("score-checkpoint-warm", lambda: search.score(c))
                root = Path(c["work"])
                values = {
                    n: transfer.read(root / n)
                    for n in [
                        "pool.json",
                        "scores.json",
                        "patches.json",
                        "recommendations.json",
                        "overlap.json",
                    ]
                }
                masks = {
                    p.name: core.digest(p)
                    for p in sorted((root / "additional_visibility").glob("*.tif"))
                }
                (args.output / f"outputs-{repeat}.json").write_text(
                    json.dumps(dict(values=values, masks=masks))
                )
                if repeat == args.repeats:
                    profile.disable()
                    records = records[:-4]
        elif args.task == "sampling":
            from glassing.acquire import srs, dump

            # 64 km² with 10 m grid and unchanged 4,000 candidate setting.
            n, halo, res = 1000, 100, 10
            yy, xx = np.mgrid[:n, :n]
            dem = (2500 + 70 * np.sin(xx / 60) * np.cos(yy / 40)).astype("float32")
            allowed = np.zeros((n, n), dtype="uint8")
            allowed[halo:-halo, halo:-halo] = 1
            gt = (300000, res, 0, 4300000, 0, -res)
            for repeat in range(args.repeats):
                work = args.output / f"sample-{repeat}"
                work.mkdir()
                c = dict(
                    work=str(work),
                    vertical_units="m",
                    max_cells=3000000,
                    seed=5403,
                    candidate_count=4000,
                    spacing_m=100,
                    manual_points=[],
                )
                for name, a in [
                    ("dem", dem),
                    ("target", allowed),
                    ("observer", allowed),
                ]:
                    core.write_raster(
                        work / (name + ".tif"), a, gt, srs(32613).ExportToWkt()
                    )
                dump(
                    work / "prepared.json",
                    dict(
                        config=c,
                        implementation_sha256=core.digest(core.__file__),
                        **{
                            k + "_sha256": core.digest(work / (k + ".tif"))
                            for k in ["dem", "target", "observer"]
                        },
                    ),
                )
                try:
                    from huntmaps_gui.sampling import TerrainSampler
                except ImportError:
                    generate = lambda: core.generate(c)
                else:
                    generate = lambda: TerrainSampler(c).generate(c)
                measure("sampling-4000", generate)
                (args.output / f"outputs-{repeat}.json").write_text(
                    (work / "candidates.json").read_text()
                )
        elif args.task == "tiles":
            from huntmaps_gui import tiles
            from huntmaps_gui.catalog import Run

            # Below budget, many small files reproduce a long-lived display cache.
            cache = args.output / "state/cache/background"
            cache.mkdir(parents=True)
            for i in range(12000):
                (cache / f"{i}.png").write_bytes(b"fixture" * 50)
            run = Run("soap-creek-decision-review-v2")
            ids = ["A0075", "V010", "V008"]
            for repeat in range(args.repeats):
                for cid in ids:
                    p = run.candidate(cid)
                    z = 15
                    x = int((p["longitude"] + 180) / 360 * 2**z)
                    y = int(
                        (
                            1
                            - math.asinh(math.tan(math.radians(p["latitude"])))
                            / math.pi
                        )
                        / 2
                        * 2**z
                    )
                    data = measure(
                        "tile-first" if repeat == 0 else "tile-switch-warm",
                        lambda: tiles.tile(run, "visible", cid, z, x, y),
                    )
                    measure(
                        "tile-repeat-warm",
                        lambda: tiles.tile(run, "visible", cid, z, x, y),
                    )
                    (args.output / (cid + ".png")).write_bytes(data)
        elif args.task == "approach":
            from huntmaps_gui.approach_search import Grid, solve
            from shapely.geometry import box, GeometryCollection, LineString

            # Real ground/cover at the solver's existing 20 m resolution.
            source = ROOT / "results/soap-creek-v1/analysis"
            center = transfer.read(source / "scores.json")[0]
            x, y = center["x"], center["y"]
            bounds = [x - 2000, y - 2000, x + 2000, y + 2000]
            arrays = []
            for name in ["dem", "tree", "shrub"]:
                ds = gdal.Warp(
                    "",
                    str(source / (name + ".tif")),
                    format="MEM",
                    outputBounds=bounds,
                    xRes=20,
                    yRes=20,
                    resampleAlg="bilinear" if name == "dem" else "near",
                    dstNodata=-9999,
                )
                a = ds.ReadAsArray().astype(float)
                a[a < -1000] = np.nan
                arrays.append(a)
            if args.synthetic:
                rr, cc = np.indices((400, 400))
                arrays = [
                    100 + 30 * np.sin(cc / 40) + 10 * np.cos(rr / 35),
                    np.where(cc < 170, 0.3, 0.1),
                    np.full(rr.shape, 0.2),
                ]
                arrays[1][10:20] = np.nan
                bounds = [x - 4000, y - 4000, x + 4000, y + 4000]
            for repeat in range(args.repeats):
                grid = measure(
                    "approach-grid",
                    lambda: Grid(
                        *arrays,
                        (bounds[0], bounds[3]),
                        box(*bounds),
                        GeometryCollection(),
                    ),
                )
                cells = np.argwhere(grid.valid)
                # A highest-coverage observer can fail the travel slope limit.
                # Use the closest valid terrain cell for the positive-path benchmark.
                end = cells[
                    np.argmin(
                        ((cells - np.array(grid.dem.shape) // 2) ** 2).sum(axis=1)
                    )
                ]
                target = grid.xy(end)
                lines = [LineString([(x - 800, y - 1200), (x - 800, y + 1200)])]
                result = measure(
                    "approach-three-objectives",
                    lambda: solve(
                        grid, lines, target, dict(slope=1, tree=1, shrub=1, gain=1)
                    ),
                )
                if not result["alternatives"]:
                    raise ValueError(
                        "Approach timing fixture produced no positive path"
                    )
                (args.output / f"outputs-{repeat}.json").write_text(json.dumps(result))
        elif args.task in ("scene", "scene-lidar", "lidar"):
            from huntmaps_gui import first_person_worker as worker
            from huntmaps_gui.catalog import Run

            run = Run("soap-creek-decision-review-v2")
            ids = ["A0075", "V010", "V008"]
            if args.task in ("lidar", "scene-lidar"):
                ids = ["A0031", "V002", "V004"]
                spec = transfer.read(ROOT / "configs/vegetation.soap-creek-v1.json")[
                    "lidar_source"
                ]
                path = ROOT / spec["path"]
                if core.digest(path) != spec["sha256"]:
                    raise ValueError("Lidar fixture checksum changed")
                sources = [
                    (
                        dict(
                            spec,
                            candidates=ids,
                            title="Cached USGS LPC local_A0031.laz",
                            acquisition_date="unknown; project label 2019",
                        ),
                        path,
                        spec["sha256"],
                    )
                ]
                try:
                    from huntmaps_gui.lidar_batch import crop_batch
                except ImportError:
                    crop_batch = None

                def batch():
                    def collect(crops=None):
                        values = {}
                        for cid in ids:
                            points, vref, hist = (
                                worker.crop_points(run, cid, sources)
                                if crops is None
                                else crops.get(cid)
                            )
                            if not len(points):
                                raise ValueError(
                                    "Lidar timing fixture has no measured returns"
                                )
                            values[cid] = dict(
                                points_sha256=hashlib.sha256(
                                    points.tobytes()
                                ).hexdigest(),
                                histogram=hist,
                                vertical_reference=vref,
                                count=len(points),
                            )
                            del points
                        return values

                    if crop_batch is None:
                        return collect()
                    with crop_batch(run, ids, sources) as crops:
                        return collect(crops)

                for repeat in range(args.repeats):
                    if args.task == "lidar":
                        values = measure("lidar-three-observers", batch)
                    else:
                        resource.setrlimit(
                            resource.RLIMIT_AS, (1536 * 1024**2, resource.RLIM_INFINITY)
                        )
                        with configured(
                            AppConfig(ROOT, args.output / f"state-{repeat}", ROOT)
                        ):

                            def scenes():
                                if crop_batch is None:
                                    for cid in ids:
                                        worker.publish(run, cid, sources)
                                else:
                                    with crop_batch(run, ids, sources) as crops:
                                        for cid in ids:
                                            worker.publish(
                                                run, cid, sources, crops, optimized=True
                                            )

                            measure("scene-lidar-three-cold", scenes)
                            values = {}
                            from huntmaps_gui import first_person as fp

                            for cid in ids:
                                ready = transfer.read(fp.ready_path(run.id, cid))
                                meta = transfer.read(
                                    fp.HOME / "bundles" / ready["key"] / "scene.json"
                                )
                                values[cid] = dict(
                                    hashes=meta["hashes"],
                                    ground=meta["ground_m"],
                                    counts=meta["classification_counts"],
                                )
                    (args.output / f"outputs-{repeat}.json").write_text(
                        json.dumps(values)
                    )
            else:
                for repeat in range(args.repeats):
                    for cid in ids:
                        measure(
                            (
                                "scene-terrain-first"
                                if repeat == 0
                                else "scene-terrain-warm"
                            ),
                            lambda: worker.publish(run, cid, []),
                        )
        elif args.task == "browser":
            for repeat in range(args.repeats):
                work = args.output / str(repeat)
                work.mkdir()
                state = work / "state"
                state.mkdir()
                with socket.socket() as sock:
                    sock.bind(("127.0.0.1", 0))
                    port = sock.getsockname()[1]
                url = f"http://127.0.0.1:{port}"
                env = dict(
                    os.environ,
                    PYTHONPATH=str(args.package.resolve()) + os.pathsep + str(ROOT),
                    HUNTMAPS_SOURCE_DIR=str(ROOT),
                    HUNTMAPS_WORKSPACE=str(work),
                    HUNTMAPS_STATE_DIR=str(state),
                    HUNTMAPS_URL=url,
                    HUNTMAPS_SCREENSHOTS=str(work / "screenshots"),
                    HUNTMAPS_DISABLE_SPEED_PROBE="1",
                )
                with (work / "server.log").open("w") as log:
                    process = subprocess.Popen(
                        [
                            sys.executable,
                            "-m",
                            "uvicorn",
                            "huntmaps_gui.server:create_app",
                            "--factory",
                            "--host",
                            "127.0.0.1",
                            "--port",
                            str(port),
                        ],
                        cwd=work,
                        env=env,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                    )
                    try:
                        for _ in range(100):
                            if process.poll() is not None:
                                raise ValueError(
                                    "Benchmark server failed; inspect "
                                    + str(work / "server.log")
                                )
                            try:
                                urllib.request.urlopen(
                                    url + "/api/runs", timeout=0.5
                                ).close()
                                break
                            except OSError:
                                time.sleep(0.1)
                        else:
                            raise ValueError("Benchmark server startup timeout")
                        for label, script in [
                            ("map-browser-session", "browser-performance-local.mjs"),
                            ("scene-browser-session", "browser-performance-check.mjs"),
                        ]:
                            stat_path = Path(f"/proc/{process.pid}/stat")

                            # Field 14/15 are user/system CPU ticks. The server's
                            # process name can contain spaces, so split after ')'.
                            def server_cpu():
                                fields = stat_path.read_text().rsplit(")", 1)[1].split()
                                return (int(fields[11]) + int(fields[12])) / os.sysconf(
                                    "SC_CLK_TCK"
                                )

                            before_cpu = server_cpu()

                            def browser_run():
                                command = ["node", script]
                                if not args.browser_cpu_profile:
                                    subprocess.run(
                                        command,
                                        cwd=ROOT / "gui/frontend",
                                        env=env,
                                        check=True,
                                        timeout=180,
                                    )
                                    return {}
                                browser_process = subprocess.Popen(
                                    command, cwd=ROOT / "gui/frontend", env=env
                                )
                                observed = {}
                                peak_rss = 0
                                began = time.monotonic()
                                try:
                                    while browser_process.poll() is None:
                                        stats = {}
                                        for entry in Path("/proc").iterdir():
                                            if not entry.name.isdigit():
                                                continue
                                            try:
                                                fields = (
                                                    (entry / "stat")
                                                    .read_text()
                                                    .rsplit(")", 1)[1]
                                                    .split()
                                                )
                                                stats[int(entry.name)] = (
                                                    int(fields[1]),
                                                    int(fields[19]),
                                                    int(fields[11]) + int(fields[12]),
                                                    int(fields[21]),
                                                )
                                            except (OSError, ValueError, IndexError):
                                                continue
                                        included = {browser_process.pid} | {
                                            pid
                                            for pid, value in stats.items()
                                            if (pid, value[1]) in observed
                                        }
                                        while True:
                                            children = {
                                                pid
                                                for pid, value in stats.items()
                                                if value[0] in included
                                            }
                                            if children <= included:
                                                break
                                            included |= children
                                        rss = 0
                                        for pid in included:
                                            if pid in stats:
                                                _, started, cpu, pages = stats[pid]
                                                observed[pid, started] = cpu
                                                rss += pages * os.sysconf(
                                                    "SC_PAGE_SIZE"
                                                )
                                        peak_rss = max(peak_rss, rss)
                                        if time.monotonic() - began > 180:
                                            raise subprocess.TimeoutExpired(
                                                command, 180
                                            )
                                        time.sleep(0.1)
                                    if browser_process.returncode:
                                        raise subprocess.CalledProcessError(
                                            browser_process.returncode, command
                                        )
                                finally:
                                    if browser_process.poll() is None:
                                        browser_process.kill()
                                        browser_process.wait()
                                return dict(
                                    browser_sampled_cpu_s=sum(observed.values())
                                    / os.sysconf("SC_CLK_TCK"),
                                    browser_sampled_peak_rss_sum_mib=peak_rss / 1024**2,
                                    browser_sampled_processes=len(observed),
                                )

                            observed_browser = measure(
                                label,
                                browser_run,
                            )
                            records[-1].update(observed_browser)
                            if observed_browser:
                                records[-1]["browser_sampled_cpu_percent"] = (
                                    100
                                    * observed_browser["browser_sampled_cpu_s"]
                                    / records[-1]["wall_s"]
                                )
                            records[-1]["server_cpu_s"] = server_cpu() - before_cpu
                            records[-1]["server_cpu_percent"] = (
                                100
                                * records[-1]["server_cpu_s"]
                                / records[-1]["wall_s"]
                            )
                        (work / "server-memory.txt").write_text(
                            Path(f"/proc/{process.pid}/status").read_text()
                        )
                    finally:
                        process.terminate()
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                record = transfer.read(work / "screenshots/performance.json")
                maps = transfer.read(work / "screenshots/map-performance.json")
                records.append(
                    dict(stage="map-browser-first", wall_s=maps["firstMs"] / 1000)
                )
                records.extend(
                    dict(stage="map-browser-switch", wall_s=s["ms"] / 1000)
                    for s in maps["switches"]
                )
                records.extend(
                    [
                        dict(
                            stage="scene-browser-ready", wall_s=record["readyMs"] / 1000
                        ),
                        dict(
                            stage="scene-browser-move", wall_s=record["moveMs"] / 1000
                        ),
                    ]
                )
    profile.dump_stats(str(args.output / "profile.pstats"))
    medians = {
        s: statistics.median(r["wall_s"] for r in records if r["stage"] == s)
        for s in sorted({r["stage"] for r in records})
    }
    report = dict(
        task=args.task,
        package=str(args.package),
        records=records,
        median_wall_s=medians,
        note="Peak RSS is process high-water mark. CPU 100% means one logical core. Cold is application cache only; OS cache is not flushed. Downloads: zero.",
    )
    (args.output / "benchmark.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(medians), flush=True)


if __name__ == "__main__":
    main()
