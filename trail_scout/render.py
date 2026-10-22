"""Local offline relief/coverage images and geometry-following field exports."""

from datetime import datetime
import html
import io
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from osgeo import gdal
from PIL import Image
from .sources import feature, collection
from .storage import atomic


def image_overlay(terrain, rgba, path):
    ds = gdal.GetDriverByName("MEM").Create(
        "", terrain.a.shape[1], terrain.a.shape[0], 4, gdal.GDT_Byte
    )
    ds.SetGeoTransform(terrain.gt)
    ds.SetProjection(terrain.ds.GetProjection())
    for b in range(4):
        ds.GetRasterBand(b + 1).WriteArray(rgba[:, :, b])
        ds.GetRasterBand(b + 1).SetColorInterpretation(
            (
                gdal.GCI_RedBand,
                gdal.GCI_GreenBand,
                gdal.GCI_BlueBand,
                gdal.GCI_AlphaBand,
            )[b]
        )
    warped = gdal.Warp(
        "",
        ds,
        format="MEM",
        dstSRS="EPSG:3857",
        width=min(1200, rgba.shape[1]),
        resampleAlg="near",
    )
    gt = warped.GetGeoTransform()
    from pyproj import Transformer

    t = Transformer.from_crs(3857, 4326, always_xy=True)
    x, y = gt[0], gt[3]
    X = x + warped.RasterXSize * gt[1]
    Y = y + warped.RasterYSize * gt[5]
    corners = [list(t.transform(*pt)) for pt in ((x, y), (X, y), (X, Y), (x, Y))]
    buffer = io.BytesIO()
    Image.fromarray(np.moveaxis(warped.ReadAsArray(), 0, -1), "RGBA").save(
        buffer, format="PNG"
    )
    atomic(path, buffer.getvalue(), True)
    return corners


def relief(terrain, path):
    dy, dx = np.gradient(terrain.a, terrain.res)
    norm = np.sqrt(dx * dx + dy * dy + 1)
    light = np.clip((-dx * 0.5 + dy * 0.5 + 0.707) / norm, 0, 1)
    z = (terrain.a - np.min(terrain.a)) / max(1, np.ptp(terrain.a))
    rgba = np.empty((*terrain.a.shape, 4), np.uint8)
    for i, (base, high) in enumerate(((105, 215), (125, 209), (105, 183))):
        rgba[:, :, i] = np.clip(
            (base + (high - base) * z) * (0.45 + 0.55 * light), 0, 255
        )
    rgba[:, :, 3] = 255
    return image_overlay(terrain, rgba, path)


def coverage_image(terrain, mask, layers, target, path):
    rgba = np.zeros((*mask.shape, 4), np.uint8)
    rgba[mask & target & layers["known"]] = [44, 182, 148, 145]
    rgba[mask & target & ~layers["known"]] = [235, 165, 48, 165]
    rgba[mask & ~target] = [160, 160, 160, 90]
    return image_overlay(terrain, rgba, path)


def geojson(plan):
    option = plan["option"]
    features = []
    for i, leg in enumerate(option["legs"] * (2 if plan["mode"] == "combined" else 1)):
        features.append(
            dict(
                type="Feature",
                geometry=leg["geometry"],
                properties=dict(
                    kind="itinerary",
                    leg=i % len(option["legs"]),
                    outing=i // len(option["legs"]) + 1,
                    role=(
                        "outbound"
                        if i % len(option["legs"]) == 0
                        else (
                            "return"
                            if i % len(option["legs"]) == len(option["legs"]) - 1
                            else "transition"
                        )
                    ),
                    distance_m=leg["distance_m"],
                    ascent_m=leg["ascent_m"],
                    hours_high=leg["hours_high"],
                ),
            )
        )
    for point in option["viewpoints"]:
        features.append(
            dict(
                type="Feature",
                geometry=dict(
                    type="Point", coordinates=[point["longitude"], point["latitude"]]
                ),
                properties={
                    k: v for k, v in point.items() if k not in ("coverage", "geometry")
                },
            )
        )
    if option["schedules"][plan["mode"]].get("practical"):
        features.extend(
            option["schedules"][plan["mode"]]["practical"]["sectors"]["features"]
        )
    return dict(
        type="FeatureCollection",
        features=features,
        trail_scout=dict(
            version=1,
            provisional=True,
            plan_id=plan["id"],
            created_utc=plan["created_utc"],
            settings=plan["settings"],
            source_revision=plan["source_revision"],
            implementation=plan["implementation"],
            schedule_mode=plan["mode"],
            units="metres, square metres, decimal hours; coordinates EPSG:4326",
        ),
    )


