"""Read-only prepared-pack adapter. Never invokes an owner API or worker."""

from functools import lru_cache
from datetime import date as Date
import json
import math
from pathlib import Path
import re

import numpy as np
from osgeo import gdal, ogr, osr
from pyproj import Transformer
from scipy.ndimage import map_coordinates
from shapely.geometry import shape, mapping, box, Point, LineString
from shapely.ops import transform, unary_union

from .storage import read, verify, identity, digest

TO_METRIC = Transformer.from_crs(4326, 32613, always_xy=True)
TO_WGS = Transformer.from_crs(32613, 4326, always_xy=True)


def project(g):
    return transform(TO_METRIC.transform, g)


def geographic(g):
    return transform(TO_WGS.transform, g)


def feature(g, **props):
    return dict(type="Feature", geometry=mapping(geographic(g)), properties=props)


def collection(features):
    return dict(type="FeatureCollection", features=features)


def raster_mask(geometry, ds):
    out = gdal.GetDriverByName("MEM").Create(
        "", ds.RasterXSize, ds.RasterYSize, 1, gdal.GDT_Byte
    )
    out.SetGeoTransform(ds.GetGeoTransform())
    out.SetProjection(ds.GetProjection())
    vector = ogr.GetDriverByName("Memory").CreateDataSource("")
    srs = osr.SpatialReference()
    srs.ImportFromWkt(ds.GetProjection())
    layer = vector.CreateLayer("mask", srs=srs, geom_type=ogr.wkbUnknown)
    f = ogr.Feature(layer.GetLayerDefn())
    f.SetGeometry(ogr.CreateGeometryFromJson(json.dumps(mapping(geometry))))
    layer.CreateFeature(f)
    gdal.RasterizeLayer(out, [1], layer, burn_values=[1])
    return out.ReadAsArray().astype(bool)


def date_match(text, date):
    """USFS MM/DD-MM/DD intervals, including year wrapping. Unknown != closed."""
    if not text:
        return None
    if str(text).lower().strip() == "yearlong":
        return True
    dates = re.findall(r"(\d{2})/(\d{2})\s*-\s*(\d{2})/(\d{2})", str(text))
    if not dates:
        return None
    remainder = re.sub(r"\d{2}/\d{2}\s*-\s*\d{2}/\d{2}", "", str(text))
    if remainder.strip(" ,;|\t\n\r"):
        return None
    day = date.month * 100 + date.day
    # Reject malformed intervals rather than comparing impossible calendar dates.
    try:
        for m, d, M, D in dates:
            Date(2000, int(m), int(d))
            Date(2000, int(M), int(D))
    except ValueError:
        return None
    for m, d, M, D in dates:
        lo = int(m) * 100 + int(d)
        hi = int(M) * 100 + int(D)
        if (lo <= hi and lo <= day <= hi) or (lo > hi and (day >= lo or day <= hi)):
            return True
    return False


