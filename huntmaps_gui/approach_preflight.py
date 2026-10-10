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
