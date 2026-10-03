"""GUI working locations and immutable, terrain-only mask revisions.

Workers write cache products only. The server commits a revision only after its
recorded job completes, so cancelled/stale workers cannot move a waypoint.
"""

import argparse
import fcntl
import hashlib
import json
import math
import re
import resource
import signal
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
import numpy as np
from osgeo import gdal
from glassing import core
from .catalog import STATE, Run, read, check_hash, collection
from .jobs import write, ACTIVE
from .storage import locked as file_locked
from . import first_person as fp, manual_observers as manual

VERSION = 1


def home(ident):
    Run(ident)
    return STATE / "working-waypoints" / ident


@contextmanager
def locked(ident):
    folder = home(ident)
    with file_locked(folder / "state.json"):
        yield folder


def state(folder):
    return read(folder / "state.json", dict(overrides={}, pending={}))


def original(ident, key):
    if key.startswith("manual-"):
        p = manual.records(ident).get(key)
        if not p:
            raise ValueError("Unknown nearby waypoint.")
        return p["anchor"], p
    r = Run(ident)
    p = r.candidate(key)
    return key, p


def signature(r, pose):
    target = r.analysis / "target.tif"
    r.validate(target)
    p = r.points[pose["anchor"]]
    spec = dict(
        version=VERSION,
        run_id=r.id,
        anchor=pose["anchor"],
        x=p["x"] + pose["east_m"],
        y=p["y"] + pose["north_m"],
        dem_sha256=r.hashes[str(r.dem_path)],
        target_sha256=r.hashes[str(target)],
        radius_m=r.config["radius_m"],
        eye_m=r.config["eye_m"],
        target_m=r.config["target_m"],
        curvature=r.config["curvature"],
        engine_sha256=core.digest(core.__file__),
        gdal_version=gdal.__version__,
    )
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest(), spec


def cached(folder, key, r):
    if not re.fullmatch("[a-f0-9]{64}", key or ""):
        raise ValueError("Invalid working mask revision.")
    path = folder / "cache" / key / "mask.tif"
    meta = read(path.parent / "result.json")
    if not meta:
        return None
    if (
        hashlib.sha256(json.dumps(meta["spec"], sort_keys=True).encode()).hexdigest()
        != key
    ):
        raise ValueError(
            "Working mask provenance changed. Restore or retry the update."
        )
    st = path.stat()
    check_hash(str(path), st.st_mtime_ns, st.st_size, meta["mask_sha256"])
    ds = gdal.Open(str(path))
    if (
        ds is None
        or ds.GetGeoTransform() != r.dem.GetGeoTransform()
        or not ds.GetSpatialRef().IsSame(r.dem.GetSpatialRef())
        or (ds.RasterXSize, ds.RasterYSize) != (r.dem.RasterXSize, r.dem.RasterYSize)
    ):
        raise ValueError("Working terrain mask is not aligned with the saved DEM.")
    if (
        meta["spec"]["dem_sha256"] != r.hashes[str(r.dem_path)]
        or meta["spec"]["target_sha256"] != r.hashes[str(r.analysis / "target.tif")]
    ):
        raise ValueError("Working mask sources no longer match this run.")
    return meta


def reconcile(folder, ident, jobs):
    data = state(folder)
    records = {j["id"]: j for j in jobs.list(include_logs=False)}
    changed = False
    for key, pending in list(data["pending"].items()):
        j = records.get(pending["job_id"])
        if j and j["status"] == "complete":
            result = cached(folder, pending["revision"], Run(ident))
            if not result:
                raise ValueError(
                    "Completed waypoint update has no validated mask. Restore or retry the update."
                )
            data["overrides"][key] = dict(
                pending["proposal"],
                revision=pending["revision"],
                metrics=result["metrics"],
                terrain=result["spec"],
            )
            del data["pending"][key]
            changed = True
        elif j and j["status"] not in ACTIVE:
            # Retain an actionable failure record, never its uncommitted coordinates.
            changed = changed or pending.get("status") != j["status"]
            pending["status"] = j["status"]
            pending["error"] = "Waypoint unchanged. Retry Update waypoint; " + j.get(
                "error", j["stage"]
            )
    if changed:
        write(folder / "state.json", data)
    return data


def snapshot(ident, jobs):
    # Reading never publishes a completed job or creates a state directory.
    return state(home(ident))


