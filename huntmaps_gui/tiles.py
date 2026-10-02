"""GDAL EPSG:3857 XYZ raster adapter. Nearest sampling for saved categorical cells."""

import hashlib
import io
import threading
from pathlib import Path
import numpy as np
from PIL import Image
from osgeo import gdal
from glassing import core
from .catalog import STATE, safe_path

LOCK = threading.RLock()
COLORS = [(0, 192, 232), (255, 103, 130), (170, 111, 255)]
CLASS_COLORS = np.array(
    [
        [0, 0, 0, 0],
        [255, 222, 103, 230],
        [151, 180, 89, 230],
        [40, 94, 64, 230],
        [173, 173, 173, 230],
    ],
    dtype="uint8",
)


def fingerprint(paths):
    return hashlib.sha256(
        "|".join(
            f"{p}:{p.stat().st_size}:{p.stat().st_mtime_ns}" for p in paths
        ).encode()
    ).hexdigest()[:24]


def rgba_file(path, rgba, ds):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp.tif")
    out = gdal.GetDriverByName("GTiff").Create(
        str(temp),
        ds.RasterXSize,
        ds.RasterYSize,
        4,
        gdal.GDT_Byte,
        options=["COMPRESS=DEFLATE"],
    )
    out.SetGeoTransform(ds.GetGeoTransform())
    out.SetProjection(ds.GetProjection())
    for i in range(4):
        out.GetRasterBand(i + 1).WriteArray(rgba[:, :, i])
        out.GetRasterBand(i + 1).SetColorInterpretation(
            [
                gdal.GCI_RedBand,
                gdal.GCI_GreenBand,
                gdal.GCI_BlueBand,
                gdal.GCI_AlphaBand,
            ][i]
        )
    out = None
    temp.replace(path)


def sources(run, layer, ident, color):
    if layer == "imagery":
        return [safe_path(i["path"]) for i in run.images], None
    ds = run.dem
    inputs = [run.dem_path]
    if layer in ["visible", "classes"]:
        inputs += [run.visibility_path(ident), run.analysis / "target.tif"]
        if layer == "classes":
            inputs += [run.analysis / "tree.tif"]
            saved = (
                run.vegetation / (ident + "_target_classes.tif")
                if run.experimental and ident not in getattr(run, "working_ids", set())
                else None
            )
            if saved and saved.exists():
                run.validate(saved)
                inputs.append(saved)
    elif layer != "hillshade":
        raise ValueError("Unknown map layer")
    key = fingerprint(inputs)
    path = STATE / "cache" / key / f"{layer}-{ident}-{color}.tif"
    if not path.exists():
        if layer == "hillshade":
            shade = gdal.DEMProcessing(
                "", ds, "hillshade", format="MEM", computeEdges=True
            )
            a = shade.ReadAsArray()
            rgba = np.stack([a, a, a, np.full_like(a, 255)], axis=-1)
            rgba[:, :, 3] = np.where(
                ds.GetRasterBand(1).GetMaskBand().ReadAsArray() > 0, 255, 0
            )
        else:
            mask, check = run.mask(ident)
            path.parent.mkdir(parents=True, exist_ok=True)
            (path.parent / f"{ident}-alignment.json").write_text(
                __import__("json").dumps(check, indent=2)
            )
            if layer == "visible":
                rgba = np.zeros((*mask.shape, 4), dtype="uint8")
                rgba[:, :, :3] = COLORS[color]
                rgba[:, :, 3] = mask * 255
            else:
                tree = run.cover("tree")
                classes = np.zeros(mask.shape, dtype="uint8")
                classes[mask & (tree < 0.1)] = 1
                classes[mask & (tree >= 0.1) & (tree < 0.4)] = 2
                classes[mask & (tree >= 0.4)] = 3
                classes[mask & ~np.isfinite(tree)] = 4
                if saved and saved.exists():
                    ds_saved = gdal.Open(str(saved))
                    if (
                        ds_saved.GetGeoTransform() != ds.GetGeoTransform()
                        or not ds_saved.GetSpatialRef().IsSame(ds.GetSpatialRef())
                        or not np.array_equal(ds_saved.ReadAsArray(), classes)
                    ):
                        raise ValueError(
                            "Saved vegetation classes differ from aligned visible targets"
                        )
                    classes = ds_saved.ReadAsArray()
                rgba = CLASS_COLORS[classes]
        rgba_file(path, rgba, ds)
    return [path], key


def tile(run, layer, ident, z, x, y, color=0):
    if not (0 <= z <= 20 and 0 <= x < 2**z and 0 <= y < 2**z and 0 <= color <= 2):
        raise ValueError("Invalid tile coordinate")
    with LOCK:
        paths, key = sources(run, layer, ident, color)
        if not paths:
            return transparent()
        cache = STATE / "cache" / "tiles" / fingerprint(paths) / f"{z}-{x}-{y}.png"
        if cache.exists():
            return cache.read_bytes()
        half = 20037508.342789244
        size = half * 2 / 2**z
        bounds = [
            -half + x * size,
            half - (y + 1) * size,
            -half + (x + 1) * size,
            half - y * size,
        ]
        # GDAL warps each actual georeferenced source into an exact Web Mercator tile.
        # Fine cached aerial clips follow context clips in the mosaic.
        ds = gdal.Warp(
            "",
            [str(p) for p in paths],
            format="MEM",
            dstSRS="EPSG:3857",
            outputBounds=bounds,
            width=256,
            height=256,
            resampleAlg="near" if layer != "imagery" else "bilinear",
            dstAlpha=True,
            multithread=False,
            warpOptions=["INIT_DEST=0"],
        )
        if ds is None:
            raise ValueError("Local raster reprojection failed")
        a = ds.ReadAsArray()
        if a.shape[0] == 3:
            a = np.concatenate([a, np.full((1, 256, 256), 255, dtype="uint8")])
        png = io.BytesIO()
        Image.fromarray(a[:4].transpose(1, 2, 0).astype("uint8"), "RGBA").save(
            png, format="PNG"
        )
        data = png.getvalue()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(data)
        return data


def transparent():
    b = io.BytesIO()
    Image.new("RGBA", (256, 256)).save(b, format="PNG")
    return b.getvalue()
