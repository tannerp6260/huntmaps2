"""Editable uncalibrated guardrails; reported capacity is never a target."""

import math

COMMON = dict(
    reserve_fraction=0.25,
    pace_mph=1.5,
    time_margin=1.35,
    max_hours=7.0,
    max_miles=2.5,
    max_gain_ft=750,
    offtrail_miles=0.25,
    offtrail_minutes=35,
    max_offtrail_slope=20,
    max_route_grade=0.30,
    max_steep_m=250,
    steep_grade=0.15,
    max_tree=0.45,
    max_shrub=0.65,
    condition_factor=1.0,
)
PROFILES = {
    "together": dict(
        COMMON,
        label="Together · conservative",
        explanation="Editable shared-party planning defaults: 2.5 miles total walking / 750 ft cumulative gain, with 25% held in reserve. Uncalibrated; the reported Dutton difficulty is not a measured capacity.",
    ),
    "dad": dict(
        COMMON,
        label="Dad · easy pace",
        explanation="Below the reported difficult 3–4 mile/1,000 ft morning at ~10,000 ft; gradual grades and short spurs. This is a starting assumption, not a measured maximum.",
    ),
    "tanner": dict(
        COMMON,
        label="Tanner · moderate",
        max_miles=6.0,
        max_gain_ft=2200,
        max_hours=10.0,
        pace_mph=2.0,
        offtrail_miles=0.75,
        offtrail_minutes=70,
        max_offtrail_slope=25,
        max_route_grade=0.40,
        max_steep_m=800,
        explanation="Below reported 5–8 miles/2,000–3,500 ft comfort; no requirement to spend capacity. Uncalibrated and conditional on terrain, altitude and condition.",
    ),
    "extended": dict(
        COMMON,
        label="Extended family · explicit option",
        max_miles=3.0,
        max_gain_ft=900,
        explanation="Explicit extended shared-party option, 3 miles / 900 ft before 25% reserve. Never selected automatically to make a route fit.",
    ),
}


def validate(value=None):
    value = value or {}
    name = value.get("preset", "together")
    if name not in PROFILES or set(value) - set(COMMON) - {
        "preset",
        "label",
        "explanation",
    }:
        raise ValueError("Unknown hunter profile or setting")
    result = {**PROFILES[name], **value, "preset": name}
    limits = dict(
        reserve_fraction=(0.1, 0.6),
        pace_mph=(0.3, 4),
        time_margin=(1.1, 2.5),
        max_hours=(1, 18),
        max_miles=(0.1, 15),
        max_gain_ft=(50, 8000),
        offtrail_miles=(0, 3),
        offtrail_minutes=(0, 240),
        max_offtrail_slope=(5, 35),
        max_route_grade=(0.05, 0.8),
        max_steep_m=(0, 5000),
        steep_grade=(0.05, 0.5),
        max_tree=(0, 1),
        max_shrub=(0, 1),
        condition_factor=(1, 3),
    )
    for k, (low, high) in limits.items():
        n = result[k]
        if type(n) not in (int, float) or not math.isfinite(n) or not low <= n <= high:
            raise ValueError(f"{k} must be within {low}–{high}")
    return result


def failures(m, p):
    reserve = 1 - p["reserve_fraction"]
    checks = [
        (
            m["distance_m"],
            p["max_miles"] * 1609.344 * reserve,
            "round-trip mileage plus reserve",
        ),
        (
            m["ascent_m"],
            p["max_gain_ft"] * 0.3048 * reserve,
            "cumulative ascent plus reserve",
        ),
        (m["hours_high"], p["max_hours"] * reserve, "movement hours plus reserve"),
        (
            m["offtrail_m"],
            p["offtrail_miles"] * 1609.344 * reserve,
            "off-trail distance plus reserve",
        ),
        (
            m["offtrail_hours_high"] * 60,
            p["offtrail_minutes"] * reserve,
            "off-trail time plus reserve",
        ),
        (m["sustained_steep_m"], p["max_steep_m"], "sustained steep travel"),
        (m["max_sustained_grade"], p["max_route_grade"], "sustained route grade"),
    ]
    return [
        f"Exceeds {label}: {actual:.2f} > {limit:.2f}"
        for actual, limit, label in checks
        if actual > limit + 1e-8
    ]


def remaining(m, p):
    usable = 1 - p["reserve_fraction"]
    return dict(
        usable_distance_m=p["max_miles"] * 1609.344 * usable - m["distance_m"],
        usable_ascent_m=p["max_gain_ft"] * 0.3048 * usable - m["ascent_m"],
        usable_movement_hours=p["max_hours"] * usable - m["hours_high"],
        usable_offtrail_m=p["offtrail_miles"] * 1609.344 * usable - m["offtrail_m"],
        held_distance_m=p["max_miles"] * 1609.344 * p["reserve_fraction"],
        held_ascent_m=p["max_gain_ft"] * 0.3048 * p["reserve_fraction"],
    )
