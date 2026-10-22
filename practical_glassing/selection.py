"""Separate schedule-specific practical frontiers; effort stays outside habitat utility."""


def select_options(options, cancel=lambda: None):
    frontiers, recommended = {}, {}
    for mode in ("am", "pm"):
        eligible = [
            o
            for o in options
            if o["schedules"][mode]["feasible"]
            and o["schedules"][mode].get("practical", {}).get("relative_m2") is not None
            and o["schedules"][mode]["practical"]["relative_m2"] > 0
        ]

        def score(o):
            return o["schedules"][mode]["practical"]["relative_m2"]

        frontier = []
        for o in eligible:
            cancel()
            dominated = any(
                score(b) >= score(o)
                and all(
                    b["movement"][k] <= o["movement"][k]
                    for k in ("hours_high", "ascent_m", "offtrail_m")
                )
                and (
                    score(b) > score(o) + 1
                    or b["movement"]["hours_high"] < o["movement"]["hours_high"] - 0.001
                )
                for b in eligible
                if b is not o
            )
            o.setdefault("practical_dominated", {})[mode] = dominated
            if not dominated:
                frontier.append(o)
        frontier.sort(key=lambda o: (-score(o), o["id"]))
        frontiers[mode] = frontier
        if frontier:
            near = [o for o in frontier if score(o) >= score(frontier[0]) * 0.90]
            least = min(o["movement"]["hours_high"] for o in near)
            easy = [o for o in near if o["movement"]["hours_high"] <= least + 0.05]
            recommended[mode] = min(
                easy,
                key=lambda o: (
                    len(o["viewpoints"]),
                    -score(o),
                    o["movement"]["ascent_m"],
                    o["id"],
                ),
            )["id"]
    # Round-robin best alternatives retains each time variant's own leaders.
    union, seen = [], set()
    for rank in range(max((len(f) for f in frontiers.values()), default=0)):
        for mode in ("am", "pm"):
            if rank < len(frontiers[mode]):
                o = frontiers[mode][rank]
                if o["id"] not in seen:
                    union.append(o)
                    seen.add(o["id"])
    return union, recommended


def member_options(viable, pinned, practical=False):
    """Bounded by the upstream 80-proposal cap, never old-score-screen practical pairs."""
    import itertools

    pool = (
        viable
        if practical
        else viable[:8] + [r for r in pinned if r["feasible"] and r not in viable[:8]]
    )
    return [(r,) for r in viable] + list(itertools.permutations(pool, 2)), len(pool)
