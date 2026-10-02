"""Versioned, bounded union surfaces. Terrain scores are never changed here."""

from functools import lru_cache
from pathlib import Path
import sys
import numpy as np
from scipy.spatial import cKDTree
from . import vegetation_screen as veg

IDENTIFIER = "rounded-cell-union-v2"
TRIANGLE_CAP = 500000
CONTACT_MARGIN = 0.001
STEPS = (0.25, 0.5, 1.0)
TILE = 8.0


class BudgetError(ValueError):
    pass


def marching():
    sys.path.insert(
        0, str(Path(__file__).resolve().parents[1] / ".cache/vegetation-deps")
    )
    try:
        from skimage.measure import marching_cubes

        return marching_cubes
    except ImportError as e:
        raise ValueError(
            "Missing isolated cluster mesher. See docs/gui/FIRST_PERSON.md for setup: "
            + str(e)
        )


def rounded_distance(offset, side):
    q = np.abs(offset) - (side / 2 - 0.25)
    return (
        np.linalg.norm(np.maximum(q, 0), axis=-1)
        + np.minimum(np.max(q, axis=-1), 0)
        - 0.25
    )


def surface(centres, side, step, cap=TRIANGLE_CAP):
    """Same global lattice and halo at every tile; only owned triangles retained."""
    from .first_person import CURVATURE, EARTH

    if not len(centres):
        return np.empty((0, 3), dtype="<f4"), np.empty((0, 3), dtype="<u4")
    centres = np.asarray(centres, dtype=float).copy()
    centres[:, 1] += (
        CURVATURE * np.hypot(centres[:, 0], centres[:, 2]) ** 2 / (2 * EARTH)
    )
    centres = np.rint(centres - 0.5) + 0.5
    tree = cKDTree(centres)
    # Tiles potentially touched by the largest rounded cell; no full-volume array.
    tiles = set()
    for shift in np.ndindex(3, 3, 3):
        keys = np.floor(
            (centres - 0.5 + (np.array(shift) - 1) * (1 + CONTACT_MARGIN)) / TILE
        ).astype(int)
        tiles.update(map(tuple, keys))
    extract = marching()
    parts = []
    face_parts = []
    total = 0
    vertex_offset = 0
    offsets = np.arange(-int(np.ceil(1 / step)), int(np.ceil(1 / step)) + 1)
    kernel_offset = np.stack(
        np.meshgrid(offsets, offsets, offsets, indexing="ij"), axis=-1
    )
    kernel = rounded_distance(kernel_offset * step, side).astype(np.float32)
    width = int(round((TILE + 4) / step)) + 1
    for key in sorted(tiles):
        low = 0.5 + np.array(key) * TILE
        origin = low - 2
        indices = tree.query_ball_point(low + TILE / 2, TILE / 2 + 2, p=np.inf)
        if not indices:
            continue
        field = np.full((width, width, width), 10, dtype=np.float32)
        for centre in centres[indices]:
            idx = np.rint((centre - origin) / step).astype(int)
            a = idx + offsets[0]
            b = idx + offsets[-1] + 1
            lo = np.maximum(a, 0)
            hi = np.minimum(b, width)
            if np.any(lo >= hi):
                continue
            dest = tuple(slice(x, y) for x, y in zip(lo, hi))
            src = tuple(slice(x, y) for x, y in zip(lo - a, hi - a))
            np.minimum(field[dest], kernel[src], out=field[dest])
        if not (field.min() < 0 and field.max() > 0):
            continue
        halo = int(round(2 / step))
        core = int(round(TILE / step)) + 1
        field = field[halo : halo + core, halo : halo + core, halo : halo + core]
        if not (field.min() < CONTACT_MARGIN and field.max() > CONTACT_MARGIN):
            continue
        origin = low
        vertices, faces, _, _ = extract(
            field,
            CONTACT_MARGIN,
            spacing=(step,) * 3,
            allow_degenerate=False,
            gradient_direction="ascent",
        )
        # Recompute edge crossings in float64 on the global lattice. Local
        # float32 marching coordinates otherwise round differently across halos.
        uv = vertices.astype(float) / step
        integer = uv == np.rint(uv)
        edge = np.count_nonzero(integer, axis=1) == 2
        positions = vertices.astype(float) + origin
        if edge.any():
            axis = np.argmin(integer[edge], axis=1)
            a = np.rint(uv[edge]).astype(int)
            a[np.arange(len(a)), axis] = np.floor(
                uv[edge][np.arange(len(a)), axis]
            ).astype(int)
            b = a.copy()
            b[np.arange(len(b)), axis] += 1
            fa = field[tuple(a.T)].astype(float)
            fb = field[tuple(b.T)].astype(float)
            t = (CONTACT_MARGIN - fa) / (fb - fa)
            p = origin + a * step
            p[np.arange(len(p)), axis] += t * step
            positions[edge] = p
        vertices = positions
        if not len(faces):
            continue
        total += len(faces)
        if total > cap:
            raise BudgetError("Cluster surface exceeds lightweight triangle budget")
        parts.append(vertices)
        face_parts.append(faces + vertex_offset)
        vertex_offset += len(vertices)
    if not parts:
        return np.empty((0, 3), dtype="<f4"), np.empty((0, 3), dtype="<u4")
    vertices = np.concatenate(parts)
    faces = np.concatenate(face_parts)
    # Weld only shared tile boundaries. Lewiner may place distinct interior
    # vertices at coincident coordinates to preserve ambiguous-cell topology.
    boundary = np.any(
        np.abs((vertices - 0.5) / TILE - np.rint((vertices - 0.5) / TILE)) < 1e-10,
        axis=1,
    )
    remap = np.arange(len(vertices))
    selected = np.flatnonzero(boundary)
    if len(selected):
        _, first, inverse = np.unique(
            np.rint(vertices[selected] * 1e6).astype(np.int64),
            axis=0,
            return_index=True,
            return_inverse=True,
        )
        remap[selected] = selected[first[inverse]]
    faces = remap[faces]
    good = (
        (faces[:, 0] != faces[:, 1])
        & (faces[:, 1] != faces[:, 2])
        & (faces[:, 0] != faces[:, 2])
    )
    faces = faces[good]
    used, inverse = np.unique(faces, return_inverse=True)
    vertices = vertices[used]
    faces = inverse.reshape(-1, 3)
    vertices[:, 1] -= (
        CURVATURE * np.hypot(vertices[:, 0], vertices[:, 2]) ** 2 / (2 * EARTH)
    )
    vertices = vertices.astype("<f4")
    faces = faces.astype("<u4")
    edges = np.sort(
        np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1
    )
    unique_edges, counts = np.unique(edges, axis=0, return_counts=True)
    if np.any(counts != 2):
        raise ValueError(
            "Cluster surface has open or nonmanifold edges; prior scene retained. "
            + str(np.unique(counts[counts != 2], return_counts=True))
            + " "
            + str(vertices[unique_edges[counts != 2]][:4])
        )
    return vertices, faces


