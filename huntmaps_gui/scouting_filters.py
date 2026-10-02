"""Immutable review filters over saved masks; obstruction DEM remains untouched."""

import uuid
import numpy as np
from shapely.geometry import Point
from .config import STATE
from .storage import write, read_json, locked
from .scouting_network import checked_id, load_networks
from .approach_search import terrain_properties

ASPECTS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def validate(value):
    defaults = dict(
        network_ids=[],
        kinds=["roads", "trails"],
        distance_m=None,
        height_m=None,
        elevation_m=None,
        slope_deg=None,
        aspects=[],
    )
    if set(value) - set(defaults):
        raise ValueError("Unknown filter setting")
    defaults.update(value)
    for k in ("distance_m", "height_m"):
        v = defaults[k]
        if v is not None and (not np.isfinite(v) or v < 0 or v > 100000):
            raise ValueError("Use a nonnegative bounded access limit")
    for k in ("elevation_m", "slope_deg"):
        v = defaults[k]
        if v is not None and (
            len(v) != 2 or not all(np.isfinite(n) for n in v) or v[0] > v[1]
        ):
            raise ValueError("Use ordered finite terrain limits")
    if defaults["slope_deg"] and not (
        0 <= defaults["slope_deg"][0] <= defaults["slope_deg"][1] <= 90
    ):
        raise ValueError("Slope must be 0–90 degrees")
    if not defaults["kinds"] or set(defaults["kinds"]) - {"roads", "trails"}:
        raise ValueError("Select roads, trails or both")
    if set(defaults["aspects"]) - set(ASPECTS):
        raise ValueError("Select compass aspects")
    for ident in defaults["network_ids"]:
        checked_id(ident)
    return defaults


def save(ident, value):
    from .catalog import Run

    run = Run(ident)
    settings = validate(value)
    _, sources = load_networks(
        settings["network_ids"], run.config["epsg"], settings["kinds"]
    )
    profile = dict(
        version=1,
        id=uuid.uuid4().hex,
        run_id=ident,
        settings=settings,
        sources=sources,
        dem_sha256=run.hashes[str(run.dem_path.resolve())],
    )
    with locked(STATE / "maintenance"):
        write(STATE / "filter-profiles" / f"{profile['id']}.json", profile)
    return profile


def load(ident, run_id):
    p = read_json(STATE / "filter-profiles" / f"{checked_id(ident)}.json")
    if not p or p.get("version") != 1 or p["run_id"] != run_id:
        raise ValueError("Filter profile belongs to another run")
    return p


def terrain_mask(dem, gt, settings):
    slope, aspect = terrain_properties(dem, abs(gt[1]))
    mask = np.ones(dem.shape, dtype=bool)
    for key, a in [("elevation_m", dem), ("slope_deg", slope)]:
        if settings[key] is not None:
            low, high = settings[key]
            mask &= np.isfinite(a) & (a >= low) & (a <= high)
    if settings["aspects"]:
        sectors = np.floor(((np.nan_to_num(aspect) + 22.5) % 360) / 45).astype(int)
        mask &= np.isfinite(aspect) & np.isin(
            sectors, [ASPECTS.index(a) for a in settings["aspects"]]
        )
    return mask


def access_evidence(point, lines, dem, gt, settings, index=None):
    if not lines:
        return dict(
            status="unknown",
            reason="No selected mapped network coverage",
            distance_m=None,
            height_m=None,
        )
    p = Point(point)
    candidates = (
        lines
        if index is None
        else [lines[int(i)] for i in index.query_nearest(p, all_matches=True)]
    )
    nearest = min(
        (line.interpolate(line.project(p)) for line in candidates),
        key=lambda q: (q.distance(p), q.x, q.y),
    )
    distance = nearest.distance(p)

    def elevation(q):
        c = int(np.floor((q[0] - gt[0]) / gt[1]))
        r = int(np.floor((q[1] - gt[3]) / gt[5]))
        if 0 <= r < dem.shape[0] and 0 <= c < dem.shape[1] and np.isfinite(dem[r, c]):
            return float(dem[r, c])

    z, e = elevation(point), elevation((nearest.x, nearest.y))
    height = max(0, z - e) if z is not None and e is not None else None
    status = "qualifies"
    if settings["distance_m"] is not None and distance > settings["distance_m"]:
        status = "excluded"
    if settings["height_m"] is not None:
        if height is None and status != "excluded":
            status = "unknown"
        elif height is not None and height > settings["height_m"]:
            status = "excluded"
    return dict(
        status=status,
        distance_m=distance,
        height_m=height,
        nearest=[nearest.x, nearest.y],
        reason="Positive elevation above nearest mapped line point; not cumulative approach gain",
    )


