"""Resumable bounded preparation of a Colorado GMU core source pack.

Run with .venv/bin/python -m huntmaps_gui.pack_builder --unit 54 --version VERSION.
Completed pieces and failed partials are retained. SIGTERM/cancellation never
publishes readiness. No existing version or source file is overwritten.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import numpy as np
from osgeo import gdal, osr
from shapely.geometry import box, shape, mapping
from shapely.ops import unary_union, transform
from glassing.acquire import digest
from glassing.transfer import project
from . import unit_packs as packs
from .storage import read_json, write, locked
from .downloads import check_space, RESERVE
from .acquisition import validate

BUDGET = 1_500_000_000
HEADROOM = 4 * 1024**3


class Transfer:
    def __init__(self, folder, budget=BUDGET):
        self.folder = folder
        self.budget = budget
        self.manifest = read_json(folder / "sources.json", {})
        self.ledger = read_json(
            folder / "transfer.json", dict(received_bytes=0, reused_bytes=0)
        )

    def fetch(self, name, url, limit, **meta):
        path = self.folder / name
        old = self.manifest.get(name)
        if path.exists():
            if not old or old["url"] != url or digest(path) != old["sha256"]:
                raise ValueError(
                    f"Changed source retained: {path}; restore exact bytes or choose new version"
                )
            return path
        check_space(self.folder, 3 * limit + HEADROOM)
        partial = path.with_suffix(path.suffix + ".partial")
        if partial.exists():
            retained = partial.with_name(
                partial.name
                + ".retained-"
                + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
            )
            partial.rename(retained)
        print(
            f'SOURCE {name}: ceiling {limit:,} bytes; cumulative {self.ledger["received_bytes"]:,}/{self.budget:,}',
            flush=True,
        )
        if limit > self.budget - self.ledger["received_bytes"]:
            raise ValueError(
                "Pack cumulative transfer budget exhausted; review ledger before increasing budget"
            )
        request = urllib.request.Request(
            url, headers={"User-Agent": "HuntMaps2-local-pack/1"}
        )
        with urllib.request.urlopen(request, timeout=90) as response, partial.open(
            "wb"
        ) as out:
            length = response.headers.get("Content-Length")
            if length and int(length) > limit:
                raise ValueError("Response exceeds bounded piece allowance")
            size = 0
            while True:
                check_space(self.folder, HEADROOM + 1024**2)
                block = response.read(min(1024**2, limit - size + 1))
                if not block:
                    break
                size += len(block)
                self.ledger["received_bytes"] += len(block)
                write(self.folder / "transfer.json", self.ledger)
                if size > limit or self.ledger["received_bytes"] > self.budget:
                    raise ValueError(
                        "Cumulative/piece transfer ceiling exceeded; partial retained"
                    )
                out.write(block)
                if size // (32 * 1024**2) != (size - len(block)) // (32 * 1024**2):
                    print(f"PROGRESS {name}: {size:,} bytes", flush=True)
            out.flush()
            os.fsync(out.fileno())
        if length and size != int(length):
            raise ValueError("Truncated provider response; partial retained")
        if path.suffix == ".tif":
            validate(partial, path.name, meta)
        elif path.suffix == ".json" or path.suffix == ".geojson":
            v = json.loads(partial.read_text())
            if isinstance(v, dict) and (
                v.get("error") or v.get("exceededTransferLimit")
            ):
                raise ValueError(
                    "Provider error/truncation; partial retained: " + str(v)[:500]
                )
        self.manifest[name] = dict(
            url=url,
            sha256=digest(partial),
            bytes=size,
            retrieved_utc=datetime.now(timezone.utc).isoformat(),
            **meta,
        )
        partial.rename(path)
        write(self.folder / "sources.json", self.manifest)
        return path

    def reuse(self, name, path, meta):
        dest = self.folder / name
        if digest(path) != meta["sha256"]:
            raise ValueError("Local source checksum mismatch: " + str(path))
        if dest.exists():
            if digest(dest) != meta["sha256"]:
                raise ValueError("Changed retained pack source: " + str(dest))
            return dest
        check_space(self.folder, path.stat().st_size + HEADROOM)
        partial = dest.with_suffix(dest.suffix + ".copy")
        shutil.copyfile(path, partial)
        if digest(partial) != meta["sha256"]:
            raise ValueError("Interrupted/corrupt source copy retained")
        partial.rename(dest)
        self.manifest[name] = dict(
            meta, reuse_origin=str(path), bytes=dest.stat().st_size
        )
        self.ledger["reused_bytes"] += dest.stat().st_size
        write(self.folder / "sources.json", self.manifest)
        write(self.folder / "transfer.json", self.ledger)
        print(f"REUSED {name}: {dest.stat().st_size:,} bytes", flush=True)
        return dest


def query(base, **params):
    return base + "?" + urllib.parse.urlencode(params)


def pieces(bounds, span):
    x, y, X, Y = bounds
    for r in range(math.ceil((Y - y) / span)):
        for c in range(math.ceil((X - x) / span)):
            yield f"{r:02d}-{c:02d}", [
                x + c * span,
                y + r * span,
                min(X, x + (c + 1) * span),
                min(Y, y + (r + 1) * span),
            ]


def raster_check(path, vegetation=False):
    ds = gdal.Open(str(path))
    sr = ds.GetSpatialRef()
    gt = ds.GetGeoTransform()
    if (
        sr.GetAuthorityCode(None) != "32613"
        or gt[2]
        or gt[4]
        or gt[1] != (30 if vegetation else 10)
        or gt[5] != -gt[1]
    ):
        raise ValueError("Incompatible prepared metric raster grid")
    if [Path(p).resolve() for p in ds.GetFileList()] != [path.resolve()]:
        raise ValueError("Unrecorded raster dependencies")
    band = ds.GetRasterBand(1)
    unknown = total = 0
    for row in range(0, ds.RasterYSize, 256):
        a = band.ReadAsArray(0, row, ds.RasterXSize, min(256, ds.RasterYSize - row))
        valid = (
            band.GetMaskBand().ReadAsArray(
                0, row, ds.RasterXSize, min(256, ds.RasterYSize - row)
            )
            > 0
        ) & np.isfinite(a)
        if vegetation:
            valid &= (a >= 0) & (a <= 100)
        if not vegetation and not valid.all():
            raise ValueError(
                "Missing obstruction terrain; acquisition/processing gap cannot be filled"
            )
        unknown += int((~valid).sum())
        total += a.size
    return dict(
        crs="EPSG:32613",
        resolution_m=gt[1],
        units="percent" if vegetation else "m",
        dimensions=[ds.RasterXSize, ds.RasterYSize],
        geotransform=list(gt),
        nodata=band.GetNoDataValue(),
        unknown_cells=unknown,
        total_cells=total,
    )


def build(unit, version, reuse_version=None):
    unit_id = f"co-gmu{unit}"
    packs.identifier(version)
    if (packs.root() / "versions" / unit_id / version).exists():
        return packs.register_existing(unit_id, version)
    folder = packs.root() / "preparing" / f"{unit_id}-{version}"
    folder.mkdir(parents=True, exist_ok=True)
    with locked(folder / "build"):

        def progress(stage, **extra):
            write(
                folder / "progress.json",
                dict(
                    unit_id=unit_id,
                    version=version,
                    stage=stage,
                    updated_utc=datetime.now(timezone.utc).isoformat(),
                    **extra,
                ),
            )
            print("STAGE " + stage, flush=True)

        t = Transfer(folder)
        try:
            check_space(folder, 3 * BUDGET + HEADROOM)
            if reuse_version:
                prior, previous = packs.load(unit_id, reuse_version)
                previous_sources = read_json(prior / "sources.json")
                for name, metadata in previous_sources.items():
                    t.reuse(name, prior / name, metadata)
                write(
                    folder / "reuse.json",
                    dict(
                        unit_id=unit_id,
                        version=reuse_version,
                        manifest_sha256=digest(prior / "pack.json"),
                        note="Explicit reuse of an immutable source snapshot; no assertion of current provider equivalence.",
                    ),
                )
            progress("Checking official unit and source catalog")
            cpw = "https://services5.arcgis.com/ttNGmDvKQA7oeDQ3/ArcGIS/rest/services/CPWAdminData/FeatureServer/6"
            layer = t.fetch(
                "boundary-layer.json",
                query(cpw, f="json"),
                5_000_000,
                provider="Colorado Parks and Wildlife",
            )
            bp = t.fetch(
                "boundary.geojson",
                query(
                    cpw + "/query",
                    where=f"GMUID={unit}",
                    outFields="*",
                    outSR=4326,
                    returnGeometry="true",
                    f="geojson",
                ),
                5_000_000,
                provider="Colorado Parks and Wildlife",
                license="CPW public GIS; retain agency terms",
            )
            boundary = read_json(bp)
            if (
                len(boundary.get("features", [])) != 1
                or boundary["features"][0]["properties"]["GMUID"] != unit
            ):
                raise ValueError("Official unit selection incomplete")
            area = transform(
                project(4326, 32613), shape(boundary["features"][0]["geometry"])
            )
            if not area.is_valid:
                raise ValueError("Unit geometry requires explicit repair/review")
            # 10 km existing access query domain dominates maximum viewshed 3 km,
            # 20 m terrain gutter, 360 m habitat neighborhoods + native/grid padding.
            b = area.bounds
            bounds = [
                math.floor((b[0] - 10440) / 30) * 30,
                math.floor((b[1] - 10440) / 30) * 30,
                math.ceil((b[2] + 10440) / 30) * 30,
                math.ceil((b[3] + 10440) / 30) * 30,
            ]
            progress(
                "Checking measured storage and elevation catalogs",
                bounds=bounds,
                reserve_bytes=RESERVE,
                peak_additional_estimate=3 * BUDGET + HEADROOM,
            )
            terrain = []
            for tile in ("n39w108", "n39w107"):
                u = "https://prd-tnm.s3.amazonaws.com/?" + urllib.parse.urlencode(
                    {
                        "list-type": 2,
                        "prefix": f"StagedProducts/Elevation/13/TIFF/current/{tile}/",
                    }
                )
                cat = t.fetch(
                    tile + "-catalog.xml",
                    u,
                    1_000_000,
                    provider="USGS official staged-products catalog",
                )
                nodes = ET.fromstring(cat.read_bytes())
                ns = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
                entries = {
                    n.find("s:Key", ns).text: n for n in nodes.findall("s:Contents", ns)
                }
                name = f"USGS_13_{tile}.tif"
                key = f"StagedProducts/Elevation/13/TIFF/current/{tile}/{name}"
                entry = entries[key]
                size = int(entry.find("s:Size", ns).text)
                xml = t.fetch(
                    tile + "-metadata.xml",
                    "https://prd-tnm.s3.amazonaws.com/" + key.replace(".tif", ".xml"),
                    1_000_000,
                    provider="USGS 3DEP tile metadata",
                )
                content = xml.read_text().lower()
                if (
                    not (
                        "navd88" in content
                        or "north american vertical datum of 1988" in content
                    )
                    or "meter" not in content
                ):
                    raise ValueError(
                        "DEM vertical units/datum not identified by official metadata"
                    )
                local = (
                    packs.current().source_dir
                    / "data/gmu54/USGS_13_n39w108_20220331.tif"
                )
                if tile == "n39w108" and local.is_file():
                    m = read_json(local.parent / "manifest.json")[local.name]
                    path = t.reuse(
                        local.name,
                        local,
                        dict(
                            m,
                            vertical_units="m",
                            vertical_datum="NAVD88",
                            publication_date="2022-03-31",
                        ),
                    )
                else:
                    path = t.fetch(
                        name,
                        "https://prd-tnm.s3.amazonaws.com/" + key,
                        size,
                        provider="USGS 3DEP",
                        vertical_units="m",
                        vertical_datum="NAVD88",
                        publication_date=ET.fromstring(xml.read_bytes()).findtext(
                            ".//pubdate"
                        ),
                        object_last_modified_utc=entry.find("s:LastModified", ns).text,
                        license="USGS public domain",
                    )
                    # Older snapshot metadata used the S3 object timestamp under
                    # publication_date. Correct only this new version, using XML.
                    t.manifest[name]["publication_date"] = ET.fromstring(
                        xml.read_bytes()
                    ).findtext(".//pubdate")
                    t.manifest[name]["object_last_modified_utc"] = entry.find(
                        "s:LastModified", ns
                    ).text
                    t.manifest[name][
                        "acquisition_date"
                    ] = "Mixed source dates; see retained XML time period"
                    write(folder / "sources.json", t.manifest)
                terrain.append(str(path))
            derived = {}
            diagnostics = {}
            progress("Preparing complete buffered terrain")
            path = folder / "dem.tif"
            if not path.exists():
                temp = folder / "dem.build.tif"
                ds = gdal.Warp(
                    str(temp),
                    terrain,
                    format="GTiff",
                    dstSRS="EPSG:32613",
                    outputBounds=bounds,
                    xRes=10,
                    yRes=10,
                    resampleAlg="bilinear",
                    dstNodata=-9999,
                    outputType=gdal.GDT_Float32,
                    creationOptions=["TILED=YES", "COMPRESS=DEFLATE", "PREDICTOR=3"],
                    warpMemoryLimit=64 * 1024**2,
                )
                if ds is None:
                    raise ValueError("Terrain preparation failed; retained sources")
                ds = None
                raster_check(temp)
                temp.rename(path)
            diagnostics["dem"] = raster_check(path)
            derived["dem"] = dict(
                path=path.name,
                sha256=digest(path),
                provider="USGS 3DEP buffered local mosaic",
                acquisition_date="Unknown; mixed tile source vintages, see source metadata",
                license="USGS public domain",
                vertical_units="m",
                vertical_datum="NAVD88; no datum correction",
                preparation="bilinear EPSG:32613 at 10m; sources retained; no hole filling",
            )
            for k, component in [
                ("tree", "tree"),
                ("shrub", "shrub"),
                ("herb", "herbaceous"),
            ]:
                progress(f"Preparing RCMAP 2023 {k}; bounded resumable pieces")
                sources = []
                for i, bb in pieces(bounds, 18000):
                    # Padded WCS requests avoid native-grid/reprojection acquisition gaps.
                    padded = [bb[0] - 120, bb[1] - 120, bb[2] + 120, bb[3] + 120]
                    u = query(
                        f"https://www.mrlc.gov/geoserver/rcmap_{k}/wcs",
                        service="WCS",
                        version="1.0.0",
                        request="GetCoverage",
                        coverage=f"rcmap_{k}:rcmap_{component}_2023",
                        crs="EPSG:32613",
                        response_crs="EPSG:32613",
                        bbox=",".join(map(str, padded)),
                        resx=30,
                        resy=30,
                        format="GeoTIFF",
                        interpolation="nearest neighbor",
                    )
                    raw = t.fetch(
                        f"{k}-{i}.tif",
                        u,
                        8_000_000,
                        provider="USGS RCMAP",
                        product="RCMAP fractional cover",
                        component=component,
                        observation_year=2023,
                        source_policy_version=1,
                        product_release="Unknown; annual WCS layer snapshot",
                        license="USGS public domain",
                        units="percent fractional cover",
                    )
                    from glassing.owner_data import coverage

                    probe = coverage(raw, bb, 32613, 30, True)
                    if not probe["geographic_coverage"]:
                        raise ValueError(
                            "Vegetation acquisition footprint gap: " + str(raw)
                        )
                    sources.append(str(raw))
                path = folder / (k + ".tif")
                if not path.exists():
                    ds = gdal.Warp(
                        str(folder / (k + ".build.tif")),
                        sources,
                        format="GTiff",
                        dstSRS="EPSG:32613",
                        outputBounds=bounds,
                        xRes=30,
                        yRes=30,
                        resampleAlg="near",
                        dstNodata=-9999,
                        outputType=gdal.GDT_Float32,
                        creationOptions=[
                            "TILED=YES",
                            "COMPRESS=DEFLATE",
                            "PREDICTOR=3",
                        ],
                    )
                    ds = None
                    raster_check(folder / (k + ".build.tif"), True)
                    (folder / (k + ".build.tif")).rename(path)
                diagnostics[k] = raster_check(path, True)
                derived[k] = dict(
                    t.manifest[Path(sources[0]).name],
                    acquisition_date="2023 annual product; individual acquisition dates unknown",
                    path=path.name,
                    sha256=digest(path),
                    preparation="nearest-neighbor mosaic; intrinsic source NoData retained; 30m analysis support, delivered source resolution recorded",
                    source_pieces=[Path(s).name for s in sources],
                )
            progress("Preparing complete seasonal and roads/trails inventory")
            networks = {"roads": [], "trails": []}
            context_features = []
            for k, base in [
                (
                    "summer",
                    "https://services5.arcgis.com/ttNGmDvKQA7oeDQ3/arcgis/rest/services/CPWSpeciesData/FeatureServer/99",
                ),
                (
                    "winter",
                    "https://services5.arcgis.com/ttNGmDvKQA7oeDQ3/arcgis/rest/services/CPWSpeciesData/FeatureServer/105",
                ),
                (
                    "roads",
                    "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RoadBasic_01/MapServer/0",
                ),
                (
                    "trails",
                    "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_TrailNFSPublish_01/MapServer/0",
                ),
            ]:
                t.fetch(
                    k + "-metadata.json",
                    query(base, f="json"),
                    5_000_000,
                    provider="CPW" if k in ("summer", "winter") else "USFS EDW",
                )
                all_features = {}
                for i, bb in pieces(bounds, 18000):
                    params = dict(
                        where="1=1",
                        geometry=",".join(map(str, bb)),
                        geometryType="esriGeometryEnvelope",
                        inSR=32613,
                        spatialRel="esriSpatialRelIntersects",
                    )
                    count = read_json(
                        t.fetch(
                            f"{k}-{i}-count.json",
                            query(
                                base + "/query",
                                **params,
                                returnCountOnly="true",
                                f="json",
                            ),
                            1_000_000,
                        )
                    )["count"]
                    raw = t.fetch(
                        f"{k}-{i}.geojson",
                        query(
                            base + "/query",
                            **params,
                            outSR=4326,
                            outFields="*",
                            returnGeometry="true",
                            f="geojson",
                        ),
                        10_000_000,
                        provider=(
                            "Colorado Parks and Wildlife"
                            if k in ("summer", "winter")
                            else "USFS EDW"
                        ),
                        acquisition_date="Service snapshot; feature dates retained",
                        license="Public agency GIS; retain metadata/terms",
                        coverage_bounds=bb,
                        coverage_epsg=32613,
                        expected_count=count,
                    )
                    value = read_json(raw)
                    if (
                        value.get("type") != "FeatureCollection"
                        or len(value["features"]) != count
                    ):
                        raise ValueError(
                            "Incomplete agency inventory; count/query mismatch: "
                            + str(raw)
                        )
                    if k in networks:
                        from .scouting_network import parse_lines

                        parse_lines(raw.read_bytes(), ".geojson", True)
                        ll = list(
                            transform(
                                project(32613, 4326), box(*bb).segmentize(100)
                            ).bounds
                        )
                        networks[k].append(dict(path=raw.name, bounds=ll, count=count))
                        for f in value["features"]:
                            g = shape(f["geometry"]).intersection(
                                box(
                                    *transform(
                                        project(32613, 4326), area.envelope
                                    ).bounds
                                )
                            )
                            if not g.is_empty:
                                context_features.append(
                                    dict(
                                        type="Feature",
                                        geometry=mapping(g.simplify(0.00015)),
                                        properties={
                                            "kind": k,
                                            "source": "USFS EDW mapped inventory",
                                        },
                                    )
                                )
                    else:
                        for f in value["features"]:
                            all_features[json.dumps(f, sort_keys=True)] = f
                if k not in networks:
                    from shapely import make_valid

                    fs = []
                    for f in all_features.values():
                        g = shape(f["geometry"])
                        if not g.is_valid:
                            g = make_valid(g)
                        if (
                            g.geom_type not in ("Polygon", "MultiPolygon")
                            or not g.is_valid
                        ):
                            raise ValueError(
                                "Agency range needs manual geometry review"
                            )
                        fs.append(dict(f, geometry=mapping(g)))
                    path = folder / (k + ".geojson")
                    write(path, dict(type="FeatureCollection", features=fs))
                    derived[k] = dict(
                        path=path.name,
                        sha256=digest(path),
                        provider="Colorado Parks and Wildlife",
                        acquisition_date="Service snapshot; feature dates retained",
                        license="CPW public GIS; source terms in retained metadata",
                        preparation="Dissjoint query responses deduplicated; explicit WGS84 normalized; GEOS make_valid where required; raw preserved",
                        coverage_bounds=bounds,
                        coverage_epsg=32613,
                    )
            write(
                folder / "context.geojson",
                dict(type="FeatureCollection", features=context_features),
            )
            progress("Validating immutable pack and publishing")
            # Local overview; source is terrain, not a required external basemap.
            small = gdal.Warp(
                "",
                str(folder / "dem.tif"),
                format="MEM",
                width=1400,
                height=1300,
                resampleAlg="bilinear",
            )
            gdal.DEMProcessing(
                str(folder / "hillshade.tif"),
                small,
                "hillshade",
                format="GTiff",
                computeEdges=True,
                creationOptions=["COMPRESS=DEFLATE"],
            )
            small = None
            assets = {}
            for p in folder.iterdir():
                if (
                    p.is_file()
                    and p.name not in ("progress.json", "pack.json", "seal.json")
                    and not p.name.endswith((".lock", ".partial"))
                ):
                    assets[p.name] = dict(
                        path=p.name, bytes=p.stat().st_size, sha256=digest(p)
                    )
            for spec in derived.values():
                spec["bytes"] = assets[spec["path"]]["bytes"]
            manifest = dict(
                contract=1,
                status="ready",
                unit_id=unit_id,
                version=version,
                label=f"Colorado GMU {unit}",
                state="Colorado",
                gmu=unit,
                epsg=32613,
                created_utc=datetime.now(timezone.utc).isoformat(),
                boundary=bp.name,
                bounds=list(shape(boundary["features"][0]["geometry"]).bounds),
                context="context.geojson",
                overview_corners=[
                    list(project(32613, 4326)(x, y))
                    for x, y in [
                        (bounds[0], bounds[3]),
                        (bounds[2], bounds[3]),
                        (bounds[2], bounds[1]),
                        (bounds[0], bounds[1]),
                    ]
                ],
                support=dict(
                    bounds=bounds,
                    epsg=32613,
                    buffer_m=10440,
                    maximum_visibility_radius_m=3000,
                    terrain_gutter_m=20,
                    approach_radius_m=2000,
                    access_query_radius_m=10000,
                    habitat_neighborhood_m=360,
                    alignment_m=30,
                ),
                detail=dict(
                    status="selected-area",
                    note="Basic terrain ready throughout unit. Detailed measured scenes require selected-area preparation; whole-unit detail is not prepared.",
                ),
                data=derived,
                assets=assets,
                networks=networks,
                network_provider="USFS EDW roads and trails; mapped inventory completeness only, no legal/safe access certification",
                diagnostics=diagnostics,
                storage=dict(
                    **t.ledger,
                    retained_bytes=sum(s["bytes"] for s in assets.values()),
                    peak_additional_estimate_bytes=3 * BUDGET + HEADROOM,
                    reserve_bytes=RESERVE,
                ),
                settings=dict(
                    dem_resample="bilinear",
                    vegetation_resample="nearest",
                    source_no_data="preserved",
                    grid="EPSG:32613 aligned metric; bounded local windows",
                ),
            )
            target = packs.publish(folder, manifest)
            print("READY " + str(target), flush=True)
            return target
        except BaseException as e:
            progress(
                (
                    "interrupted"
                    if isinstance(e, (KeyboardInterrupt, SystemExit))
                    else "failed"
                ),
                error=str(e),
                next_action=f"Retry unchanged: .venv/bin/python -m huntmaps_gui.pack_builder --unit {unit} --version {version}; completed pieces retained",
            )
            raise


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--unit", type=int, default=54, choices=[54])
    ap.add_argument("--version", required=True)
    ap.add_argument(
        "--reuse-version",
        help="Reuse an explicitly selected immutable source snapshot, without contacting providers",
    )
    a = ap.parse_args()
    build(a.unit, a.version, a.reuse_version)


if __name__ == "__main__":
    main()
