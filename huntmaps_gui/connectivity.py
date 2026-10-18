"""Disposable, unweighted connection evidence. Never changes analysis or decisions."""

import json
import math
import time
from pathlib import Path
import numpy as np
from osgeo import gdal, ogr
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from shapely.geometry import Point, box, shape, mapping, GeometryCollection
from shapely.ops import transform, unary_union
from shapely.prepared import prep
from .config import STATE
from .storage import read_json, write
from .approach_search import (
    Grid,
    RESOLUTION,
    MAX_CELLS,
    departures,
    network_paths,
    terrain_properties,
    implementation,
)
from .approach_service import digest, geometry
from .scouting_network import file_identity, load_networks, checked_id
from glassing.transfer import project

VERSION = "terrain-connection-v1"
ZERO = dict(slope=0, gain=0, tree=0, shrub=0)


def limit(value):
    if (
        type(value) not in (float, int)
        or not math.isfinite(value)
        or not 0 < value <= 35
    ):
        raise ValueError("Choose a modeled slope limit above zero and up to 35 degrees")
    return value


class ConnectionGrid(Grid):
    """Same hard edges as Grid. Convex domains need no per-edge geometry queries."""

    def __init__(self, dem, origin, area, exclusions, maximum):
        domain = area.difference(exclusions)
        empty = np.zeros_like(dem)
        convex = domain.equals(domain.convex_hull)
        if dem.size > MAX_CELLS or min(dem.shape) < 2:
            raise ValueError("Travel grid exceeds limits or is too small")
        import shapely

        self.dem, self.tree, self.shrub = dem, empty, empty
        self.origin, self.resolution, self.maximum = origin, RESOLUTION, maximum
        self.domain, self.prepared = domain, prep(domain)
        self.search_area = area
        self.slope, _ = terrain_properties(dem, RESOLUTION)
        rows, cols = np.indices(dem.shape)
        self.valid = (
            np.isfinite(dem) & np.isfinite(self.slope) & (self.slope <= maximum)
        )
        self.valid &= shapely.covers(
            domain,
            shapely.points(
                origin[0] + (cols + 0.5) * RESOLUTION,
                origin[1] - (rows + 0.5) * RESOLUTION,
            ),
        )
        self.edge_directions = ((0, 1), (1, -1), (1, 0), (1, 1))
        self.edge_valid = []
        for dr, dc in self.edge_directions:
            allowed = np.zeros(dem.shape, dtype=bool)
            a, b = slices(dem.shape, dr, dc)
            good = self.valid[a] & self.valid[b]
            if dr and dc:
                good &= self.valid[(a[0], b[1])] & self.valid[(b[0], a[1])]
            allowed[a] = good
            if not convex:
                rr, cc = np.nonzero(allowed)
                source = np.column_stack(
                    (
                        origin[0] + (cc + 0.5) * RESOLUTION,
                        origin[1] - (rr + 0.5) * RESOLUTION,
                    )
                )
                target = np.column_stack(
                    (
                        origin[0] + (cc + dc + 0.5) * RESOLUTION,
                        origin[1] - (rr + dr + 0.5) * RESOLUTION,
                    )
                )
                allowed[rr, cc] = shapely.covers(
                    domain, shapely.linestrings(np.stack((source, target), axis=1))
                )
            self.edge_valid.append(allowed)


def slices(shape_, dr, dc):
    h, w = shape_
    return (
        (slice(0, h - dr), slice(max(0, -dc), min(w, w - dc))),
        (slice(dr, h), slice(max(0, dc), min(w, w + dc))),
    )