def start(ident, key, body, jobs):
    anchor, p = original(ident, key)
    if body.get("scene_key"):
        meta = fp.scene(ident, key)
        if meta.get("key") != body["scene_key"]:
            raise ValueError(
                "Scene changed; reopen the current view before moving a waypoint"
            )
        if meta.get("scene_signature"):
            anchor = key
    pose = fp.observer(ident, anchor, body)
    f = manual.fields(
        dict(
            name=body.get("name") or p.get("name", key),
            notes=body.get("notes", p.get("notes", "")),
            status="needs inspection",
        )
    )
    r = Run(ident)
    revision, spec = signature(r, pose)
    proposal = dict(
        pose,
        **f,
        id=key,
        run_id=ident,
        kind="working-waypoint",
        analysis="Calculated terrain-only visibility",
        access="Access, footing and current field sightlines unverified",
        foliage_assumption="dense",
        foliage_radius_m=120,
    )
    with file_locked(STATE / "maintenance"), jobs.lock, locked(ident) as folder:
        with jobs.lock:
            if any(j["status"] in ACTIVE for j in jobs.list(include_logs=False)):
                raise ValueError(
                    "Another job is running. Wait or cancel it, then Update waypoint."
                )
            data = reconcile(folder, ident, jobs)
            result = cached(folder, revision, r)
            if result:
                record = dict(
                    proposal,
                    revision=revision,
                    metrics=result["metrics"],
                    terrain=result["spec"],
                )
                data["overrides"][key] = record
                data["pending"].pop(key, None)
                write(folder / "state.json", data)
                return dict(status="complete", cached=True, waypoint=record)
            token = uuid.uuid4().hex
            write(
                folder / "tasks" / (token + ".json"),
                dict(
                    run_id=ident,
                    key=key,
                    proposal=proposal,
                    revision=revision,
                    spec=spec,
                ),
            )
            job = jobs.start(
                [
                    sys.executable,
                    "-u",
                    "-m",
                    "huntmaps_gui.working_waypoints",
                    ident,
                    token,
                    "--state",
                    str(STATE),
                ],
                "waypoint-update",
                name=ident,
                plan=token,
            )
            data["pending"][key] = dict(
                job_id=job["id"], proposal=proposal, revision=revision, status="running"
            )
            write(folder / "state.json", data)
            return dict(status="running", job=job)


def restore(ident, key, jobs):
    original(ident, key)
    with file_locked(STATE / "maintenance"), jobs.lock, locked(ident) as folder:
        data = state(folder)
        pending = data["pending"].pop(key, None)
        if pending:
            j = next(
                (
                    j
                    for j in jobs.list(include_logs=False)
                    if j["id"] == pending["job_id"]
                ),
                None,
            )
            if j and j["status"] == "running":
                jobs.cancel(j["id"])
        data["overrides"].pop(key, None)
        write(folder / "state.json", data)
    return dict(restored=key)


def review(ident, key, body, jobs):
    with file_locked(STATE / "maintenance"), jobs.lock, locked(ident) as folder:
        data = reconcile(folder, ident, jobs)
        if key not in data["overrides"]:
            raise ValueError("This setup has no working waypoint.")
        data["overrides"][key].update(manual.fields(body))
        write(folder / "state.json", data)
        return data["overrides"][key]


class DisplayRun:
    """Explicit working-view adapter; historical Run APIs remain unchanged."""

    def __init__(self, ident, jobs):
        self.base = Run(ident)
        self.working = snapshot(ident, jobs)["overrides"]
        self.working_ids = set(self.working)

    def __getattr__(self, name):
        return getattr(self.base, name)

    def visibility_path(self, key):
        if key not in self.working:
            return self.base.visibility_path(key)
        folder = home(self.id)
        cached(folder, self.working[key]["revision"], self.base)
        return folder / "cache" / self.working[key]["revision"] / "mask.tif"

    def mask(self, key):
        if key not in self.working:
            return self.base.mask(key)
        path = self.visibility_path(key)
        mask = gdal.Open(str(path)).ReadAsArray() == 1
        if (
            abs(
                float(mask.sum())
                * abs(self.dem.GetGeoTransform()[1] * self.dem.GetGeoTransform()[5])
                / 1e6
                - self.working[key]["metrics"]["raw_km2"]
            )
            > 1e-9
        ):
            raise ValueError("Working visible area differs from its mask.")
        return mask, dict(
            mapped_km2=self.working[key]["metrics"]["raw_km2"],
            revision=self.working[key]["revision"],
            terrain_only=True,
        )

    def candidate(self, key, include_mask=False):
        if key not in self.working:
            if key.startswith("manual-"):
                p = manual.records(self.id).get(key)
                if not p:
                    raise ValueError("Unknown manual waypoint")
                return p
            return self.base.candidate(key, include_mask)
        p = self.working[key]
        anchor, old = original(self.id, key)
        return dict(
            id=key,
            name=p["name"],
            longitude=p["longitude"],
            latitude=p["latitude"],
            parent=old.get("parent", ""),
            neighborhood=old.get("neighborhood"),
            metrics=p["metrics"],
            foreground={},
            access=p["access"],
            obstruction="Terrain-only view; branches, understory and field sightlines remain unverified.",
            obstruction_scenarios=[],
            diagnostics=p,
            alignment=self.mask(key)[1] if include_mask else None,
            has_visibility=True,
            working_revision=p["revision"],
            original_analysis=old,
            anchor=anchor,
        )

    def sectors(self, key):
        return collection([]) if key in self.working else self.base.sectors(key)