def build_range(centres, radius, cap=TRIANGLE_CAP):
    if isinstance(radius, bool) or radius not in veg.RANGES:
        raise ValueError("Choose nearby foliage range 30, 60 or 120 m")
    subset = centres[np.hypot(centres[:, 0], centres[:, 2]) <= radius]
    for step in STEPS:
        try:
            meshes = {
                name: surface(subset, side, step, cap)
                for name, side in veg.SCENARIOS.items()
            }
            return step, meshes, len(subset)
        except BudgetError:
            continue
    raise BudgetError(
        "Even 1 m cluster detail exceeds the lightweight triangle budget; choose a smaller range. No supported cells were discarded."
    )


@lru_cache(maxsize=6)
def load_mesh(vertices, indices, signature):
    v = np.fromfile(vertices, dtype="<f4").reshape(-1, 3)
    f = np.fromfile(indices, dtype="<u4").reshape(-1, 3)
    triangles = v[f].astype(float)
    return (
        triangles,
        triangles.min(axis=1) if len(f) else np.empty((0, 3)),
        triangles.max(axis=1) if len(f) else np.empty((0, 3)),
    )


def ray_hits(triangles, start, direction):
    if not len(triangles):
        return np.empty(0)
    a = triangles[:, 0]
    e1 = triangles[:, 1] - a
    e2 = triangles[:, 2] - a
    h = np.cross(direction, e2)
    det = np.einsum("ij,ij->i", e1, h)
    good = np.abs(det) > 1e-12
    inv = np.divide(1.0, det, out=np.zeros_like(det), where=good)
    s = start - a
    u = inv * np.einsum("ij,ij->i", s, h)
    q = np.cross(s, e1)
    w = inv * (q @ direction)
    t = inv * np.einsum("ij,ij->i", e2, q)
    return t[good & (u >= -1e-8) & (w >= -1e-8) & (u + w <= 1 + 1e-8) & (t >= -1e-8)]


