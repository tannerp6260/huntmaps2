"""Immutable LANDFIRE companion; raw objects, analytical COGs, indexed vectors.

The existing GMU pack is an immutable dependency, never a destination for writes.
Preparation is resumable by exact request and bounded by received bytes, including
failed responses. No provider requests occur during analysis.
"""

import csv
import io
import json
import math
from pathlib import Path
import shutil
import urllib.parse
import urllib.request

import numpy as np
from osgeo import gdal, ogr, osr
from pyproj import Transformer
from shapely.ops import transform

from trail_scout.storage import (
    atomic,
    checked,
    digest,
    file_hash,
    now,
    read,
    seal,
    verify,
)

RELEASE = "LF2025"
LIMIT = 250 * 1024**2
SERVICE = "https://edcintl.cr.usgs.gov/arcgis/rest/services/Landfire_LF2025/LF2025_{}_CONUS/ImageServer"
LEGEND = "https://landfire.gov/sites/default/files/CSV/LF2025/LF2025_{}.csv"


def installed_root(paths):
    """Explicit state-local package wins; disposable analysis can reuse installed bytes."""
    local = paths.state / "community"
    return (
        local
        if (local / "active.json").exists()
        else paths.source / ".trailscout/community"
    )


def legends(data, product):
    rows = list(csv.DictReader(data.decode("utf-8-sig").splitlines()))
    name = "EVT_NAME" if product == "EVT" else "CLASSNAMES"
    if not rows or not {"VALUE", name}.issubset(rows[0]):
        raise ValueError("Not a release-specific analytical legend")
    result = {}
    for row in rows:
        code = int(row["VALUE"])
        if code in result or not row[name]:
            raise ValueError("Duplicate or unnamed legend code")
        result[code] = row
    return result


class Receiver:
    def __init__(self, folder, cancel=lambda: None):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.cancel = cancel
        self.ledger = read(
            self.folder / "ledger.json", {"received_bytes": 0, "requests": {}}
        )

    def get(self, url, cap):
        key = digest(url)
        prior = self.ledger["requests"].get(key)
        if prior:
            p = self.folder / "objects" / prior["sha256"]
            verify(p, prior["sha256"])
            return p, prior
        if self.ledger["received_bytes"] + cap > LIMIT:
            raise ValueError("Companion cumulative transfer admission exceeds 250 MiB")
        if shutil.disk_usage(self.folder).free - cap < 20 * 1024**3:
            raise ValueError("Companion must retain 20 GiB free space")
        self.cancel()
        target = self.folder / (key + ".partial")
        # An interrupted partial stays recoverable; do not overwrite it.
        if target.exists():
            target.rename(target.with_name(target.name + "." + digest(now())[:12]))
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "HuntMaps2 practical research/1"}
            )
            with urllib.request.urlopen(req, timeout=40) as response, target.open(
                "wb"
            ) as out:
                if response.status != 200:
                    raise ValueError("Provider returned a non-success response")
                length = response.headers.get("Content-Length")
                if length and int(length) > cap:
                    raise ValueError("Response exceeds admitted byte cap")
                size = 0
                while True:
                    self.cancel()
                    data = response.read(min(65536, cap - size + 1))
                    if not data:
                        break
                    size += len(data)
                    self.ledger["received_bytes"] += len(data)
                    out.write(data)
                    atomic(self.folder / "ledger.json", self.ledger)
                    if size > cap:
                        raise ValueError("Response exceeded byte cap; retained partial")
                if length and size != int(length):
                    raise ValueError("Truncated provider response")
            sha = file_hash(target)
            obj = self.folder / "objects" / sha
            obj.parent.mkdir(exist_ok=True)
            if obj.exists():
                verify(obj, sha)
                target.unlink()  # only our verified duplicate temporary transfer
            else:
                target.rename(obj)
            record = dict(url=url, sha256=sha, bytes=size, retrieved_utc=now())
            self.ledger["requests"][key] = record
            atomic(self.folder / "ledger.json", self.ledger)
            return obj, record
        except Exception:
            atomic(self.folder / "ledger.json", self.ledger)
            raise

    def json(self, url, cap=2 * 1024**2):
        path, record = self.get(url, cap)
        value = json.loads(path.read_text())
        if (
            not isinstance(value, dict)
            or "error" in value
            or value.get("exceededTransferLimit")
        ):
            raise ValueError(
                "Invalid/incomplete provider response; raw response retained"
            )
        return value, record


