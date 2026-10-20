"""Bounded new viewpoints, conservative spurs and exact aligned coverage."""

import io
import math
from pathlib import Path
import tempfile

import numpy as np
from osgeo import gdal
from scipy.ndimage import uniform_filter, distance_transform_edt
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from shapely.geometry import Point, LineString, box

from huntmaps_gui import habitat
from .sources import raster_mask, Terrain, feature, collection
from .storage import digest, atomic, read, seal, checked, IntegrityError
from .network import measured, reverse
from . import effort, profiles


def npz_write(path, **arrays):
    buffer = io.BytesIO()
    np.savez_compressed(buffer, **arrays)
    atomic(path, buffer.getvalue(), True)
    seal(path)


def npz_read(path):
    try:
        with np.load(checked(path), allow_pickle=False) as f:
            return {k: f[k] for k in f.files}
    except (ValueError, OSError, KeyError) as error:
        raise IntegrityError(
            f"Invalid sealed analytical cache {path}: {error}. Retained for diagnosis; restore exact bytes before retrying."
        ) from error


def habitat_layers(pack, terrain, folder):
    """Keep established H/G coefficients and full-neighborhood support contract."""
    res = 40
    halo = 400
    bounds = [
        math.floor((terrain.bounds[0] - halo) / res) * res,
        math.floor((terrain.bounds[1] - halo) / res) * res,
        math.ceil((terrain.bounds[2] + halo) / res) * res,
        math.ceil((terrain.bounds[3] + halo) / res) * res,
    ]
    key = digest(
        [
            "habitat-40m-v1",
            habitat.VERSION,
            habitat.DEFAULTS,
            [pack.spec["data"][k] for k in ("tree", "shrub")],
            bounds,
            terrain.gt,
            terrain.a.shape,
        ]
    )
    path = folder / "habitat" / key / "layers.npz"
    # A warm derived cache does not excuse checking its current raw dependencies.
    for name in ("tree", "shrub"):
        pack.asset(pack.spec["data"][name]["path"])
    if path.exists():
        return npz_read(path), key
    arrays = []
    first_grid = None
    years = {pack.spec["data"][k].get("observation_year") for k in ("tree", "shrub")}
    if len(years) != 1 or None in years:
        raise ValueError("RCMAP observation years are missing or incompatible")
    for name in ("tree", "shrub"):
        src = gdal.Open(str(pack.asset(pack.spec["data"][name]["path"])))
        grid = (
            src.GetGeoTransform(),
            src.GetProjection(),
            src.RasterXSize,
            src.RasterYSize,
        )
        if first_grid is None:
            first_grid = grid
        elif grid != first_grid:
            raise ValueError("Raw tree/shrub source grids are not aligned")
        if pack.spec["data"][name].get("component") != name or not str(
            pack.spec["data"][name].get("units", "")
        ).startswith("percent"):
            raise ValueError("RCMAP component identity/percent units missing")
        gt = src.GetGeoTransform()
        a = src.ReadAsArray().astype(float)
        nodata = src.GetRasterBand(1).GetNoDataValue()
        known = np.isfinite(a) & (a >= 0) & (a <= 100) & (a != nodata)

        def warp(v):
            ds = gdal.GetDriverByName("MEM").Create(
                "", src.RasterXSize, src.RasterYSize, 1, gdal.GDT_Float32
            )
            ds.SetGeoTransform(gt)
            ds.SetProjection(src.GetProjection())
            ds.GetRasterBand(1).WriteArray(v)
            out = gdal.Warp(
                "",
                ds,
                format="MEM",
                outputBounds=bounds,
                xRes=res,
                yRes=res,
                resampleAlg="average",
                dstSRS="EPSG:32613",
                dstNodata=0,
            )
            return out.ReadAsArray()

        support = warp(known.astype(float))
        mean = warp(np.where(known, a / 100, 0))
        rows, cols = np.indices(support.shape)
        inside = (
            (bounds[0] + cols * res >= gt[0])
            & (bounds[0] + (cols + 1) * res <= gt[0] + src.RasterXSize * gt[1])
            & (bounds[3] - rows * res <= gt[3])
            & (bounds[3] - (rows + 1) * res >= gt[3] + src.RasterYSize * gt[5])
        )
        arrays.append(
            np.where(
                inside & (support >= 0.999999),
                mean / np.maximum(support, 1e-12),
                np.nan,
            )
        )
    f = habitat.features(*arrays, res, habitat.DEFAULTS)
    layers = habitat.evaluate(f, habitat.DEFAULTS)
    rr, cc = np.indices(terrain.a.shape)
    cr = np.floor(
        (bounds[3] - (terrain.gt[3] - (rr + 0.5) * terrain.res)) / res
    ).astype(int)
    cl = np.floor(
        ((terrain.gt[0] + (cc + 0.5) * terrain.res) - bounds[0]) / res
    ).astype(int)
    result = {k: v[cr, cl] for k, v in layers.items() if k != "components"}
    result["tree"] = arrays[0][cr, cl]
    result["shrub"] = arrays[1][cr, cl]
    # Unknown remains NaN in observer/spur inputs, known mask controls target scoring.
    npz_write(path, **result)
    return result, key


