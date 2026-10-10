"""Deterministic provisional approaches; independent of historical scoring/search."""

import heapq
import math
import numpy as np
from shapely.geometry import Point, LineString
from shapely.prepared import prep

VERSION = "approach-20m-v1"
RESOLUTION = 20
MAX_CELLS = 3_000_000
MAX_DEPARTURES = 10000


def implementation():
    from glassing.acquire import digest
    from pathlib import Path
    import hashlib

    return hashlib.sha256(
        "".join(
            digest(Path(__file__).with_name(name))
            for name in [
                "approach_search.py",
                "approach_native.py",
                "approach_dijkstra.cpp",
            ]
        ).encode()
    ).hexdigest()


def terrain_properties(dem, resolution):
    dy, dx = np.gradient(dem, resolution)
    slope = np.degrees(np.arctan(np.hypot(dx, dy)))
    # North is negative row direction; downhill bearing clockwise from north.
    aspect = (np.degrees(np.arctan2(-dx, dy)) + 360) % 360
    aspect[np.hypot(dx, dy) < 1e-9] = np.nan
    return slope, aspect


class Grid:
    def __init__(
        self, dem, tree, shrub, origin, area, exclusions, maximum=30, resolution=20
    ):
        if dem.size > MAX_CELLS or min(dem.shape) < 2:
            raise ValueError(
                "Travel grid exceeds limits or is too small; narrow the travel area"
            )
        self.dem, self.tree, self.shrub = dem, tree, shrub
        self.origin, self.resolution, self.maximum = origin, resolution, maximum
        self.domain = area.difference(exclusions)
        self.prepared = prep(self.domain)
        self.slope, _ = terrain_properties(dem, resolution)
        self.valid = (
            np.isfinite(dem) & np.isfinite(self.slope) & (self.slope <= maximum)
        )
        import shapely

        xs = origin[0] + (np.arange(dem.shape[1]) + 0.5) * resolution
        for r in range(dem.shape[0]):
            ys = np.full(dem.shape[1], origin[1] - (r + 0.5) * resolution)
            self.valid[r] &= shapely.covers(self.domain, shapely.points(xs, ys))
        self.edge_valid = []
        self.edge_directions = ((0, 1), (1, -1), (1, 0), (1, 1))
        # Batch exact travel/exclusion geometry tests once; reusable by all objectives.
        for dr, dc in self.edge_directions:
            allowed = np.zeros(dem.shape, dtype=bool)
            for r in range(dem.shape[0] - dr):
                cs = np.arange(max(0, -dc), min(dem.shape[1], dem.shape[1] - dc))
                valid = self.valid[r, cs] & self.valid[r + dr, cs + dc]
                if dr and dc:
                    valid &= self.valid[r + dr, cs] & self.valid[r, cs + dc]
                cs = cs[valid]
                if not cs.size:
                    continue
                a = np.column_stack(
                    (xs[cs], np.full(cs.size, origin[1] - (r + 0.5) * resolution))
                )
                b = np.column_stack(
                    (
                        xs[cs + dc],
                        np.full(cs.size, origin[1] - (r + dr + 0.5) * resolution),
                    )
                )
                allowed[r, cs] = shapely.covers(
                    self.domain, shapely.linestrings(np.stack((a, b), axis=1))
                )
            self.edge_valid.append(allowed)
        self.penalty_tree = np.where(np.isfinite(tree), tree, 1)
        self.penalty_shrub = np.where(np.isfinite(shrub), shrub, 1)

    def xy(self, cell):
        r, c = cell
        return (
            self.origin[0] + (c + 0.5) * self.resolution,
            self.origin[1] - (r + 0.5) * self.resolution,
        )

    def cell(self, xy):
        return (
            int(math.floor((self.origin[1] - xy[1]) / self.resolution)),
            int(math.floor((xy[0] - self.origin[0]) / self.resolution)),
        )

    def inside(self, cell):
        r, c = cell
        return (
            0 <= r < self.dem.shape[0]
            and 0 <= c < self.dem.shape[1]
            and self.valid[r, c]
        )

    def elevation(self, xy):
        cell = self.cell(xy)
        return float(self.dem[cell]) if self.inside(cell) else None

    def segment(self, a, b, weights, mapped=False):
        """Check exact geometry and all crossed raster cells; costs use sampled ground."""
        length = math.dist(a, b)
        if not self.prepared.covers(Point(a) if length == 0 else LineString([a, b])):
            return None
        # Subcell sampling plus exact intersection with all touched cells prevents
        # narrow hard-cell barriers slipping between samples.
        from shapely.geometry import box

        ca, cb = self.cell(a), self.cell(b)
        line = Point(a) if length == 0 else LineString([a, b])
        crossed_slopes = []
        for r in range(min(ca[0], cb[0]), max(ca[0], cb[0]) + 1):
            for c in range(min(ca[1], cb[1]), max(ca[1], cb[1]) + 1):
                x, y = self.xy((r, c))
                h = self.resolution / 2
                cell_box = box(x - h, y - h, x + h, y + h)
                if line.intersects(cell_box):
                    if not self.inside((r, c)):
                        return None
                    if length and line.intersection(cell_box).length > 1e-8:
                        crossed_slopes.append(float(self.slope[r, c]))
        if not self.inside(ca) or not self.inside(cb):
            return None
        za, zb = float(self.dem[ca]), float(self.dem[cb])
        step_slope = math.degrees(math.atan2(abs(zb - za), length)) if length else 0
        slope = max(
            float(self.slope[ca]), float(self.slope[cb]), step_slope, *crossed_slopes
        )
        if slope > self.maximum:
            return None
        tree = [float(self.tree[p]) for p in (ca, cb)]
        shrub = [float(self.shrub[p]) for p in (ca, cb)]
        unknown = any(not math.isfinite(v) for v in tree + shrub)
        tc = sum(v if math.isfinite(v) else 1 for v in tree) / 2
        sc = sum(v if math.isfinite(v) else 1 for v in shrub) / 2
        uphill, downhill = max(0, zb - za), max(0, za - zb)
        parts = [
            length,
            length * weights["slope"] * (slope / 15) ** 2,
            0 if mapped else length * weights["tree"] * tc,
            0 if mapped else length * weights["shrub"] * sc,
            weights["gain"] * 10 * uphill,
        ]
        return dict(
            cost=sum(parts),
            contributions=parts,
            distance_m=length,
            ascent_m=uphill,
            descent_m=downhill,
            slope_deg=slope,
            tree=tc,
            shrub=sc,
            unknown=unknown,
            tree_known=sum(tree) / 2 if all(math.isfinite(v) for v in tree) else None,
            shrub_known=(
                sum(shrub) / 2 if all(math.isfinite(v) for v in shrub) else None
            ),
            elevations=[za, zb],
        )

    def neighbors(self, cell):
        r, c = cell
        for dr, dc in (
            (-1, -1),
            (-1, 0),
            (-1, 1),
            (0, -1),
            (0, 1),
            (1, -1),
            (1, 0),
            (1, 1),
        ):
            n = (r + dr, c + dc)
            if not self.inside(n):
                continue
            if (
                dr
                and dc
                and (not self.inside((r + dr, c)) or not self.inside((r, c + dc)))
            ):
                continue
            yield n

    def search(self, target, weights):
        end = self.cell(target)
        connector = self.segment(self.xy(end), target, weights)
        if connector is None:
            return {}, {}
        from .approach_native import search

        result = search(self, end, connector["cost"], weights)
        return self.search_reference(target, weights) if result is None else result

    def search_reference(self, target, weights):
        """One reverse directed Dijkstra for all network departures."""
        end = self.cell(target)
        connector = self.segment(self.xy(end), target, weights)
        if connector is None:
            return {}, {}
        dist, successor = {end: connector["cost"]}, {end: None}
        queue = [(dist[end], end)]
        while queue:
            cost, cell = heapq.heappop(queue)
            if cost != dist[cell]:
                continue
            for n in self.neighbors(cell):
                dr, dc = cell[0] - n[0], cell[1] - n[1]
                source = n
                if dr < 0 or (dr == 0 and dc < 0):
                    source = cell
                    dr, dc = -dr, -dc
                direction = self.edge_directions.index((dr, dc))
                if not self.edge_valid[direction][source]:
                    continue
                length = self.resolution * (math.sqrt(2) if dr and dc else 1)
                dz = float(self.dem[cell] - self.dem[n])
                slope = max(
                    float(self.slope[cell]),
                    float(self.slope[n]),
                    math.degrees(math.atan2(abs(dz), length)),
                )
                if slope > self.maximum:
                    continue
                edge_cost = length * (
                    1
                    + weights["slope"] * (slope / 15) ** 2
                    + weights["tree"]
                    * (self.penalty_tree[n] + self.penalty_tree[cell])
                    / 2
                    + weights["shrub"]
                    * (self.penalty_shrub[n] + self.penalty_shrub[cell])
                    / 2
                ) + weights["gain"] * 10 * max(0, dz)
                value = cost + edge_cost
                if value < dist.get(n, math.inf):
                    dist[n], successor[n] = value, cell
                    heapq.heappush(queue, (value, n))
        return dist, successor