def indexed_vectors(path, pack):
    ds = ogr.GetDriverByName("GPKG").CreateDataSource(str(path))
    sr = osr.SpatialReference()
    sr.ImportFromEPSG(32613)
    layers = [
        (
            "unit",
            ogr.wkbMultiPolygon,
            [
                (
                    "co-gmu54",
                    pack.boundary,
                    {"role": "unit context, not access permission"},
                )
            ],
        ),
        (
            "network",
            ogr.wkbLineString,
            [
                (
                    r["id"],
                    r["geometry"],
                    dict(
                        r["properties"],
                        inventory_kind=r["kind"],
                        motor_closed=r["motor_closed"],
                        mvum=r["mvum"],
                    ),
                )
                for r in pack.network
            ],
        ),
    ]
    for key in ("ownership", "surface_management"):
        from shapely.geometry import shape

        projector = Transformer.from_crs(4326, 32613, always_xy=True).transform
        records = []
        for i, feature in enumerate(pack.extra.get(key, [])):
            props = feature.get("properties", {})
            ident = str(props.get("GlobalID", props.get("OBJECTID", i)))
            records.append(
                (ident, transform(projector, shape(feature["geometry"])), props)
            )
        if records:
            layers.append((key, ogr.wkbUnknown, records))
    for name, geom_type, records in layers:
        layer = ds.CreateLayer(name, sr, geom_type, options=["SPATIAL_INDEX=YES"])
        for field in ("source_id", "attributes_json"):
            layer.CreateField(ogr.FieldDefn(field, ogr.OFTString))
        for ident, geometry, props in records:
            f = ogr.Feature(layer.GetLayerDefn())
            f.SetField("source_id", ident)
            f.SetField("attributes_json", json.dumps(props, sort_keys=True))
            g = ogr.CreateGeometryFromWkb(geometry.wkb)
            if geom_type == ogr.wkbMultiPolygon:
                g = ogr.ForceToMultiPolygon(g)
            f.SetGeometry(g)
            if layer.CreateFeature(f) != 0:
                raise ValueError("Failed to preserve vector feature")
    ds = None


def freeze_access(pack, root):
    """Portable exact source objects; no dependency on analysis archives at runtime."""
    result = {}
    objects = root / "objects"
    objects.mkdir(exist_ok=True)
    for key, features in pack.extra.items():
        metadata = pack.extra_specs.get(key)
        if not metadata:
            continue
        original = pack.paths.source / "data/scouting" / (key + ".geojson")
        if metadata.get("sha256") and original.is_file():
            verify(original, metadata["sha256"])
            raw = original.read_bytes()
            recipe = (
                "exact verified raw source bytes; dates and original metadata retained"
            )
        else:
            raw = json.dumps(
                dict(type="FeatureCollection", features=features), sort_keys=True
            ).encode()
            recipe = "normalized current attributed feature collection; original merged source identities retained in original_metadata"
        import hashlib

        sha = hashlib.sha256(raw).hexdigest()
        target = objects / sha
        if target.exists():
            verify(target, sha)
        else:
            atomic(target, raw, binary=True)
        result[key] = dict(
            object_sha256=sha,
            bytes=len(raw),
            features=len(features),
            original_metadata=metadata,
            processing=recipe,
            coverage="bounded dated inventory; query footprint and provider restrictions retained in original metadata; not complete unit access or current closure coverage",
        )
    pack.recheck()
    return result