def visibility(terrain, point, radius, folder, terrain_identity, cancel):
    key = digest(
        [
            "gdal-edge-v1",
            gdal.VersionInfo(),
            terrain_identity,
            terrain.gt,
            terrain.a.shape,
            list(point),
            radius,
            1.7,
            0.8,
            6 / 7,
        ]
    )
    path = folder / "viewsheds" / key / "mask.npz"
    if path.exists():
        data = npz_read(path)
        if tuple(data["shape"]) != terrain.a.shape:
            raise ValueError("Visibility grid shape mismatch")
        return (
            np.unpackbits(data["bits"], count=terrain.a.size)
            .reshape(terrain.a.shape)
            .astype(bool),
            key,
            True,
        )
    cancel()
    x, y = point
    if (
        min(
            x - terrain.bounds[0],
            terrain.bounds[2] - x,
            y - terrain.bounds[1],
            terrain.bounds[3] - y,
        )
        < radius + terrain.res
    ):
        raise ValueError("Observer lacks full obstruction halo for requested radius")
    # GDAL endpoint is exact; a moved observer always gets its own identity.
    with tempfile.TemporaryDirectory(dir=folder) as temp:
        out = gdal.ViewshedGenerate(
            terrain.ds.GetRasterBand(1),
            "GTiff",
            str(Path(temp) / "view.tif"),
            None,
            x,
            y,
            1.7,
            0.8,
            1,
            0,
            0,
            255,
            6 / 7,
            gdal.GVM_Edge,
            radius,
        )
        if out is None:
            raise ValueError("GDAL viewshed calculation failed")
        gt = out.GetGeoTransform()
        col = (gt[0] - terrain.gt[0]) / terrain.res
        row = (terrain.gt[3] - gt[3]) / terrain.res
        if abs(col - round(col)) > 1e-6 or abs(row - round(row)) > 1e-6:
            raise ValueError("Viewshed is not aligned to analytical grid")
        a = out.ReadAsArray()
        rr, cc = int(round(row)), int(round(col))
        mask = np.zeros(terrain.a.shape, bool)
        mask[rr : rr + a.shape[0], cc : cc + a.shape[1]] = a == 1
        # Enforce explicit cell-centre circular target radius as well as GDAL bound.
        rows, cols = np.ogrid[: mask.shape[0], : mask.shape[1]]
        mask &= (terrain.gt[0] + (cols + 0.5) * terrain.res - x) ** 2 + (
            terrain.gt[3] - (rows + 0.5) * terrain.res - y
        ) ** 2 <= radius**2
        out = None
    cancel()
    npz_write(path, bits=np.packbits(mask), shape=np.array(mask.shape))
    return mask, key, False


