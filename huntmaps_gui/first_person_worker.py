"""Bounded lidar preparation subprocess; all outputs are separate GUI assets."""

import argparse
import hashlib
import json
import math
import os
import resource
import signal
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
import numpy as np
from osgeo import gdal
from scipy.spatial import Delaunay, cKDTree
from . import first_person as fp
from .catalog import ROOT, Run, read
from .jobs import write
from glassing.acquire import digest


def deps():
    try:
        import laspy, pyproj
    except ImportError as e:
        raise ValueError(
            "Missing local lidar decoder: "
            + str(e)
            + ". See docs/gui/FIRST_PERSON.md for isolated setup."
        )
    return laspy, pyproj


def geographic_box(run, cid):
    _, pyproj = deps()
    p = run.points[cid]
    tr = pyproj.Transformer.from_crs(run.config["epsg"], 4326, always_xy=True)
    corners = [
        tr.transform(p["x"] + x, p["y"] + y) for x in [-300, 300] for y in [-300, 300]
    ]
    return [
        min(v[0] for v in corners),
        min(v[1] for v in corners),
        max(v[0] for v in corners),
        max(v[1] for v in corners),
    ]


def discover(ident):
    fp.stage("Checking pilot source catalog metadata; no bulk downloads")
    p = fp.plan(ident)
    run = Run(fp.RUN)
    sources = {}
    existing = read(ROOT / "configs/vegetation.soap-creek-v1.json")["lidar_source"]
    cached = ROOT / existing["path"]
    if cached.exists():
        fp.verify_file(cached, existing["sha256"])
    for cid in fp.PILOT:
        bbox = geographic_box(run, cid)
        query = urllib.parse.urlencode(
            dict(
                datasets="Lidar Point Cloud (LPC)",
                bbox=",".join(map(str, bbox)),
                max=100,
            )
        )
        with urllib.request.urlopen(
            "https://tnmaccess.nationalmap.gov/api/v1/products?" + query, timeout=30
        ) as response:
            result = json.load(response)
        if result.get("errors") or result.get("total", 0) > 100:
            raise ValueError(
                "Lidar catalog incomplete or truncated; no source plan approved."
            )
        for item in result.get("items", []):
            url = item.get("downloadURL", "")
            parsed = urllib.parse.urlparse(url)
            if (
                parsed.scheme != "https"
                or parsed.hostname
                not in ["rockyweb.usgs.gov", "prd-tnm.s3.amazonaws.com"]
                or not parsed.path.lower().endswith(".laz")
            ):
                continue
            # Do not mix overlapping acquisitions in this pilot.
            if "CO_WestCentral_2019" not in url:
                continue
            size = int(item.get("sizeInBytes") or 0)
            if size <= 0:
                raise ValueError("Catalog source size missing; cannot bound downloads")
            key = hashlib.sha256(url.encode()).hexdigest()[:24] + ".laz"
            entry = sources.setdefault(
                key,
                dict(
                    key=key,
                    url=url,
                    bytes=size,
                    title=item["title"],
                    bounds=item["boundingBox"],
                    acquisition_date="2019 project; individual return dates not resolved",
                    publication_date=item.get("publicationDate"),
                    provider="USGS 3DEP",
                    candidates=[],
                    cached=False,
                ),
            )
            entry["candidates"].append(cid)
            if url == existing["url"] and cached.exists():
                entry.update(cached=True, path=str(cached), sha256=existing["sha256"])
            elif (fp.HOME / "sources" / key).exists():
                rec = read(fp.HOME / "sources" / "manifest.json", {}).get(key)
                if rec:
                    fp.verify_file(fp.HOME / "sources" / key, rec["sha256"])
                    entry.update(
                        cached=True,
                        path=str(fp.HOME / "sources" / key),
                        sha256=rec["sha256"],
                    )
    entries = list(sources.values())
    for s in entries:
        partial = fp.HOME / "sources" / Path(s["key"]).with_suffix(".partial")
        s["remaining_bytes"] = (
            0
            if s["cached"]
            else max(
                0, s["bytes"] - (partial.stat().st_size if partial.exists() else 0)
            )
        )
    estimated = sum(s["remaining_bytes"] for s in entries)
    spent = read(fp.HOME / "sources" / "ledger.json", {}).get("received_bytes", 0)
    p.update(
        prepared=True,
        sources=entries,
        estimated_new_bytes=estimated,
        already_received_bytes=spent,
        errors=(
            []
            if estimated + spent <= fp.LIMIT
            else [
                "Source estimate plus previous transfers exceeds the 500 MB pilot budget. Cached-only preparation is still available."
            ]
        ),
        coverage={
            cid: sum(cid in s["candidates"] for s in entries) for cid in fp.PILOT
        },
        source_note="Catalog bounds do not guarantee ground-return coverage. Fine-data gaps remain unknown.",
    )
    write(fp.HOME / "plans" / (ident + ".json"), p)
    fp.stage(
        "Acquisition plan ready: "
        + str(round(estimated / 1e6, 2))
        + " MB new sources; review before acquisition"
    )


