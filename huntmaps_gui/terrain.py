"""Display-only local DEM adapter. Never changes analysis elevations or masks."""

import io
import math
from functools import lru_cache
import numpy as np
from PIL import Image
from osgeo import gdal, osr
from scipy.ndimage import distance_transform_edt
from .catalog import STATE
from .tiles import LOCK, fingerprint


def _lonlat(ds):
    src = ds.GetSpatialRef()
    dst = osr.SpatialReference()
    dst.ImportFromEPSG(4326)
    src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    dst.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform = osr.CoordinateTransformation(src, dst)
    gt = ds.GetGeoTransform()
    return [
        list(transform.TransformPoint(gt[0] + x * gt[1], gt[3] + y * gt[5])[:2])
        for x, y in [
            (0, 0),
            (ds.RasterXSize, 0),
            (ds.RasterXSize, ds.RasterYSize),
            (0, ds.RasterYSize),
        ]
    ]


@lru_cache(maxsize=128)
def _metadata(path, key):
    ds = gdal.Open(path)
    a = ds.ReadAsArray()
    valid = (ds.GetRasterBand(1).GetMaskBand().ReadAsArray() > 0) & np.isfinite(a)
    corners = _lonlat(ds)
    xs, ys = zip(*corners)
    resolution = abs(ds.GetGeoTransform()[1])
    lat = sum(ys) / 4
    supported = bool(valid.all()) and bool(((a >= -32768) & (a < 32768)).all())
    return dict(
        available=supported,
        reason=(
            ""
            if supported
            else "3D needs complete, valid elevation coverage. Use the 2D map for this run."
        ),
        bounds=[min(xs), min(ys), max(xs), max(ys)],
        coverage=dict(type="Polygon", coordinates=[corners + [corners[0]]]),
        resolution_m=resolution,
        minzoom=12,
        maxzoom=max(
            12,
            min(
                17,
                math.ceil(
                    math.log2(156543.033928 * math.cos(math.radians(lat)) / resolution)
                ),
            ),
        ),
        encoding="terrarium",
        exaggeration=1,
    )


def metadata(run):
    ds = run.dem  # validates saved source integrity before any cache is consulted
    return _metadata(str(run.dem_path), fingerprint([run.dem_path]))


def elevation_tile(run, z, x, y):
    info = metadata(run)
    if not info["available"]:
        raise ValueError(info["reason"])
    if not (0 <= z <= 20 and 0 <= x < 2**z and 0 <= y < 2**z):
        raise ValueError("Invalid terrain tile coordinate")
    with LOCK:
        cache = (
            STATE
            / "cache"
            / "terrain-v1"
            / fingerprint([run.dem_path])
            / f"{z}-{x}-{y}.png"
        )
        if cache.exists():
            return cache.read_bytes()
        half = 20037508.342789244
        size = 2 * half / 2**z
        bounds = [
            -half + x * size,
            half - (y + 1) * size,
            -half + (x + 1) * size,
            half - y * size,
        ]
        ds = gdal.Warp(
            "",
            run.dem,
            format="MEM",
            dstSRS="EPSG:3857",
            outputBounds=bounds,
            width=256,
            height=256,
            outputType=gdal.GDT_Float32,
            resampleAlg="bilinear",
            dstNodata=-9999,
        )
        if ds is None:
            raise ValueError("Local elevation reprojection failed; use 2D")
        a = ds.ReadAsArray()
        valid = np.isfinite(a) & (ds.GetRasterBand(1).GetMaskBand().ReadAsArray() > 0)
        if not valid.any():
            # A bounding-box corner may intersect the source bounds but contain
            # no projected DEM pixels. Provide renderer-only edge padding there;
            # the coverage polygon hides it. Truly distant requests are rejected.
            west = x / 2**z * 360 - 180
            east = (x + 1) / 2**z * 360 - 180
            south = math.degrees(
                math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / 2**z)))
            )
            north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / 2**z))))
            b = info["bounds"]
            if east <= b[0] or west >= b[2] or north <= b[1] or south >= b[3]:
                raise ValueError("This tile is outside local elevation coverage")
            src = run.dem
            merc = osr.SpatialReference()
            merc.ImportFromEPSG(3857)
            dest = src.GetSpatialRef()
            merc.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
            dest.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
            px, py, _ = osr.CoordinateTransformation(merc, dest).TransformPoint(
                (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2
            )
            gt = src.GetGeoTransform()
            col = min(src.RasterXSize - 1, max(0, int((px - gt[0]) / gt[1])))
            row = min(src.RasterYSize - 1, max(0, int((py - gt[3]) / gt[5])))
            a[:] = float(src.GetRasterBand(1).ReadAsArray(col, row, 1, 1)[0, 0])
            valid[:] = True
        # Encoding has no NoData channel. Pad ONLY outside the complete source
        # footprint with nearest edge elevations for renderer gutters. The UI
        # covers this region and constrains navigation to measured coverage.
        if not valid.all():
            indices = distance_transform_edt(
                ~valid, return_distances=False, return_indices=True
            )
            a = a[tuple(indices)]
        packed = np.rint((a.astype("float64") + 32768) * 256).astype("uint32")
        rgba = np.stack(
            [
                (packed >> 16) & 255,
                (packed >> 8) & 255,
                packed & 255,
                np.full_like(packed, 255),
            ],
            axis=-1,
        ).astype("uint8")
        stream = io.BytesIO()
        Image.fromarray(rgba, "RGBA").save(stream, format="PNG")
        data = stream.getvalue()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(data)
        return data
