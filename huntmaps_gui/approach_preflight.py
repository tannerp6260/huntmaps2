"""Read-only geometry/departure checks; no raster preparation or path calculation."""

import math
from shapely.geometry import Point, GeometryCollection
from shapely.ops import transform, unary_union
from glassing.transfer import project
from .approach_service import point_snapshot, geometry
from .approach_search import departures, RESOLUTION, MAX_CELLS
from .scouting_network import load_networks


def check(run, body, jobs=None):
    r, points = point_snapshot(run, jobs)
    ids = body.get("ids", [])
    if (
        not ids
        or len(ids) > 250
        or len(set(ids)) != len(ids)
        or any(i not in points for i in ids)
    ):
        raise ValueError("Choose current shortlisted setups")
    area = transform(project(4326, r.config["epsg"]), geometry(body["travel_area"]))
    exclusions = (
        unary_union(
            [
                transform(project(4326, r.config["epsg"]), geometry(v))
                for v in body.get("exclusions", [])
            ]
        )
        if body.get("exclusions")
        else GeometryCollection()
    )
    domain = area.difference(exclusions)
    left, bottom, right, top = area.bounds
    width, height = math.ceil((right - left) / RESOLUTION), math.ceil(
        (top - bottom) / RESOLUTION
    )
    cells = width * height
    lines, _ = load_networks(
        body.get("network_ids", []),
        r.config["epsg"],
        body.get("kinds", ["roads", "trails"]),
    )
    clipped = []
    for line in lines:
        g = line.intersection(domain)
        if g.geom_type == "LineString" and not g.is_empty:
            clipped.append(g)
        elif g.geom_type in ("MultiLineString", "GeometryCollection"):
            clipped.extend(p for p in g.geoms if p.geom_type == "LineString")
    xy = project(4326, r.config["epsg"])
    for name in ("start", "pinned"):
        if body.get(name) is not None:
            point = geometry(dict(type="Point", coordinates=body[name]), False)
            if point.geom_type != "Point":
                raise ValueError("Choose a valid network point")
    pinned = xy(*body["pinned"]) if body.get("pinned") else None
    rows = []
    for cid in ids:
        target = xy(points[cid]["longitude"], points[cid]["latitude"])
        message = ""
        count = 0
        if not domain.covers(Point(target)):
            message = "This setup is outside the usable search boundary. Draw or edit a boundary around this setup and a mapped road or trail."
        elif cells > MAX_CELLS or min(width, height) < 2:
            message = "Draw a smaller search boundary (at most 3 million grid cells), large enough to include this setup and a mapped departure."
        elif not clipped:
            message = "No selected mapped road or trail lies inside this boundary. Edit the boundary or review road/trail sources."
        else:
            try:
                count = len(departures(clipped, target, pinned))
                if not count:
                    message = "No mapped departures within one mile of this setup lie inside the boundary. Edit the boundary or review road/trail sources."
            except ValueError as e:
                message = str(e)
        if body.get("start") and not domain.covers(Point(xy(*body["start"]))):
            message = "The network start must lie inside the usable search boundary."
        elif body.get("start") and not any(
            line.distance(Point(xy(*body["start"]))) < 1e-6 for line in clipped
        ):
            message = "The network start must lie on a selected mapped road or trail inside the boundary."
        rows.append(dict(id=cid, ready=not message, message=message, departures=count))
    return dict(
        ready=all(p["ready"] for p in rows),
        points=rows,
        grid_cells=cells,
        note="Geometry and mapped departures checked. Path calculation still checks terrain and constraints.",
    )


def suggest(run, body, jobs=None):
    """A separate, unconfirmed proposal; observer and target domains are untouched."""
    import numpy as np
    from shapely.geometry import box, mapping, shape
    from .scouting_network import covering_networks

    r, points = point_snapshot(run, jobs)
    cid = body.get("id")
    if cid not in points:
        raise ValueError("Choose a current shortlisted setup")
    xy = project(4326, r.config["epsg"])
    ll = project(r.config["epsg"], 4326)
    target = Point(xy(points[cid]["longitude"], points[cid]["latitude"]))
    ds = r.dem
    gt = ds.GetGeoTransform()
    if gt[2] or gt[4] or gt[1] <= 0 or gt[5] >= 0:
        raise ValueError("Suggestion needs a north-up metric terrain grid")
    footprint = box(
        gt[0], gt[3] + ds.RasterYSize * gt[5], gt[0] + ds.RasterXSize * gt[1], gt[3]
    )
    # Fine holes stay outside the proposed domain, just as they do in path calculation.
    band = ds.GetRasterBand(1)
    values = band.ReadAsArray()
    valid = np.isfinite(values) & (band.GetMaskBand().ReadAsArray() > 0)
    if not valid.all():
        from osgeo import gdal, ogr

        mask = gdal.GetDriverByName("MEM").Create(
            "", ds.RasterXSize, ds.RasterYSize, 1, gdal.GDT_Byte
        )
        mask.SetGeoTransform(gt)
        mask.SetProjection(ds.GetProjection())
        mask.GetRasterBand(1).WriteArray(valid.astype("uint8"))
        vector = ogr.GetDriverByName("Memory").CreateDataSource("")
        layer = vector.CreateLayer("valid", geom_type=ogr.wkbPolygon)
        gdal.Polygonize(mask.GetRasterBand(1), mask.GetRasterBand(1), layer, -1, [])
        import json

        footprint = unary_union(
            [shape(json.loads(f.GetGeometryRef().ExportToJson())) for f in layer]
        )
    area = target.buffer(2000, resolution=48).intersection(footprint)
    if area.is_empty or not area.covers(target):
        raise ValueError("No supported obstruction terrain at this setup")
    geographic = mapping(transform(ll, area))
    networks = covering_networks(shape(geographic).bounds)
    ids = [n["id"] for n in networks]
    preflight = check(
        run,
        dict(
            ids=[cid],
            travel_area=geographic,
            exclusions=body.get("exclusions", []),
            network_ids=ids,
        ),
        jobs,
    )
    return dict(
        travel_area=geographic,
        buffer_m=2000,
        boundary_confirmed=False,
        network_ids=ids,
        preflight=preflight,
        note="Suggested boundary clipped to obstruction terrain. Confirm or edit it; mapped departures do not establish permission.",
    )