def parallel_ranges(s, part, offset):
    import concurrent.futures
    import threading
    import shutil

    folder = part.parent
    lock = threading.Lock()
    receipts_path = folder / (s["key"] + ".ranges.json")
    receipts = read(receipts_path, {})

    def fetch(bounds):
        start, end = bounds
        name = s["key"] + f".range-{start}-{end}"
        target = folder / name
        if target.exists() and name in receipts:
            fp.verify_file(target, receipts[name])
            return target
        partial = target.with_suffix(target.suffix + ".partial")
        done = partial.stat().st_size if partial.exists() else 0
        size = end - start + 1
        if done > size:
            raise ValueError("Range partial larger than expected")
        if done < size:
            begin = start + done
            req = urllib.request.Request(
                s["url"],
                headers={
                    "Range": f"bytes={begin}-{end}",
                    "User-Agent": "HuntMaps2-local-first-person/1",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status != 206 or not response.headers.get(
                    "Content-Range", ""
                ).startswith(f"bytes {begin}-{end}/"):
                    raise ValueError(
                        "Source server did not return the exact requested byte range"
                    )
                if urllib.parse.urlparse(response.url).hostname not in [
                    "rockyweb.usgs.gov",
                    "prd-tnm.s3.amazonaws.com",
                ]:
                    raise ValueError("Unexpected lidar range host")
                with partial.open("ab" if done else "wb") as f:
                    while True:
                        block = response.read(1024 * 1024)
                        if not block:
                            break
                        with lock:
                            ledger = read(
                                folder / "ledger.json", dict(received_bytes=0)
                            )
                            if ledger["received_bytes"] + len(block) > fp.LIMIT:
                                raise ValueError(
                                    "500 MB cumulative pilot transfer cap reached; partial ranges retained"
                                )
                            before = ledger["received_bytes"]
                            ledger["received_bytes"] += len(block)
                            write(folder / "ledger.json", ledger)
                            if before // (8 * 1024 * 1024) != ledger[
                                "received_bytes"
                            ] // (8 * 1024 * 1024):
                                fp.stage(
                                    "Acquiring sources · "
                                    + str(round(ledger["received_bytes"] / 1e6, 1))
                                    + " MB actually received"
                                )
                        f.write(block)
                        if f.tell() > size:
                            raise ValueError("Source range exceeds reviewed byte count")
        if partial.stat().st_size != size:
            raise ValueError("Incomplete lidar byte range; safe partial retained")
        h = digest(partial)
        partial.replace(target)
        with lock:
            receipts[name] = h
            write(receipts_path, receipts)
        return target

    ranges = [
        (start, min(start + 8 * 1024 * 1024 - 1, s["bytes"] - 1))
        for start in range(offset, s["bytes"], 8 * 1024 * 1024)
    ]
    # One preparation job, at most eight bounded HTTP connections; never parallel analysis.
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        pieces = list(executor.map(fetch, ranges))
    assembled = part.with_suffix(".assembling")
    with assembled.open("wb") as out:
        if offset:
            with part.open("rb") as src:
                shutil.copyfileobj(src, out, 1024 * 1024)
        for piece in pieces:
            with piece.open("rb") as src:
                shutil.copyfileobj(src, out, 1024 * 1024)
    if assembled.stat().st_size != s["bytes"]:
        raise ValueError("Assembled lidar size differs from source plan")
    assembled.replace(part)
    for piece in pieces:
        piece.unlink()
    receipts_path.unlink(missing_ok=True)


def acquire(s, allow):
    signal.alarm(900) if __name__ == "__main__" else None
    if s["cached"]:
        fp.verify_file(Path(s["path"]), s["sha256"])
        return Path(s["path"]), s["sha256"]
    folder = fp.HOME / "sources"
    folder.mkdir(parents=True, exist_ok=True)
    manifest = read(folder / "manifest.json", {})
    path = folder / s["key"]
    if path.exists() and s["key"] in manifest:
        fp.verify_file(path, manifest[s["key"]]["sha256"])
        return path, manifest[s["key"]]["sha256"]
    if not allow:
        return None, None
    part = path.with_suffix(".partial")
    offset = part.stat().st_size if part.exists() else 0
    if offset > s["bytes"]:
        raise ValueError("Partial lidar source exceeds catalog size")
    headers = (
        {"User-Agent": "HuntMaps2-local-first-person/1", "Range": f"bytes={offset}-"}
        if offset
        else {"User-Agent": "HuntMaps2-local-first-person/1"}
    )
    fp.stage("Downloading " + s["title"] + f" · resume offset {offset} bytes")
    if offset < s["bytes"] and s["bytes"] - offset > 4 * 1024 * 1024:
        parallel_ranges(s, part, offset)
    elif offset < s["bytes"]:
        with urllib.request.urlopen(
            urllib.request.Request(s["url"], headers=headers), timeout=30
        ) as r:
            if urllib.parse.urlparse(r.url).hostname not in [
                "rockyweb.usgs.gov",
                "prd-tnm.s3.amazonaws.com",
            ]:
                raise ValueError("Unexpected lidar download host")
            if offset and (
                r.status != 206
                or not r.headers.get("Content-Range", "").startswith(f"bytes {offset}-")
            ):
                raise ValueError(
                    "Source server cannot safely resume this partial file; retained for inspection."
                )
            if offset == s["bytes"]:
                pass
            else:
                with part.open("ab" if offset else "wb") as f:
                    while True:
                        block = r.read(1024 * 1024)
                        if not block:
                            break
                        ledger = read(folder / "ledger.json", dict(received_bytes=0))
                        if ledger["received_bytes"] + len(block) > fp.LIMIT:
                            raise ValueError(
                                "500 MB cumulative pilot transfer cap reached; partial source retained."
                            )
                        # Account before writing to keep crashes conservative.
                        ledger["received_bytes"] += len(block)
                        write(folder / "ledger.json", ledger)
                        f.write(block)
                        if f.tell() > s["bytes"]:
                            raise ValueError(
                                "Source larger than its reviewed catalog estimate"
                            )
    if part.stat().st_size != s["bytes"]:
        raise ValueError("Incomplete lidar source; partial file retained")
    laspy, _ = deps()
    with laspy.open(part) as reader:
        if reader.header.parse_crs() is None:
            raise ValueError("Lidar header CRS missing")
    h = digest(part)
    part.replace(path)
    manifest[s["key"]] = dict(s, sha256=h)
    write(folder / "manifest.json", manifest)
    return path, h


def crop_points(run, cid, sources, radius=308):
    laspy, pyproj = deps()
    p = run.points[cid]
    parts = []
    references = set()
    hist = {}
    total = 0
    for s, path, h in sources:
        if cid not in s["candidates"]:
            continue
        fp.stage("Reading measured lidar returns for " + cid + " · " + path.name)
        with laspy.open(path, laz_backend=laspy.LazBackend.Lazrs) as reader:
            crs = reader.header.parse_crs()
            if crs is None:
                raise ValueError("Lidar CRS missing")
            vertical = [a for a in crs.axis_info if a.direction.lower() == "up"]
            if len(vertical) != 1:
                raise ValueError("Explicit lidar vertical reference and units required")
            unit = vertical[0].unit_conversion_factor
            vref = crs.sub_crs_list[-1].to_wkt() if crs.is_compound else None
            if not vref:
                raise ValueError("Lidar vertical datum missing")
            references.add(vref)
            tr = pyproj.Transformer.from_crs(crs, run.config["epsg"], always_xy=True)
            for chunk in reader.chunk_iterator(100000):
                x, y = tr.transform(np.asarray(chunk.x), np.asarray(chunk.y))
                z = np.asarray(chunk.z) * unit
                classes = np.asarray(chunk.classification)
                # Include 8 m support halo; display remains a 300 m circle.
                keep = (
                    (np.hypot(x - p["x"], y - p["y"]) <= radius)
                    & ~np.asarray(chunk.withheld, dtype=bool)
                    & ~np.isin(classes, [7, 18])
                    & np.isfinite(z)
                )
                a = np.column_stack(
                    [x[keep] - p["x"], y[keep] - p["y"], z[keep], classes[keep]]
                ).astype(np.float64)
                total += len(a)
                if total > 8_000_000:
                    raise ValueError(
                        "Local point count exceeds bounded preparation memory; no silent processing thinning."
                    )
                parts.append(a)
                u, n = np.unique(classes[keep], return_counts=True)
                for k, v in zip(u, n):
                    hist[str(k)] = hist.get(str(k), 0) + int(v)
    if len(references) > 1:
        raise ValueError(
            "Incompatible lidar vertical references; no guessed elevation adjustment"
        )
    return (
        (np.concatenate(parts) if parts else np.empty((0, 4))),
        next(iter(references), ""),
        hist,
    )


def fine_grid(points):
    ground = points[points[:, 3] == 2]
    if len(ground) < 3:
        return np.full((601, 601), np.nan, dtype=np.float32), np.full(
            (601, 601), np.nan, dtype=np.float32
        )
    # Select a measured ground return per 0.25 m bin; no synthetic height averaging.
    bins = np.floor(ground[:, :2] * 4).astype(int)
    _, ids = np.unique(bins, axis=0, return_index=True)
    ground = ground[np.sort(ids)]
    if len(ground) > 800000:
        raise ValueError("Ground-return mesh exceeds bounded triangulation memory")
    # Bounded local triangulations. A 10 m halo exceeds the 5 m allowed edge,
    # and limits Qhull working memory instead of triangulating ~650k points at once.
    heights = np.full((601, 601), np.nan, dtype=np.float32)
    for r0 in range(0, 601, 60):
        for c0 in range(0, 601, 60):
            r1 = min(601, r0 + 60)
            c1 = min(601, c0 + 60)
            xmin = c0 - 300
            xmax = c1 - 1 - 300
            ymax = 300 - r0
            ymin = 300 - (r1 - 1)
            keep = (
                (ground[:, 0] >= xmin - 10)
                & (ground[:, 0] <= xmax + 10)
                & (ground[:, 1] >= ymin - 10)
                & (ground[:, 1] <= ymax + 10)
            )
            local = ground[keep]
            if len(local) < 3:
                continue
            try:
                tri = Delaunay(local[:, :2])
            except __import__("scipy").spatial.QhullError:
                continue
            corners = local[tri.simplices, :2]
            edges = np.stack(
                [
                    np.linalg.norm(corners[:, 0] - corners[:, 1], axis=1),
                    np.linalg.norm(corners[:, 1] - corners[:, 2], axis=1),
                    np.linalg.norm(corners[:, 2] - corners[:, 0], axis=1),
                ],
                1,
            )
            permitted = edges.max(1) <= 5
            rr, cc = np.mgrid[r0:r1, c0:c1]
            q = np.column_stack([(cc - 300).ravel(), (300 - rr).ravel()])
            simplex = tri.find_simplex(q)
            safe = np.maximum(simplex, 0)
            valid = (
                (simplex >= 0) & permitted[safe] & (np.hypot(q[:, 0], q[:, 1]) <= 300)
            )
            transform = tri.transform[safe]
            b = np.einsum("nij,nj->ni", transform[:, :2], q - transform[:, 2])
            weights = np.column_stack([b, 1 - b.sum(1)])
            z = (local[tri.simplices[safe], 2] * weights).sum(1)
            heights[r0:r1, c0:c1] = np.where(valid, z, np.nan).reshape(r1 - r0, c1 - c0)
    rows, cols = np.indices((601, 601))
    q = np.column_stack([(cols - 300).ravel(), (300 - rows).ravel()])
    support = cKDTree(ground[:, :2]).query(q)[0].reshape(601, 601)
    return heights, np.where(np.isfinite(heights), support, np.nan).astype(np.float32)


def baseline_grid(run, cid):
    p = run.points[cid]
    gt = run.dem.GetGeoTransform()
    a = run.dem.ReadAsArray().astype(np.float32)
    r, c = np.indices(a.shape)
    xx = gt[0] + (c + 0.5) * gt[1] - p["x"]
    yy = gt[3] + (r + 0.5) * gt[5] - p["y"]
    # Crop around exact observer, retaining native cell centers.
    mask = (abs(xx) <= 2020) & (abs(yy) <= 2020)
    rr, cc = np.where(mask)
    if not len(rr):
        raise ValueError("Baseline has no local terrain coverage")
    lo, hi = rr.min(), rr.max() + 1
    left, right = cc.min(), cc.max() + 1
    nodata = run.dem.GetRasterBand(1).GetNoDataValue()
    a = np.where(np.isfinite(a) & (a != nodata), a, np.nan)[lo:hi, left:right]
    return a, float(gt[1]), float(xx[lo, left]), float(yy[lo, left])


def imagery_mosaic(images, epsg, bounds, pixels):
    """Coarse first, then valid sharp pixels; transparency never erases coverage."""
    rgba = np.zeros((pixels, pixels, 4), dtype=np.uint8)
    ordered = sorted(
        images,
        key=lambda i: abs(gdal.Open(str(i["path"])).GetGeoTransform()[1]),
        reverse=True,
    )
    for image in ordered:
        ds = gdal.Warp(
            "",
            str(image["path"]),
            format="MEM",
            dstSRS=f"EPSG:{epsg}",
            outputBounds=bounds,
            width=pixels,
            height=pixels,
            resampleAlg="bilinear",
            dstAlpha=True,
        )
        if ds is None:
            raise ValueError("Cannot warp cached imagery")
        a = ds.ReadAsArray()
        if a.shape[0] < 4:
            raise ValueError("Cached imagery lacks RGB/alpha")
        valid = a[-1] > 0
        for band in range(3):
            rgba[:, :, band][valid] = a[band][valid]
        rgba[:, :, 3][valid] = a[-1][valid]
    return rgba


def texture(run, cid, folder, radius=300, pixels=1200, name="imagery.png"):
    from PIL import Image

    p = run.points[cid]
    images = []
    for i in run.images:
        path = Path(i["path"])
        path = path if path.is_absolute() else ROOT / path
        run.validate(str(path))
        images.append(dict(i, path=str(path)))
    if not images:
        return None
    rgba = imagery_mosaic(
        images,
        run.config["epsg"],
        [p["x"] - radius, p["y"] - radius, p["x"] + radius, p["y"] + radius],
        pixels,
    )
    Image.fromarray(rgba, "RGBA").save(folder / name)
    return dict(
        file=name,
        radius_m=radius,
        pixels=pixels,
        pixel_spacing_m=2 * radius / pixels,
        coverage_fraction=float((rgba[:, :, 3] > 0).mean()),
        native_resolution_m=sorted(
            set(v for i in images for v in i.get("native_resolution_m", []))
        ),
        dates=sorted(
            set(
                d
                for i in images
                for d in i.get("dates", i.get("acquisition_dates", []))
            )
        ),
        warning="Photographed canopy is draped onto bare ground; not an eye-height vegetation reconstruction.",
    )


def above_ground(points, ground):
    z = fp.sample(ground, 1, -300, 300, points[:, 0], points[:, 1])
    return points[(points[:, 3] != 2) & np.isfinite(z) & (points[:, 2] - z > 0.5)]


def enrich_foliage(folder, meta):
    from . import vegetation_screen as veg
    from PIL import Image

    centres = np.fromfile(
        folder / meta["vegetation"]["centres_file"], dtype="<f4"
    ).reshape(-1, 3)
    kinds = np.fromfile(folder / meta["vegetation"]["kinds_file"], dtype="u1")
    rgba = (
        np.asarray(Image.open(folder / meta["texture"]["file"]).convert("RGBA"))
        if meta.get("texture")
        else np.zeros((1, 1, 4), dtype=np.uint8)
    )
    colors, used = veg.foliage_colors(centres, kinds, rgba)
    colors.tofile(folder / "vegetation-colors.bin")
    write(folder / "foliage-primitive.json", veg.primitive())
    meta["vegetation"].update(
        colors_file="vegetation-colors.bin",
        primitive_file="foliage-primitive.json",
        geometry_identifier=veg.GEOMETRY,
        color_sampled_cell_count=int(used.sum()),
        nearby_counts={
            str(r): int((np.hypot(centres[:, 0], centres[:, 2]) <= r).sum())
            for r in veg.RANGES
        },
        default_radius_m=veg.DEFAULT_RADIUS,
        ranges_m=list(veg.RANGES),
        display_cap=veg.DISPLAY_CAP,
        color_note="75% median valid aerial RGB beneath each centre +25% green, in sRGB; missing imagery uses green. Appearance, not classification.",
        warning="Inferred opaque rounded clumps; support, shape and screening thickness are assumptions, not validated vegetation opacity.",
    )


def publish_copy(run, cid, key, prior, target, started):
    import shutil

    meta = read(prior / "scene.json")
    for name, h in meta["hashes"].items():
        fp.verify_file(prior / name, h)
    for image in run.images:
        run.validate(image["path"])
    existing = sum(
        f.stat().st_size
        for area in ["bundles", "partial"]
        for f in (fp.HOME / area).rglob("*")
        if f.is_file()
    )
    needed = sum((prior / name).stat().st_size for name in meta["hashes"]) + 10_000_000
    if existing + needed > 800_000_000:
        raise ValueError("800 MB derived-asset cap lacks room; prior bundles retained.")
    folder = fp.HOME / "partial" / (key + "-" + __import__("uuid").uuid4().hex)
    folder.mkdir(parents=True)
    for name in meta["hashes"]:
        shutil.copyfile(prior / name, folder / name)
    enrich_foliage(folder, meta)
    meta.update(
        version=fp.VERSION,
        key=key,
        preparation_wall_s=round(time.monotonic() - started, 3),
        peak_process_rss_mib=round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2
        ),
        reused_cell_bundle=prior.name,
    )
    meta["hashes"] = {f.name: digest(f) for f in folder.iterdir() if f.is_file()}
    write(folder / "scene.json", meta)
    target.parent.mkdir(parents=True, exist_ok=True)
    folder.replace(target)
    write(fp.HOME / "ready" / (cid + ".json"), dict(key=key))
    fp.stage(cid + " nearby foliage ready; verified cells and photographs reused")