def component_labels(grid):
    """Undirected hard connectivity; uphill costs cannot affect feasibility."""
    ids = np.arange(grid.dem.size).reshape(grid.dem.shape)
    sources, targets = [], []
    for direction, (dr, dc) in enumerate(grid.edge_directions):
        a, b = slices(grid.dem.shape, dr, dc)
        step = np.degrees(
            np.arctan2(
                np.abs(grid.dem[b] - grid.dem[a]),
                grid.resolution * (math.sqrt(2) if dr and dc else 1),
            )
        )
        good = grid.edge_valid[direction][a] & (step <= grid.maximum)
        sources.append(ids[a][good])
        targets.append(ids[b][good])
    source, target = np.concatenate(sources), np.concatenate(targets)
    graph = coo_matrix(
        (np.ones(len(source), dtype="u1"), (source, target)),
        shape=(grid.dem.size, grid.dem.size),
    ).tocsr()
    return connected_components(graph, directed=False, return_labels=True)[1].reshape(
        grid.dem.shape
    )


def connection(grid, lines, target, start=None, pinned=None):
    """No weighted terrain search, route reconstruction, or alternatives."""
    if not grid.domain.covers(Point(target)):
        excluded = hasattr(grid, "search_area") and grid.search_area.covers(
            Point(target)
        )
        return dict(
            status="no_connection",
            reason="excluded" if excluded else "outside_boundary",
            message=(
                "This setup lies inside an area to avoid."
                if excluded
                else "This setup is outside the usable search boundary."
            ),
        )
    cell = grid.cell(target)
    if not grid.inside(cell):
        r, c = cell
        in_grid = 0 <= r < grid.dem.shape[0] and 0 <= c < grid.dem.shape[1]
        slope = grid.slope[cell] if in_grid else np.nan
        reason = (
            "missing_terrain"
            if not in_grid or not np.isfinite(grid.dem[cell]) or not np.isfinite(slope)
            else "endpoint_slope" if slope > grid.maximum else "endpoint_cell_boundary"
        )
        return dict(
            status="unavailable" if reason == "missing_terrain" else "no_connection",
            reason=reason,
            message=(
                "Terrain at the setup exceeds this modeled slope limit."
                if reason == "endpoint_slope"
                else (
                    "Terrain near the setup is missing or unsupported."
                    if reason == "missing_terrain"
                    else "The setup cannot connect to a usable terrain cell within this boundary and its areas to avoid."
                )
            ),
        )
    if grid.segment(grid.xy(cell), target, ZERO) is None:
        return dict(
            status="no_connection",
            reason="endpoint_connector",
            message="The exact setup cannot connect to its terrain cell under these constraints.",
        )
    samples = departures(lines, target, pinned)
    if not samples:
        return dict(
            status="no_connection",
            reason="no_departures",
            message="No eligible mapped departure lies within one mile inside this boundary.",
        )
    if start is not None:
        samples = list(network_paths(grid, lines, samples, start, ZERO))
        if not samples:
            return dict(
                status="no_connection",
                reason="network_start",
                message="The selected network start does not connect to an eligible departure.",
            )
    labels = component_labels(grid)
    for point in samples:
        node = grid.cell(point)
        if (
            grid.inside(node)
            and labels[node] == labels[cell]
            and grid.segment(point, grid.xy(node), ZERO) is not None
        ):
            return dict(
                status="connection_found",
                reason="connected",
                message="Modeled connection found.",
            )
    return dict(
        status="no_connection",
        reason="disconnected",
        message="Terrain does not connect this setup to an eligible mapped departure within the current boundary and exclusions.",
    )


