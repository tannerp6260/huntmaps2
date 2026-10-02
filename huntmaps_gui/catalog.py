"""Adapters for completed owner runs and the explicitly bounded Soap Creek review."""

import csv
import json
import hashlib
from functools import lru_cache
from pathlib import Path
import numpy as np
from osgeo import gdal, ogr, osr
from glassing.transfer import project
from glassing.review_maps import visible_mask

from .config import SOURCE as ROOT, STATE


from .storage import read_json as read


def safe_path(value):
    p = (ROOT / value).resolve()
    if not p.is_relative_to(ROOT):
        raise ValueError("Source must be inside this project")
    return p


@lru_cache(maxsize=4096)
def check_hash(path, mtime, size, expected):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    if h.hexdigest() != expected:
        raise ValueError(
            "Saved source changed: "
            + path
            + ". Restore its original bytes or use a new run; the GUI will not rewrite it."
        )


def feature(geometry, **properties):
    return dict(type="Feature", geometry=geometry, properties=properties)


def collection(features):
    return dict(type="FeatureCollection", features=features)


def runs():
    entries = []
    for p in sorted((ROOT / "results").glob("*/scouting.json")):
        if (p.parent / "manifest.json").exists() and (
            p.parent / "analysis/scores.json"
        ).exists():
            synthetic = read(p).get("input_kind") == "synthetic_fixture"
            entries.append(
                dict(
                    id=p.parent.name,
                    label=p.parent.name
                    + (" · SYNTHETIC TEST" if synthetic else " · baseline"),
                    experimental=False,
                )
            )
    if (ROOT / "results/soap-creek-decision-review-v2/shortlist.csv").exists():
        entries.insert(
            0,
            dict(
                id="soap-creek-decision-review-v2",
                label="Soap Creek · saved neighborhood review (experimental)",
                experimental=True,
            ),
        )
    return entries


@lru_cache(maxsize=128)
def static_json(path, mtime, size):
    return json.loads(Path(path).read_text())