def enrich_clusters(folder, meta, points, ground_grid):
    from . import vegetation_screen as veg, foliage_clusters as clusters
    from PIL import Image

    # Fresh terrain preparation also reads the full 300 m fine-ground circle.
    # Foliage admission needs only the supported 120 m range plus its halo.
    local = points[np.hypot(points[:, 0], points[:, 1]) <= 122]
    centres, kinds, counts, eligible = veg.cells(
        local, ground_grid, meta["ground_m"], neighbor_support=True
    )
    selected = np.hypot(centres[:, 0], centres[:, 2]) <= 120
    centres = centres[selected]
    kinds = kinds[selected]
    counts = counts[selected]
    centres.tofile(folder / "cluster-centres.bin")
    kinds.tofile(folder / "cluster-kinds.bin")
    counts.tofile(folder / "cluster-counts.bin")
    image_path = (
        fp.asset_path(folder, meta, meta["texture"]["file"])
        if meta.get("texture")
        else None
    )
    rgba = (
        np.asarray(Image.open(image_path).convert("RGBA"))
        if image_path
        else np.zeros((1, 1, 4), dtype="u1")
    )
    meshes = {}
    for radius in veg.RANGES:
        fp.stage(
            meta["candidate"] + " building connected foliage · " + str(radius) + " m"
        )
        try:
            step, surfaces, total = clusters.build_range(centres, radius)
        except clusters.BudgetError as e:
            meshes[str(radius)] = dict(unavailable=True, reason=str(e))
            continue
        entries = {}
        for name, (vertices, faces) in surfaces.items():
            prefix = "cluster-" + str(radius) + "-" + name
            # Nearest admitted cell retains classification provenance for fallback color.
            from scipy.spatial import cKDTree

            nearest = (
                cKDTree(centres).query(vertices)[1]
                if len(vertices)
                else np.empty(0, int)
            )
            colors, used = veg.foliage_colors(vertices, kinds[nearest], rgba)
            vertices.tofile(folder / (prefix + "-vertices.bin"))
            faces.tofile(folder / (prefix + "-indices.bin"))
            colors.tofile(folder / (prefix + "-colors.bin"))
            entries[name] = dict(
                vertices_file=prefix + "-vertices.bin",
                indices_file=prefix + "-indices.bin",
                colors_file=prefix + "-colors.bin",
                triangle_count=len(faces),
                vertex_count=len(vertices),
                color_sampled_vertex_count=int(used.sum()),
            )
        meshes[str(radius)] = dict(
            sampling_interval_m=step, cell_count=total, scenarios=entries
        )
    if all(info.get("unavailable") for info in meshes.values()):
        raise ValueError(
            "No nearby range fits the cluster budget; prior scene retained."
        )
    meta["vegetation"] = dict(
        centres_file="cluster-centres.bin",
        kinds_file="cluster-kinds.bin",
        counts_file="cluster-counts.bin",
        cell_count=len(centres),
        inferred_cell_count=int(kinds.sum()),
        classified_cell_count=int((kinds == 0).sum()),
        strong_cell_count=int((counts >= 4).sum()),
        neighbor_supported_cell_count=int((counts < 4).sum()),
        eligible_distinct_returns=eligible,
        cell_size_m=1,
        minimum_distinct_returns=2,
        strong_minimum_distinct_returns=4,
        required_strong_neighbors=2,
        recursive_support=False,
        scenarios=veg.SCENARIOS,
        geometry_identifier=clusters.IDENTIFIER,
        meshes=meshes,
        triangle_cap=clusters.TRIANGLE_CAP,
        nearby_counts={
            str(r): int((np.hypot(centres[:, 0], centres[:, 2]) <= r).sum())
            for r in veg.RANGES
        },
        default_radius_m=veg.DEFAULT_RADIUS,
        ranges_m=list(veg.RANGES),
        warning="Connected opaque foliage inferred from measured support. Two/three-return cells require two original strong neighbors. Shape, thickness and opacity are assumptions, not validated vegetation.",
    )