class Terrain:
    def __init__(self, run):
        self.run = run
        run.validate(run.dem_path)
        self.ds = run.dem
        gt = self.ds.GetGeoTransform()
        if gt[2] or gt[4] or gt[1] <= 0 or gt[5] >= 0:
            raise ValueError("Connection screening needs north-up metric terrain")
        self.xy = project(4326, run.config["epsg"])
        self.ll = project(run.config["epsg"], 4326)
        self.footprint = box(
            gt[0],
            gt[3] + self.ds.RasterYSize * gt[5],
            gt[0] + self.ds.RasterXSize * gt[1],
            gt[3],
        )
        band = self.ds.GetRasterBand(1)
        valid = np.isfinite(band.ReadAsArray()) & (band.GetMaskBand().ReadAsArray() > 0)
        if not valid.all():
            mask = gdal.GetDriverByName("MEM").Create(
                "", self.ds.RasterXSize, self.ds.RasterYSize, 1, gdal.GDT_Byte
            )
            mask.SetGeoTransform(gt)
            mask.SetProjection(self.ds.GetProjection())
            mask.GetRasterBand(1).WriteArray(valid.astype("u1"))
            vector = ogr.GetDriverByName("Memory").CreateDataSource("")
            layer = vector.CreateLayer("valid", geom_type=ogr.wkbPolygon)
            gdal.Polygonize(mask.GetRasterBand(1), mask.GetRasterBand(1), layer, -1, [])
            self.footprint = unary_union(
                [shape(json.loads(f.GetGeometryRef().ExportToJson())) for f in layer]
            )

    def proposal(self, point):
        target = Point(self.xy(point["longitude"], point["latitude"]))
        area = target.buffer(2000, resolution=48).intersection(self.footprint)
        # The proposal is published in WGS84 before approach calculation. Preserve
        # that same round trip, including grid-origin/ceil effects at native edges.
        return transform(self.xy, transform(self.ll, area))

    def raster(self, area):
        left, bottom, right, top = area.bounds
        width, height = math.ceil((right - left) / 20), math.ceil((top - bottom) / 20)
        if width * height > MAX_CELLS or min(width, height) < 2:
            raise ValueError("Boundary exceeds the supported travel grid limits")
        ds = gdal.Warp(
            "",
            self.ds,
            format="MEM",
            outputBounds=[left, top - height * 20, left + width * 20, top],
            width=width,
            height=height,
            dstSRS=f"EPSG:{self.run.config['epsg']}",
            resampleAlg="bilinear",
            dstNodata=-9999,
        )
        dem = ds.ReadAsArray().astype(float)
        dem[dem == -9999] = np.nan
        return dem, (left, top)


def inventory():
    result = []
    for path in sorted((STATE / "networks").glob("*/network.json")):
        value = read_json(path)
        originals = sorted(path.parent.glob("original.*"))
        result.append(
            dict(
                metadata=file_identity(path),
                original=file_identity(originals[0]) if originals else None,
                id=value["id"],
                kind=value["kind"],
                sha256=value["sha256"],
                coverage=value.get("coverage"),
                retrieved_utc=value.get("retrieved_utc", ""),
            )
        )
    return result


def snapshot(run, maximum=None):
    from .working_waypoints import DisplayRun
    from .manual_observers import records as manual_records
    from .approach_review import records
    from .workflow import point

    r = DisplayRun(run, None)
    r.validate(r.dem_path)
    review = records(run) or {}
    defaults = review.get("defaults", {})
    maximum = limit(
        defaults.get("maximum_slope_deg", 25) if maximum is None else maximum
    )
    rows = []
    xy = project(4326, r.config["epsg"])
    for cid in sorted(set(r.points) | set(r.working) | set(manual_records(run))):
        current = point(run, cid, run_data=r)
        draft = review.get("drafts", {}).get(cid, {})
        if draft.get("point") != current:
            draft = {}
        settings = dict(
            maximum_slope_deg=maximum,
            kinds=defaults.get("kinds", ["roads", "trails"]),
            exclusions=[],
            travel_area=None,
            network_ids=[],
            start=None,
            pinned=None,
        )
        for key in settings:
            if key in draft:
                settings[key] = draft[key]
        original = r.points.get(cid, {})
        ranking = {
            k: original[k]
            for k in (
                "id",
                "x",
                "y",
                "raw_km2",
                "matching_km2",
                "foreground_category",
                "standing_eligible",
                "group",
            )
            if k in original
        }
        ranking["id"] = cid
        if cid in r.working:
            metrics = r.working[cid].get("metrics", {})
            for key in ("raw_km2", "matching_km2", "standing_eligible"):
                if key in metrics:
                    ranking[key] = metrics[key]
        if cid in r.working or "x" not in ranking or "y" not in ranking:
            ranking["x"], ranking["y"] = xy(current["longitude"], current["latitude"])
        rows.append(dict(point=current, settings=settings, ranking=ranking))
    from glassing.acquire import digest as file_digest

    spec = dict(
        version=VERSION,
        implementation=implementation(),
        screen_implementation=file_digest(__file__),
        run_id=run,
        maximum_slope_deg=maximum,
        dem=[r.hashes[str(r.dem_path.resolve())], file_identity(r.dem_path)],
        epsg=r.config["epsg"],
        recommendation_count=r.config.get("search", {}).get("recommendation_count", 20),
        separation_m=r.config.get("search", {}).get("recommendation_separation_m", 0),
        rows=rows,
        inventory=inventory(),
    )
    return json.loads(json.dumps(spec)), r