def access(row, date, vehicle="truck", manual=(), width_inches=None):
    p = row["properties"]
    kind = row["kind"]
    foot = "unknown"
    motor = "unknown"
    evidence = []
    if kind == "trails":
        if date_match(p.get("hiker_pedestrian_restricted"), date):
            foot = "closed"
            evidence.append("USFS pedestrian restricted dates")
        elif any(
            date_match(p.get(k), date)
            for k in ("hiker_pedestrian_managed", "hiker_pedestrian_accpt")
        ):
            foot = "supported"
            evidence.append("USFS pedestrian managed/accepted dates")
        if (
            p.get("hiker_pedestrian_restricted")
            and date_match(p["hiker_pedestrian_restricted"], date) is None
        ):
            foot = "unknown"
            evidence.append("Unparseable pedestrian restriction dates; review source")
    if row.get("motor_closed"):
        motor = "closed"
        evidence.append("USFS separate motor-closed inventory")
    # MVUM geometry is matched over the actual segment, not merely by road name.
    motor_evidence = []
    for m in row.get("mvum", []):
        key = "truck" if vehicle == "truck" else "other_ohv_gt50inches"
        if str(m.get(key, "")).lower() in ("closed", "prohibited"):
            motor_evidence.append("closed")
            evidence.append("MVUM explicit motor prohibition")
        if str(m.get(key, "")).lower() == "open":
            active = date_match(m.get(key + "_datesopen"), date)
            if active is not None:
                status = "supported" if active else "closed"
                motor_evidence.append(status)
                evidence.append(f"MVUM {key}: {m.get(key+'_datesopen')}")
    if motor != "closed" and motor_evidence:
        motor = "closed" if "closed" in motor_evidence else "supported"
        if len(set(motor_evidence)) > 1:
            evidence.append(
                "Conflicting MVUM records: closed controls; current order review required"
            )
    if vehicle == "teryx" and motor == "supported":
        if width_inches is None or not 50 < width_inches <= 100:
            motor = "unknown"
            evidence.append(
                "Actual side-by-side width over 50 inches required for this MVUM class; ATV eligibility is not inferred"
            )
    condition = "unknown"
    maint = str(p.get("oper_maint_level", p.get("operationalmaintlevel", "")))
    if maint.startswith("1") or str(p.get("route_status", "")).startswith("DE"):
        condition = "possibly obstructed/decommissioned"
    closures = set()
    for rule in manual:
        if rule.get("segment") not in (row["id"], "*"):
            continue
        if rule.get("from") and date.isoformat() < rule["from"]:
            continue
        if rule.get("until") and date.isoformat() > rule["until"]:
            continue
        if not rule.get("provenance"):
            raise ValueError("Manual restrictions require dated provenance")
        if rule.get("foot") in ("supported", "unknown", "closed"):
            foot = rule["foot"]
            if foot == "closed":
                closures.add("foot")
        if rule.get("motor") in ("supported", "unknown", "closed"):
            motor = rule["motor"]
            if motor == "closed":
                closures.add("motor")
        if rule.get("condition"):
            condition = rule["condition"]
        evidence.append("Manual: " + rule["provenance"])
    # Active prohibitions cannot be reopened by record order or a generic assertion.
    if "foot" in closures or (
        kind == "trails" and date_match(p.get("hiker_pedestrian_restricted"), date)
    ):
        foot = "closed"
    if "motor" in closures or row.get("motor_closed") or "closed" in motor_evidence:
        motor = "closed"
    if (
        vehicle == "teryx"
        and motor == "supported"
        and (width_inches is None or not 50 < width_inches <= 100)
    ):
        motor = "unknown"
    if row.get("source_conflict"):
        foot = "unknown" if foot == "supported" else foot
        motor = "unknown" if motor == "supported" else motor
        evidence.append(
            "Conflicting duplicate inventory features; no primary permission inference"
        )
    return dict(
        foot=foot,
        motor=motor,
        condition=condition,
        evidence=evidence,
        certification=False,
    )


