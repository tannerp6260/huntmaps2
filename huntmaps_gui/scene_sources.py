"""Deterministic compatible detail selection and bounded, dated scene imagery."""

import hashlib
import json
import math
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from shapely.geometry import box
from shapely.ops import unary_union
from osgeo import gdal
import numpy as np
from . import first_person as fp
from .catalog import read
from .storage import write
from .downloads import check_space

NAIP = (
    "https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer"
)


def lidar_acquisition(url):
    """Canonical project identity shared by catalog and historical cache records."""
    if not isinstance(url, str):
        raise ValueError("Lidar source URL is missing")
    parsed = urllib.parse.urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in ("rockyweb.usgs.gov", "prd-tnm.s3.amazonaws.com")
        or not parsed.path.lower().endswith(".laz")
    ):
        raise ValueError("Unrecognized USGS lidar source URL")
    project = (
        parsed.path.split("/LAZ/", 1)[0]
        if "/LAZ/" in parsed.path
        else parsed.path.rsplit("/", 1)[0]
    )
    if not project:
        raise ValueError("Lidar acquisition cannot be identified")
    return project


def cached_lidar(source, key):
    """Adapt old manifests in memory; never rewrite historical source records."""
    if not isinstance(source, dict):
        raise ValueError("Cached lidar metadata is missing")
    acquisition = lidar_acquisition(source.get("url", ""))
    if source.get("acquisition") and source["acquisition"] != acquisition:
        raise ValueError("Recorded lidar acquisition conflicts with its source URL")
    bounds = source.get("bounds", {})
    if not isinstance(bounds, dict):
        raise ValueError("Cached lidar coverage is unknown or invalid")
    values = [bounds.get(k) for k in ("minX", "minY", "maxX", "maxY")]
    if (
        any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in values)
        or values[0] >= values[2]
        or values[1] >= values[3]
    ):
        raise ValueError("Cached lidar coverage is unknown or invalid")
    if not isinstance(source.get("bytes"), int) or source["bytes"] <= 0:
        raise ValueError("Cached lidar source size is unknown")
    checksum = source.get("sha256")
    if not isinstance(checksum, str) or not re.fullmatch(r"[a-f0-9]{64}", checksum):
        raise ValueError("Cached lidar checksum is missing")
    return dict(
        source,
        key=key,
        acquisition=acquisition,
        title=source.get("title") or key,
        acquisition_date=source.get("acquisition_date") or "Unknown acquisition date",
        vertical_reference=source.get("vertical_reference")
        or "Requires LAS header inspection; no vertical correction implied",
        candidates=[],
        cached=True,
    )


def choose_acquisition(entries, bounds):
    groups = {}
    for source in entries:
        groups.setdefault(source["acquisition"], []).append(source)
    region = unary_union([box(*b) for b in bounds])

    def rank(item):
        name, sources = item
        footprints = [
            box(
                s["bounds"]["minX"],
                s["bounds"]["minY"],
                s["bounds"]["maxX"],
                s["bounds"]["maxY"],
            )
            for s in sources
        ]
        cached = [g for g, s in zip(footprints, sources) if s.get("cached")]
        coverage = unary_union(footprints).intersection(region).area
        cache_coverage = unary_union(cached).intersection(region).area if cached else 0
        dates = [
            s.get("acquisition_date", "")[:10]
            for s in sources
            if s.get("acquisition_date", "")[:4].isdigit()
        ]
        date = max(dates, default="0000-00-00")
        return (
            -cache_coverage,
            -coverage,
            tuple(-ord(c) for c in date),
            sum(s["bytes"] for s in sources if not s.get("cached")),
            name,
        )

    return min(groups.items(), key=rank)[0] if groups else None


def metadata(url):
    with urllib.request.urlopen(url, timeout=20) as response:
        raw = response.read(5_000_001)
    if len(raw) > 5_000_000:
        raise ValueError("Scene catalog exceeds 5 MB")
    result = json.loads(raw)
    if result.get("error") or result.get("exceededTransferLimit"):
        raise ValueError("Scene imagery catalog incomplete")
    return result


