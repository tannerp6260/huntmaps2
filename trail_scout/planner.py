"""One shared browser/headless engine; bounded alternatives, explicit tradeoffs."""

from datetime import date as Date
import math
from pathlib import Path
import time

import numpy as np
from osgeo import gdal
from shapely.geometry import shape, Point, LineString, box
from shapely.ops import unary_union

from .storage import digest, implementation, atomic, now, IntegrityError
from .sources import Pack, project, geographic, feature, collection, raster_mask, access
from .network import Network, starts, measured, reverse, concatenate
from .analysis import habitat_layers, visibility, coverage, Spurs, observer_screen
from . import profiles, schedule, effort, render

WARNINGS = [
    "Provisional desktop scenarios. Mapped access is not verified permission, safe tread or parking. Check current GMUG orders/alerts and applicable ownership/easements.",
    "USFS/MVUM snapshots and network completeness are limited. Missing lines or closure records cannot establish remoteness or permission.",
    "10 m bare-earth terrain and coarse annual 2023 vegetation cannot certify standing clearance, understory, leaf-off visibility, current snow or conditions.",
    "Habitat preference and glassability are unchanged structural proxies; no deer occupancy, detection or shooting-distance model.",
    "Travel pace, brush penalties, time margins and hunter limits are uncalibrated assumptions. Carry reserves; rests do not reset physical effort.",
    "Astronomical sunrise/twilight are logistics aids with an approximate horizon, separate from terrain shadows and legal shooting hours. Verify official CPW rules.",
]


def validate(body):
    allowed = {
        "date",
        "profile",
        "start_id",
        "custom_start",
        "vehicle",
        "corridor_m",
        "view_radius_m",
        "search_envelope_m",
        "candidate_budget",
        "explore_unknown",
        "excluded_segments",
        "excluded_areas",
        "rejected",
        "pinned",
        "restrictions",
        "schedule",
        "travel_area",
        "target_area",
        "practical",
        "practical_plan",
        "vehicle_width_inches",
    }
    if not isinstance(body, dict) or set(body) - allowed:
        raise ValueError("Unknown analysis input")
    out = dict(
        date="2026-10-31",
        profile={},
        start_id="",
        custom_start=None,
        vehicle="truck",
        corridor_m=2500,
        view_radius_m=1500,
        search_envelope_m=300,
        candidate_budget=32,
        explore_unknown=False,
        excluded_segments=[],
        excluded_areas=[],
        rejected=[],
        pinned=[],
        restrictions=[],
        schedule={},
        travel_area=None,
        target_area=None,
        practical=None,
        practical_plan=None,
        vehicle_width_inches=None,
    )
    out.update(body)
    if out["practical"] is not None:
        from practical_glassing.model import settings as practical_settings

        out["practical"] = practical_settings(out["practical"])
    if out["practical_plan"] is not None:
        from practical_glassing.timed import settings as timed_settings

        out["practical_plan"] = timed_settings(out["practical_plan"])
    width = out["vehicle_width_inches"]
    if width is not None and (
        type(width) not in (int, float)
        or not math.isfinite(width)
        or not 30 <= width <= 100
    ):
        raise ValueError(
            "Supply actual vehicle width in inches, 30–100, or leave unknown"
        )
    try:
        Date.fromisoformat(out["date"])
    except (ValueError, TypeError):
        raise ValueError("Use an ISO calendar date")
    if out["vehicle"] not in ("truck", "teryx"):
        raise ValueError(
            "Choose truck or Teryx; width/use restrictions remain source specific"
        )
    for key, low, high in (
        ("corridor_m", 500, 4500),
        ("view_radius_m", 500, 3000),
        ("search_envelope_m", 0, 1500),
        ("candidate_budget", 8, 80),
    ):
        n = out[key]
        if type(n) not in (int, float) or not math.isfinite(n) or not low <= n <= high:
            raise ValueError(f"{key} must be within {low}–{high}")
    if type(out["candidate_budget"]) is not int:
        raise ValueError("Candidate budget must be an integer")
    if type(out["explore_unknown"]) is not bool:
        raise ValueError("Unknown access must be an explicit scenario toggle")
    out["profile"] = profiles.validate(out["profile"])
    out["schedule"] = schedule.settings(out["schedule"])
    for k in (
        "excluded_segments",
        "excluded_areas",
        "rejected",
        "pinned",
        "restrictions",
    ):
        if not isinstance(out[k], list) or len(out[k]) > 100:
            raise ValueError("Bounded edits must be lists of at most 100 records")
    if len(out["pinned"]) > 2:
        raise ValueError(
            "First release evaluates single locations and pairs; at most two pinned viewpoints per plan"
        )
    for k in ("excluded_segments", "rejected"):
        if any(not isinstance(v, str) for v in out[k]):
            raise ValueError("Segment/viewpoint IDs must be strings")
    for point in out["pinned"]:
        if not isinstance(point, dict) or not all(
            type(point.get(k)) in (int, float) and math.isfinite(point[k])
            for k in ("longitude", "latitude")
        ):
            raise ValueError("Pinned viewpoints need exact finite longitude/latitude")
        if not -108 < point["longitude"] < -106 or not 38 < point["latitude"] < 40:
            raise ValueError("Pinned point outside GMU54 source region")
    for rule in out["restrictions"]:
        if (
            not isinstance(rule, dict)
            or not rule.get("segment")
            or not rule.get("provenance")
        ):
            raise ValueError(
                "Manual restriction/status needs segment, provenance and dates"
            )
        for k in ("from", "until"):
            if rule.get(k):
                Date.fromisoformat(rule[k])
        if rule.get("from") and rule.get("until") and rule["from"] > rule["until"]:
            raise ValueError("Restriction dates are reversed")
    for g in out["excluded_areas"] + [out["travel_area"], out["target_area"]]:
        if g is None:
            continue
        geo = shape(g.get("geometry", g))
        if (
            geo.geom_type not in ("Polygon", "MultiPolygon")
            or not geo.is_valid
            or geo.is_empty
        ):
            raise ValueError("Use a valid nonempty WGS84 polygon")
        if not box(-108, 38, -106, 40).covers(geo):
            raise ValueError("Edit polygon is outside supported GMU54 region")
    return out