def gpx(plan):
    ns = "http://www.topografix.com/GPX/1/1"
    ET.register_namespace("", ns)
    root = ET.Element(
        "gpx", xmlns=ns, version="1.1", creator="TrailScout provisional desktop planner"
    )
    metadata = ET.SubElement(root, "metadata")
    ET.SubElement(metadata, "name").text = plan["name"]
    ET.SubElement(metadata, "time").text = plan["created_utc"]
    ET.SubElement(metadata, "desc").text = (
        "Provisional modeled approach; not verified permission/safety. Exact inputs and revisions in companion JSON/GeoJSON."
    )
    for p in plan["option"]["viewpoints"]:
        w = ET.SubElement(root, "wpt", lon=str(p["longitude"]), lat=str(p["latitude"]))
        ET.SubElement(w, "name").text = p["id"]
    track = ET.SubElement(root, "trk")
    ET.SubElement(track, "name").text = plan["name"]
    for leg in plan["option"]["legs"] * (2 if plan["mode"] == "combined" else 1):
        seg = ET.SubElement(track, "trkseg")
        for lon, lat in leg["geometry"]["coordinates"]:
            ET.SubElement(seg, "trkpt", lon=str(lon), lat=str(lat))
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def field_summary(plan):
    o = plan["option"]
    c = o["coverage"]
    schedule = o["schedules"][plan["mode"]]
    m = schedule.get("movement", o["movement"])

    def clock(value):
        return datetime.fromisoformat(value).strftime("%a %H:%M %Z") + " " + value[-6:]

    lines = [
        f"# {plan['name']}",
        f"TrailScout provisional desktop plan · {plan['created_utc']}",
        f"Date: {plan['settings']['date']} · {plan['mode'].upper()} · America/Denver",
        f"Entry: {plan['start']['label']} ({plan['start']['longitude']:.7f}, {plan['start']['latitude']:.7f})",
        plan["start"]["note"],
        f"Hunter: {plan['settings']['profile']['label']} (uncalibrated)",
        f"Every traveled leg: {m['distance_m']/1609.344:.2f} mi; +{m['ascent_m']/0.3048:.0f}/−{m['descent_m']/0.3048:.0f} ft; {m['hours_low']:.2f}–{m['hours_high']:.2f} movement hours; off trail {m['offtrail_m']/1609.344:.2f} mi.",
        f"Unique matching terrain: {c['matching_m2']/4046.8564224:.0f} acres; quality-adjusted equivalents: {(c['effective_m2'] or 0)/4046.8564224:.0f}; unsupported vegetation/context: {c['unknown_m2']/4046.8564224:.0f} acres.",
        "Quality-adjusted area is neither literal acreage searched nor deer/detection probability.",
        f"View radius: {plan['settings']['view_radius_m']} m · 16×50 binoculars / 77 mm scope and tripod assumed; no optical-clearance guarantee.",
        "## Schedule",
    ]
    for event in schedule["events"]:
        if event["kind"] == "observe":
            lines.append(
                f"- Observe stop {event['stop']+1}: {clock(event['start'])}–{clock(event['end'])} ({event['minutes']:.0f} min)"
            )
        elif event["kind"] == "outbound":
            lines.append(
                f"- Depart {clock(event['depart'])}; arrival {clock(event['arrival_range'][0])}–{clock(event['arrival_range'][1])}"
            )
        elif event["kind"] == "return":
            lines.append(
                f"- Return trigger {clock(event['depart'])}; conservative arrival {clock(event['arrival'])}"
            )
        elif event["kind"] == "transition":
            lines.append(
                f"- Walk between stops: {clock(event['depart'])}–{clock(event['arrival'])}"
            )
        else:
            lines.append(f"- Break allowance {event['minutes']:.0f} min")
    lines += ["## Viewpoints"]
    for p in o["viewpoints"]:
        lines.append(
            f"- {p['id']}: {p['longitude']:.8f}, {p['latitude']:.8f}; {p['kind']}; {p['standing_note']}"
        )
    practical = schedule.get("practical")
    if practical:
        lines += [
            "## Experimental practical scans",
            f"{practical['relative_m2']:.1f} relative-index m², conditional on unverified foreground. Not literal acres or probability. Habitat supported {practical['supported_m2']:.0f} m²; unknown {practical['unknown_m2']:.0f} m²; selected-view overlap {practical['overlap_relative_m2']:.1f}.",
        ]
        for i, v in enumerate(practical["visits"]):
            lines.append(
                f"Stop {i+1}: {v['minutes_used']:.2f} useful scan / {v['observation_minutes']:.1f} available minutes; {v['unused_observation_minutes']:.1f} unused/rest. Adds {v['marginal_relative_m2']:.1f}; exclusive improvement {v['exclusive_relative_m2']:.1f} relative-index m²."
            )
            for p in v["patches"]:
                lines.append(
                    f"- Grid bearing {p['azimuth_start']}–{p['azimuth_end']}°, {p['inner_m']}–{p['outer_m']} m: {p['minutes']:.2f} min (full footprint; hidden terrain remains hidden)."
                )
        for item in o.get("inspection", []):
            lines.append(
                f"Foreground {item['id']}: {item['status']}; {item.get('source','no compatible measured input')}. No score adjustment or clear-sightline claim."
            )
    profile = plan["settings"]["profile"]
    lines += [
        f"Nominal limits {profile['max_miles']:.3f} mi / {profile['max_gain_ft']:.1f} ft; {profile['reserve_fraction']*100:.0f}% held reserve; usable {profile['max_miles']*(1-profile['reserve_fraction']):.3f} mi / {profile['max_gain_ft']*(1-profile['reserve_fraction']):.1f} ft."
    ]
    lines += [
        "## Official references",
        "[GMUG conditions and alerts](https://www.fs.usda.gov/r02/gmug) · [CPW big game rules to verify](https://cpw.state.co.us/activities/hunting/big-game)",
        "## Field review",
        *["- " + v for v in plan["warnings"]],
        f"Source revision: {plan['source_revision']}",
        f"Implementation: {plan['implementation']}",
        f"Immutable saved version: {plan['id']} · parent {plan.get('parent_id') or 'none'}",
    ]
    return "\n\n".join(lines) + "\n"