def path(token):
    return STATE / "cache/connectivity" / (checked_id(token) + ".json")


def current(run, jobs=None):
    spec, _ = snapshot(run)
    token = digest(spec)[:32]
    value = read_json(path(token)) or dict(
        id=token,
        version=VERSION,
        run_id=run,
        maximum_slope_deg=spec["maximum_slope_deg"],
        status="not_started",
        points={},
        total=len(spec["rows"]),
        completed=0,
    )
    if value.get("status") != "not_started":
        if value.get("snapshot") != spec or value.get("id") != token:
            raise ValueError("Connection cache changed; check connections again")
        if value.get("status") == "complete" and value.get("sha256") != digest(
            {k: v for k, v in value.items() if k != "sha256"}
        ):
            raise ValueError("Connection cache changed; check connections again")
        from .display_cache import touch

        touch(path(token))
    if value.get("status") == "running" and jobs is not None:
        job_id = read_json(path(token).with_suffix(".job.json"), {}).get("id")
        job = jobs.get(job_id) if job_id else None
        value = dict(value, job=job)
        if not job or job["status"] not in ("running", "cancelling"):
            value["status"] = job["status"] if job else "interrupted"
    if value.get("status") == "complete":
        from .display_cache import pin, maybe_evict

        with pin([path(token), path(token).with_suffix(".job.json")]):
            maybe_evict()
    return {k: v for k, v in value.items() if k not in ("snapshot", "sha256")}


def start(run, body, jobs):
    from .storage import locked

    with locked(STATE / "maintenance"):
        return _start(run, body, jobs)


def _start(run, body, jobs):
    if body.get("save_default"):
        if any(j["status"] in ("running", "cancelling") for j in jobs.list(False)):
            raise ValueError(
                "Wait for the active job before changing connection defaults"
            )
        from .approach_review import path as review_path, records
        from .storage import locked

        with locked(STATE / "maintenance"), locked(review_path(run)):
            review = records(run) or dict(
                version=1, revision=0, queue=[], drafts={}, active_point=None
            )
            review.setdefault("defaults", {})["maximum_slope_deg"] = limit(
                body.get("maximum_slope_deg")
            )
            review["revision"] += 1
            write(review_path(run), review)
    spec, _ = snapshot(run)
    token = digest(spec)[:32]
    cached = read_json(path(token))
    if cached and cached.get("status") == "complete":
        try:
            return current(run, jobs)
        except ValueError:
            pass  # Only this disposable display entry is regenerated.
    active = next(
        (
            j
            for j in jobs.list(False)
            if j.get("kind") == "connectivity-screen"
            and j.get("plan") == token
            and j["status"] in ("running", "cancelling")
        ),
        None,
    )
    if active:
        return dict(current(run, jobs), job=active)
    if any(j["status"] in ("running", "cancelling") for j in jobs.list(False)):
        raise ValueError("Wait for the active job before screening connections")
    from .downloads import check_space

    check_space(STATE)
    write(
        path(token),
        dict(
            id=token,
            version=VERSION,
            run_id=run,
            maximum_slope_deg=spec["maximum_slope_deg"],
            snapshot=spec,
            status="running",
            points={},
            completed=0,
            total=len(spec["rows"]),
        ),
    )
    import sys

    job = jobs.start(
        [sys.executable, "-u", "-m", "huntmaps_gui.connectivity_worker", run, token],
        "connectivity-screen",
        name=run,
        plan=token,
    )
    write(path(token).with_suffix(".job.json"), dict(id=job["id"]))
    return dict(current(run, jobs), job=job)


