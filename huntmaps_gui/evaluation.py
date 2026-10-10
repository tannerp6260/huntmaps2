"""Job-local verified terrain/layers for the unchanged transfer scoring model.

No process-global engine patches or cross-job arrays. components executes the
frozen function with only its viewshed boundary replaced by a verified boundary.
"""

import json
from pathlib import Path
from types import FunctionType
import numpy as np
from osgeo import gdal
from glassing import core, transfer, compare, attention, comparison_models as model
from .sampling import stamp


class Evaluation:
    def __init__(self, c):
        self.c = json.loads(json.dumps(c))
        self.root = root = transfer.work(c)
        names = ["prepared.json", "core_config.json", "input_identity.json"] + [
            k + ".tif"
            for k in [
                "dem",
                "target",
                "observer",
                "tree",
                "shrub",
                "herb",
                "summer",
                "winter",
                "vegetation_unknown",
                "actionability",
            ]
        ]
        paths = [root / name for name in names] + [Path(c["model_lock"])]
        self.stamps = {p: stamp(p) for p in paths}
        self.hashes = {p: core.digest(p) for p in paths}
        self.bc = bc = transfer.read(root / "core_config.json")
        self.grid = core.load_grid(bc)
        ds, a, gt, masks = self.grid
        self.layers = {}
        for k in [
            "tree",
            "shrub",
            "herb",
            "summer",
            "winter",
            "vegetation_unknown",
            "actionability",
        ]:
            layer = gdal.Open(str(root / (k + ".tif")))
            if (
                layer.GetGeoTransform() != gt
                or layer.GetProjection() != ds.GetProjection()
                or (layer.RasterYSize, layer.RasterXSize) != a.shape
            ):
                raise ValueError("Layer grid mismatch: " + k)
            v = layer.ReadAsArray()
            self.layers[k] = (
                np.where(v < 0, np.nan, v) if k in ["tree", "shrub", "herb"] else v
            )
        lock = transfer.read(c["model_lock"])
        self.mc = dict(lock["comparison"], work=str(root), light=c["season"]["light"])
        self.b = dict(
            bc,
            baseline_radius_m=c["radius_m"],
            eye_m=c["eye_m"],
            target_m=c["target_m"],
            curvature=c["curvature"],
        )
        self.grad = np.gradient(a.astype("float64"), gt[1])
        self.grad[0] *= -1
        self.settings = lock["attention"]
        self.components = FunctionType(
            compare.components.__code__, dict(compare.__dict__, get_view=self.get_view)
        )
        self.verify()

    def verify(self, full=False):
        for path, value in self.stamps.items():
            if stamp(path) != value or (
                full and core.digest(path) != self.hashes[path]
            ):
                raise ValueError("Evaluation input changed during job: " + str(path))

    def get_view(self, c, b, base, ds, p, radius, original=True):
        if original:
            raise ValueError("Job evaluator is only for normal supplemental viewsheds")
        # load_grid validated the complete DEM, units, CRS, size and NoData once.
        # Only endpoint/halo checks vary with the observer. GDAL stays unchanged.
        _, a, gt, _ = self.grid
        x, y = p["x"], p["y"]
        col, row = int((x - gt[0]) / gt[1]), int((y - gt[3]) / gt[5])
        if not (0 <= row < a.shape[0] and 0 <= col < a.shape[1]):
            raise ValueError("Observer outside terrain")
        if (
            min(
                x - gt[0],
                gt[0] + a.shape[1] * gt[1] - x,
                gt[3] - y,
                y - (gt[3] + a.shape[0] * gt[5]),
            )
            < radius
        ):
            raise ValueError("Insufficient terrain halo for radius")
        folder = self.root / "additional_visibility"
        folder.mkdir(exist_ok=True)
        result = gdal.ViewshedGenerate(
            ds.GetRasterBand(1),
            "GTiff",
            str(folder / f'{p["id"]}_{radius}.tif'),
            None,
            x,
            y,
            b["eye_m"],
            b["target_m"],
            1,
            0,
            0,
            255,
            b["curvature"],
            gdal.GVM_Edge,
            radius,
        )
        if result is None:
            raise RuntimeError("GDAL viewshed failed")
        result.FlushCache()
        return result

    def evaluate(self, points):
        self.verify()
        c, root = self.c, self.root
        ds, a, gt, masks = self.grid
        mc, settings = self.mc, self.settings
        area = gt[1] ** 2 / 1e6
        rows, patches = [], {}
        for p in points:
            v = self.components(
                mc,
                self.b,
                root,
                ds,
                a,
                gt,
                masks,
                self.layers,
                p,
                self.grad,
                original=False,
                stress=False,
            )
            mix = c["season"]["winter_mix"]
            reward = (
                (
                    (1 - mix)
                    * model.habitat(
                        v["summer"],
                        v["shrub"],
                        v["herb"],
                        "summer",
                        mc["habitat_floor"],
                    )
                    + mix
                    * model.habitat(
                        v["winter"],
                        v["shrub"],
                        v["herb"],
                        "winter",
                        mc["habitat_floor"],
                    )
                )
                * v["search"]
                * model.distance_response(v["d"], mc)
                * v["perspective"]
                * model.sunlight(
                    v["gx"], v["gy"], v["dx"], v["dy"], v["dz"], mc["light"], mc
                )
            )
            ps = attention.patches(
                v["dx"],
                v["dy"],
                reward,
                area,
                settings["width_deg"],
                settings["band_m"],
                c["radius_m"],
            )
            sel = attention.select(
                ps,
                c["observation_minutes"],
                settings["rate_km2_min"],
                settings["overhead_minutes"],
            )
            patches[p["id"]] = dict(patches=ps, selection=sel)
            rows.append(
                dict(
                    p,
                    raw_km2=v["total"],
                    within_1km_km2=float((v["d"] <= 1000).sum() * area),
                    beyond_1km_km2=float((v["d"] > 1000).sum() * area),
                    low_tree_cover_km2=float(
                        ((v["tree"] < 0.1) & ~v["uncertain"]).sum() * area
                    ),
                    unknown_cover_fraction=(
                        float(v["uncertain"].mean()) if len(v["d"]) else None
                    ),
                    selective_score=sel["score"],
                    foreground_cover_mean=v["foreground_cover_mean"],
                    foreground_unknown_fraction=v["foreground_unknown_fraction"],
                    light=c["season"]["light_label"],
                )
            )
        self.verify()
        return rows, patches