def imagery_plan(run, ids, radius):
    sources = []
    for cid in ids:
        point = run.points[cid]
        for tag, r, pixels in [("fine", 300, 1200), ("context", radius, 2048)]:
            bounds = [point["x"] - r, point["y"] - r, point["x"] + r, point["y"] + r]
            # Existing dated imagery with full geographic coverage needs no transfer.
            covered = False
            for image in run.images:
                path = run.path(image["path"])
                run.validate(path)
                ds = gdal.Open(str(path))
                gt = ds.GetGeoTransform()
                if (
                    ds.GetSpatialRef().IsSame(run.dem.GetSpatialRef())
                    and not gt[2]
                    and not gt[4]
                    and (image.get("dates") or image.get("acquisition_dates"))
                ):
                    footprint = box(
                        gt[0],
                        gt[3] + ds.RasterYSize * gt[5],
                        gt[0] + ds.RasterXSize * gt[1],
                        gt[3],
                    )
                    covered = covered or footprint.covers(box(*bounds))
            if covered:
                continue
            identity = dict(
                version=1, epsg=run.config["epsg"], bounds=bounds, pixels=pixels
            )
            # Reuse a verified, dated cached clip before consulting the provider.
            request_key = hashlib.sha256(
                json.dumps(identity, sort_keys=True).encode()
            ).hexdigest()[:32]
            record = read(fp.HOME / "imagery" / (request_key + ".json"))
            if record:
                fp.verify_file(Path(record["path"]), record["sha256"])
                sources.append(
                    dict(record, cached=True, remaining_bytes=0, candidates=[cid])
                )
                continue
            query = dict(
                f="json",
                where="Category=1",
                geometry=",".join(map(str, bounds)),
                geometryType="esriGeometryEnvelope",
                inSR=run.config["epsg"],
                spatialRel="esriSpatialRelIntersects",
                outFields="*",
                returnGeometry="false",
            )
            records = metadata(NAIP + "/query?" + urllib.parse.urlencode(query)).get(
                "features", []
            )
            dated = [
                f["attributes"]
                for f in records
                if f["attributes"].get("acquisition_date")
                and f["attributes"].get("Year")
            ]
            if not dated:
                continue
            year = max(f["Year"] for f in dated)
            chosen = sorted(
                [f for f in dated if f["Year"] == year], key=lambda f: f["OBJECTID"]
            )
            dates = sorted(
                {
                    datetime.fromtimestamp(f["acquisition_date"] / 1000, timezone.utc)
                    .date()
                    .isoformat()
                    for f in chosen
                }
            )
            params = dict(
                f="image",
                bbox=",".join(map(str, bounds)),
                bboxSR=run.config["epsg"],
                imageSR=run.config["epsg"],
                size=f"{pixels},{pixels}",
                format="tiff",
                mosaicRule=json.dumps(
                    dict(
                        mosaicMethod="esriMosaicLockRaster",
                        lockRasterIds=[f["OBJECTID"] for f in chosen],
                    )
                ),
                renderingRule=json.dumps(dict(rasterFunction="NaturalColor")),
            )
            ceiling = pixels * pixels * 4 + 1_000_000
            sources.append(
                dict(
                    identity,
                    key=request_key,
                    tag=tag,
                    candidates=[cid],
                    url=NAIP + "/exportImage?" + urllib.parse.urlencode(params),
                    bytes=ceiling,
                    remaining_bytes=ceiling,
                    dates=dates,
                    acquisition_date=", ".join(dates),
                    title="Dated NAIP " + tag + " imagery",
                    provider="USGS/USDA NAIP",
                    cached=False,
                    object_ids=[f["OBJECTID"] for f in chosen],
                    native_resolution_m=sorted(
                        {
                            f.get("resolution_value", f.get("Resolution"))
                            for f in chosen
                            if f.get("resolution_value", f.get("Resolution"))
                        }
                    ),
                )
            )
    return sources


def cached_source(source, kind):
    """Resolve verified complete cache entries without changing approval metadata."""
    if source.get("cached"):
        fp.verify_file(Path(source["path"]), source["sha256"])
        return source
    key = source.get("key")
    if not key:
        return None
    if Path(key).name != key:
        raise ValueError("Invalid scene source key")
    folder = fp.HOME / kind
    target = folder / (key + ".tif" if kind == "imagery" else key)
    record = (
        read(folder / (key + ".json"))
        if kind == "imagery"
        else read(folder / "manifest.json", {}).get(key)
    )
    if not target.exists():
        return None
    if not record or any(
        record.get(field) != source[field]
        for field in ("url", "bytes", "epsg", "bounds", "pixels", "object_ids")
        if field in source
    ):
        raise ValueError(
            "Cached scene source identity differs from the reviewed plan: " + key
        )
    fp.verify_file(target, record["sha256"])
    return dict(
        source,
        path=str(target),
        sha256=record["sha256"],
        cached=True,
        remaining_bytes=0,
    )


def acquire_imagery(source, allow):
    cached = cached_source(source, "imagery")
    if cached:
        return cached
    if not allow:
        return None
    from glassing.acquire import digest
    from .progress import received

    folder = fp.HOME / "imagery"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (source["key"] + ".tif")
    part = target.with_suffix(".partial")
    check_space(folder, source["bytes"])
    size = 0
    with urllib.request.urlopen(source["url"], timeout=30) as response, part.open(
        "wb"
    ) as out:
        if urllib.parse.urlparse(response.url).hostname != "imagery.nationalmap.gov":
            raise ValueError("Unexpected scene imagery host")
        while True:
            block = response.read(min(1024 * 1024, source["bytes"] - size + 1))
            if not block:
                break
            received(len(block), source["url"])
            size += len(block)
            ledger = read(fp.HOME / "sources" / "ledger.json", dict(received_bytes=0))
            ledger["received_bytes"] += len(block)
            write(fp.HOME / "sources" / "ledger.json", ledger)
            if size > source["bytes"] or ledger["received_bytes"] > fp.LIMIT:
                raise ValueError(
                    "Reviewed scene imagery allowance reached; partial retained"
                )
            check_space(folder, len(block))
            out.write(block)
    ds = gdal.Open(str(part))
    if (
        ds is None
        or ds.RasterCount < 3
        or ds.RasterXSize != source["pixels"]
        or ds.RasterYSize != source["pixels"]
    ):
        raise ValueError("Invalid scene imagery response")
    gt = ds.GetGeoTransform()
    actual = [
        gt[0],
        gt[3] + ds.RasterYSize * gt[5],
        gt[0] + ds.RasterXSize * gt[1],
        gt[3],
    ]
    if ds.GetSpatialRef().GetAuthorityCode(None) != str(
        source["epsg"]
    ) or not np.allclose(actual, source["bounds"], atol=0.05, rtol=0):
        raise ValueError("Scene imagery footprint or CRS differs from approved plan")
    ds = None
    checksum = digest(part)
    part.replace(target)
    record = dict(source, path=str(target), sha256=checksum, downloaded_bytes=size)
    write(folder / (source["key"] + ".json"), record)
    return record