def calculate(ident, token):
    started = time.monotonic()
    if not re.fullmatch("[a-f0-9]{32}", token):
        raise ValueError("Invalid waypoint task.")
    folder = home(ident)
    task = read(folder / "tasks" / (token + ".json"))
    if not task or task["run_id"] != ident:
        raise ValueError("Unknown waypoint update task.")
    print("STAGE Validating cached terrain and target sources", flush=True)
    r = Run(ident)
    pose = fp.observer(
        ident,
        task["proposal"]["anchor"],
        dict(
            observer_east_m=task["proposal"]["east_m"],
            observer_north_m=task["proposal"]["north_m"],
        ),
    )
    key, spec = signature(r, pose)
    if key != task["revision"] or spec != task["spec"]:
        raise ValueError(
            "Waypoint update sources or settings changed. Retry the update."
        )
    if cached(folder, key, r):
        print("STAGE Validated cached terrain view reused", flush=True)
        return
    dest = folder / "cache" / key
    temp = folder / "partials" / token
    temp.mkdir(parents=True, exist_ok=True)
    a, gt, _ = core.validate(r.dem)
    target_ds = gdal.Open(str(r.analysis / "target.tif"))
    if (
        target_ds.GetGeoTransform() != gt
        or not target_ds.GetSpatialRef().IsSame(r.dem.GetSpatialRef())
        or target_ds.ReadAsArray().shape != a.shape
    ):
        raise ValueError("Target mask is not aligned to terrain.")
    target = target_ds.ReadAsArray() == 1
    print("STAGE Calculating terrain visibility for the updated observer", flush=True)
    vs = core.viewshed(
        r.dem,
        temp / "viewshed.tif",
        spec["x"],
        spec["y"],
        spec["radius_m"],
        spec["eye_m"],
        spec["target_m"],
        spec["curvature"],
    )
    area, bands, visible = core.score_mask(
        vs, gt, a.shape, target, spec["x"], spec["y"], spec["radius_m"]
    )
    vg = vs.GetGeoTransform()
    col = round((vg[0] - gt[0]) / gt[1])
    row = round((vg[3] - gt[3]) / gt[5])
    mask = np.zeros(a.shape, dtype=np.uint8)
    mask[row : row + visible.shape[0], col : col + visible.shape[1]] = visible
    print("STAGE Clipping targets and writing aligned map mask", flush=True)
    path = temp / "mask.tif"
    out = gdal.GetDriverByName("GTiff").Create(
        str(path),
        a.shape[1],
        a.shape[0],
        1,
        gdal.GDT_Byte,
        options=["COMPRESS=DEFLATE"],
    )
    out.SetGeoTransform(gt)
    out.SetProjection(r.dem.GetProjection())
    out.GetRasterBand(1).SetNoDataValue(255)
    out.GetRasterBand(1).WriteArray(mask)
    out = None
    vs = None
    if np.any((mask == 1) & ~target):
        raise ValueError("Updated mask exceeds target eligibility.")
    tree = r.cover("tree")
    shrub = r.cover("shrub")
    pixel = abs(gt[1] * gt[5]) / 1e6
    m = mask == 1
    metrics = dict(
        raw_km2=area,
        tree_lt10_km2=float((m & (tree < 0.1)).sum() * pixel),
        tree_10to40_km2=float((m & (tree >= 0.1) & (tree < 0.4)).sum() * pixel),
        tree_ge40_km2=float((m & (tree >= 0.4)).sum() * pixel),
        tree_unknown_km2=float((m & ~np.isfinite(tree)).sum() * pixel),
        shrub_gt30_km2=float((m & (shrub > 0.3)).sum() * pixel),
    )
    write(
        temp / "result.json",
        dict(
            spec=spec,
            metrics=metrics,
            bands=bands,
            mask_sha256=core.digest(path),
            worker_wall_s=time.monotonic() - started,
            worker_peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            / 1024,
        ),
    )
    if (
        sum(
            p.stat().st_size
            for sub in ["cache", "partials"]
            for p in (folder / sub).rglob("*")
            if p.is_file()
        )
        > 800_000_000
    ):
        raise ValueError("Waypoint output budget exceeded.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp.replace(dest)
    print(
        "STAGE Updated terrain view ready; awaiting successful job completion",
        flush=True,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("token")
    ap.add_argument("--state", type=Path, default=STATE)
    args = ap.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (1536 * 1024**2, 1536 * 1024**2))
    signal.signal(
        signal.SIGALRM,
        lambda *_: (_ for _ in ()).throw(
            ValueError(
                "Waypoint update exceeded 900 seconds; previous waypoint retained."
            )
        ),
    )
    signal.alarm(900)
    try:
        from dataclasses import replace
        from .config import configured, current

        with configured(replace(current(), state_dir=Path(args.state))):
            calculate(args.run, args.token)
    except Exception as e:
        print("GUI JOB:", e, flush=True)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())


def publish_completed(jobs):
    """Called at startup/completion under maintenance then job locks."""
    with file_locked(STATE / "maintenance"), jobs.lock:
        for path in (STATE / "working-waypoints").glob("*/state.json"):
            try:
                with locked(path.parent.name) as folder:
                    reconcile(folder, path.parent.name, jobs)
            except (ValueError, OSError, KeyError) as error:
                message = f"Waypoint publication needs recovery ({path}): {error}"
                if message not in jobs.storage_errors:
                    jobs.storage_errors.append(message)