class FilteredRun:
    def __init__(self, run, profile):
        self.run, self.profile = run, profile
        self.settings = profile["settings"]
        self.dem_array = run.dem.ReadAsArray().astype(float)
        nodata = run.dem.GetRasterBand(1).GetNoDataValue()
        if nodata is not None:
            self.dem_array[self.dem_array == nodata] = np.nan
        self.matching = terrain_mask(
            self.dem_array, run.dem.GetGeoTransform(), self.settings
        )
        if profile.get("dem_sha256") != run.hashes[str(run.dem_path.resolve())]:
            raise ValueError("Filter terrain changed; explicitly apply a new profile")
        self.lines, self.network_sources = load_networks(
            self.settings["network_ids"], run.config["epsg"], self.settings["kinds"]
        )
        from shapely.strtree import STRtree

        self.network_index = STRtree(self.lines) if self.lines else None
        if self.network_sources != profile.get("sources", []):
            raise ValueError("Filter network changed; explicitly apply a new profile")

    def __getattr__(self, name):
        return getattr(self.run, name)

    def mask(self, ident):
        mask, check = self.run.mask(ident)
        return mask & self.matching, dict(check, filter_profile=self.profile["id"])

    def results(self, ids):
        area = abs(self.dem.GetGeoTransform()[1] * self.dem.GetGeoTransform()[5]) / 1e6
        values = []
        for order, ident in enumerate(ids):
            p = self.run.points[ident]
            if ident in getattr(self.run, "working", {}):
                from glassing.transfer import project

                current = self.run.working[ident]
                x, y = project(4326, self.config["epsg"])(
                    current["longitude"], current["latitude"]
                )
                p = dict(p, x=x, y=y)
            original, _ = self.run.mask(ident)
            matching = original & self.matching
            access = access_evidence(
                (p["x"], p["y"]),
                self.lines,
                self.dem_array,
                self.dem.GetGeoTransform(),
                self.settings,
                self.network_index,
            )
            enabled = (
                self.settings["distance_m"] is not None
                or self.settings["height_m"] is not None
            )
            values.append(
                dict(
                    id=ident,
                    original_km2=float(original.sum() * area),
                    matching_km2=float(matching.sum() * area),
                    access=access,
                    qualifies=not enabled or access["status"] == "qualifies",
                    order=order,
                )
            )
        values.sort(key=lambda p: (not p["qualifies"], -p["matching_km2"], p["order"]))
        return dict(
            profile=self.profile, candidates=values, sources=self.network_sources
        )


def sampling_exclusion(config, settings, output):
    """Add one observer-only exclusion file; leave input/target/terrain domains intact."""
    import json
    from pathlib import Path
    from osgeo import gdal, ogr, osr
    from shapely.geometry import shape, mapping, box
    from shapely.ops import transform, unary_union
    from glassing.transfer import project, source, polygon

    s = validate(settings)
    if s["distance_m"] is None and s["height_m"] is None:
        raise ValueError("Enable an access limit for constrained sampling")
    area = polygon(config["observer_polygon"], config["epsg"])
    lines, sources = load_networks(s["network_ids"], config["epsg"], s["kinds"])
    if not lines:
        raise ValueError(
            "Observer sampling has unknown network coverage; import/acquire lines first"
        )
    from shapely.strtree import STRtree

    index = STRtree(lines)
    res = config["resolution_m"]
    import math

    xmin, ymin, xmax, ymax = area.bounds
    bounds = (
        math.floor(xmin / res) * res,
        math.floor(ymin / res) * res,
        math.ceil(xmax / res) * res,
        math.ceil(ymax / res) * res,
    )
    width = int(np.ceil((bounds[2] - bounds[0]) / res))
    height = int(np.ceil((bounds[3] - bounds[1]) / res))
    if width * height > config["max_cells"]:
        raise ValueError("Observer eligibility grid exceeds cell limit")
    ds = gdal.Warp(
        "",
        str(source(config["data"]["dem"])),
        format="MEM",
        dstSRS=f"EPSG:{config['epsg']}",
        outputBounds=[
            bounds[0],
            bounds[3] - height * res,
            bounds[0] + width * res,
            bounds[3],
        ],
        width=width,
        height=height,
        resampleAlg="bilinear",
        dstNodata=-9999,
    )
    dem = ds.ReadAsArray().astype(float)
    dem[dem == -9999] = np.nan
    gt = ds.GetGeoTransform()
    excluded = np.zeros(dem.shape, dtype="uint8")
    for r in range(height):
        for c in range(width):
            p = (gt[0] + (c + 0.5) * res, gt[3] + (r + 0.5) * gt[5])
            if (
                area.covers(Point(p))
                and access_evidence(p, lines, dem, gt, s, index)["status"]
                != "qualifies"
            ):
                excluded[r, c] = 1
    if excluded.all():
        raise ValueError(
            "Access filters exclude all observers; relax filters or inspect mapped coverage"
        )
    raster = gdal.GetDriverByName("MEM").Create("", width, height, 1, gdal.GDT_Byte)
    raster.SetGeoTransform(gt)
    raster.SetProjection(ds.GetProjection())
    raster.GetRasterBand(1).WriteArray(excluded)
    vector = ogr.GetDriverByName("Memory").CreateDataSource("")
    layer = vector.CreateLayer("exclusions", srs=ds.GetSpatialRef())
    layer.CreateField(ogr.FieldDefn("value", ogr.OFTInteger))
    gdal.Polygonize(raster.GetRasterBand(1), None, layer, 0, [])
    shapes = [
        shape(json.loads(f.GetGeometryRef().ExportToJson()))
        for f in layer
        if f.GetField("value") == 1
    ]
    if shapes:
        excluded_geometry = unary_union(shapes).intersection(area)
        write(
            output,
            dict(
                type="Feature",
                geometry=mapping(
                    transform(project(config["epsg"], 4326), excluded_geometry)
                ),
                properties=dict(
                    role="observer eligibility only", settings=s, sources=sources
                ),
            ),
        )
        return str(Path(output).resolve())
    return None