def observer_screen(terrain, layers, xy):
    offsets = np.array(
        [
            (x, y)
            for x in (-30, -15, 0, 15, 30)
            for y in (-30, -15, 0, 15, 30)
            if x * x + y * y <= 30**2
        ]
    )
    locations = np.asarray(xy)[None, :] + offsets
    tree = terrain.sample(locations, layers["tree"])
    shrub = terrain.sample(locations, layers["shrub"])
    known = np.isfinite(tree) & np.isfinite(shrub)
    own_tree = float(terrain.sample(xy, layers["tree"])[0])
    own_shrub = float(terrain.sample(xy, layers["shrub"])[0])
    support = float(known.mean())
    mean_tree = float(np.mean(tree[known])) if known.any() else None
    mean_shrub = float(np.mean(shrub[known])) if known.any() else None
    unknown = (
        not math.isfinite(own_tree) or not math.isfinite(own_shrub) or support < 0.8
    )
    blocked = not unknown and (
        max(own_tree, mean_tree) > 0.35 or max(own_shrub, mean_shrub) > 0.50
    )
    return dict(
        own_tree=own_tree if math.isfinite(own_tree) else None,
        own_shrub=own_shrub if math.isfinite(own_shrub) else None,
        foreground_radius_m=30,
        foreground_tree=mean_tree,
        foreground_shrub=mean_shrub,
        known_fraction=support,
        unknown=unknown,
        blocked=blocked,
        interpretation="Coarse standing/near-foreground cover proxy; no clearing, understory or optical-clearance certification",
    )


def coverage(masks, layers, target, area):
    mask = np.logical_or.reduce(masks)
    visible = mask & target
    known = visible & layers["known"]
    q = layers["h"] * layers["g"]
    return (
        dict(
            effective_m2=(
                float(np.sum(q[known], dtype=np.float64) * area)
                if known.any()
                else None
            ),
            visible_m2=float(mask.sum() * area),
            matching_m2=float(visible.sum() * area),
            scorable_m2=float(known.sum() * area),
            unknown_m2=float((visible & ~layers["known"]).sum() * area),
            priority_m2=float(
                (known & (layers["h"] >= 0.45) & (layers["g"] >= 0.45)).sum() * area
            ),
        ),
        mask,
    )