def resolve_start(pack, c):
    rows = starts(
        pack,
        Date.fromisoformat(c["date"]),
        c["vehicle"],
        c["restrictions"],
        c.get("vehicle_width_inches"),
    )
    if c["custom_start"]:
        v = c["custom_start"]
        seg = next((r for r in pack.network if r["id"] == v.get("segment")), None)
        if seg is None:
            raise ValueError("Custom start must identify its intended segment")
        pt = project(Point(v["longitude"], v["latitude"]))
        if pt.distance(seg["geometry"]) > 0.5:
            raise ValueError(
                "Custom start is not on its intended mapped line (0.5 m tolerance). Select a point on that line; no arbitrary nearest-line connection is assumed."
            )
        exact = seg["geometry"].interpolate(seg["geometry"].project(pt))
        lon, lat = geographic(exact).coords[0]
        return dict(
            id=digest(v)[:32],
            segment=seg["id"],
            label=v.get("label", "Owner selected start"),
            x=exact.x,
            y=exact.y,
            longitude=lon,
            latitude=lat,
            motor_gap_m=None,
            note=f"Owner selected intended segment; point projected {pt.distance(exact):.3f} m onto mapped geometry. Parking/vehicle approach unverified.",
        )
    if not c["start_id"] and rows:
        return rows[0]
    selected = next((r for r in rows if r["id"] == c["start_id"]), None)
    if not selected:
        raise ValueError(
            "Selected entry lacks supported vehicle/date evidence in this scenario. Choose a currently supported entry or explicitly enter a reviewed manual start/status."
        )
    return selected