def departures(lines, target, pinned=None):
    samples = set()
    for line in lines:
        nearest = line.interpolate(line.project(Point(target)))
        if nearest.distance(Point(target)) > 1609.344:
            continue
        coords = list(line.coords)
        for a, b in zip(coords, coords[1:]):
            segment = LineString([a, b])
            count = math.ceil(segment.length / 20)
            if count > MAX_DEPARTURES:
                raise ValueError(
                    "Too many departure samples; narrow the search network/travel area"
                )
            for i in range(count + 1):
                p = segment.interpolate(min(i * 20, segment.length))
                if p.distance(Point(target)) <= 1609.344:
                    samples.add(tuple(p.coords[0]))
        samples.add(tuple(nearest.coords[0]))
        if len(samples) > MAX_DEPARTURES:
            raise ValueError(
                "Too many departure samples; narrow the search network/travel area"
            )
    if pinned is not None:
        if not any(l.distance(Point(pinned)) < 1e-6 for l in lines):
            raise ValueError("Pinned departure must lie on the selected mapped network")
        samples.add(tuple(pinned))
    if len(samples) > MAX_DEPARTURES:
        raise ValueError("Too many departures; narrow the search")
    return sorted(samples)


def network_paths(grid, lines, samples, start, weights):
    """Shared exact vertices connect; arbitrary crossings/gaps do not."""
    if start is None:
        return {p: (0, [p]) for p in samples}
    if not any(l.distance(Point(start)) < 1e-6 for l in lines):
        raise ValueError("Trail starting point must lie on the selected mapped network")
    graph, locations = {}, {}
    from shapely.strtree import STRtree

    sample_points = [*samples, tuple(start)]
    index = STRtree([Point(p) for p in sample_points])
    for li, line in enumerate(lines):
        for si, (a, b) in enumerate(zip(line.coords, list(line.coords)[1:])):
            seg = LineString([a, b])
            length = seg.length
            if not length:
                continue
            points = {tuple(a), tuple(b)}
            count = math.ceil(length / 20)
            if count > MAX_DEPARTURES:
                raise ValueError("Network too large; narrow travel area")
            points.update(
                tuple(seg.interpolate(min(i * 20, length)).coords[0])
                for i in range(count + 1)
            )
            points.update(
                sample_points[int(i)]
                for i in index.query(seg.buffer(1e-6))
                if seg.distance(Point(sample_points[int(i)])) < 1e-6
            )
            ordered = sorted(points, key=lambda p: seg.project(Point(p)))

            def node(p):
                # Only supplied vertices join globally. Interior samples belong
                # to one source segment, even when densification lands on a crossing.
                key = (p, (-1, -1) if p in (tuple(a), tuple(b)) else (li, si))
                locations.setdefault(p, set()).add(key)
                if len(locations) > 100000:
                    raise ValueError(
                        "Network graph exceeds resource guard; narrow the travel area"
                    )
                return key

            for u, v in zip(ordered, ordered[1:]):
                for x, y in ((u, v), (v, u)):
                    nx, ny = node(x), node(y)
                    edge = grid.segment(x, y, weights, True)
                    if edge is not None:
                        graph.setdefault(nx, {})[ny] = edge["cost"]
    starts = sorted(locations.get(tuple(start), []))
    if not starts:
        return {}
    # An interior crossing start is ambiguous; use the first source segment
    # deterministically rather than inventing a crossing junction.
    start_node = starts[0]
    dist, prev = {start_node: 0}, {}
    queue = [(0, start_node)]
    while queue:
        value, u = heapq.heappop(queue)
        if value != dist[u]:
            continue
        for v, cost in sorted(graph.get(u, {}).items()):
            new = value + cost
            if new < dist.get(v, math.inf):
                dist[v], prev[v] = new, u
                heapq.heappush(queue, (new, v))
    result = {}
    for p in samples:
        candidates = [(dist[n], n) for n in locations.get(p, []) if n in dist]
        if not candidates:
            continue
        cost, n = min(candidates)
        path = [n]
        while path[-1] != start_node:
            path.append(prev[path[-1]])
        result[p] = (cost, [n[0] for n in path[::-1]])
    return result