def publish_clusters(run, cid, key, prior, target, started, sources):
    meta = read(prior / "scene.json")
    for name, h in meta["hashes"].items():
        fp.verify_file(fp.asset_path(prior, meta, name), h)
    for image in run.images:
        run.validate(image["path"])
    points, _, _ = crop_points(run, cid, sources, radius=122)
    path = fp.asset_path(prior, meta, "fine.npz")
    with np.load(path) as grid:
        ground_grid = grid["heights"]
    folder = fp.HOME / "partial" / (key + "-" + __import__("uuid").uuid4().hex)
    folder.mkdir(parents=True)
    # Immutable base assets are referenced and verified, never duplicated or moved.
    meta["asset_bundles"] = {
        name: meta.get("asset_bundles", {}).get(name, prior.name)
        for name in meta["hashes"]
    }
    enrich_clusters(folder, meta, points, ground_grid)
    meta.update(
        version=fp.VERSION,
        key=key,
        reused_base_bundle=prior.name,
        preparation_wall_s=round(time.monotonic() - started, 3),
        peak_process_rss_mib=round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2
        ),
    )
    meta["hashes"].update({f.name: digest(f) for f in folder.iterdir() if f.is_file()})
    write(folder / "scene.json", meta)
    size = sum(
        f.stat().st_size
        for area in ["bundles", "partial"]
        for f in (fp.HOME / area).rglob("*")
        if f.is_file()
    )
    if size > 800_000_000:
        raise ValueError("800 MB derived-asset cap exceeded; prior scene retained.")
    target.parent.mkdir(parents=True, exist_ok=True)
    folder.replace(target)
    write(fp.HOME / "ready" / (cid + ".json"), dict(key=key))
    fp.stage(cid + " connected foliage ready")