def access_evidence(
    point,
    mask,
    target,
    terrain,
    pack,
    all_starts,
    c,
    network,
    depart_node=None,
    context=None,
):
    day = Date.fromisoformat(c["date"])
    pt = Point(point)
    motor = (
        context["motor"]
        if context
        else [
            r
            for r in pack.network
            if access(
                r, day, c["vehicle"], c["restrictions"], c.get("vehicle_width_inches")
            )["motor"]
            == "supported"
        ]
    )
    nearest = min(motor, key=lambda r: pt.distance(r["geometry"]), default=None)
    other = [
        s
        for s in all_starts
        if s["id"] != network.start["id"]
        and math.dist((s["x"], s["y"]), (network.start["x"], network.start["y"])) > 100
    ]
    entry = min(other, key=lambda s: math.dist(point, (s["x"], s["y"])), default=None)
    neararea = 0.0
    if motor:
        nearby = (
            context["near_mask"]
            if context
            else raster_mask(
                unary_union(
                    [
                        r["geometry"].buffer(500)
                        for r in motor
                        if r["geometry"].distance(box(*terrain.bounds)) < 500
                    ]
                ),
                terrain.ds,
            )
        )
        neararea = float((mask & target & nearby).sum() * terrain.res**2)
    known_distance = pt.distance(nearest["geometry"]) if nearest else None
    label = (
        "near mapped motor access"
        if known_distance is not None and known_distance <= 500
        else "access completeness limited"
    )
    return dict(
        label=label,
        nearest_motor_m=known_distance,
        motor_name=nearest["properties"].get("name") if nearest else None,
        other_entry=entry["label"] if entry else None,
        other_entry_straight_m=(
            math.dist(point, (entry["x"], entry["y"])) if entry else None
        ),
        target_near_motor_m2=neararea,
        shared_approach_m=None,
        definition="Near: <=500 m straight-line distance to date/mode-supported mapped motor route. All other cases retain completeness-limited status; no solitude prediction or remoteness bonus. Other-entry distance is a lower bound, not a supported walking connection.",
        completeness="USFS mapped inventory with dated MVUM/closed-road snapshots; other jurisdictions and current emergency/area/foot closures may be missing.",
    )