def summarize(grid, mapped, offtrail, weights):
    edges, profile, total = [], [], 0
    for mode, points in ((True, mapped), (False, offtrail)):
        for a, b in zip(points, points[1:]):
            edge = grid.segment(a, b, weights, mode)
            if edge is None:
                raise ValueError("Export segment violates modeled constraints")
            edges.append((mode, edge))
            if not profile:
                profile.append([0, edge["elevations"][0]])
            total += edge["distance_m"]
            profile.append([total, edge["elevations"][1]])
    parts = (
        np.sum([e["contributions"] for _, e in edges], axis=0).tolist()
        if edges
        else [0] * 5
    )
    off = sum(e["distance_m"] for m, e in edges if not m)

    def mean(key):
        return (
            sum(e[key] * e["distance_m"] for m, e in edges if not m) / off
            if off
            else None
        )

    def known_mean(key):
        known = [e for m, e in edges if not m and e[key] is not None]
        length = sum(e["distance_m"] for e in known)
        return sum(e[key] * e["distance_m"] for e in known) / length if length else None

    return dict(
        cost=sum(parts),
        cost_contributions=dict(
            zip(("distance", "slope", "tree", "shrub", "climbing"), parts)
        ),
        mapped_distance_m=sum(e["distance_m"] for m, e in edges if m),
        offtrail_distance_m=off,
        ascent_m=sum(e["ascent_m"] for _, e in edges),
        descent_m=sum(e["descent_m"] for _, e in edges),
        maximum_slope_deg=max((e["slope_deg"] for _, e in edges), default=0),
        average_tree=known_mean("tree_known"),
        average_shrub=known_mean("shrub_known"),
        offtrail_unknown_cover_fraction=mean("unknown"),
        unknown_cover_fraction=(
            sum(e["distance_m"] * e["unknown"] for _, e in edges) / total
            if total
            else None
        ),
        elevation_profile=profile,
    )