def inside(mesh, point):
    triangles, low, high = mesh
    # Non-axis ray avoids coplanar face/edge ambiguity; de-duplicate shared hits.
    direction = np.array([1.0, 0.37139067, 0.52982213])
    possible = np.all(high >= point, axis=1)
    t = ray_hits(triangles[possible], point, direction)
    if np.any(np.abs(t) < 1e-7):
        return True
    return bool(len(np.unique(np.rint(t[t > 1e-7] * 1e7))) % 2)


def intersect(mesh, start, end):
    triangles, low, high = mesh
    start = np.asarray(start, float)
    end = np.asarray(end, float)
    delta = end - start
    enter = np.zeros(len(low))
    leave = np.ones(len(low))
    possible = np.ones(len(low), bool)
    for axis in range(3):
        if abs(delta[axis]) < 1e-12:
            possible &= (start[axis] >= low[:, axis] - 1e-7) & (
                start[axis] <= high[:, axis] + 1e-7
            )
        else:
            a = (low[:, axis] - start[axis]) / delta[axis]
            b = (high[:, axis] - start[axis]) / delta[axis]
            enter = np.maximum(enter, np.minimum(a, b))
            leave = np.minimum(leave, np.maximum(a, b))
    t = ray_hits(triangles[possible & (enter <= leave + 1e-7)], start, delta)
    t = t[t <= 1 + 1e-8]
    initial = inside(mesh, start)
    final = inside(mesh, end)
    return (
        0.0 if initial else float(np.clip(t.min(), 0, 1)) if len(t) else None,
        len(t),
        initial,
        final,
    )


def evaluate(
    folder, meta, start, end, distance, ground, scenario, unknown, radius, resolve
):
    info = meta["vegetation"]["meshes"].get(str(int(radius)))
    if not info or info.get("unavailable"):
        return dict(
            status="unavailable",
            reason=(info or {}).get(
                "reason", "Prepare cluster surfaces for this range."
            ),
        )
    results = {}
    for name, entry in info["scenarios"].items():
        vp = resolve(folder, meta, entry["vertices_file"])
        ip = resolve(folder, meta, entry["indices_file"])
        mesh = load_mesh(
            str(vp), str(ip), (vp.stat().st_mtime_ns, ip.stat().st_mtime_ns)
        )
        t, count, a, b = intersect(mesh, start, end)
        point = None
        if t is not None:
            p = np.asarray(start) + (np.asarray(end) - start) * t
            point = dict(
                distance_m=distance * t,
                east_m=float(p[0]),
                north_m=float(-p[2]),
                line_m=float(p[1] + ground),
            )
        results[name] = dict(
            result=(
                "intersects inferred vegetation"
                if t is not None
                else "no modeled intersection"
            ),
            intersected_surface_triangles=count,
            first_intersection=point,
            observer_inside=a,
            target_inside=b,
            side_m=veg.SCENARIOS[name],
        )
    return dict(
        status="evaluated",
        selected_scenario=scenario,
        scenarios=results,
        unknown_ground=unknown,
        evaluated_radius_m=radius,
        included_cell_count=info["cell_count"],
        sampling_interval_m=info["sampling_interval_m"],
        geometry_identifier=IDENTIFIER,
        farther_vegetation_unevaluated=distance > radius,
        warning="Experimental opaque-foliage assumption, not verified vegetation or a clear field sightline. Missing returns do not mean open space.",
    )
