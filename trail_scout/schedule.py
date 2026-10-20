"""NOAA solar approximation, zoneinfo clocks, conservative logistics."""

import calendar
from datetime import date as Date, datetime, time, timedelta, timezone
import math
from zoneinfo import ZoneInfo

ZONE = "America/Denver"


def solar(day, lat, lon, zone=ZONE):
    """NOAA fractional-year approximation, sea-level apparent horizon.

    https://gml.noaa.gov/grad/solcalc/solareqns.PDF
    Mountain horizon/weather are not represented. Not legal shooting hours.
    """
    d = Date.fromisoformat(day)
    gamma = (
        2
        * math.pi
        / (366 if calendar.isleap(d.year) else 365)
        * (d.timetuple().tm_yday - 1)
    )
    eq = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )
    decl = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma)
        + 0.00148 * math.sin(3 * gamma)
    )
    out = {}
    midnight = datetime.combine(d, time(), timezone.utc)
    for zenith, names in (
        (90.833, ("sunrise", "sunset")),
        (96, ("civil_dawn", "civil_dusk")),
    ):
        c = math.cos(math.radians(zenith)) / (
            math.cos(math.radians(lat)) * math.cos(decl)
        ) - math.tan(math.radians(lat)) * math.tan(decl)
        if not -1 <= c <= 1:
            raise ValueError("Solar window unavailable at this latitude/date")
        ha = math.degrees(math.acos(c))
        for sign, name in ((1, names[0]), (-1, names[1])):
            out[name] = (
                midnight + timedelta(minutes=720 - 4 * (lon + sign * ha) - eq)
            ).astimezone(ZoneInfo(zone))
    return out


def settings(value=None):
    value = value or {}
    defaults = dict(
        am_start_offset=0,
        am_end_offset=180,
        pm_start_offset=-180,
        pm_end_offset=0,
        min_glassing_minutes=60,
        setup_minutes=15,
        break_minutes=20,
        dark_travel=False,
        earliest="04:00",
        latest="21:00",
        vehicle_transition_minutes=0,
    )
    if set(value) - set(defaults):
        raise ValueError("Unknown schedule setting")
    out = dict(defaults, **value)
    for k in defaults:
        if k in ("earliest", "latest"):
            try:
                time.fromisoformat(out[k])
            except (TypeError, ValueError):
                raise ValueError("Use local HH:MM times")
        elif k == "dark_travel":
            if type(out[k]) is not bool:
                raise ValueError("Dark travel must be true/false")
        else:
            n = out[k]
            if (
                type(n) not in (int, float)
                or not math.isfinite(n)
                or not -360 <= n <= 720
            ):
                raise ValueError(
                    "Schedule allowances must be finite minutes within -360–720"
                )
            if k.endswith("minutes") and n < 0:
                raise ValueError("Allowances cannot be negative")
    if out["min_glassing_minutes"] < 15:
        raise ValueError("Minimum worthwhile observation must be at least 15 minutes")
    if (
        out["am_end_offset"] <= out["am_start_offset"]
        or out["pm_end_offset"] <= out["pm_start_offset"]
    ):
        raise ValueError("Observation windows must have positive duration")
    return out


def advance(value, delta):
    """Add actual elapsed time across DST transitions, retaining local offset."""
    return (value.astimezone(timezone.utc) + delta).astimezone(value.tzinfo)


def elapsed(later, earlier):
    return (
        later.astimezone(timezone.utc) - earlier.astimezone(timezone.utc)
    ).total_seconds()