def frozen_read(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    st = p.stat()
    return static_json(str(p.resolve()), st.st_mtime_ns, st.st_size)


class Run:
    def __init__(self, ident):
        entry = next((r for r in runs() if r["id"] == ident), None)
        if entry is None:
            raise ValueError("Select a completed local run")
        self.id = ident
        self.experimental = entry["experimental"]
        self.base = ROOT / "results" / ("soap-creek-v1" if self.experimental else ident)
        self.hashes = {}
        manifests = [self.base / "manifest.json"]
        if self.experimental:
            manifests.extend(
                [
                    ROOT / "results/soap-creek-vegetation-v2/manifest.json",
                    ROOT / "results" / self.id / "manifest.json",
                ]
            )
        if self.base.name == "soap-creek-v1":
            manifests.append(ROOT / "results/soap-creek-v1-review-v2/manifest.json")
        for manifest in manifests:
            for path, h in frozen_read(manifest, {}).items():
                self.hashes[str(safe_path(path))] = h
        self.validate(self.base / "scouting.json")
        self.config = frozen_read(self.base / "scouting.json")
        self.analysis = safe_path(self.config["work"])
        self.dem_path = self.analysis / "dem.tif"
        self.validate(self.dem_path)
        self.validate(self.analysis / "scores.json")
        self.dem = gdal.Open(str(self.dem_path))
        if self.dem is None:
            raise ValueError("Saved DEM is unavailable")
        self.points = {p["id"]: p for p in frozen_read(self.analysis / "scores.json")}
        self.rows = {k: dict(v) for k, v in self.points.items()}
        self.details = {}
        self.obstruction_scenarios = {}
        self.groups = {}
        self.images = []
        if self.experimental:
            self.vegetation = ROOT / "results/soap-creek-vegetation-v2"
            for name in ["alternatives.json", "components.json", "details.json"]:
                self.validate(self.vegetation / name)
            self.points.update(
                {p["id"]: p for p in frozen_read(self.vegetation / "alternatives.json")}
            )
            self.rows = {
                p["id"]: p for p in frozen_read(self.vegetation / "components.json")
            }
            self.details = frozen_read(self.vegetation / "details.json")
            self.validate(self.vegetation / "coarse_ray_scenarios.csv")
            with (self.vegetation / "coarse_ray_scenarios.csv").open() as f:
                for row in csv.DictReader(f):
                    self.obstruction_scenarios.setdefault(row["id"], []).append(row)
            self.validate(ROOT / "results" / ident / "shortlist.csv")
            with (ROOT / "results" / ident / "shortlist.csv").open() as f:
                for r in csv.DictReader(f):
                    self.groups.setdefault(r["neighborhood"], []).append(r["id"])
        # Soap Creek imagery is a specific saved companion, never applied to another AOI.
        if self.base.name == "soap-creek-v1":
            self.validate(ROOT / "results/soap-creek-v1-review-v2/imagery.json")
            self.images = list(
                frozen_read(
                    ROOT / "results/soap-creek-v1-review-v2/imagery.json", {}
                ).values()
            )
        else:
            self.images = [
                dict(r, dates=[r.get("acquisition_date", "unknown")], resolution_m=0)
                for r in self.config["data"].get("imagery", [])
            ]
        self.images = [
            i for i in self.images if i.get("path") and safe_path(i["path"]).is_file()
        ]
        self.images.sort(key=lambda i: -i.get("resolution_m", 0))
        for i in self.images:
            self.validate(safe_path(i["path"]))
        self.validate(self.analysis / "patches.json")
        self.validate(self.analysis / "approaches.json")
        self.ll = project(self.config["epsg"], 4326)
        self.patches = frozen_read(self.analysis / "patches.json", {})
        self.approaches = frozen_read(self.analysis / "approaches.json", {})

    def validate(self, path):
        path = Path(path).resolve()
        if not path.is_file():
            raise ValueError(
                "Saved source missing: "
                + str(path)
                + ". Restore it or select another completed run."
            )
        expected = self.hashes.get(str(path))
        if not expected:
            raise ValueError("Saved source has no integrity record: " + str(path))
        stat = path.stat()
        check_hash(str(path), stat.st_mtime_ns, stat.st_size, expected)

    def visibility_path(self, ident):
        if ident not in self.points:
            raise ValueError("Unknown candidate")
        if self.experimental and ident.startswith("V"):
            p = self.vegetation / "viewsheds" / (ident + ".tif")
        else:
            p = (
                self.analysis
                / "additional_visibility"
                / f'{ident}_{self.config["radius_m"]}.tif'
            )
        if not p.exists():
            raise ValueError(
                "No saved visibility for this candidate; GUI does not recalculate it"
            )
        self.validate(p)
        return p

    def mask(self, ident):
        self.validate(self.analysis / "target.tif")
        p = dict(self.points[ident], raw_km2=self.rows[ident]["raw_km2"])
        return visible_mask(
            gdal.Open(str(self.visibility_path(ident))),
            self.dem,
            gdal.Open(str(self.analysis / "target.tif")).ReadAsArray() == 1,
            p,
            self.config["radius_m"],
        )

    def cover(self, name):
        self.validate(self.analysis / (name + ".tif"))
        ds = gdal.Open(str(self.analysis / (name + ".tif")))
        if (
            ds.GetGeoTransform() != self.dem.GetGeoTransform()
            or not ds.GetSpatialRef().IsSame(self.dem.GetSpatialRef())
            or (ds.RasterYSize, ds.RasterXSize)
            != (self.dem.RasterYSize, self.dem.RasterXSize)
        ):
            raise ValueError("Saved cover raster is not aligned to the DEM")
        a = ds.ReadAsArray()
        return np.where(np.isfinite(a) & (a >= 0) & (a <= 1), a, np.nan)

    def candidate(self, ident, include_mask=False):
        if ident not in self.points:
            raise ValueError("Unknown candidate")
        p = self.points[ident]
        r = self.rows[ident]
        lon, lat = self.ll(p["x"], p["y"])
        metrics = {k: v for k, v in r.items() if k not in ["x", "y", "id", "parent"]}
        check = None
        if include_mask:
            mask, check = self.mask(ident)
            tree = self.cover("tree")
            shrub = self.cover("shrub")
            area = (
                abs(self.dem.GetGeoTransform()[1] * self.dem.GetGeoTransform()[5]) / 1e6
            )
            measured = dict(
                tree_lt10_km2=float((mask & (tree < 0.1)).sum() * area),
                tree_10to40_km2=float(
                    (mask & (tree >= 0.1) & (tree < 0.4)).sum() * area
                ),
                tree_ge40_km2=float((mask & (tree >= 0.4)).sum() * area),
                tree_unknown_km2=float((mask & ~np.isfinite(tree)).sum() * area),
                shrub_gt30_km2=float((mask & (shrub > 0.3)).sum() * area),
                cover_unknown_km2=float(
                    (mask & (~np.isfinite(tree) | ~np.isfinite(shrub))).sum() * area
                ),
            )
            for k, v in measured.items():
                if k in r and abs(r[k] - v) > 1e-9:
                    raise ValueError("Saved vegetation breakdown mismatch: " + k)
            metrics.update(measured)
        return dict(
            id=ident,
            longitude=lon,
            latitude=lat,
            parent=r.get("parent", ""),
            neighborhood=next((k for k, v in self.groups.items() if ident in v), None),
            metrics=metrics,
            foreground={k: v for k, v in p.items() if k.startswith("foreground")},
            obstruction="Ground-level branches and understory remain unverified. Coarse cover is not an obstruction probability.",
            access=self.approaches.get(
                ident,
                "UNRESOLVED: no documented connected legal approach for this setup",
            ),
            diagnostics=self.details.get(ident, {}),
            obstruction_scenarios=self.obstruction_scenarios.get(ident, []),
            alignment=check,
            has_visibility=self.visibility_path(ident).exists(),
        )

    def boundary(self):
        p = self.base / "observer.geojson"
        if p.exists():
            self.validate(p)
            return frozen_read(p)
        return collection([])

    def summary(self):
        gt = self.dem.GetGeoTransform()
        corners = [
            self.ll(gt[0], gt[3] + self.dem.RasterYSize * gt[5]),
            self.ll(gt[0] + self.dem.RasterXSize * gt[1], gt[3]),
        ]
        pts = [self.candidate(k) for k in self.rows]
        return dict(
            id=self.id,
            experimental=self.experimental,
            synthetic=self.config.get("input_kind") == "synthetic_fixture",
            candidates=pts,
            groups=self.groups,
            review_ids=(
                sum(self.groups.values(), [])
                if self.experimental
                else [p["id"] for p in frozen_read(self.analysis / "leading.json", [])]
            ),
            boundary=self.boundary(),
            bounds=corners,
            radius_m=self.config["radius_m"],
            imagery=[
                {
                    k: v
                    for k, v in i.items()
                    if k
                    in [
                        "dates",
                        "native_resolution_m",
                        "resolution_m",
                        "acquisition_date",
                        "provider",
                        "path",
                    ]
                }
                for i in self.images
            ],
            warning=(
                "Saved Soap Creek experiment only; vegetation screens are unvalidated and unavailable for new areas."
                if self.experimental
                else "Terrain baseline with inherited heuristic inspection scores. Legal access and actual sightlines require review."
            ),
        )

    def sectors(self, ident):
        p = self.points[ident]
        if self.experimental:
            d = self.details[ident]
            patches = d["patches"]
            ids = d["selections"]["target_heuristic"]["patch_ids"]
        else:
            d = self.patches.get(ident, {})
            patches = d.get("patches", [])
            ids = d.get("selection", {}).get("patch_ids", [])
        fs = []
        for patch in patches:
            if patch["id"] not in ids:
                continue
            angles = (
                np.linspace(patch["azimuth_start"], patch["azimuth_end"], 16)
                * np.pi
                / 180
            )
            ring = [
                self.ll(p["x"] + radius * np.sin(a), p["y"] + radius * np.cos(a))
                for radius, aa in [
                    (patch["outer_m"], angles),
                    (patch["inner_m"], angles[::-1]),
                ]
                for a in aa
            ]
            ring.append(ring[0])
            fs.append(
                feature(
                    dict(type="Polygon", coordinates=[ring]),
                    candidate=ident,
                    description="Saved inspection sector includes hidden terrain; not a visibility mask",
                )
            )
        return collection(fs)