def calculate(paths, pack, body, folder, progress=lambda *a: None, cancel=lambda: None):
    begin = time.perf_counter()
    c = validate(body)
    impl = implementation()
    start = resolve_start(pack, c)
    folder.mkdir(parents=True, exist_ok=True)
    cache = paths.state / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    paths.space(350 * 1024**2)
    progress("terrain", 0, 1, "Validating buffered 10 m terrain and source identity")
    # Extent depends on explicit search settings, never on GMU as obstruction clip.
    outer = c["corridor_m"] + c["search_envelope_m"] + c["view_radius_m"] + 100
    terrain = pack.terrain(Point(start["x"], start["y"]).buffer(outer).bounds)
    cancel()
    progress(
        "habitat", 0, 1, "Preparing coarse supported habitat/context; unknowns retained"
    )
    layers, hkey = habitat_layers(pack, terrain, cache)
    target_domain = (
        pack.boundary
        if c["target_area"] is None
        else project(shape(c["target_area"].get("geometry", c["target_area"])))
    )
    target = raster_mask(target_domain, terrain.ds)
    route_basis = None
    if c["practical_plan"] is not None and c["practical"] is None:
        from practical_glassing import replan

        route_basis = replan.key(paths, pack, c)
        if (route_basis / "basis.json").exists():
            result = replan.run(
                paths,
                pack,
                c,
                folder,
                terrain,
                layers,
                target,
                route_basis,
                progress,
                cancel,
            )
            result["performance"]["total_seconds"] = time.perf_counter() - begin
            atomic(folder / "result.json", result)
            return result
    public = pack.public_area(terrain.bounds)
    if c["travel_area"]:
        public = project(shape(c["travel_area"].get("geometry", c["travel_area"])))
    exclusions = unary_union(
        [project(shape(g.get("geometry", g))) for g in c["excluded_areas"]]
    )
    local = dict(
        c,
        _exclusion_geometry=exclusions,
        _travel_geometry=public if c["travel_area"] else None,
    )
    domain = (
        public if public is not None else Point(start["x"], start["y"]).buffer(0)
    ).difference(exclusions)
    progress(
        "network",
        0,
        1,
        "Profiling along actual mapped geometry; exact endpoint junctions only",
    )
    network = Network(
        pack, start, terrain, c["profile"], local, layers["tree"], layers["shrub"]
    )
    departures = network.departures()
    if not departures:
        raise ValueError(
            "No connected evaluated walking portion from this start. Exclusions/access/topology may disconnect it; this is not proof all routes are impossible."
        )
    cancel()
    progress(
        "spurs",
        0,
        1,
        "Searching new supported positions with return-aware off-trail connections",
    )
    spur = Spurs(network, terrain, layers, domain, c["search_envelope_m"], cancel)
    proposals = []
    automatic_budget = c["candidate_budget"] - len(c["pinned"])
    mapped_count = automatic_budget // 2
    indices = np.linspace(
        0, len(departures) - 1, min(mapped_count, len(departures)), dtype=int
    )
    for i in indices:
        d = departures[i]
        proposals.append(
            dict(xy=d["xy"], chunks=d["chunks"], kind="mapped route", pinned=False)
        )
    for xy in spur.candidates(automatic_budget - len(proposals)):
        chunks, error = spur.path(xy)
        proposals.append(
            dict(xy=xy, chunks=chunks, kind="off-trail spur", error=error, pinned=False)
        )
    for p in c["pinned"]:
        xy = project(Point(p["longitude"], p["latitude"])).coords[0]
        nearest = min(departures, key=lambda d: math.dist(d["xy"], xy))
        if math.dist(nearest["xy"], xy) < 0.001:
            chunks, error = nearest["chunks"], None
        else:
            chunks, error = spur.path(xy)
        proposals = [x for x in proposals if math.dist(x["xy"], xy) > 0.001]
        proposals.append(
            dict(
                xy=xy,
                chunks=chunks,
                kind="pinned",
                error=error,
                pinned=True,
                longitude=p["longitude"],
                latitude=p["latitude"],
            )
        )
    all_starts = starts(
        pack,
        Date.fromisoformat(c["date"]),
        c["vehicle"],
        c["restrictions"],
        c.get("vehicle_width_inches"),
    )
    network.prepare_other_access(all_starts)
    motor = [
        r
        for r in pack.network
        if access(
            r,
            Date.fromisoformat(c["date"]),
            c["vehicle"],
            c["restrictions"],
            c.get("vehicle_width_inches"),
        )["motor"]
        == "supported"
    ]
    near_mask = raster_mask(
        unary_union(
            [
                r["geometry"].buffer(500)
                for r in motor
                if r["geometry"].distance(box(*terrain.bounds)) < 500
            ]
        ),
        terrain.ds,
    )
    access_context = dict(motor=motor, near_mask=near_mask)
    candidates = []
    masks = {}
    paths_by_id = {}
    hits = 0
    target_key = digest([pack.revision, c["target_area"], terrain.gt, terrain.a.shape])
    for i, proposal in enumerate(proposals):
        cancel()
        xy = proposal["xy"]
        ident = digest(["point", [round(float(v), 6) for v in xy]])[:32]
        lon, lat = geographic(Point(xy)).coords[0]
        lon = proposal.get("longitude", lon)
        lat = proposal.get("latitude", lat)
        row = dict(
            id=ident,
            longitude=lon,
            latitude=lat,
            x=xy[0],
            y=xy[1],
            kind=proposal["kind"],
            pinned=proposal["pinned"],
            rejected=ident in c["rejected"],
            reasons=[],
        )
        progress(
            "viewpoints",
            i,
            len(proposals),
            f"Evaluating {i+1}/{len(proposals)} exact positions; completed masks retained",
        )
        if row["rejected"]:
            row["reasons"].append("Rejected by owner")
        if proposal.get("error"):
            row["reasons"].append(proposal["error"])
        try:
            tree = float(terrain.sample(xy, layers["tree"])[0])
            shrub = float(terrain.sample(xy, layers["shrub"])[0])
            slope = float(terrain.sample(xy, terrain.slope)[0])
            screen = observer_screen(terrain, layers, xy)
            row["observer_screen"] = screen
            if screen["unknown"]:
                row["reasons"].append("Observer/30 m foreground vegetation unknown")
            elif screen["blocked"]:
                row["reasons"].append(
                    "Standing/foreground cover proxy exceeds conservative 35% tree / 50% shrub screening"
                )
            if slope > 25:
                row["reasons"].append("Standing ground slope exceeds 25° screen")
            row["standing_note"] = (
                f"Coarse standing tree/shrub {tree*100:.0f}%/{shrub*100:.0f}%, ground slope {slope:.0f}°. 30 m foreground support {screen['known_fraction']*100:.0f}%; clearing, understory and sightlines unverified."
            )
            if not row["reasons"] and proposal["chunks"]:
                out = measured(
                    proposal["chunks"],
                    terrain,
                    c["profile"],
                    layers["tree"],
                    layers["shrub"],
                )
                ret = measured(
                    reverse(proposal["chunks"]),
                    terrain,
                    c["profile"],
                    layers["tree"],
                    layers["shrub"],
                )
                movement = effort.add_metrics(out, ret)
                row.update(
                    outbound=out,
                    return_leg=ret,
                    movement=movement,
                    remaining=profiles.remaining(movement, c["profile"]),
                )
                row["reasons"].extend(profiles.failures(movement, c["profile"]))
                if not row["reasons"]:
                    mask, key, hit = visibility(
                        terrain,
                        xy,
                        c["view_radius_m"],
                        cache,
                        pack.spec["data"]["dem"]["sha256"],
                        cancel,
                    )
                    hits += int(hit)
                    cov, _ = coverage([mask], layers, target, terrain.res**2)
                    row.update(coverage=cov, mask_key=key)
                    if c["practical_plan"] is None and (
                        cov["effective_m2"] is None or cov["effective_m2"] <= 0
                    ):
                        row["reasons"].append(
                            "No positive supported quality-adjusted target coverage"
                        )
                    else:
                        masks[ident] = mask
                        paths_by_id[ident] = proposal["chunks"]
                        row["access"] = access_evidence(
                            xy,
                            mask,
                            target,
                            terrain,
                            pack,
                            all_starts,
                            c,
                            network,
                            context=access_context,
                        )
                        row["access"]["connected_other_access"] = network.other_access(
                            proposal["chunks"], ret["offtrail_hours_high"]
                        )

        except IntegrityError:
            raise
        except ValueError as error:
            row["reasons"].append(str(error))
        row["feasible"] = not row["reasons"]
        candidates.append(row)
        atomic(
            folder / "checkpoint.json",
            dict(
                implementation=impl,
                input_token=digest(c),
                completed=[r["id"] for r in candidates],
                stage="viewpoints",
                updated_utc=now(),
                reuse="Independent sealed source/habitat/mask caches survive retry; interrupted planner resumes by deterministic reevaluation.",
            ),
        )
    viable = [r for r in candidates if r["feasible"]]
    viable.sort(key=lambda r: -(r["coverage"]["effective_m2"] or 0))
    pinned = [r for r in candidates if r["pinned"]]
    pin_errors = [
        dict(id=r["id"], reasons=r["reasons"]) for r in pinned if not r["feasible"]
    ]
    progress(
        "plans",
        0,
        1,
        "Checking complete out-and-back / connected-pair alternatives and conservative AM/PM schedules",
    )
    objective = None
    if c["practical_plan"] is not None:
        from practical_glassing.timed import Objective

        progress(
            "practical-support",
            0,
            len(viable),
            "Preparing unselected community/task patches; unknowns remain explicit",
        )
        objective = Objective(
            paths,
            pack,
            terrain,
            layers,
            target,
            [dict(r, radius_m=c["view_radius_m"]) for r in viable],
            masks,
            c["practical_plan"],
            cancel,
        )
    selection_begin = time.perf_counter()
    from practical_glassing.selection import member_options

    alternatives, pair_pool_size = member_options(viable, pinned, objective is not None)
    options = []
    for members in alternatives:
        cancel()
        if pin_errors or any(p["id"] not in {r["id"] for r in members} for p in pinned):
            continue
        chunks = [paths_by_id[members[0]["id"]]]
        if len(members) == 2:
            a, b = [paths_by_id[r["id"]] for r in members]
            prefix = 0
            while (
                prefix < min(len(a), len(b))
                and a[prefix]["segment"] == b[prefix]["segment"]
                and a[prefix]["coords"] == b[prefix]["coords"]
            ):
                prefix += 1
            transition = reverse(a[prefix:]) + b[prefix:]
            if not transition:
                continue
            chunks.append(transition)
        chunks.append(reverse(paths_by_id[members[-1]["id"]]))
        # These exact candidate legs have already been measured with the same
        # terrain/profile/settings. Only a new between-stop traversal needs work.
        legs = (
            [members[0]["outbound"]]
            + [
                measured(ch, terrain, c["profile"], layers["tree"], layers["shrub"])
                for ch in chunks[1:-1]
            ]
            + [members[-1]["return_leg"]]
        )
        movement = effort.add_metrics(*legs)
        if profiles.failures(movement, c["profile"]):
            continue
        cov, union = coverage(
            [masks[r["id"]] for r in members], layers, target, terrain.res**2
        )
        mode = {
            m: schedule.variant(c["date"], start, legs, c["profile"], c["schedule"], m)
            for m in ("am", "pm")
        }
        if objective:
            for m in ("am", "pm"):
                mode[m]["practical"] = objective.score(
                    [r["id"] for r in members], mode[m], cancel
                )
                score = mode[m]["practical"]
                if score and score["relative_m2"] is None:
                    mode[m]["feasible"] = False
                    mode[m]["reasons"].append(
                        "Insufficient supported community/structure data for practical planning"
                    )
        mode["combined"] = schedule.combined(
            mode["am"], mode["pm"], movement, c["profile"], c["schedule"]
        )
        # Stay at the same observation location all day: one movement budget,
        # separate day clock, no fictitious midday vehicle trip or reset.
        if len(members) == 1:
            am = mode["am"]
            pm = mode["pm"]
            elapsed = (
                __import__("datetime").datetime.fromisoformat(
                    pm["events"][-1]["arrival"]
                )
                - __import__("datetime").datetime.fromisoformat(
                    am["events"][0]["depart"]
                )
            ).total_seconds() / 3600
            reasons = (
                []
                if am["feasible"]
                and pm["feasible"]
                and elapsed <= c["profile"]["max_hours"]
                else [
                    "Stay-put combined day exceeds elapsed limit or one observation window does not fit"
                ]
            )
            mode["stay"] = dict(
                mode="stay",
                feasible=not reasons,
                reasons=reasons,
                movement=movement,
                clock_hours=elapsed,
                events=[am["events"][0]]
                + am["events"][1:-2]
                + [
                    dict(
                        kind="break",
                        start=am["events"][-2]["start"],
                        minutes=max(
                            0, (elapsed - am["clock_hours"] - pm["clock_hours"]) * 60
                        ),
                    )
                ]
                + pm["events"][1:],
                description="One location, one outbound/return; waiting and both observation windows count toward elapsed time.",
            )
        if objective:
            for m in ("combined", "stay"):
                mode[m] = dict(
                    mode=m,
                    feasible=False,
                    reasons=[
                        "Combined/stay days are established-mode-only; practical mode evaluates one AM or PM outing"
                    ],
                    events=[],
                )
        ident = digest([digest(c), [r["id"] for r in members]])[:32]
        contributions = []
        prior = []
        for r in () if objective else members:
            before = (
                coverage(prior, layers, target, terrain.res**2)[0]["effective_m2"]
                if prior
                else 0
            )
            prior.append(masks[r["id"]])
            after = coverage(prior, layers, target, terrain.res**2)[0]["effective_m2"]
            others = [masks[x["id"]] for x in members if x["id"] != r["id"]]
            exclusive = masks[r["id"]] & ~(
                np.logical_or.reduce(others) if others else np.zeros_like(union)
            )
            ex = coverage([exclusive], layers, target, terrain.res**2)[0]
            contributions.append(
                dict(
                    id=r["id"],
                    inclusion_effective_m2=after - before,
                    final_exclusive_effective_m2=ex["effective_m2"] or 0,
                    added_roundtrip_hours=movement["hours_high"]
                    - (members[0]["movement"]["hours_high"] if len(prior) > 1 else 0),
                )
            )
        options.append(
            dict(
                id=ident,
                label=" → ".join(r["id"][:6] for r in members),
                movement=movement,
                remaining=profiles.remaining(movement, c["profile"]),
                coverage=cov,
                access_near_motor_fraction=float(
                    (union & target & near_mask).sum() / max(1, (union & target).sum())
                ),
                legs=legs,
                viewpoints=[
                    {
                        k: v
                        for k, v in r.items()
                        if k not in ("outbound", "return_leg", "movement")
                    }
                    for r in members
                ],
                contributions=contributions,
                schedules=mode,
                coverage_url=f"/artifacts/{folder.name}/coverage-{ident}.png",
                reasons=[],
                _mask=None if objective else union,
            )
        )
    # Pareto frontier uses comparable supported E, movement and off-trail only.
    frontier = []
    for o in [] if objective else options:
        dominated = any(
            (
                b["coverage"]["effective_m2"] >= o["coverage"]["effective_m2"]
                and b["movement"]["hours_high"] <= o["movement"]["hours_high"]
                and b["movement"]["ascent_m"] <= o["movement"]["ascent_m"]
                and b["movement"]["offtrail_m"] <= o["movement"]["offtrail_m"]
                and b["access_near_motor_fraction"] <= o["access_near_motor_fraction"]
                and all(
                    not v["feasible"] or b["schedules"].get(mode, {}).get("feasible")
                    for mode, v in o["schedules"].items()
                )
                and (
                    b["coverage"]["effective_m2"] > o["coverage"]["effective_m2"] + 1
                    or b["movement"]["hours_high"] < o["movement"]["hours_high"] - 0.001
                )
            )
            for b in options
            if b is not o
        )
        o["dominated"] = dominated
        if not dominated:
            frontier.append(o)
    frontier.sort(key=lambda o: -(o["coverage"]["effective_m2"] or 0))
    recommended = {}
    for m in ("am", "pm", "combined", "stay"):
        feasible = [o for o in frontier if o["schedules"].get(m, {}).get("feasible")]
        if feasible:
            best = max(o["coverage"]["effective_m2"] for o in feasible)
            near = [o for o in feasible if o["coverage"]["effective_m2"] >= best * 0.90]
            least_time = min(o["movement"]["hours_high"] for o in near)
            similarly_easy = [
                o for o in near if o["movement"]["hours_high"] <= least_time + 0.05
            ]
            recommended[m] = min(
                similarly_easy,
                key=lambda o: (
                    len(o["viewpoints"]),
                    -(o["coverage"]["effective_m2"] or 0),
                    o["movement"]["ascent_m"],
                ),
            )["id"]
    if objective:
        from practical_glassing.selection import select_options

        frontier, recommended = select_options(options, cancel)
    retained = []
    retained_ids = set()
    preferred = [o for o in frontier if o["id"] in recommended.values()]
    for o in preferred + frontier:
        if o["id"] in retained_ids:
            continue
        if not objective and o["id"] not in recommended.values():
            similar = False
            for prior in retained:
                common = (o["_mask"] & prior["_mask"] & target).sum()
                union_count = ((o["_mask"] | prior["_mask"]) & target).sum()
                same_views = len(o["viewpoints"]) == len(prior["viewpoints"])
                if (
                    common / max(1, union_count) > 0.88
                    and abs(
                        o["movement"]["hours_high"] - prior["movement"]["hours_high"]
                    )
                    < 0.10
                    and abs(o["movement"]["ascent_m"] - prior["movement"]["ascent_m"])
                    < 25
                    and same_views
                ):
                    similar = True
                    break
            if similar:
                continue
        if len(retained) >= 6:
            continue
        retained.append(o)
        retained_ids.add(o["id"])
    if not objective:
        retained.sort(key=lambda o: -(o["coverage"]["effective_m2"] or 0))
    selection_seconds = time.perf_counter() - selection_begin
    if objective:
        from practical_glassing.inspection import finalists

        inspection_begin = time.perf_counter()
        finalists(retained, objective, terrain, layers, paths, cancel, folder)
        inspection_seconds = time.perf_counter() - inspection_begin
    corners = render.relief(terrain, folder / "relief.png")
    for o in retained:
        if objective:
            o["_mask"] = np.logical_or.reduce([masks[r["id"]] for r in o["viewpoints"]])
        render.coverage_image(
            terrain, o.pop("_mask"), layers, target, folder / f"coverage-{o['id']}.png"
        )
    # Include actual graph/spur geometry, never straight-line waypoint connectors.
    lines = []
    for o in retained:
        for ch in [paths_by_id[r["id"]] for r in o["viewpoints"]]:
            for segment in ch:
                if segment["offtrail"]:
                    lines.append(
                        feature(
                            LineString(segment["coords"]),
                            kind="offtrail",
                            option=o["id"],
                        )
                    )
    # Large raw profiles remain useful in drill-down but the full candidate table
    # needs only out/return totals. Options retain complete profiles.
    for r in candidates:
        for k in ("outbound", "return_leg"):
            if k in r:
                r[k] = {
                    a: b for a, b in r[k].items() if a not in ("profile", "geometry")
                }
    pack.recheck()
    result = dict(
        version=2 if objective else 1,
        created_utc=now(),
        input_token=digest(c),
        settings=c,
        implementation=impl,
        source_revision=pack.revision,
        source=pack.summary(),
        start=start,
        grid=dict(
            gt=terrain.gt,
            shape=terrain.a.shape,
            epsg=32613,
            resolution_m=10,
            habitat_support_m=40,
            area_m2=terrain.res**2,
            target_revision=target_key,
        ),
        analysis_id=folder.name,
        candidates=candidates,
        options=retained,
        recommended=recommended,
        pin_errors=pin_errors,
        warnings=WARNINGS
        + (
            [
                "Unknown foot-access scenario enabled; candidate travel may lack verified foot permission."
            ]
            if c["explore_unknown"]
            else []
        )
        + (
            [
                "Off-trail travel is unavailable outside mapped USFS ownership support or an explicit owner travel-area scenario."
            ]
            if public is None
            else []
        ),
        search=dict(
            candidate_budget=c["candidate_budget"],
            evaluated=len(candidates),
            supported_viewpoints=len(viable),
            route_departures=len(departures),
            all_evaluated_plan_variants=len(options),
            returned_variants=len(retained),
            corridor_radius_m=c["corridor_m"],
            offtrail_envelope_m=c["search_envelope_m"],
            pair_search_leaders=pair_pool_size if objective else 8,
            pair_search=(
                "All feasible singles and both orders of every pair within proposal cap"
                if objective
                else "Established top-eight pair pool"
            ),
            pair_proposals=pair_pool_size * max(0, pair_pool_size - 1),
            viewshed_cache_hits=hits,
            global_optimum=False,
        ),
        map=dict(
            corners=corners,
            relief_url=f"/artifacts/{folder.name}/relief.png",
            network=collection(network.rows),
            spurs=collection(lines),
            target_boundary=feature(target_domain, kind="target eligibility"),
            travel_domain=feature(domain, kind="travel evidence"),
        ),
        recommendation_method="Best supported among evaluated candidates. Hard constraints first; Pareto coverage/time/ascent/off-trail screen. Among plans with at least 90% of the best supported E for the selected time variant, retain plans within three minutes of the least conservative movement time and prefer fewer stops (more observation time), then supported coverage and ascent. Access exposure remains separate; tiny score differences do not automatically justify climbing.",
        marginal=[
            dict(
                id=o["id"],
                return_included=True,
                hours_high=o["movement"]["hours_high"],
                distance_m=o["movement"]["distance_m"],
                effective_m2=o["coverage"]["effective_m2"],
                ascent_m=o["movement"]["ascent_m"],
                dominated=o.get("dominated", False),
            )
            for o in options
        ],
        performance=dict(total_seconds=time.perf_counter() - begin),
    )
    if objective:
        result["practical_plan"] = dict(
            version="practical-timed-1",
            status=(
                "scored_conditional"
                if retained
                else "no_positive_supported_feasible_plan"
            ),
            package=objective.package.spec["id"],
            settings=c["practical_plan"],
            allocation="Multi-start marginal whole-patch knapsacks and two coordinate sweeps, with independent allocation lower bound; no global guarantee",
            support_bytes=objective.bytes,
            support_cache_hits=objective.hits,
        )
        result["performance"].update(
            support_seconds=objective.seconds,
            plan_selection_seconds=selection_seconds,
            inspection_seconds=inspection_seconds,
        )
        result["recommendation_method"] = (
            "practical-easier-1: separate AM/PM frontiers; at least 90% of the best practical utility, within three minutes of the least conservative movement time; prefer fewer stops, then utility and ascent. Best among evaluated connected alternatives only."
        )
        result["marginal"] = [
            dict(
                id=o["id"],
                viewpoint_ids=[r["id"] for r in o["viewpoints"]],
                hours_high=o["movement"]["hours_high"],
                ascent_m=o["movement"]["ascent_m"],
                effective_m2=o["coverage"]["effective_m2"],
                movement=o["movement"],
                modes={m: o["schedules"][m].get("practical") for m in ("am", "pm")},
            )
            for o in options
        ]
    if not retained:
        result["empty_reason"] = "No feasible evaluated plan. " + (
            "Pinned point constraints cannot be met; see pinned explanations."
            if pin_errors
            else "Review candidate rejection reasons, start, access scenario or limits. This bounded search does not prove every possible route impossible."
        )
    if c["practical"] is not None:
        from practical_glassing.adapters import trail_review

        result["practical"] = trail_review(
            paths,
            pack,
            result,
            terrain,
            layers,
            target,
            masks,
            folder / "practical",
            c["practical"],
            progress,
            cancel,
        )
        result["performance"]["total_seconds"] = time.perf_counter() - begin
    result["performance"]["total_seconds"] = time.perf_counter() - begin
    if route_basis is not None:
        from practical_glassing import replan

        replan.store(route_basis, result, options, paths_by_id, folder)
    atomic(folder / "result.json", result)
    return result