def select_sources(inventories, bounds, kinds, explicit):
    if explicit:
        return explicit
    result = []
    for kind in kinds:
        candidates = [s for s in inventories if s["kind"] == kind]
        covering = [
            s
            for s in candidates
            if s.get("coverage") and box(*s["coverage"]).covers(box(*bounds))
        ]
        if covering:
            result.append(
                max(covering, key=lambda s: (s["retrieved_utc"], s["id"]))["id"]
            )
        else:
            seen = set()
            for s in candidates:
                if s.get("coverage") and not box(*s["coverage"]).intersects(
                    box(*bounds)
                ):
                    continue
                if s["sha256"] not in seen:
                    result.append(s["id"])
                    seen.add(s["sha256"])
    return result


class Index:
    """Shared validated terrain/network preparation; exact local component queries."""

    def __init__(self, run, inventories):
        self.terrain = Terrain(run)
        self.inventories = inventories
        self.networks = {}
        self.errors = {}
        for item in inventories:
            try:
                self.networks[item["id"]] = load_networks(
                    [item["id"]], run.config["epsg"], [item["kind"]]
                )[0]
            except (ValueError, OSError, StopIteration) as error:
                self.errors[item["id"]] = str(error)

    def query(self, point, settings, diagnose=False):
        terrain = self.terrain
        maximum = limit(settings["maximum_slope_deg"])
        area = (
            transform(terrain.xy, geometry(settings["travel_area"]))
            if settings.get("travel_area")
            else terrain.proposal(point)
        )
        if area.is_empty or (
            not settings.get("travel_area")
            and not area.covers(
                Point(terrain.xy(point["longitude"], point["latitude"]))
            )
        ):
            return dict(
                status="unavailable",
                reason="missing_terrain",
                message="No supported obstruction terrain at this setup.",
                maximum_slope_deg=maximum,
            )
        exclusions = unary_union(
            [transform(terrain.xy, geometry(g)) for g in settings.get("exclusions", [])]
        )
        bounds = transform(terrain.ll, area).bounds
        ids = select_sources(
            self.inventories,
            bounds,
            settings.get("kinds", ["roads", "trails"]),
            settings.get("network_ids"),
        )
        known = [
            i for i in self.inventories if i["id"] in ids and i["id"] in self.networks
        ]
        coverage = all(
            any(
                s["kind"] == k
                and s.get("coverage")
                and box(*s["coverage"]).covers(box(*bounds))
                for s in known
            )
            for k in settings.get("kinds", ["roads", "trails"])
        )
        domain = area.difference(exclusions)
        lines = []
        seen = set()
        for ident in ids:
            for line in self.networks.get(ident, []):
                clipped = line.intersection(domain)
                parts = (
                    [clipped]
                    if clipped.geom_type == "LineString"
                    else list(getattr(clipped, "geoms", []))
                )
                for p in parts:
                    if (
                        p.geom_type == "LineString"
                        and not p.is_empty
                        and p.wkb not in seen
                    ):
                        lines.append(p)
                        seen.add(p.wkb)
        dem, origin = terrain.raster(area)
        target = terrain.xy(point["longitude"], point["latitude"])
        start_ = terrain.xy(*settings["start"]) if settings.get("start") else None
        pinned = terrain.xy(*settings["pinned"]) if settings.get("pinned") else None
        result = connection(
            ConnectionGrid(dem, origin, area, exclusions, maximum),
            lines,
            target,
            start_,
            pinned,
        )
        result.update(
            maximum_slope_deg=maximum,
            network_ids=ids,
            coverage_complete=coverage,
            boundary_confirmed=False,
        )
        if diagnose and result["status"] != "connection_found":
            for candidate in (30, 35):
                if candidate <= maximum:
                    continue
                other = connection(
                    ConnectionGrid(dem, origin, area, exclusions, candidate),
                    lines,
                    target,
                    start_,
                    pinned,
                )
                if other["status"] == "connection_found":
                    result.update(
                        next_limit_deg=candidate, slope_blocker_confirmed=True
                    )
                    break
        if (
            result["status"] == "no_connection"
            and not coverage
            and result["reason"] in ("disconnected", "no_departures", "network_start")
        ):
            result.update(
                status="unavailable",
                reason="network_coverage",
                message="Verified roads/trails do not cover this search boundary. Prepare sources or use Show all.",
            )
        return result