def solve(grid, lines, target, weights, start=None, pinned=None):
    samples = departures(lines, target, pinned)
    alternatives = []
    reachable_count = 0
    objectives = [
        ("Recommended", weights),
        ("Shortest distance", dict(slope=0, tree=0, shrub=0, gain=0)),
        ("Brush avoidance", dict(weights, tree=3, shrub=3)),
    ]
    if pinned is not None:
        objectives.append(("Pinned departure", weights))
    for label, w in objectives:
        distances, successor = grid.search(target, w)
        mapped = network_paths(grid, lines, samples, start, w)
        choices = []
        for point, (trailcost, trail) in mapped.items():
            if label == "Pinned departure" and point != tuple(pinned):
                continue
            cell = grid.cell(point)
            edge = grid.segment(point, grid.xy(cell), w)
            if edge and cell in distances:
                choices.append(
                    (trailcost + edge["cost"] + distances[cell], point, trail)
                )
        if label == "Recommended":
            reachable_count = len(choices)
        if not choices:
            continue
        _, point, trail = min(choices, key=lambda item: (item[0], item[1]))
        path = [point]
        cell = grid.cell(point)
        while cell is not None:
            if path[-1] != grid.xy(cell):
                path.append(grid.xy(cell))
            cell = successor[cell]
        if path[-1] != tuple(target):
            path.append(tuple(target))
        identity = (trail, path)
        same = next(
            (a for a in alternatives if (a["mapped"], a["offtrail"]) == identity), None
        )
        if same:
            same["labels"].append(label)
            continue
        alternatives.append(
            dict(
                labels=[label],
                departure=point,
                mapped=trail,
                offtrail=path,
                weights=w,
                **summarize(grid, trail, path, w),
            )
        )
    return dict(
        alternatives=alternatives,
        departure_count=len(samples),
        grid_resolution_m=grid.resolution,
        pinned_status=(
            (
                "Pinned departure has a modeled path under these constraints"
                if any("Pinned departure" in a["labels"] for a in alternatives)
                else "No path found within these constraints and mapped coverage for the pinned departure"
            )
            if pinned is not None
            else ""
        ),
        message=(
            ""
            if alternatives
            else "No path found within these constraints and mapped coverage"
        ),
        limiting_evidence=dict(
            valid_cells=int(grid.valid.sum()),
            network_lines=len(lines),
            departures=len(samples),
            maximum_slope_deg=grid.maximum,
            endpoint_inside_travel_area=grid.domain.covers(Point(target)),
            endpoint_valid_terrain=bool(grid.inside(grid.cell(target))),
            departures_connected_to_start=len(mapped),
            reachable_departures=reachable_count,
            explanation="Every path must satisfy supplied travel/exclusion geometry, valid DEM and cell/step slopes; unmapped gaps stay disconnected",
        ),
    )
