"""Conservative endpoint topology and shared directed walking profiles."""

from datetime import date as Date
import heapq
import math

import numpy as np
from shapely.geometry import Point, LineString, box
from shapely.ops import substring
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

from .sources import access, geographic, feature, collection, TO_WGS
from .storage import digest
from . import effort


def starts(pack, day, vehicle="truck", manual=(), width_inches=None):
    entry_region = pack.boundary.buffer(2000)
    motor = [
        r
        for r in pack.network
        if access(r, day, vehicle, manual, width_inches)["motor"] == "supported"
    ]
    results = []
    for row in pack.network:
        if (
            row["kind"] != "trails"
            or access(row, day, vehicle, manual, width_inches)["foot"] != "supported"
            or row["geometry"].length < 500
        ):
            continue
        for end in (0, 1):
            pt = Point(row["geometry"].coords[0 if end == 0 else -1])
            nearest = min(motor, key=lambda r: pt.distance(r["geometry"]), default=None)
            gap = pt.distance(nearest["geometry"]) if nearest else math.inf
            if gap > 150 or not entry_region.covers(pt):
                continue
            ident = digest([row["id"], end])[:32]
            lon, lat = geographic(pt).coords[0]
            results.append(
                dict(
                    id=ident,
                    segment=row["id"],
                    end=end,
                    longitude=lon,
                    latitude=lat,
                    x=pt.x,
                    y=pt.y,
                    label=(
                        row["properties"].get("trail_name") or "Unnamed trail"
                    ).title()
                    + (" · far end" if end else " · entry"),
                    motor_gap_m=gap,
                    vehicle_evidence=access(
                        nearest, day, vehicle, manual, width_inches
                    ),
                    motor_route=nearest["properties"].get("name"),
                    note=(
                        "Plausible mapped entry. Parking, complete vehicle approach and current restrictions require owner review."
                        if gap < 1
                        else f"Mapped motor route is {gap:.0f} m away. Entry/parking connection unresolved; select only as an explicit start assumption."
                    ),
                )
            )
    priority = {"Soap Creek": 0, "Mill Castle": 1, "Beaver Ponds": 2, "Lion Gulch": 3}
    return sorted(
        results, key=lambda r: (priority.get(r["label"].split(" ·")[0], 10), r["label"])
    )


def sample_line(line, spacing=20):
    ds = np.r_[np.arange(0, line.length, spacing), line.length]
    ds = np.unique(ds)
    return ds, np.array([line.interpolate(float(d)).coords[0] for d in ds])


def concatenate(chunks):
    coords = []
    modes = []
    for chunk in chunks:
        pts = list(chunk["coords"])
        if coords and math.dist(coords[-1], pts[0]) > 0.001:
            raise ValueError("Disconnected route: no invented connector")
        if not coords:
            coords.append(pts[0])
        for pt in pts[1:]:
            if math.dist(coords[-1], pt) > 1e-8:
                coords.append(pt)
                modes.append(chunk.get("offtrail", False))
    return coords, modes


def reverse(chunks):
    return [dict(c, coords=list(reversed(c["coords"]))) for c in reversed(chunks)]


def measured(chunks, terrain, p, tree, shrub):
    coords, modes = concatenate(chunks)
    line = LineString(coords)
    ds, xy = sample_line(line)
    breaks = np.cumsum([LineString(c["coords"]).length for c in chunks])
    ds = np.sort(np.r_[ds, breaks])
    ds = ds[np.r_[True, np.diff(ds) > 1e-6]]
    xy = np.array([line.interpolate(float(d)).coords[0] for d in ds])
    # Assign each sample interval by its midpoint along the *traversed* chain.
    original = np.r_[
        0, np.cumsum(np.linalg.norm(np.diff(np.array(coords), axis=0), axis=1))
    ]
    mids = (ds[:-1] + ds[1:]) / 2
    mode = np.array(modes)[
        np.minimum(np.searchsorted(original, mids, side="right") - 1, len(modes) - 1)
    ]
    raw = terrain.sample(xy)
    t = terrain.sample((xy[:-1] + xy[1:]) / 2, tree)
    s = terrain.sample((xy[:-1] + xy[1:]) / 2, shrub)
    result = effort.measure(xy, raw, mode, p, t, s, distance=ds)
    result["geometry"] = feature(line, kind="itinerary")["geometry"]
    result["source_segments"] = [
        dict(
            source_id=c["segment"],
            offtrail=c["offtrail"],
            attributes=c.get("source_properties"),
            permissions=c.get("status"),
            direction_start=list(c["coords"][0]),
            direction_end=list(c["coords"][-1]),
        )
        for c in chunks
    ]
    lon, lat = TO_WGS.transform(xy[:, 0], xy[:, 1])
    for point, x, y in zip(result["profile"], lon, lat):
        point.update(longitude=float(x), latitude=float(y))
    ground = terrain.sample(xy, terrain.slope)
    result["max_surrounding_ground_slope_deg"] = float(np.max(ground))
    result["mapped_steep_hillside_m"] = float(
        np.diff(ds)[(~mode) & ((ground[:-1] + ground[1:]) / 2 > 25)].sum()
    )
    result["unknown_cover_m"] = float(
        np.diff(ds)[~np.isfinite(t) | ~np.isfinite(s)].sum()
    )
    return result