def variant(day, start, legs, p, config, mode):
    """legs: outbound, transitions, return; conservative upper travel bounds."""
    sun = solar(day, start["latitude"], start["longitude"])
    c = settings(config)
    tz = ZoneInfo(ZONE)
    d = Date.fromisoformat(day)
    earliest = datetime.combine(d, time.fromisoformat(c["earliest"]), tz)
    latest = datetime.combine(d, time.fromisoformat(c["latest"]), tz)
    if earliest >= latest:
        raise ValueError(
            "Earliest departure must precede latest return on the same day"
        )
    light_start = earliest if c["dark_travel"] else max(earliest, sun["civil_dawn"])
    light_end = latest if c["dark_travel"] else min(latest, sun["civil_dusk"])
    anchor = sun["sunrise"] if mode == "am" else sun["sunset"]
    window_start = advance(anchor, timedelta(minutes=c[mode + "_start_offset"]))
    window_end = advance(anchor, timedelta(minutes=c[mode + "_end_offset"]))
    outbound = legs[0]
    ret = legs[-1]
    between = legs[1:-1]
    setup = timedelta(minutes=c["setup_minutes"])
    rest = timedelta(minutes=c["break_minutes"])
    depart = max(
        light_start,
        advance(window_start, -timedelta(hours=outbound["hours_high"]) - setup),
    )
    arrival_low = advance(depart, timedelta(hours=outbound["hours_low"]))
    arrival_high = advance(depart, timedelta(hours=outbound["hours_high"]))
    observation_start = max(window_start, advance(arrival_high, setup))
    n = len(legs) - 1
    moving = sum(x["hours_high"] for x in between)
    latest_leave = min(
        window_end, advance(light_end, -timedelta(hours=ret["hours_high"]) - rest)
    )
    available = (
        elapsed(latest_leave, observation_start) / 60
        - moving * 60
        - c["setup_minutes"] * (n - 1)
    )
    reasons = []
    if available < c["min_glassing_minutes"] * n:
        reasons.append(
            f'Conservative arrival/return leaves {max(0,available):.0f} observation minutes; need {c["min_glassing_minutes"]*n:.0f}'
        )
    if depart >= light_end:
        reasons.append("No departure within allowed light/time bounds")
    events = []
    cursor = observation_start
    per = max(0, available) / n
    events.append(
        dict(
            kind="outbound",
            depart=depart.isoformat(),
            arrival_range=[arrival_low.isoformat(), arrival_high.isoformat()],
        )
    )
    for i in range(n):
        end = advance(cursor, timedelta(minutes=per))
        events.append(
            dict(
                kind="observe",
                stop=i,
                start=cursor.isoformat(),
                end=end.isoformat(),
                minutes=per,
            )
        )
        cursor = end
        if i < len(between):
            events.append(
                dict(
                    kind="transition",
                    depart=cursor.isoformat(),
                    arrival=(
                        advance(cursor, timedelta(hours=between[i]["hours_high"]))
                    ).isoformat(),
                )
            )
            cursor = advance(cursor, timedelta(hours=between[i]["hours_high"]) + setup)
    return_depart = advance(latest_leave, rest)
    return_arrival = advance(return_depart, timedelta(hours=ret["hours_high"]))
    events.append(
        dict(kind="break", start=latest_leave.isoformat(), minutes=c["break_minutes"])
    )
    events.append(
        dict(
            kind="return",
            depart=return_depart.isoformat(),
            arrival=return_arrival.isoformat(),
        )
    )
    total_clock = elapsed(return_arrival, depart) / 3600
    if total_clock > p["max_hours"]:
        reasons.append(
            f'Elapsed outing {total_clock:.2f} h exceeds {p["max_hours"]:.2f} h'
        )
    return dict(
        mode=mode,
        feasible=not reasons,
        reasons=reasons,
        events=events,
        latest_leave_viewpoint=latest_leave.isoformat(),
        return_by=light_end.isoformat(),
        clock_hours=total_clock,
        observation_minutes=max(0, available),
        solar={k: v.isoformat() for k, v in sun.items()},
        timezone=ZONE,
        dark_travel=c["dark_travel"],
        assumption="NOAA approximate astronomical horizon; terrain shadows, weather and legal shooting hours are separate.",
    )


def combined(am, pm, movement, p, config):
    c = settings(config)
    reasons = []
    if not am["feasible"] or not pm["feasible"]:
        reasons.append("Both individual schedules must fit first")
    from .profiles import failures

    doubled = {
        k: (
            v * 2
            if k
            in (
                "distance_m",
                "mapped_m",
                "offtrail_m",
                "ascent_m",
                "descent_m",
                "hours_low",
                "hours_high",
                "offtrail_hours_high",
                "sustained_steep_m",
            )
            else v
        )
        for k, v in movement.items()
        if k != "profile"
    }
    reasons.extend(failures(doubled, p))
    gap = (
        datetime.fromisoformat(pm["events"][0]["depart"])
        - datetime.fromisoformat(am["events"][-1]["arrival"])
    ).total_seconds() / 60
    if gap < c["vehicle_transition_minutes"]:
        reasons.append("Morning return and vehicle allowance overlap evening departure")
    first = datetime.fromisoformat(am["events"][0]["depart"])
    last = datetime.fromisoformat(pm["events"][-1]["arrival"])
    elapsed = (last - first).total_seconds() / 3600
    if elapsed > p["max_hours"]:
        reasons.append(
            f'Combined elapsed day {elapsed:.2f} h exceeds {p["max_hours"]:.2f} h; rest does not reset effort'
        )
    return dict(
        mode="combined",
        feasible=not reasons,
        reasons=reasons,
        movement=doubled,
        clock_hours=elapsed,
        vehicle_transition_minutes=c["vehicle_transition_minutes"],
        description="Two complete out-and-back outings to this selected entry; movement counted twice. No unsupported vehicle relocation.",
        events=am["events"] + pm["events"],
    )
