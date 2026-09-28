"""Readable handoff for the existing, unchanged scoring engine."""
import shutil
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from osgeo import gdal
from shapely.geometry import shape
from .transfer import read,project
from .transfer_packet import draw_lines,extent

def handoff(c,root):
    analysis=Path(c['work']);points=read(analysis/'leading.json');patches=read(analysis/'patches.json');inp=read(analysis/'intake.json');ds=gdal.Open(str(analysis/'dem.tif'))
    fig,ax=plt.subplots(figsize=(10,9));im=ax.imshow(ds.ReadAsArray(),extent=extent(ds),cmap='terrain');fig.colorbar(im,ax=ax,label='Bare-earth elevation (m)')
    draw_lines(ax,shape(inp['geometry']['target']).boundary,color='purple',lw=1)
    draw_lines(ax,shape(inp['geometry']['observer']).boundary,color='cyan',lw=2)
    for n,p in enumerate(points):
        ax.plot(p['x'],p['y'],'ro' if p['group']=='automated' else 'ks',ms=5);ax.annotate((str(n+1)+': ' if p['group']=='automated' else '')+p.get('original_id',p['id']),(p['x'],p['y']),xytext=(5,5),textcoords='offset points',fontsize=8)
    ax.set_title(c['input_kind'].upper()+' — provisional observer opportunities\nCyan: observer-search area | purple: target support\nPositions and targets do not imply legal access')
    ax.set_aspect('equal');ax.ticklabel_format(style='plain',useOffset=False);ax.set_xlabel(f'Easting, EPSG:{c["epsg"]}');ax.set_ylabel('Northing (m)');fig.tight_layout();fig.savefig(root/'overview.png',dpi=160);plt.close(fig)
    for name in ['review.gpx','sectors.kml','comparison.gpkg','review_packet.pdf','components.csv','overlap.csv','export_checks.json']:
        shutil.copy2(analysis/name,root/name)
    lines=['# Provisional scouting results','',f'Input: **{c["input_kind"]}**. Observer positions were searched inside your polygon. Target terrain extends up to {c["radius_m"]} m beyond positions; it is not a hunting-permission boundary.','', 'Open **overview.png** first, then **review_packet.pdf** for selected sectors, 500 m distance bands, foreground proxies and individual terrain/imagery cards. GPX contains provisional positions; KML contains inspection footprints, including hidden terrain. **comparison.gpkg** contains distinct observer/target/terrain/access domains for QGIS.','', 'Automated alternatives are ordered by the inherited selective-attention hypothesis. Raw terrain area and cover summaries remain separate in components.csv. Scores are relative model outputs, never deer probabilities. No detection or legal-access claim is made.','', '| Position | Latitude, longitude | Visible km² | Within 1 km | Low-tree-cover km² | Selective score |','|---|---|---:|---:|---:|---:|']
    to_ll=project(c['epsg'],4326)
    for p in points:
        lo,la=to_ll(p['x'],p['y']);lines.append(f'| {p.get("original_id",p["id"])} ({p["group"]}) | {la:.6f}, {lo:.6f} | {p["raw_km2"]:.3f} | {p["within_1km_km2"]:.3f} | {p["low_tree_cover_km2"]:.3f} | {p["selective_score"]:.5f} |')
    for p in points:
        chosen=patches[p['id']]
        sectors='; '.join(f"{t['azimuth_start']}–{t['azimuth_end']}° / {t['inner_m']}–{t['outer_m']} m" for t in chosen['patches'] if t['id'] in chosen['selection']['patch_ids'])
        lines.extend(['',f'**{p.get("original_id",p["id"])}**: '+('Included among the highest selective-attention alternatives: coherent inspection patches fit the common time budget.' if p['group']=='automated' else 'Your imported selection, retained unchanged regardless of score.')+f' Visible terrain {p["raw_km2"]:.3f} km²; low tree fraction proxy {p["low_tree_cover_km2"]:.3f} km². Foreground cover proxy {p["foreground_cover_mean"]}; this does not establish ground-level sightlines. Selected sectors (bearings clockwise from north): '+sectors+'.'])
    lines.extend(['','**Unresolved:** access/parking/physical approach require documented evidence; absent sources mean pending, not inaccessible. Canopy fraction is not optical transmittance. Apparent open terrain may be obstructed. Seasonal use and light remain inherited hypotheses; light angles are not a dated sun forecast. Imagery is displayed only when a checked raster is supplied; otherwise cards say IMAGERY PENDING. No labeled review is blinded validation.','',f'Common effort: {c["observation_minutes"]} minutes; eye {c["eye_m"]} m; target {c["target_m"]} m above bare earth. Editable hiking preferences: {c["hiking_preferences"]}. No route or itinerary is generated.','', 'Optional manual comparison: see overlap.csv and analysis/comparison_review.json. Agreement is not independent proof of hunting value. Local refinement is a density diagnostic and does not replace the original candidate pool.','', 'Sources/configuration: scouting.json, acquisition.json, download_plan.json, originals/. Runtime/peak memory: analysis/execution.jsonl. Integrity: manifest.json; run ./scout verify --name '+root.name+'.'])
    (root/'REPORT.md').write_text('\n'.join(lines)+'\n')
