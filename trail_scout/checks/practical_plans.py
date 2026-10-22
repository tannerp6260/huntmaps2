"""Reproducible real-entry comparison; no providers, owner state or synthetic deer."""

from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import platform
import resource
import socket
import tempfile
import time
import uuid
from unittest.mock import patch

import numpy as np
from osgeo import gdal, ogr
from shapely.geometry import Point, shape

from trail_scout.storage import Paths, atomic, read, file_hash, implementation
from trail_scout.sources import Pack, raster_mask, project
from trail_scout.network import starts
from trail_scout.analysis import habitat_layers, npz_read
from trail_scout.planner import calculate
from practical_glassing import replan
from practical_glassing.timed import Objective, union_values
from practical_glassing.selection import select_options
from practical_glassing.engine import community_layers


def selection(result, mode):
    ident = result["recommended"].get(mode)
    return next((o for o in result["options"] if o["id"] == ident), None)


def brief(option, mode, objective):
    if option is None:
        return None
    v = option["schedules"][mode]
    common = objective.score([r["id"] for r in option["viewpoints"]], v)
    return dict(
        ids=[r["id"] for r in option["viewpoints"]],
        coordinates=[[r["longitude"], r["latitude"]] for r in option["viewpoints"]],
        movement={
            k: option["movement"][k]
            for k in (
                "distance_m",
                "ascent_m",
                "descent_m",
                "hours_low",
                "hours_high",
                "offtrail_m",
            )
        },
        remaining=option["remaining"],
        terrain=option["coverage"],
        schedule=v,
        common_practical=common,
        entry_conditional=True,
    )


def indices_for(option, mode, objective, selected=False):
    cells = []
    score = objective.score(
        [r["id"] for r in option["viewpoints"]], option["schedules"][mode]
    )
    for p, v in zip(option["viewpoints"], score["visits"]):
        s = objective.support[p["id"]]
        keep = (
            np.isin(s.patch, [p["id"] for p in v["patches"]])
            if selected
            else np.ones(len(s.indices), bool)
        )
        cells.append(s.indices[keep])
    return np.unique(np.concatenate(cells))