class Pack:
    def __init__(self, paths, unit="co-gmu54"):
        self.paths = paths
        catalog = read(paths.source / "data/unit-packs/catalog.json")
        if not isinstance(catalog, dict):
            raise ValueError(
                "Prepared-pack catalog is corrupt or missing; restore its sealed sources. Saved TrailScout plans remain retained."
            )
        version = catalog.get("units", {}).get(unit)
        if not version or not re.fullmatch("[a-z0-9_-]+", version):
            raise ValueError("No ready GMU54 pack; import a sealed pack first")
        self.folder = paths.source / "data/unit-packs/versions" / unit / version
        manifest = self.folder / "pack.json"
        verify(manifest, read(self.folder / "seal.json")["sha256"])
        self.spec = read(manifest)
        if self.spec.get("status") != "ready" or self.spec.get("epsg") != 32613:
            raise ValueError("Pack not ready or unsupported CRS")
        self.revision = digest([read(self.folder / "seal.json"), version])
        self.files = {manifest: identity(manifest)}
        boundary = read(self.asset(self.spec["boundary"]))
        self.boundary = (
            unary_union([project(shape(f["geometry"])) for f in boundary["features"]])
            if boundary.get("type") == "FeatureCollection"
            else project(shape(boundary.get("geometry", boundary)))
        )
        self.network = self._network()
        self.extra = {}
        self.extra_specs = {}
        for key in (
            "closed_roads",
            "mvum_roads",
            "mvum_trails",
            "ownership",
            "surface_management",
            "access_points",
        ):
            try:
                self.extra[key], self.extra_specs[key] = self.supplement(key)
            except FileNotFoundError:
                self.extra[key] = []
        self._reconcile()
        self.revision = digest([self.revision, self.extra_specs])

    def asset(self, name):
        p = self.folder / name
        if not p.resolve().is_relative_to(self.folder.resolve()):
            raise ValueError("Pack asset escaped source root")
        specs = [s for s in self.spec["assets"].values() if s["path"] == name]
        if len(specs) != 1:
            raise ValueError("Missing/ambiguous pack asset " + name)
        verify(p, specs[0]["sha256"])
        self.raster_dependencies(p)
        self.files[p] = identity(p)
        return p

    def raster_dependencies(self, path):
        if path.suffix.lower() != ".tif":
            return
        for suffix in (".aux.xml", ".ovr", ".msk", ".aux"):
            if Path(str(path) + suffix).exists():
                raise ValueError(
                    f"Unsealed raster companion: {path}{suffix}. Restore the self-contained sealed source or prepare a new version; no owner files changed."
                )
        ds = gdal.Open(str(path))
        if ds is None or any(
            Path(p).resolve() != path.resolve() for p in ds.GetFileList()
        ):
            raise ValueError("Raster has missing/external dependencies: " + str(path))

    def supplement(self, key):
        folder = self.paths.source / "data/scouting"
        p = folder / (key + ".geojson")
        manifest = read(folder / "manifest.json", {})
        if (folder / "manifest.json").exists():
            self.files[folder / "manifest.json"] = identity(folder / "manifest.json")
        active_path = self.paths.state / "imports/active.json"
        active = read(active_path, {})
        if not p.exists() and key not in active:
            # Only an entirely absent legacy archive may use the compiled snapshot.
            # A damaged/partial archive never silently falls back to other bytes.
            if not (folder / "manifest.json").exists():
                from practical_glassing.package import CommunityPackage, installed_root

                if not hasattr(self, "_compiled_access"):
                    root = installed_root(self.paths)
                    self._compiled_access = (
                        CommunityPackage(root)
                        if (root / "active.json").exists()
                        else None
                    )
                package = self._compiled_access
                if package is not None and key in package.spec.get("extra_sources", {}):
                    if (
                        package.spec["base_manifest_sha256"]
                        != read(self.folder / "seal.json")["sha256"]
                    ):
                        raise ValueError(
                            "Compiled access snapshot belongs to another base pack"
                        )
                    record = package.spec["extra_sources"][key]
                    source = package.access_object(record)
                    self.files[source] = identity(source)
                    self.files[package.folder / "manifest.json"] = identity(
                        package.folder / "manifest.json"
                    )
                    self.files[package.root / "active.json"] = identity(
                        package.root / "active.json"
                    )
                    return read(source)["features"], record["original_metadata"]
            raise FileNotFoundError(p)
        spec = manifest.get(p.name, {})
        rows = []
        if p.exists():
            verify(p, spec.get("sha256"))
            self.files[p] = identity(p)
            rows = read(p)["features"]
        active_path = self.paths.state / "imports/active.json"
        active = read(active_path, {})
        if key in active:
            imported = active[key]
            ip = Path(imported["path"])
            if not ip.resolve().is_relative_to(
                (self.paths.state / "imports").resolve()
            ):
                raise ValueError("Imported source escaped TrailScout imports")
            if not ip.is_file():
                raise ValueError(
                    "Required imported source missing: "
                    + str(ip)
                    + ". Restore exact bytes or import a new snapshot; saved plans remain available."
                )
            verify(ip, imported["sha256"])
            self.files[ip] = identity(ip)
            self.files[active_path] = identity(active_path)
            fresh = read(ip)["features"]
            bounds = imported.get("query_bounds_wgs84")
            if bounds:
                rows = [
                    f for f in rows if not shape(f["geometry"]).intersects(box(*bounds))
                ]
            by_id = {
                str(
                    f["properties"].get(
                        "globalid", f["properties"].get("objectid", f.get("id"))
                    )
                ): f
                for f in rows
            }
            for f in fresh:
                props = {k.lower(): v for k, v in f["properties"].items()}
                by_id[
                    str(props.get("globalid", props.get("objectid", f.get("id"))))
                ] = f
            rows = list(by_id.values())
            spec = dict(prior=spec, imported=imported)
        return rows, spec

    def _network(self):
        rows = {}
        for kind, pieces in self.spec["networks"].items():
            for piece in pieces:
                for f in read(self.asset(piece["path"]))["features"]:
                    p = {str(k).lower(): v for k, v in f.get("properties", {}).items()}
                    g = project(shape(f["geometry"]))
                    parts = [g] if g.geom_type == "LineString" else list(g.geoms)
                    for i, line in enumerate(parts):
                        key = f"{kind}:{p.get('globalid',p.get('objectid',f.get('id')))}:{i}"
                        if key in rows:
                            prior = rows[key]
                            if (
                                not line.equals_exact(prior["geometry"], 1e-8)
                                or p != prior["properties"]
                            ):
                                prior["source_conflict"] = True
                                prior.setdefault("conflicting_features", []).append(
                                    dict(geometry_wkt=line.wkt, properties=p)
                                )
                            continue
                        rows[key] = dict(
                            id=key,
                            kind=kind,
                            geometry=line,
                            properties=p,
                            motor_closed=False,
                            mvum=[],
                        )
        return list(rows.values())

    def _reconcile(self):
        # Exact stable identity reconciles the separate closed-road layer. No
        # duplicate traversal edges or remoteness credit for duplicated inventory.
        gids = {}
        for r in self.network:
            if r["kind"] == "roads":
                gids.setdefault(r["properties"].get("globalid"), []).append(r)
        for f in self.extra["closed_roads"]:
            p = {k.lower(): v for k, v in f["properties"].items()}
            g = project(shape(f["geometry"]))
            old = gids.get(p.get("globalid"))
            if old:
                for r in old:
                    r["motor_closed"] = True
                continue
            parts = [g] if g.geom_type == "LineString" else list(g.geoms)
            for i, line in enumerate(parts):
                key = f"closed:{p.get('globalid',p.get('objectid'))}:{i}"
                self.network.append(
                    dict(
                        id=key,
                        kind="roads",
                        geometry=line,
                        properties=p,
                        motor_closed=True,
                        mvum=[],
                    )
                )
        motor = []
        for key in ("mvum_roads", "mvum_trails"):
            for f in self.extra[key]:
                motor.append(
                    (
                        project(shape(f["geometry"])),
                        {k.lower(): v for k, v in f["properties"].items()},
                    )
                )
        for row in self.network:
            p = row["properties"]
            g = row["geometry"]
            route = p.get("rte_cn") or p.get("trail_cn")
            for line, m in motor:
                other = m.get("rte_cn")
                rid = p.get("id") or p.get("trail_no")
                mid = m.get("id")
                same = (route and other and str(route) == str(other)) or (
                    rid and mid and str(rid) == str(mid)
                )
                if same and g.intersection(line.buffer(5)).length >= g.length * 0.95:
                    row["mvum"].append(m)
        self.network.sort(key=lambda r: r["id"])

    def recheck(self):
        for p, stamp in self.files.items():
            self.raster_dependencies(p)
            if identity(p) != stamp:
                raise ValueError("Source changed during calculation: " + str(p))

    def terrain(self, bounds, res=10):
        bounds = [
            math.floor(bounds[0] / res) * res,
            math.floor(bounds[1] / res) * res,
            math.ceil(bounds[2] / res) * res,
            math.ceil(bounds[3] / res) * res,
        ]
        cells = (bounds[2] - bounds[0]) * (bounds[3] - bounds[1]) / res**2
        if cells > 2_000_000:
            raise ValueError(
                f"Analysis needs {cells:,.0f} cells, above the 2,000,000-cell guard. Shorten corridor/view radius explicitly; precision was not changed."
            )
        if not box(*self.spec["support"]["bounds"]).covers(box(*bounds)):
            raise ValueError(
                "Terrain buffer leaves prepared source support; select a smaller corridor or import buffered data"
            )
        source = gdal.Open(str(self.asset(self.spec["data"]["dem"]["path"])))
        srs = source.GetSpatialRef()
        gt = source.GetGeoTransform()
        diagnostic = self.spec["diagnostics"]["dem"]
        if (
            not srs
            or not srs.IsProjected()
            or abs(srs.GetLinearUnits() - 1) > 1e-9
            or tuple(gt) != tuple(diagnostic["geotransform"])
            or [source.RasterXSize, source.RasterYSize] != diagnostic["dimensions"]
        ):
            raise ValueError(
                "Actual DEM CRS/grid/dimensions disagree with sealed pack diagnostics"
            )
        ds = gdal.Warp(
            "",
            source,
            format="MEM",
            outputBounds=bounds,
            xRes=res,
            yRes=res,
            resampleAlg="bilinear",
            dstSRS="EPSG:32613",
            outputType=gdal.GDT_Float32,
            dstNodata=-9999,
        )
        if ds is None:
            raise ValueError("Terrain window failed")
        a = ds.ReadAsArray()
        if not np.isfinite(a).all() or (a == -9999).any():
            raise ValueError(
                "Missing obstruction terrain in requested window; cannot calculate supported visibility"
            )
        if self.spec["data"]["dem"].get("vertical_units") != "m":
            raise ValueError("DEM vertical units must be metres")
        return Terrain(ds)

    def public_area(self, bounds):
        areas = []
        for f in self.extra.get("ownership", []):
            p = {k.lower(): v for k, v in f["properties"].items()}
            g = project(shape(f["geometry"]))
            if g.intersects(box(*bounds)):
                areas.append(g)
        return unary_union(areas) if areas else None

    def summary(self):
        return dict(
            id="co-gmu54",
            version=self.spec["version"],
            revision=self.revision,
            label=self.spec["label"],
            bounds=self.spec["bounds"],
            support=self.spec["support"],
            diagnostics=self.spec["diagnostics"],
            network_count=len(self.network),
            sources=self.spec["data"],
            supplements=self.extra_specs,
            note="Unit core sources ready; each analysis is a bounded corridor. Vegetation has intrinsic unknown cells. Access snapshots do not establish current closures, parking or permission. Official GMU boundary limits target eligibility only.",
        )


class Terrain:
    def __init__(self, ds):
        self.ds = ds
        self.a = ds.ReadAsArray().astype(float)
        self.gt = ds.GetGeoTransform()
        self.res = self.gt[1]
        self.bounds = (
            self.gt[0],
            self.gt[3] - self.a.shape[0] * self.res,
            self.gt[0] + self.a.shape[1] * self.res,
            self.gt[3],
        )
        dy, dx = np.gradient(self.a, self.res)
        self.slope = np.degrees(np.arctan(np.hypot(dx, dy)))

    def sample(self, xy, array=None):
        pts = np.atleast_2d(xy)
        cols = (pts[:, 0] - self.gt[0]) / self.res - 0.5
        rows = (self.gt[3] - pts[:, 1]) / self.res - 0.5
        if (
            np.any(cols < 0)
            or np.any(rows < 0)
            or np.any(cols > self.a.shape[1] - 1)
            or np.any(rows > self.a.shape[0] - 1)
        ):
            raise ValueError("Route/candidate outside supported terrain")
        return map_coordinates(
            self.a if array is None else array,
            [rows, cols],
            order=1,
            mode="constant",
            cval=np.nan,
            prefilter=False,
        )