def calculate(run, token):
    began = time.perf_counter()
    value = read_json(path(token))
    spec, r = snapshot(run)
    if not value or value.get("snapshot") != spec:
        raise ValueError("Screen inputs changed; start a current screen")
    index = Index(r, spec["inventory"])
    value["recommendation_pool"] = [row["ranking"] for row in spec["rows"]]
    value["recommendation_count"] = spec["recommendation_count"]
    value["separation_m"] = spec["separation_m"]
    value["bounds"] = list(
        transform(
            index.terrain.ll,
            unary_union(
                [
                    (
                        transform(
                            index.terrain.xy, geometry(row["settings"]["travel_area"])
                        )
                        if row["settings"].get("travel_area")
                        else index.terrain.proposal(row["point"])
                    )
                    for row in spec["rows"]
                ]
            ),
        ).bounds
    )
    for i, row in enumerate(spec["rows"]):
        try:
            result = index.query(row["point"], row["settings"])
        except (ValueError, OSError, MemoryError) as error:
            result = dict(
                status="unavailable",
                reason="unsupported",
                message=str(error)
                or "Memory limit reached; narrow this search boundary.",
                maximum_slope_deg=row["settings"]["maximum_slope_deg"],
            )
        value["points"][row["point"]["id"]] = result
        value["completed"] = i + 1
        if i % 8 == 0 or i + 1 == len(spec["rows"]):
            write(path(token), value)
            print(
                f"STAGE Screening terrain connections · {i+1}/{len(spec['rows'])}",
                flush=True,
            )
    if snapshot(run)[0] != spec:
        raise ValueError("Screen inputs changed; results retained as prior evidence")
    value.update(status="complete", elapsed_s=round(time.perf_counter() - began, 3))
    value["sha256"] = digest(value)
    write(path(token), value)
    from .display_cache import changed, maybe_evict

    changed()
    maybe_evict()
    return value


def eligible(run, token):
    value = current(run)
    if value["id"] != token:
        raise ValueError("Connection screen changed; refresh recommendations")
    return {
        cid for cid, p in value["points"].items() if p["status"] == "connection_found"
    }


def diagnose(ident, jobs=None):
    from .approach_service import status

    value = status(ident, jobs)
    if value["stale"] or value.get("point_stale"):
        raise ValueError(
            "Prior comparison inputs changed; calculate current settings first"
        )
    scenario = value["scenario"]
    from .catalog import Run

    index = Index(Run(scenario["run_id"]), inventory())
    results = {}
    for row in (value.get("results") or {}).get("results", []):
        if not row["alternatives"]:
            results[row["point"]["id"]] = index.query(row["point"], scenario, True)
    return dict(scenario=ident, points=results)