def publish(run, cid, sources):
    signal.alarm(900) if __name__ == "__main__" else None
    started = time.monotonic()
    fp.stage("Building fine terrain, support masks and scene for " + cid)
    p = run.candidate(cid)
    signature = dict(
        version=fp.VERSION,
        observer=[p["longitude"], p["latitude"]],
        sources=[h for s, path, h in sources if cid in s["candidates"]],
        baseline=digest(run.dem_path),
        radius=300,
    )
    from .foliage_clusters import IDENTIFIER

    signature["foliage_geometry"] = IDENTIFIER
    key = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()[
        :32
    ]
    target = fp.HOME / "bundles" / key
    if target.exists():
        # Verify before reuse; stale/corrupt immutable assets are never overwritten.
        meta = read(target / "scene.json")
        for name, h in meta["hashes"].items():
            fp.verify_file(fp.asset_path(target, meta, name), h)
        write(fp.HOME / "ready" / (cid + ".json"), dict(key=key))
        fp.stage(cid + " cached bundle verified and reused")
        return
    previous_signature = {
        k: v for k, v in dict(signature, version=5).items() if k != "foliage_geometry"
    }
    previous_key = hashlib.sha256(
        json.dumps(previous_signature, sort_keys=True).encode()
    ).hexdigest()[:32]
    prior = fp.HOME / "bundles" / previous_key
    if (prior / "scene.json").exists():
        publish_clusters(run, cid, key, prior, target, started, sources)
        return
    points, vref, hist = crop_points(run, cid, sources)
    a, support = fine_grid(points)
    fine_ground = float(fp.sample(a, 1, -300, 300, np.array([0.0]), np.array([0.0]))[0])
    base, res, x0, y0 = baseline_grid(run, cid)
    baseline_ground = float(
        fp.sample(base, res, x0, y0, np.array([0.0]), np.array([0.0]))[0]
    )
    if not np.isfinite(baseline_ground):
        raise ValueError("Baseline observer ground unavailable")
    hasfine = np.isfinite(fine_ground)
    ground = fine_ground if hasfine else baseline_ground
    existing_bytes = (
        sum(
            f.stat().st_size
            for area in ["bundles", "partial"]
            for f in (fp.HOME / area).rglob("*")
            if f.is_file()
        )
        if fp.HOME.exists()
        else 0
    )
    if existing_bytes + 60_000_000 > 800_000_000:
        raise ValueError(
            "800 MB derived-asset cap lacks space for another bounded bundle; retained partials need review."
        )
    folder = fp.HOME / "partial" / (key + "-" + __import__("uuid").uuid4().hex)
    folder.mkdir(parents=True)
    np.savez_compressed(
        folder / "fine.npz", heights=a, support=support, res=1, x0=-300, y0=300
    )
    np.savez_compressed(folder / "baseline.npz", heights=base, res=res, x0=x0, y0=y0)
    vertices, faces = fp.mesh(a, 1, -300, 300, ground, 300)
    vertices.tofile(folder / "fine-vertices.bin")
    faces.tofile(folder / "fine-indices.bin")
    # NAVD88 recognition is explicit; retain source realization caveat and a gap.
    baseline_ref = json.dumps(run.config)
    context_ok = (not hasfine) or ("NAVD88" in vref and "NAVD88" in baseline_ref)
    bv, bf = fp.mesh(base, res, x0, y0, ground, 2000, 320 if hasfine else 0)
    if not context_ok:
        bf = np.empty((0, 3), dtype=np.uint32)
    bv.tofile(folder / "context-vertices.bin")
    bf.tofile(folder / "context-indices.bin")
    if len(faces) + len(bf) > 1_000_000:
        raise ValueError("Scene terrain triangle cap exceeded")
    within = points[np.hypot(points[:, 0], points[:, 1]) <= 300]
    eligible = above_ground(within, a)
    step = max(1, math.ceil(len(eligible) / 500000))
    display = eligible[::step]
    pv = np.column_stack(
        [
            display[:, 0],
            display[:, 2]
            - ground
            - fp.CURVATURE
            * np.hypot(display[:, 0], display[:, 1]) ** 2
            / (2 * fp.EARTH),
            -display[:, 1],
        ]
    ).astype("<f4")
    pv.tofile(folder / "points.bin")
    display[:, 3].astype("u1").tofile(folder / "classes.bin")
    from . import vegetation_screen as veg

    if hasfine:
        centres, kinds, counts, eligible_count = veg.cells(points, a, ground)
    else:
        centres = np.empty((0, 3), dtype="<f4")
        kinds = np.empty(0, dtype="u1")
        counts = np.empty(0, dtype="<u4")
        eligible_count = 0
    centres.tofile(folder / "vegetation-centres.bin")
    kinds.tofile(folder / "vegetation-kinds.bin")
    counts.tofile(folder / "vegetation-counts.bin")
    vegetation = dict(
        centres_file="vegetation-centres.bin",
        kinds_file="vegetation-kinds.bin",
        counts_file="vegetation-counts.bin",
        cell_count=len(centres),
        inferred_cell_count=int(kinds.sum()),
        classified_cell_count=int((kinds == 0).sum()),
        eligible_distinct_returns=eligible_count,
        cell_size_m=1,
        minimum_distinct_returns=4,
        scenarios=veg.SCENARIOS,
        warning="Inferred opaque foliage volumes; four-return support and expansion are assumptions, not confidence or validated opacity.",
    )
    image = texture(run, cid, folder)
    context_image = texture(run, cid, folder, 2000, 2048, "context-imagery.png")
    valid = np.isfinite(a)
    circle = np.hypot(*np.indices(a.shape) - 300) <= 300
    hashes = {f.name: digest(f) for f in folder.iterdir() if f.is_file()}
    meta = dict(
        status="ready",
        version=fp.VERSION,
        key=key,
        candidate=cid,
        observer=p,
        origin_epsg=run.config["epsg"],
        ground_m=ground,
        fine_ground_m=fine_ground if hasfine else None,
        baseline_ground_m=baseline_ground,
        fine_observer_available=bool(hasfine),
        radius_m=300,
        context_radius_m=2000,
        context_available=context_ok,
        baseline_resolution_m=res,
        resolution_m=1,
        coverage_fraction=float((valid & circle).sum() / circle.sum()),
        maximum_support_distance_m=float(np.nanmax(support)) if valid.any() else None,
        ground_interpolation="Linear classified-ground triangulation in 60 m tiles with 10 m support halos; one measured ground return per 0.25 m bin; edges >5 m excluded; no extrapolation. 1 m derived grid is not a claim of 1 m accuracy.",
        acquisition_date="2019 project; individual return dates unresolved",
        vertical_reference=vref,
        vertical_note="Local sources share the same recorded vertical CRS. Coarse NAVD88 context may differ in realization; the 300–320 m transition is deliberately not joined.",
        classification_counts=hist,
        raw_local_point_count=len(within),
        above_ground_point_count=len(eligible),
        point_filter="Non-ground returns >0.5 m above supported fine ground; unknown ground excluded",
        display_point_count=len(display),
        display_stride=step,
        vegetation=vegetation,
        triangle_count=len(faces) + len(bf),
        texture=image,
        context_texture=context_image,
        hashes=hashes,
        sources=[
            dict(
                title=s["title"],
                sha256=h,
                bytes=path.stat().st_size,
                acquisition_date=s["acquisition_date"],
            )
            for s, path, h in sources
            if cid in s["candidates"]
        ],
        preparation_wall_s=round(time.monotonic() - started, 3),
        peak_process_rss_mib=round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2
        ),
        warning="Terrain-model preview, not a photograph or verified sightline. Lidar points are incomplete measured returns, not reconstructed trees. Fine-data holes remain unknown.",
    )
    enrich_clusters(folder, meta, points, a)
    meta["hashes"] = {f.name: digest(f) for f in folder.iterdir() if f.is_file()}
    write(folder / "scene.json", meta)
    size = sum(
        f.stat().st_size
        for area in ["bundles", "partial"]
        for f in (fp.HOME / area).rglob("*")
        if f.is_file()
    )
    if size > 800_000_000:
        raise ValueError("800 MB derived-asset cap exceeded")
    target.parent.mkdir(parents=True, exist_ok=True)
    folder.replace(target)
    write(fp.HOME / "ready" / (cid + ".json"), dict(key=key))
    fp.stage(
        cid
        + " ready · "
        + str(round(meta["coverage_fraction"] * 100, 1))
        + "% supported fine ground"
    )