class Spurs:
    def __init__(self, network, terrain, layers, domain, envelope, cancel):
        self.network = network
        self.terrain = terrain
        self.layers = layers
        self.domain = domain
        self.envelope = envelope
        self.p = network.p
        self.departures = network.departures()
        inward = [
            math.ceil(terrain.bounds[0] / 20) * 20,
            math.ceil(terrain.bounds[1] / 20) * 20,
            math.floor(terrain.bounds[2] / 20) * 20,
            math.floor(terrain.bounds[3] / 20) * 20,
        ]
        self.grid = Terrain(
            gdal.Warp(
                "",
                terrain.ds,
                format="MEM",
                outputBounds=inward,
                xRes=20,
                yRes=20,
                resampleAlg="bilinear",
            )
        )
        g = self.grid
        rr, cc = np.indices(g.a.shape)
        xy = np.column_stack(
            ((g.gt[0] + (cc.ravel() + 0.5) * 20), (g.gt[3] - (rr.ravel() + 0.5) * 20))
        )
        self.tree = terrain.sample(xy, layers["tree"]).reshape(g.a.shape)
        self.shrub = terrain.sample(xy, layers["shrub"]).reshape(g.a.shape)
        self.slope = terrain.sample(xy, terrain.slope).reshape(g.a.shape)
        valid = (
            np.isfinite(self.tree)
            & np.isfinite(self.shrub)
            & (self.tree <= self.p["max_tree"])
            & (self.shrub <= self.p["max_shrub"])
            & (self.slope <= self.p["max_offtrail_slope"])
            & raster_mask(domain, g.ds)
        )
        seedmap = {}
        self.seed_connectors = {}
        for i, d in enumerate(self.departures):
            r, c = self.cell(d["xy"])
            if not (0 <= r < g.a.shape[0] and 0 <= c < g.a.shape[1]) or not valid[r, c]:
                continue
            line = LineString([d["xy"], self.xy(r, c)])
            if line.length and not self.supported(line):
                continue
            idx = r * g.a.shape[1] + c
            connector_hours = 0.0
            if line.length:
                endpoints = np.asarray(line.coords)
                z = terrain.sample(endpoints)
                grade = (z[1] - z[0]) / line.length
                tree = float(np.mean(terrain.sample(endpoints, layers["tree"])))
                shrub = float(np.mean(terrain.sample(endpoints, layers["shrub"])))
                connector_hours = float(
                    line.length / effort.speed(grade, self.p, True, tree, shrub)
                    + line.length / effort.speed(-grade, self.p, True, tree, shrub)
                )
            base = (
                network.dist[d["node"]]
                + network.return_cost[d["node"]]
                + connector_hours
            )

            if idx not in seedmap or base < seedmap[idx][1]:
                seedmap[idx] = (i, base)
        self.seedmap = seedmap
        near = np.ones(g.a.shape, bool)
        for idx in seedmap:
            near.flat[idx] = False
        distance = distance_transform_edt(near, sampling=20)
        valid &= distance <= envelope
        self.valid = valid
        self.distance = distance
        n = valid.size
        self.super = n
        rows = []
        cols = []
        weights = []
        for dr, dc in ((0, 1), (1, -1), (1, 0), (1, 1)):
            cancel()
            r0 = slice(0, g.a.shape[0] - dr)
            c0 = slice(max(0, -dc), min(g.a.shape[1], g.a.shape[1] - dc))
            r1 = slice(dr, g.a.shape[0])
            c1 = slice(max(0, dc), min(g.a.shape[1], g.a.shape[1] + dc))
            ok = valid[r0, c0] & valid[r1, c1]
            if dr and dc:
                ok &= valid[r0, c1] & valid[r1, c0]
            r, c = np.where(ok)
            r += 0
            c += max(0, -dc)
            nr = r + dr
            nc = c + dc
            a = r * g.a.shape[1] + c
            b = nr * g.a.shape[1] + nc
            length = 20 * math.hypot(dr, dc)
            grade = (g.a[nr, nc] - g.a[r, c]) / length
            keep = np.abs(np.degrees(np.arctan(grade))) <= self.p["max_offtrail_slope"]
            a = a[keep]
            b = b[keep]
            r = r[keep]
            c = c[keep]
            nr = nr[keep]
            nc = nc[keep]
            grade = grade[keep]
            t = (self.tree[r, c] + self.tree[nr, nc]) / 2
            s = (self.shrub[r, c] + self.shrub[nr, nc]) / 2
            w = length / effort.speed(
                grade, self.p, True, t, s
            ) + length / effort.speed(-grade, self.p, True, t, s)
            rows.extend((a, b))
            cols.extend((b, a))
            weights.extend((w, w))
        for idx, (i, cost) in seedmap.items():
            rows.append(np.array([n]))
            cols.append(np.array([idx]))
            weights.append(np.array([cost]))
        if not rows:
            self.cost = np.full(n + 1, np.inf)
            self.prev = np.full(n + 1, -9999)
            return
        graph = coo_matrix(
            (np.concatenate(weights), (np.concatenate(rows), np.concatenate(cols))),
            shape=(n + 1, n + 1),
        ).tocsr()
        self.cost, self.prev = dijkstra(
            graph,
            directed=True,
            indices=n,
            return_predecessors=True,
            limit=self.p["max_hours"],
        )

    def cell(self, xy):
        return int((self.grid.gt[3] - xy[1]) / 20), int((xy[0] - self.grid.gt[0]) / 20)

    def xy(self, r, c):
        return (self.grid.gt[0] + (c + 0.5) * 20, self.grid.gt[3] - (r + 0.5) * 20)

    def supported(self, line):
        if not self.domain.covers(line):
            return False
        ds = np.r_[np.arange(0, line.length, 5), line.length]
        xy = np.array([line.interpolate(float(d)).coords[0] for d in ds])
        slope = self.terrain.sample(xy, self.terrain.slope)
        tree = self.terrain.sample(xy, self.layers["tree"])
        shrub = self.terrain.sample(xy, self.layers["shrub"])
        return bool(
            np.isfinite(tree).all()
            and np.isfinite(shrub).all()
            and np.all(slope <= self.p["max_offtrail_slope"])
            and np.all(tree <= self.p["max_tree"])
            and np.all(shrub <= self.p["max_shrub"])
        )

    def path(self, point):
        r, c = self.cell(point)
        g = self.grid
        if not (0 <= r < g.a.shape[0] and 0 <= c < g.a.shape[1]):
            return None, "Outside spur grid"
        idx = r * g.a.shape[1] + c
        if not np.isfinite(self.cost[idx]):
            return (
                None,
                "No supported off-trail connection under slope/brush/public-land/envelope limits",
            )
        chain = []
        node = idx
        while self.prev[node] != self.super:
            if self.prev[node] < 0:
                return None, "No supported spur predecessor"
            chain.append(node)
            node = int(self.prev[node])
        seed = node
        chain.append(node)
        chain.reverse()
        dep = self.departures[self.seedmap[seed][0]]
        coords = (
            [dep["xy"]]
            + [self.xy(*divmod(n, g.a.shape[1])) for n in chain]
            + [tuple(point)]
        )
        coords = [
            p
            for i, p in enumerate(coords)
            if i == 0 or math.dist(p, coords[i - 1]) > 1e-7
        ]
        if len(coords) < 2:
            return dep["chunks"], None
        line = LineString(coords)
        if not self.supported(line):
            return (
                None,
                "Exact spur crosses excluded/unsupported terrain; no connector was invented",
            )
        return (
            dep["chunks"]
            + [
                dict(
                    coords=coords,
                    offtrail=True,
                    segment="offtrail",
                    status=dict(
                        foot="scenario",
                        condition="unknown",
                        evidence=[
                            "Modeled terrain connection on mapped USFS area; permission/footing/brush unverified"
                        ],
                    ),
                )
            ],
            None,
        )

    def candidates(self, count):
        g = self.grid
        relief = g.a - uniform_filter(g.a, size=25, mode="nearest")
        options = (
            np.isfinite(self.cost[:-1]).reshape(g.a.shape)
            & self.valid
            & (self.distance >= 40)
            & (self.distance <= self.envelope)
            & (self.slope <= 25)
            & (self.tree <= 0.35)
            & (self.shrub <= 0.50)
        )
        # Coarse-to-fine: one local topographic/open candidate per 160m block,
        # then spatially distributed leaders. No old viewpoint seeds used.
        proposed = []
        for r in range(0, g.a.shape[0], 8):
            for c in range(0, g.a.shape[1], 8):
                mask = options[r : r + 8, c : c + 8]
                if not mask.any():
                    continue
                proxy = (
                    relief[r : r + 8, c : c + 8]
                    - self.slope[r : r + 8, c : c + 8] * 0.5
                    - self.tree[r : r + 8, c : c + 8] * 20
                )
                at = np.argmax(np.where(mask, proxy, -np.inf))
                dr, dc = np.unravel_index(at, mask.shape)
                proposed.append((float(proxy[dr, dc]), r + dr, c + dc))
        proposed.sort(reverse=True)
        selected = []
        for value, r, c in proposed:
            xy = self.xy(r, c)
            if any(math.dist(xy, x) < 200 for x in selected):
                continue
            selected.append(xy)
            if len(selected) >= count:
                break
        return selected
