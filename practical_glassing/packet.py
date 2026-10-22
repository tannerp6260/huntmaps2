"""Offline, inspectable comparison maps and an interactive self-contained index."""

import html as escaping
import json
import math

import numpy as np
from osgeo import gdal
from PIL import Image, ImageDraw

from . import model
from trail_scout.storage import atomic, seal, checked, file_hash, read, verify

COLORS = np.array(
    [
        [145, 145, 145],
        [230, 191, 73],
        [139, 158, 63],
        [44, 101, 70],
        [174, 110, 62],
        [165, 173, 99],
        [180, 211, 145],
        [80, 90, 110],
    ],
    dtype=np.uint8,
)


def maps(folder, dem, layers, matching, report, store, unions):
    z = dem.ReadAsArray().astype(float)
    gy, gx = np.gradient(z)
    shade = np.clip(175 - gx * 3 + gy * 3, 65, 225).astype(np.uint8)
    background = np.repeat(shade[:, :, None], 3, axis=2)
    gt = dem.GetGeoTransform()
    shape = matching.shape
    point_rows = {r["id"]: r for r in report["rows"]}

    def save(name, rgb, ids=()):
        rgb = np.where(matching[:, :, None], rgb, background // 2)
        im = Image.fromarray(rgb.astype(np.uint8))
        draw = ImageDraw.Draw(im)
        for ident in ids:
            p = point_rows[ident]
            x = (p["x"] - gt[0]) / gt[1]
            y = (p["y"] - gt[3]) / gt[5]
            draw.ellipse(
                (x - 5, y - 5, x + 5, y + 5), fill="white", outline="black", width=2
            )
            draw.text(
                (x + 7, y - 7),
                ident[:12],
                fill="white",
                stroke_width=1,
                stroke_fill="black",
            )
        draw.text(
            (10, 10),
            "N ^   10 m terrain; 30/40 m habitat support",
            fill="white",
            stroke_width=1,
            stroke_fill="black",
        )
        draw.line(
            (10, shape[0] - 20, 10 + 500 / gt[1], shape[0] - 20), fill="white", width=3
        )
        draw.text(
            (10, shape[0] - 38),
            "500 m",
            fill="white",
            stroke_width=1,
            stroke_fill="black",
        )
        im.save(folder / name)

    save(
        "community.png",
        COLORS[layers["group"]],
        report["collections"]["combined"]["ids"],
    )
    h = np.nan_to_num(layers["h"])
    hrgb = np.stack((240 * (1 - h), 180 * h + 40, 60 + 30 * h), axis=-1)
    save("habitat.png", hrgb, report["collections"]["combined"]["ids"])
    save(
        "unknown.png",
        np.where(layers["known"][:, :, None], background, np.array([255, 150, 30])),
    )
    for arm, union in unions.items():
        mask = union.reshape(shape)
        save(
            "union-" + arm + ".png",
            np.where(mask[:, :, None], np.array([66, 190, 230]), background),
            report["collections"][arm]["ids"],
        )
    finalists = set()
    finalists.update(
        i
        for i in ("R0080", "R0003", "C0095", "C0064", "C0068", "C0049")
        if i in point_rows
    )
    for arm in report["arms"]:
        finalists.update(report["collections"][arm]["ids"])
        finalists.update(report["orders"][arm][:3])
    if report["rows"]:
        rank0 = {i: k for k, i in enumerate(report["orders"]["fall_mixed_v1"])}
        rank1 = {i: k for k, i in enumerate(report["orders"]["combined"])}
        differences = sorted(point_rows, key=lambda i: rank0[i] - rank1[i])
        finalists.update(differences[:2] + differences[-2:])
    from trail_scout.storage import digest

    for ident in sorted(finalists):
        v = store.get(ident, "combined")
        mask = np.zeros(matching.size, bool)
        mask[v.indices] = True
        q = np.zeros(matching.size)
        q[v.indices] = v.values
        rgb = np.where(
            mask.reshape(shape)[:, :, None], np.array([100, 155, 210]), background
        )
        rgb = np.where(
            (q.reshape(shape) > 0)[:, :, None], np.array([40, 215, 100]), rgb
        )
        rgb = np.where(
            (mask.reshape(shape) & ~layers["known"])[:, :, None],
            np.array([255, 150, 30]),
            rgb,
        )
        name = "view-" + digest(ident)[:16] + ".png"
        save(name, rgb, [ident])
        point_rows[ident]["map"] = name
    # Analytical export retains raw class and strict unknown mask, not RGB classes.
    dst = folder / "community-context.tif"
    ds = gdal.GetDriverByName("GTiff").Create(
        str(dst),
        dem.RasterXSize,
        dem.RasterYSize,
        6,
        gdal.GDT_Float32,
        options=["TILED=YES", "COMPRESS=DEFLATE"],
    )
    ds.SetGeoTransform(gt)
    ds.SetProjection(dem.GetProjection())
    for i, (a, label) in enumerate(
        (
            (layers["evt"], "LF2025 EVT code; nearest 30 m support"),
            (
                np.where(layers["known"], layers["h"], -9999),
                "relative habitat index; planning assumption",
            ),
            (layers["known"], "habitat supported = 1; unknown = 0"),
            (
                layers["evc"],
                "LF2025 EVC encoded dominant-lifeform cover; use pinned legend",
            ),
            (
                layers["evh"],
                "LF2025 EVH encoded dominant-lifeform height; use pinned legend",
            ),
            (
                layers["short_aspen"],
                "short-canopy aspen proxy; age and stem density unknown",
            ),
        ),
        1,
    ):
        band = ds.GetRasterBand(i)
        band.WriteArray(a)
        band.SetDescription(label)
        band.SetNoDataValue(-9999)
    ds = None


def html(folder, report):
    data = json.dumps(report, allow_nan=False).replace("<", "\\u003c")
    legend = " ".join(
        f'<span style="border-left:14px solid rgb{tuple(int(x) for x in color)};padding-left:4px">{escaping.escape(name.replace("_"," "))}</span>'
        for name, color in zip(model.GROUPS, COLORS)
    )
    content = r"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Practical glassing comparison</title>
<style>body{font:16px system-ui;margin:24px auto;padding:0 20px;max-width:1250px;background:#f3f1e9;color:#20372e}h1{font-size:28px}select{font:inherit;padding:8px;margin:8px}img{width:100%;max-height:700px;object-fit:contain;background:#27322d}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:8px;border-bottom:1px solid #b7c5bb}button{font:inherit;cursor:pointer}small{display:block;margin:12px 0}#detail{white-space:pre-wrap;background:white;padding:16px;border-radius:8px}.legend{display:flex;flex-wrap:wrap;gap:12px;font-size:13px}</style>
<h1>Practical glassing · experimental desktop review</h1><p>Compare the same exact positions and terrain masks. The static shortlist is not a daily route. Foreground, intervening vegetation and target-side access remain unverified. Relative-index m² are not literal acres searched or deer probabilities.</p>
<p><a href="comparison.json" download>Full evidence JSON</a> · <a href="points.csv" download>Coordinates and scores CSV</a> · <a href="shortlist.gpx" download>Provisional static waypoints GPX</a> · <a href="community-context.tif">GIS class/support raster</a></p>
<label>Compare model <select id="arm"></select></label><label>Map <select id="layer"><option value="community.png">Community classes</option><option value="habitat.png">Habitat assumption</option><option value="unknown.png">Habitat unknown</option><option value="union">Unique terrain coverage</option><option value="point">Combined support · selected point</option></select></label>
<div class="legend" id="legend">LEGEND</div><p id="summary"></p><img id="map" alt="Actual projected candidate and coverage map"><small>Blue: visible matching terrain. Green on point maps: selected search patches with supported value. Orange: habitat unknown. Foreground is uninspected throughout. Grey outside the target domain still obstructs terrain sightlines.</small>
<div id="detail">Select a point to inspect its coordinates, distance bands and scan sectors.</div><details><summary>Raw classes, assumptions and approach evidence</summary><pre id="raw" style="max-height:400px;overflow:auto;white-space:pre-wrap"></pre></details><h2>Canonical candidate order</h2><table><thead><tr><th>Rank / point</th><th>Relative-index m²</th><th>Mapped support</th><th>Status</th></tr></thead><tbody id="rows"></tbody></table>
<script>const data=DATA;const byId=Object.fromEntries(data.rows.map(r=>[r.id,r]));const arm=document.getElementById('arm'),layer=document.getElementById('layer');for(const a of data.arms){let o=document.createElement('option');o.value=a;o.textContent=a.replaceAll('_',' ');arm.append(o)}arm.value='combined';let inspected=null;function inspect(r){inspected=r;if(r.map){document.getElementById('map').src=r.map;layer.value='point';document.getElementById('legend').style.display='none';}const groups=Object.entries(r.community_m2).filter(([name])=>!['unsupported','nonhabitat'].includes(name)).sort((a,b)=>b[1]-a[1]).slice(0,3);const scans=r.scan.patches.map((p,i)=>(i+1)+'. '+p.azimuth_start+'–'+p.azimuth_end+'° grid bearing, '+p.inner_m+'–'+p.outer_m+' m');const member=data.collections[arm.value].members.find(p=>p.id===r.id);document.getElementById('detail').textContent=r.id+' · '+r.latitude.toFixed(6)+', '+r.longitude.toFixed(6)+'\nMapped habitat: '+groups.map(([n,a])=>n.replaceAll('_',' ')+' ('+Math.round(a/10000)+' ha visible)').join(', ')+'\nMapped support: '+(r.support_fraction===null?'Unknown':Math.round(r.support_fraction*100)+'%')+'; '+Math.round(r.habitat_unknown_m2/10000)+' ha habitat unknown. Foreground and intervening vegetation remain uninspected.\n'+(r.movement?'Individual approach including return: '+(r.movement.distance_m/1609.344).toFixed(2)+' mi, '+Math.round(r.movement.ascent_m/.3048)+' ft gain, '+r.movement.hours_low.toFixed(1)+'–'+r.movement.hours_high.toFixed(1)+' h travel. Parking/permission conditional.':'Approach/return unavailable for this saved-pool static comparison.')+'\nDistance bands: '+r.bands.filter(b=>b.physical_m2>0).map(b=>b.from_m+'–'+b.to_m+' m: '+Math.round(b.physical_m2/10000)+' ha visible').join('; ')+'\nScan sectors (approximate order):\n'+(scans.join('\n')||'None selected')+'\n'+r.scan.minutes_used+' assumed scan minutes; uncalibrated search rate.\n'+(member?'Increment to this static collection: '+Math.round(member.incremental_relative_m2).toLocaleString()+' relative-index m².':'Not selected in the current static collection.')+'\nTarget hunt permission, stalk and retrieval remain unknown.';document.getElementById('raw').textContent=JSON.stringify({route_effort:r.movement||"Unavailable for saved-pool static comparison",access_evidence:r.access||"Unknown",distance_bands:r.bands,scan_order:r.scan.patches,raw_classes:Object.entries(r.raw_class_m2||{}).map(([code,area_m2])=>({code,area_m2,...data.class_traits[code]})),bounds:r.bounds},null,2)}function update(){const a=arm.value,c=data.collections[a];document.getElementById('legend').style.display=layer.value==='community.png'?'flex':'none';document.getElementById('map').src=layer.value==='union'?'union-'+a+'.png':layer.value==='point'?(inspected?.map||'community.png'):layer.value;document.getElementById('summary').textContent='Static shortlist: '+(c.ids.map(i=>i.slice(0,12)).join(', ')||'No positive supported collection')+' · '+(c.relative_m2===null?'Unknown':Math.round(c.relative_m2).toLocaleString())+' relative-index m². '+Math.round(c.habitat_unknown_m2).toLocaleString()+' m² habitat unknown. Same collection under v1: '+Math.round(c.common_policies.fall_mixed_v1).toLocaleString()+'.';let body=document.getElementById('rows');body.replaceChildren();data.orders[a].forEach((id,i)=>{let r=byId[id],tr=document.createElement('tr');let td=document.createElement('td'),b=document.createElement('button');b.textContent=(i+1)+'. '+id;b.onclick=()=>inspect(r);td.append(b);tr.append(td);for(const text of [r.scores[a]===null?'Unknown':Math.round(r.scores[a]).toLocaleString(),r.support_fraction===null?'Unknown':Math.round(r.support_fraction*100)+'%',r.eligible===false?'Excluded by existing filters':r.status==='insufficient_data'?'Insufficient habitat support':'Conditional; foreground uninspected']){let cell=document.createElement('td');cell.textContent=text;tr.append(cell)}body.append(tr)})}arm.onchange=update;layer.onchange=update;update();</script></html>"""
    content = content.replace("LEGEND", legend).replace("DATA", data)
    (folder / "review.html").write_text(content)


def publish(folder, report):
    atomic(folder / "comparison.json", report)
    seal(folder / "comparison.json")
    html(folder, report)
    from xml.etree import ElementTree as ET

    root = ET.Element(
        "gpx",
        version="1.1",
        creator="HuntMaps2 experimental static review",
        xmlns="http://www.topografix.com/GPX/1/1",
    )
    rows = {r["id"]: r for r in report["rows"]}
    for ident in report["collections"]["combined"]["ids"]:
        row = rows[ident]
        point = ET.SubElement(
            root, "wpt", lat=repr(row["latitude"]), lon=repr(row["longitude"])
        )
        ET.SubElement(point, "name").text = ident
        ET.SubElement(point, "desc").text = (
            "Provisional static opportunity; unverified foreground, access, target permission and retrieval. No combined daily route. Model "
            + report["version"]
            + "; package "
            + report["package"]
        )
    (folder / "shortlist.gpx").write_bytes(
        ET.tostring(root, encoding="utf-8", xml_declaration=True)
    )
    records = {
        p.name: file_hash(p)
        for p in folder.iterdir()
        if p.is_file()
        and (
            p.suffix in (".png", ".html", ".tif", ".csv", ".gpx")
            or p.name == "comparison.json"
        )
    }
    atomic(folder / "packet-seal.json", records)
    seal(folder / "packet-seal.json")


def artifact(folder, name):
    records = read(checked(folder / "packet-seal.json"))
    if name not in records:
        raise ValueError("Artifact missing from complete review packet")
    path = folder / name
    verify(path, records[name])
    return path