class Network:
    def __init__(self, pack, start, terrain, p, settings, tree, shrub):
        self.start = start
        self.terrain = terrain
        self.p = p
        self.tree = tree
        self.shrub = shrub
        self.rows = []
        self.edges = {}
        self.adj = {}
        self.nodes = []
        self.keys = {}
        self.blocked = []
        day = Date.fromisoformat(settings["date"])
        radius = settings["corridor_m"]
        boundary = Point(start["x"], start["y"]).buffer(radius)
        travel_area = settings.get("_travel_geometry")
        if travel_area is not None:
            boundary = boundary.intersection(travel_area)
        exclusions = settings.get("_exclusion_geometry")
        entries = []
        for row in pack.network:
            if not row["geometry"].intersects(boundary):
                continue
            status = access(
                row,
                day,
                settings["vehicle"],
                settings.get("restrictions", []),
                settings.get("vehicle_width_inches"),
            )
            public = dict(
                id=row["id"],
                kind="closed-road" if row["motor_closed"] else row["kind"],
                name=row["properties"].get("trail_name", row["properties"].get("name"))
                or "Unnamed",
                access=status,
                properties=row["properties"],
            )
            self.rows.append(feature(row["geometry"], **public))
            if (
                row["id"] in settings["excluded_segments"]
                or status["foot"] == "closed"
                or (status["foot"] == "unknown" and not settings["explore_unknown"])
            ):
                continue
            clipped = row["geometry"].intersection(boundary)
            parts = (
                [clipped]
                if clipped.geom_type == "LineString"
                else list(getattr(clipped, "geoms", []))
            )
            for part in parts:
                if part.geom_type != "LineString" or part.length < 1:
                    continue
                if exclusions and part.intersects(exclusions):
                    part = part.difference(exclusions)
                    sub = (
                        [part]
                        if part.geom_type == "LineString"
                        else list(getattr(part, "geoms", []))
                    )
                else:
                    sub = [part]
                entries.extend(
                    (row, status, l)
                    for l in sub
                    if l.geom_type == "LineString" and l.length > 1
                )

        # Only exact endpoint-to-line contacts are junctions. Geometric crossings
        # and close parallel lines have no automatic junctions/gap repair.
        def level(row):
            p = row["properties"]
            if str(p.get("bridge", "")).lower() in ("yes", "true", "1"):
                return "bridge"
            if str(p.get("tunnel", "")).lower() in ("yes", "true", "1"):
                return "tunnel"
            return str(p.get("layer", p.get("level", "0")))

        endpoints = [
            (Point(c), level(row))
            for row, _, l in entries
            for c in (l.coords[0], l.coords[-1])
        ]
        selected = Point(start["x"], start["y"])
        self.start_node = None
        for row, status, line in entries:
            cuts = list(np.arange(0, line.length, 160)) + [line.length]
            for pt, other_level in endpoints:
                if other_level == level(row) and pt.distance(line) < 0.00001:
                    cuts.append(line.project(pt))
            if row["id"] == start["segment"] and selected.distance(line) < 0.00001:
                cuts.append(line.project(selected))
            cuts = sorted(set(float(x) for x in cuts))
            cuts = [
                value
                for i, value in enumerate(cuts)
                if i == 0 or value - cuts[i - 1] > 1e-5
            ]
            cuts[0] = 0.0
            cuts[-1] = line.length
            for a, b in zip(cuts, cuts[1:]):
                if b - a < 0.01:
                    continue
                sub = substring(line, a, b)
                coords = list(sub.coords)
                u = self.node(coords[0], level(row))
                v = self.node(coords[-1], level(row))
                if row["id"] == start["segment"]:
                    for n in (u, v):
                        if math.dist(self.nodes[n], selected.coords[0]) < 0.001:
                            self.start_node = n
                ds, xy = sample_line(sub)
                raw = terrain.sample(xy)
                z = effort.clean_profile(ds, raw)
                dz = np.diff(z)
                delta = np.diff(ds)
                forward = float(np.sum(delta / effort.speed(dz / delta, p)))
                backward = float(np.sum(delta / effort.speed(-dz / delta, p)))
                key = len(self.edges)
                self.edges[key] = dict(
                    u=u,
                    v=v,
                    key=key,
                    coords=coords,
                    segment=row["id"],
                    offtrail=False,
                    status=status,
                    source_properties=row["properties"],
                    forward_hours=forward,
                    backward_hours=backward,
                )
                self.adj.setdefault(u, []).append((v, key, forward))
                self.adj.setdefault(v, []).append((u, key, backward))
        if self.start_node is None:
            raise ValueError(
                "Selected start is excluded, closed, unknown in this scenario, or not on its intended segment. Change start/access assumptions."
            )
        self.dist = {self.start_node: 0}
        self.previous = {}
        queue = [(0, self.start_node)]
        while queue:
            cost, u = heapq.heappop(queue)
            if cost != self.dist[u]:
                continue
            for v, key, weight in self.adj.get(u, []):
                new = cost + weight
                if new < self.dist.get(v, math.inf):
                    self.dist[v] = new
                    self.previous[v] = (u, key)
                    heapq.heappush(queue, (new, v))

        self.return_cost = {self.start_node: 0}
        for node in sorted(self.dist, key=self.dist.get):
            if node == self.start_node:
                continue
            parent, key = self.previous[node]
            edge = self.edges[key]
            reverse_hours = (
                edge["backward_hours"] if edge["u"] == parent else edge["forward_hours"]
            )
            self.return_cost[node] = self.return_cost[parent] + reverse_hours

    def prepare_other_access(self, entries):
        incoming = {}
        for u, neighbors in self.adj.items():
            for v, key, hours in neighbors:
                incoming.setdefault(v, []).append((u, key, hours))
        self.other_cost = {}
        self.other_distance = {}
        self.other_origin = {}
        self.other_next = {}
        queue = []
        for entry in entries:
            if (
                entry["id"] == self.start["id"]
                or math.dist(
                    (entry["x"], entry["y"]), (self.start["x"], self.start["y"])
                )
                <= 100
            ):
                continue
            for node, xy in enumerate(self.nodes):
                if math.dist(xy, (entry["x"], entry["y"])) < 0.001 and any(
                    self.edges[key]["segment"] == entry["segment"]
                    for _, key, _ in self.adj.get(node, [])
                ):
                    self.other_cost[node] = 0
                    self.other_distance[node] = 0
                    self.other_origin[node] = entry
                    heapq.heappush(queue, (0, node))
        while queue:
            cost, node = heapq.heappop(queue)
            if cost != self.other_cost[node]:
                continue
            for previous, key, hours in incoming.get(node, []):
                proposed = cost + hours
                if proposed < self.other_cost.get(previous, math.inf):
                    self.other_cost[previous] = proposed
                    self.other_distance[previous] = (
                        self.other_distance[node]
                        + LineString(self.edges[key]["coords"]).length
                    )
                    self.other_origin[previous] = self.other_origin[node]
                    self.other_next[previous] = (node, key)
                    heapq.heappush(queue, (proposed, previous))

    def other_access(self, chunks, return_spur_hours):
        mapped = [c for c in chunks if not c["offtrail"]]
        if not mapped:
            return None
        pt = mapped[-1]["coords"][-1]
        node = min(
            self.other_cost, key=lambda n: math.dist(pt, self.nodes[n]), default=None
        )
        if node is None or math.dist(pt, self.nodes[node]) > 0.001:
            return None
        offtrail = sum(LineString(c["coords"]).length for c in chunks if c["offtrail"])
        own_keys = {c["key"] for c in mapped}
        shared = 0
        cursor = node
        while cursor in self.other_next:
            after, key = self.other_next[cursor]
            if key in own_keys:
                shared += LineString(self.edges[key]["coords"]).length
            cursor = after
        return dict(
            entry=self.other_origin[node]["label"],
            walking_distance_m=self.other_distance[node] + offtrail,
            walking_hours_high=self.other_cost[node] * self.p["time_margin"]
            + return_spur_hours,
            shared_selected_approach_m=shared,
            assumption="Connected in the supported/scenario walking graph; entry parking and vehicle approach remain unverified. No missing connection is filled.",
        )

    def node(self, pt, level="0"):
        key = tuple(round(v, 5) for v in pt) + (level,)
        if key not in self.keys:
            self.keys[key] = len(self.nodes)
            self.nodes.append(tuple(pt))
        return self.keys[key]

    def path(self, node):
        chunks = []
        while node != self.start_node:
            prev, key = self.previous[node]
            edge = self.edges[key]
            chunks.append(
                dict(
                    edge,
                    coords=(
                        edge["coords"]
                        if edge["u"] == prev
                        else list(reversed(edge["coords"]))
                    ),
                )
            )
            node = prev
        return list(reversed(chunks))

    def departures(self):
        out = []
        for n in sorted(self.dist, key=self.dist.get):
            if n == self.start_node:
                continue
            chunks = self.path(n)
            if self.dist[n] + self.return_cost[n] > self.p["max_hours"]:
                continue
            coords, _ = concatenate(chunks)
            if LineString(coords).length * 2 > self.p["max_miles"] * 1609.344:
                continue
            out.append(dict(node=n, xy=self.nodes[n], chunks=chunks))
        return out