def map_svg(path, terrain, new, established, practical, mode, start):
    """Actual categorical polygons and complete connected routes; no RGB class proxy."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as PlotPath
    from shapely.geometry.polygon import orient
    from matplotlib.collections import PatchCollection
    from matplotlib.lines import Line2D
    from matplotlib.colors import ListedColormap, BoundaryNorm
    from practical_glassing.model import GROUPS

    colors = [
        "#bababa",
        "#d6d675",
        "#a2b983",
        "#315d48",
        "#a17b4e",
        "#c2bd96",
        "#d8e6b7",
        "#d4dce1",
    ]
    ds = gdal.GetDriverByName("MEM").Create(
        "", terrain.a.shape[1], terrain.a.shape[0], 1, gdal.GDT_Byte
    )
    ds.SetGeoTransform(terrain.gt)
    ds.SetProjection(terrain.ds.GetProjection())
    ds.GetRasterBand(1).WriteArray(new["group"])
    vectors = ogr.GetDriverByName("Memory").CreateDataSource("")
    layer = vectors.CreateLayer("community", geom_type=ogr.wkbPolygon)
    layer.CreateField(ogr.FieldDefn("group", ogr.OFTInteger))
    gdal.Polygonize(ds.GetRasterBand(1), None, layer, 0, [])
    fig, ax = plt.subplots(figsize=(9, 8))
    patches = []
    values = []
    for row in layer:
        geom = shape(json.loads(row.GetGeometryRef().ExportToJson()))
        geom = orient(geom, sign=1)
        rings = [geom.exterior, *geom.interiors]
        outline = PlotPath.make_compound_path(
            *[PlotPath(np.asarray(r.coords), closed=True) for r in rings]
        )
        patches.append(PathPatch(outline))
        values.append(row["group"])
    coll = PatchCollection(
        patches,
        cmap=ListedColormap(colors),
        norm=BoundaryNorm(np.arange(-0.5, 8.5), 8),
        linewidth=0,
    )
    coll.set_array(np.array(values))
    ax.add_collection(coll)
    for option, color in [(established, "#176fd0"), (practical, "#be2c2c")]:
        if not option:
            continue
        for leg in option["legs"]:
            xy = np.asarray(project(shape(leg["geometry"])).coords)
            ax.plot(xy[:, 0], xy[:, 1], color=color, lw=2)
        for i, p in enumerate(option["viewpoints"]):
            ax.scatter([p["x"]], [p["y"]], c=color, s=30)
            ax.text(p["x"], p["y"], f" {i+1}:{p['id'][:6]}", color=color, fontsize=8)
    if practical:
        p = practical["schedules"][mode]["practical"]
        for f in p["sectors"]["features"]:
            geom = project(shape(f["geometry"]))
            a = np.asarray(geom.exterior.coords)
            ax.plot(a[:, 0], a[:, 1], c="#a35b00", lw=0.6, alpha=0.6)
        points = practical["viewpoints"]
        xs = [p["x"] for p in points] + [start["x"]]
        ys = [p["y"] for p in points] + [start["y"]]
        ax.set_xlim(min(xs) - 1700, max(xs) + 1700)
        ax.set_ylim(min(ys) - 1700, max(ys) + 1700)
    ax.scatter([start["x"]], [start["y"]], marker="s", c="black", s=40)
    ax.set_aspect("equal")
    ax.set_title(
        f"{start['label']} · {mode.upper()} · provisional desktop\nBlue established / red practical / amber selected scan footprints"
    )
    handles = [
        Line2D([0], [0], marker="s", color=colors[i], label=n, linestyle="")
        for i, n in enumerate(GROUPS)
    ]
    ax.legend(handles=handles, loc="upper left", fontsize=7, ncol=2)
    ax.set_xlabel(
        "EPSG:32613 metres. LF2025 classes; unknown grey. No field sightline certification."
    )
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main():
    root = Path(tempfile.mkdtemp(prefix="practical-plans-comparison-"))
    paths = Paths(state=root / "state")
    rows = []
    times = []
    with patch.object(
        socket.socket, "connect", side_effect=AssertionError("No network in comparison")
    ):
        pack = Pack(paths)
        entries = starts(pack, date(2026, 10, 31))
        for name in ("Soap Creek · entry", "Flattop Bench · entry"):
            entry = next(e for e in entries if e["label"] == name)
            body = dict(start_id=entry["id"], candidate_budget=32, date="2026-10-31")

            def run(label, inputs):
                t = time.perf_counter()
                r = calculate(
                    paths, pack, inputs, paths.artifact("analyses", uuid.uuid4().hex)
                )
                wall = time.perf_counter() - t
                times.append(
                    dict(
                        entry=name,
                        label=label,
                        wall_seconds=wall,
                        stages=r["performance"],
                        route_basis_reused=r["search"].get("route_basis_reused", False),
                        peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                        / 1024,
                    )
                )
                print(name, label, round(wall, 3), flush=True)
                return r

            established = run("established", body)
            paths = Paths(state=root / (name.split()[0] + "-practical-state"))
            practical = run("practical cold", dict(body, practical_plan={}))
            warm = run("practical warm", dict(body, practical_plan={}))
            assert practical["recommended"] == warm["recommended"]
            same = lambda r: [
                (p["id"], p["longitude"], p["latitude"]) for p in r["candidates"]
            ]
            assert same(established) == same(practical)
            terrain = pack.terrain(Point(entry["x"], entry["y"]).buffer(4400).bounds)
            layers, _ = habitat_layers(pack, terrain, paths.state / "cache")
            target = raster_mask(pack.boundary, terrain.ds)
            viable = [r for r in practical["candidates"] if r["feasible"]]
            masks = {}
            for r in viable:
                z = npz_read(
                    paths.state / "cache/viewsheds" / r["mask_key"] / "mask.npz"
                )
                masks[r["id"]] = (
                    np.unpackbits(z["bits"], count=terrain.a.size)
                    .reshape(terrain.a.shape)
                    .astype(bool)
                )
            objective = Objective(
                paths,
                pack,
                terrain,
                layers,
                target,
                [dict(r, radius_m=1500) for r in viable],
                masks,
                practical["settings"]["practical_plan"],
            )
            basis = read(replan.key(paths, pack, practical["settings"]) / "basis.json")
            alternatives = deepcopy(basis["options"])
            # Use the exact actual schedule machinery and the full evaluated pool.
            from trail_scout import schedule

            for o in alternatives:
                o["schedules"] = {
                    m: schedule.variant(
                        body["date"],
                        entry,
                        o["legs"],
                        practical["settings"]["profile"],
                        practical["settings"]["schedule"],
                        m,
                    )
                    for m in ("am", "pm")
                }
            ablations = {}
            for label, joint, cap in [
                ("joint actual", True, None),
                ("independent actual", False, None),
                ("joint fixed 30", True, 30),
                ("joint cap 60", True, 60),
            ]:
                options = deepcopy(alternatives)
                for o in options:
                    for m in ("am", "pm"):
                        o["schedules"][m]["practical"] = objective.score(
                            [r["id"] for r in o["viewpoints"]],
                            o["schedules"][m],
                            joint=joint,
                            cap_override=cap,
                        )
                _, rec = select_options(options)
                ablations[label] = {
                    m: brief(
                        next((o for o in options if o["id"] == rec.get(m)), None),
                        m,
                        objective,
                    )
                    for m in ("am", "pm")
                }
            sensitivities = {}
            for label, policy in [
                ("spot", dict(task="spot")),
                ("assess", dict(task="assess")),
                ("leaf off", dict(leaf="off")),
            ]:
                changed = run(label, dict(body, practical_plan=dict(policy=policy)))
                sensitivities[label] = {
                    m: brief(selection(changed, m), m, objective) for m in ("am", "pm")
                }
            modes = {}
            for m in ("am", "pm"):
                a, b = selection(established, m), selection(practical, m)
                physical_a, physical_b = indices_for(a, m, objective), indices_for(
                    b, m, objective
                )
                searched_a, searched_b = indices_for(
                    a, m, objective, True
                ), indices_for(b, m, objective, True)

                def jac(a, b):
                    return len(np.intersect1d(a, b)) / max(1, len(np.union1d(a, b)))

                modes[m] = dict(
                    established=brief(a, m, objective),
                    practical=brief(b, m, objective),
                    terrain_jaccard=jac(physical_a, physical_b),
                    searched_jaccard=jac(searched_a, searched_b),
                )
                map_svg(
                    root / (name.split()[0] + "-" + m + ".svg"),
                    terrain,
                    community_layers(objective.package, terrain.ds),
                    a,
                    b,
                    m,
                    entry,
                )
            # Verify unchanged candidate old scores against the fresh pre-edit run.
            baseline_root = Path("/tmp/trailscout-performance-crw59fuf/state/analyses")
            baseline = next(
                (
                    read(f)
                    for f in baseline_root.glob("*/result.json")
                    if read(f)["start"]["label"] == name
                ),
                None,
            )
            reproduction = dict(available=baseline is not None)
            if baseline:
                assert same(baseline) == same(established)
                errors = [
                    abs(
                        (a["coverage"]["effective_m2"] or 0)
                        - (b["coverage"]["effective_m2"] or 0)
                    )
                    for a, b in zip(baseline["candidates"], established["candidates"])
                    if "coverage" in a
                ]
                reproduction.update(
                    coordinates_exact=True,
                    max_abs_old_score_error_m2=max(errors, default=0),
                )
                assert reproduction["max_abs_old_score_error_m2"] <= 1e-6
            rows.append(
                dict(
                    entry=entry,
                    candidate_coordinates=same(practical),
                    candidate_masks={r["id"]: r["mask_key"] for r in viable},
                    baseline_reproduction=reproduction,
                    search=practical["search"],
                    modes=modes,
                    ablations=ablations,
                    sensitivities=sensitivities,
                )
            )
            atomic(
                root / "comparison.json",
                dict(
                    version=1,
                    implementation=implementation(),
                    source=pack.revision,
                    package=objective.package.spec["id"],
                    network_attempts=0,
                    hardware=dict(
                        platform=platform.platform(),
                        processor=platform.processor(),
                        python=platform.python_version(),
                    ),
                    measurements=times,
                    entries=rows,
                ),
            )
    print("COMPARISON EVIDENCE:", root, flush=True)


if __name__ == "__main__":
    main()