def prepare(ident, allow):
    p = fp.plan(ident)
    if not p.get("prepared"):
        raise ValueError("Review the first-person source plan first")
    if allow and p.get("errors"):
        raise ValueError("; ".join(p["errors"]))
    sources = []
    for s in p["sources"]:
        path, h = acquire(s, allow)
        if path:
            sources.append((s, path, h))
    run = Run(fp.RUN)
    failures = {}
    for cid in fp.PILOT:
        try:
            publish(run, cid, sources)
        except (ValueError, RuntimeError, MemoryError) as e:
            failures[cid] = str(e)
            fp.stage(cid + " could not prepare: " + str(e))
    p.update(failures=failures, completed=True, finished=time.time())
    write(fp.HOME / "plans" / (ident + ".json"), p)
    if failures:
        raise ValueError(
            "Some setups could not prepare: "
            + json.dumps(failures)
            + ". Other validated bundles were retained."
        )
    fp.stage("Pilot ready; existing scores, masks and coordinates unchanged")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("operation", choices=["plan", "prepare"])
    ap.add_argument("ident")
    ap.add_argument("--download", action="store_true")
    args = ap.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (1536 * 1024**2, 1536 * 1024**2))
    signal.signal(
        signal.SIGALRM,
        lambda *_: (_ for _ in ()).throw(
            ValueError("900 second preparation stage timeout; partial files retained")
        ),
    )
    signal.alarm(900)
    try:
        if args.operation == "plan":
            discover(args.ident)
        else:
            prepare(args.ident, args.download)
    except Exception as e:
        print("GUI JOB: " + str(e), flush=True)
        raise


if __name__ == "__main__":
    main()