def prepare(pack, root, progress=lambda *a: None, cancel=lambda: None):
    root = Path(root)
    receiver = Receiver(root, cancel)
    boundary = transform(
        Transformer.from_crs(32613, 5070, always_xy=True).transform, pack.boundary
    )
    # 600 m supports all declared context radii even across unit edges.
    b = boundary.buffer(600).bounds
    meta, meta_record = receiver.json(SERVICE.format("EVT") + "?f=json")
    if (
        meta.get("pixelType") != "S16"
        or meta.get("bandCount") != 1
        or meta.get("pixelSizeX") != 30
    ):
        raise ValueError("Unexpected analytical service type/resolution")
    origin = (meta["extent"]["xmin"], meta["extent"]["ymin"])
    bounds = [
        origin[i % 2] + fn((b[i] - origin[i % 2]) / 30) * 30
        for i, fn in enumerate((math.floor, math.floor, math.ceil, math.ceil))
    ]
    width, height = [int((bounds[i + 2] - bounds[i]) / 30) for i in (0, 1)]
    if width * height > 4_000_000:
        raise ValueError("Companion exceeds bounded core export grid")
    sources = {}
    raw = {}
    for i, product in enumerate(("EVT", "EVC", "EVH")):
        cancel()
        progress("community", i, 3, "Validating LANDFIRE 2025 " + product)
        m, mr = receiver.json(SERVICE.format(product) + "?f=json")
        if (
            m.get("pixelType") != "S16"
            or m.get("bandCount") != 1
            or m.get("pixelSizeX") != 30
            or m.get("pixelSizeY") != 30
        ):
            raise ValueError("Analytical class service required")
        lp, lr = receiver.get(LEGEND.format(product), 1024**2)
        legend = legends(lp.read_bytes(), product)
        query = dict(
            f="json",
            bbox=",".join(str(x) for x in bounds),
            bboxSR=5070,
            imageSR=5070,
            size=f"{width},{height}",
            format="tiff",
            pixelType="S16",
            interpolation="RSP_NearestNeighbor",
            renderingRule=json.dumps({"rasterFunction": "None"}),
            noData=-9999,
        )
        export, er = receiver.json(
            SERVICE.format(product) + "/exportImage?" + urllib.parse.urlencode(query)
        )
        href = export.get("href", "")
        if urllib.parse.urlparse(href).hostname not in (
            "edcintl.cr.usgs.gov",
            "lfps.usgs.gov",
        ) or not href.startswith("https://"):
            raise ValueError("Unexpected export asset host")
        rp, rr = receiver.get(href, 32 * 1024**2)
        ds = gdal.Open(str(rp))
        expected_gt = (bounds[0], 30, 0, bounds[3], 0, -30)
        if (
            ds is None
            or ds.RasterCount != 1
            or ds.GetRasterBand(1).DataType != gdal.GDT_Int16
            or (ds.RasterXSize, ds.RasterYSize) != (width, height)
            or not np.allclose(ds.GetGeoTransform(), expected_gt, atol=1e-7, rtol=0)
        ):
            raise ValueError("Export raster extent/grid/bands differ from request")
        if ds.GetSpatialRef().GetAuthorityCode(None) != "5070":
            raise ValueError("Unexpected LANDFIRE CRS")
        a = ds.ReadAsArray()
        codes = set(int(x) for x in np.unique(a))
        if codes - set(legend):
            raise ValueError("Raster contains values absent from its release legend")
        raw[product] = rp
        sources[product] = dict(
            provider="USGS/USFS LANDFIRE",
            product=product,
            release=RELEASE,
            observation_dates=None,
            observation_note="2025 update label; individual pixel observation/acquisition dates unknown",
            acquisition_dates=None,
            retrieved_utc=rr["retrieved_utc"],
            request=er,
            service=mr,
            raw=rr,
            legend=lr,
            units="categorical code; decode only with this release's legend",
            crs="EPSG:5070",
            vertical_datum="not applicable to categorical vegetation height classes",
            grid=list(expected_gt),
            shape=[height, width],
            nodata=ds.GetRasterBand(1).GetNoDataValue(),
            codes=sorted(codes),
            valid_fraction=float(np.mean(a != -9999)),
            footprint_bounds=bounds,
            license="U.S. Government LANDFIRE public data; attribution USGS/USFS LANDFIRE; no field accuracy warranty",
            attribution_url="https://landfire.gov/data/lf2025",
            processing="raw S16 export; no rendering; nearest; aligned native 30 m grid; lossless COG",
            gaps=[
                "No understory, stem density, forage quality, stand age or optical transmission measurement",
                "Product update year is not per-pixel acquisition date",
            ],
        )
    extra_sources = freeze_access(pack, root)
    token = digest(
        dict(
            contract=1,
            recipe=2,
            base=pack.revision,
            sources=sources,
            extra_sources=extra_sources,
        )
    )
    final = root / "versions" / token
    if final.exists():
        spec = CommunityPackage(root, token).spec
        atomic(root / "active.json", {"id": token})
        return spec
    stage = root / "preparing" / token
    stage.mkdir(parents=True, exist_ok=True)
    for product, rp in raw.items():
        cancel()
        dst = stage / (product + ".tif")
        if dst.exists():
            # A failed unpublished stage is resumable; only rewrite our derived file.
            dst.unlink()
        gdal.Translate(
            str(dst),
            str(rp),
            format="COG",
            creationOptions=[
                "COMPRESS=DEFLATE",
                "BLOCKSIZE=256",
                "OVERVIEW_RESAMPLING=NEAREST",
            ],
        )
        check = gdal.Open(str(dst))
        if not np.array_equal(check.ReadAsArray(), gdal.Open(str(rp)).ReadAsArray()):
            raise ValueError("COG conversion changed categorical values")
        sources[product]["cog"] = dict(
            path=dst.name, sha256=file_hash(dst), bytes=dst.stat().st_size
        )
    vp = stage / "context.gpkg"
    if not vp.exists():
        indexed_vectors(vp, pack)
    spec = dict(
        contract=1,
        id=token,
        status="ready",
        unit="co-gmu54",
        release=RELEASE,
        base_pack_revision=pack.revision,
        base_manifest_sha256=file_hash(pack.folder / "pack.json"),
        sources=sources,
        recipe_version=2,
        extra_sources=extra_sources,
        vectors=dict(path=vp.name, sha256=file_hash(vp), bytes=vp.stat().st_size),
        source_received_bytes=receiver.ledger["received_bytes"],
        known_gaps=[
            "No current closure or parking certification",
            "Historical access snapshots retained with original attributes; ownership is not permission",
        ],
        prepared_utc=now(),
    )
    atomic(stage / "manifest.json", spec)
    seal(stage / "manifest.json")
    final.parent.mkdir(exist_ok=True)
    cancel()
    stage.rename(final)
    CommunityPackage(root, token)  # validate before active pointer publication
    atomic(root / "active.json", {"id": token})
    return spec


class CommunityPackage:
    def __init__(self, root, token=None):
        self.root = Path(root)
        token = token or read(self.root / "active.json", {}).get("id")
        if (
            not token
            or len(token) != 64
            or any(c not in "0123456789abcdef" for c in token)
        ):
            raise ValueError("No installed community companion; prepare it explicitly")
        self.folder = self.root / "versions" / token
        self.spec = read(checked(self.folder / "manifest.json"))
        if self.spec.get("release") != RELEASE or self.spec.get("id") != token:
            raise ValueError("Unsupported community package release/identity")
        self.legend = {}
        for product, source in self.spec["sources"].items():
            if source["release"] != RELEASE or source["product"] != product:
                raise ValueError("Mixed source product/release")
            lp = self.root / "objects" / source["legend"]["sha256"]
            verify(lp, source["legend"]["sha256"])
            self.legend[product] = legends(lp.read_bytes(), product)
            self.asset(source["cog"])
        self.asset(self.spec["vectors"])
        for record in self.spec.get("extra_sources", {}).values():
            self.access_object(record)

    def access_object(self, record):
        sha = record.get("object_sha256", "")
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ValueError("Invalid portable access object identity")
        path = self.root / "objects" / sha
        verify(path, sha)
        return path

    def asset(self, record):
        p = self.folder / record["path"]
        if not p.resolve().is_relative_to(self.folder.resolve()):
            raise ValueError("Package path escaped version root")
        verify(p, record["sha256"])
        if p.suffix == ".tif":
            ds = gdal.Open(str(p))
            if (
                ds is None
                or ds.GetFileList() != [str(p)]
                or any(Path(str(p) + s).exists() for s in (".aux.xml", ".ovr", ".msk"))
            ):
                raise ValueError("Unsealed raster dependency")
        return p

    def window(self, bounds, resolution=30, epsg=32613):
        if resolution < 30 or resolution > 120 or epsg != 32613:
            raise ValueError("Use conservative metric community support, 30–120 m")
        if (
            any(not math.isfinite(x) for x in bounds)
            or bounds[2] <= bounds[0]
            or bounds[3] <= bounds[1]
        ):
            raise ValueError("Invalid window bounds")
        if (bounds[2] - bounds[0]) * (
            bounds[3] - bounds[1]
        ) / resolution**2 > 3_000_000:
            raise ValueError("Community window exceeds cell cap")
        arrays = {}
        for name, source in self.spec["sources"].items():
            ds = gdal.Warp(
                "",
                str(self.asset(source["cog"])),
                format="MEM",
                outputBounds=bounds,
                dstSRS=f"EPSG:{epsg}",
                xRes=resolution,
                yRes=resolution,
                resampleAlg="near",
                errorThreshold=0,
                overviewLevel="NONE",
                dstNodata=-9999,
            )
            arrays[name] = ds.ReadAsArray()
            if set(int(x) for x in np.unique(arrays[name])) - set(self.legend[name]):
                raise ValueError("Window categorical code invalid")
        return arrays, ds.GetGeoTransform(), ds.GetProjection()
