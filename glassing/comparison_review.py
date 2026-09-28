"""Inspectable comparison outputs and blank blinded review packets."""
import json
import math
import os
from pathlib import Path
import numpy as np
from osgeo import ogr,osr,gdal
from .acquire import dump,srs,digest


def review(c):
    from .compare import load,read_layers,identity,write_csv
    b,base,ds,a,gt,masks=load(c);layers=read_layers(c);root=Path(c['work'])
    if json.loads((root/'run_identity.json').read_text())!=identity(c):raise ValueError('Comparison run stale')
    points=json.loads((root/'pool.json').read_text());point_map={p['id']:p for p in points}
    rows=json.loads((root/'component_scores.json').read_text());score_maps={arm:{r['id']:r for r in rows if r['scenario']==arm and r['id'] in point_map} for arm in ['M1_raw','M2_habitat','M3_glass']}
    random=json.loads((root/'random_baseline.json').read_text());chosen=[];seen=set()
    for arm in score_maps:
        for i in sorted(score_maps[arm],key=lambda i:(-score_maps[arm][i]['score'],i)):
            if i not in seen:chosen.append(dict(id=i,role=arm));seen.add(i);break
    for i in random['first_draw']:
        if i not in seen:chosen.append(dict(id=i,role='stratified_random'));seen.add(i);break
    # A fifth alternative selected for rank stability, not greater predicted benefit.
    all_rows={}
    for row in rows:
        if row['id'] in point_map and 'rank_common_pool' in row:all_rows.setdefault(row['id'],[]).append(row['rank_common_pool'])
    for i in sorted(all_rows,key=lambda i:(np.median(all_rows[i]),i)):
        if i not in seen:chosen.append(dict(id=i,role='median_rank_across_predeclared_scenarios'));break
    transform=osr.CoordinateTransformation(srs(b['epsg']),srs(4326))
    alternatives=[]
    for ch in chosen:
        p=point_map[ch['id']];lon,lat,_=transform.TransformPoint(p['x'],p['y'])
        row=dict(ch,x=p['x'],y=p['y'],longitude=lon,latitude=lat,access='UNKNOWN unless supplied verified route evidence',observation_minutes=c['observation_minutes'],
                 rationale='Top distinct candidate for '+ch['role']+'; scenario comparison, not a field recommendation',
                 provenance=';'.join(p['provenance']),eye_m=b['eye_m'],target_m=b['target_m'],radius_m=b['baseline_radius_m'])
        for arm in score_maps:
            row[arm]=score_maps[arm][p['id']]['score']
            row[arm+'_rank']=score_maps[arm][p['id']]['rank_common_pool']
            row[arm+'_equal_effort']=score_maps[arm][p['id']]['equal_effort_score']
        detail=score_maps['M3_glass'][p['id']]
        for component in ['habitat_mean','searchability_mean','distance_mean','perspective_mean','light_mean','inspection_fraction','unknown_vegetation_fraction']:row[component]=detail[component]
        row['rationale']+='; M1/M2 often nominate the same winner, so the next distinct M2 position is shown. See explicit arm ranks.'
        row['limitations']=score_maps['M3_glass'][p['id']]['flags'];alternatives.append(row)
    dump(root/'field_ready_shortlist.json',dict(candidates=[],reason='Comparison alternatives require independent geometry/setup and connected-access review; no field-ready recommendation'))
    dump(root/'alternatives.json',alternatives);write_csv(root/'alternatives.csv',alternatives)
    gpkg=root/'comparison.gpkg'
    if gpkg.exists():gpkg.unlink()
    out=ogr.GetDriverByName('GPKG').CreateDataSource(str(gpkg));layer=out.CreateLayer('common_candidates_UNKNOWN_ACCESS',srs=srs(b['epsg']),geom_type=ogr.wkbPoint)
    fields=['id','access','provenance','M1_raw','M2_habitat','M3_glass']
    for f in fields:layer.CreateField(ogr.FieldDefn(f,ogr.OFTReal if f.startswith('M') else ogr.OFTString))
    for p in points:
        feat=ogr.Feature(layer.GetLayerDefn());feat.SetField('id',p['id']);feat.SetField('access',score_maps['M3_glass'][p['id']]['reachable_status']);feat.SetField('provenance',';'.join(p['provenance']))
        for arm in score_maps:feat.SetField(arm,score_maps[arm][p['id']]['score'])
        geom=ogr.Geometry(ogr.wkbPoint);geom.AddPoint_2D(p['x'],p['y']);feat.SetGeometry(geom);layer.CreateFeature(feat)
    out=None
    read=ogr.Open(str(gpkg));layer=read.GetLayer(0)
    assert layer.GetFeatureCount()==len(points) and layer.GetSpatialRef().IsSame(srs(b['epsg']))
    for f in layer:
        p=point_map[f.GetField('id')];geom=f.GetGeometryRef();assert math.hypot(p['x']-geom.GetX(),p['y']-geom.GetY())<1e-6
    dump(root/'export_checks.json',dict(passed=True,candidates=len(points),epsg=b['epsg']))
    # Reviewer-visible sheet contains neither model rank nor model score.
    nominees=set(random['first_draw'][:3])
    for arm in score_maps:nominees.update(sorted(score_maps[arm],key=lambda i:(-score_maps[arm][i]['score'],i))[:3])
    rng=np.random.default_rng(c['seed']+19);ids=list(rng.permutation(sorted(nominees)))
    packets=[];key=[];targets=[]
    study=json.loads((base/'study.json').read_text());geom=ogr.CreateGeometryFromJson(json.dumps(study['geometry']));mid=geom.Centroid().GetY()
    for n,i in enumerate(ids,1):
        p=point_map[i];lon,lat,_=transform.TransformPoint(p['x'],p['y']);blind=f'B{n:03}'
        packets.append(dict(blind_id=blind,longitude=lon,latitude=lat,imagery_review_minutes=15,field_dwell_minutes=c['observation_minutes'],
            eye_m=b['eye_m'],target_m=b['target_m'],task='detect; separately record classification/judgment',
            split='development' if p['y']>=mid else 'held_out',access_verified='',setup_usable='',target_patches_inspectable='',critical_false_visible='',planning_minutes='',reviewer='',reviewed_utc='',imagery_date='',notes=''))
        key.append(dict(blind_id=blind,candidate_id=i,arms=[arm for arm in score_maps if i in sorted(score_maps[arm],key=lambda j:(-score_maps[arm][j]['score'],j))[:3]],random=i in random['first_draw']))
        # Identical radial design independent of weighted/visible targets; keeps failures.
        for k,az in enumerate(np.arange(0,360,45)):
            distance=500 if k%2==0 else 1500
            x=p['x']+distance*np.sin(np.radians(az));y=p['y']+distance*np.cos(np.radians(az))
            longitude,latitude,_=transform.TransformPoint(x,y)
            r=math.floor((y-gt[3])/gt[5]);col=math.floor((x-gt[0])/gt[1])
            targets.append(dict(blind_id=blind,patch_id=f'P{k+1}',longitude=longitude,latitude=latitude,
                in_study=bool(masks['target'][r,col]),patch_radius_m=30,terrain_visible='',vegetation_blocks='',can_detect_deer_sized_object='',can_classify='',can_judge_antlers='',evidence='',notes=''))
    write_csv(root/'BLINDED_REVIEW.csv',packets);write_csv(root/'BLINDED_TARGETS.csv',targets);dump(root/'DO_NOT_SHARE_REVIEW_KEY.json',key)
    (root/'REVIEW_INSTRUCTIONS.md').write_text('''# Equal-effort review packet
Give reviewers only BLINDED_REVIEW.csv, BLINDED_TARGETS.csv, neutral imagery/terrain
and these instructions. Keep model layers, alternatives, scores and the separate key
hidden until completed sheets are frozen. No observations have been filled in.
Each position gets 15 minutes of imagery review and a proposed 30-minute field dwell.
Use the same optics for all; retain the eight prespecified 30m patches, including
out-of-study patches as context only (do not score them as eligible target benefit).
Do not visit without independently verified connected approach and current closures.
Mark uncertain imagery/foreground conditions unknown, not absent. Counterbalance
morning/evening and reviewer order within spatial blocks; record actual dates, duration,
optics, clouds and image acquisition dates. Northern half is development, southern
half held-out; do not tune on held-out review. Count failed setups and blank sessions.
Geometry or independent useful-area/planning-time gains are needed to justify a model;
rank changes and self-weighted scores are not validation. See the frozen PROTOCOL.md.
''')
    os.environ.setdefault('MPLCONFIGDIR',str(root/'.mplcache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    extent=[gt[0],gt[0]+a.shape[1]*gt[1],gt[3]+a.shape[0]*gt[5],gt[3]]
    fig,axes=plt.subplots(2,3,figsize=(15,9))
    for ax,arm in zip(axes[0],score_maps):
        ax.imshow(a,extent=extent,cmap='gray');colors=[score_maps[arm][p['id']]['score'] for p in points]
        artist=ax.scatter([p['x'] for p in points],[p['y'] for p in points],c=colors,s=12,cmap='viridis');fig.colorbar(artist,ax=ax,label='relative weighted km² (M1: km²)');ax.set_title(arm+' — unknown access')
    for ax,name in zip(axes[1],['habitat_summer','target_searchability','vegetation_unknown']):
        data=gdal.Open(str(root/(name+'.tif'))).ReadAsArray();artist=ax.imshow(data,extent=extent,cmap='viridis');fig.colorbar(artist,ax=ax);ax.set_title(name+' (coarse hypotheses)')
    for ax in axes.flat:ax.set_xlabel('UTM easting m');ax.set_ylabel('UTM northing m')
    fig.tight_layout();fig.savefig(root/'comparison.png',dpi=140);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,8));ax.imshow(a,extent=extent,cmap='gray')
    for item in key:
        p=point_map[item['candidate_id']];ax.scatter([p['x']],[p['y']],c='red',s=12);ax.annotate(item['blind_id'],(p['x'],p['y']),fontsize=8)
    ax.set_title('Blinded review positions — access verification required');ax.set_xlabel('UTM easting m');ax.set_ylabel('UTM northing m');fig.tight_layout();fig.savefig(root/'BLINDED_MAP.png',dpi=160);plt.close(fig)
    # Local fine-resolution diagnostic maps use the same extents per candidate.
    fine=json.loads((root/'fine_resolution.json').read_text())
    if fine.get('checks'):
        fig,axes=plt.subplots(len(fine['checks']),2,figsize=(9,4*len(fine['checks'])),squeeze=False)
        for row,check in enumerate(fine['checks']):
            for col,suffix in enumerate(['viewshed10m_local','viewshed1m']):
                raster=gdal.Open(str(root/(check['id']+'_'+suffix+'.tif')));vg=raster.GetGeoTransform();v=raster.ReadAsArray()
                axes[row,col].imshow(v,extent=[vg[0],vg[0]+v.shape[1]*vg[1],vg[3]+v.shape[0]*vg[5],vg[3]],vmin=0,vmax=1,cmap='gray')
                axes[row,col].set_title(check['id']+' '+suffix+' (400m)')
        fig.tight_layout();fig.savefig(root/'fine_comparison.png',dpi=130);plt.close(fig)
    prepared=json.loads((root/'prepared.json').read_text());sensitivity=json.loads((root/'sensitivity.json').read_text());resolution=json.loads((root/'resolution.json').read_text());dense=json.loads((root/'dense_reference.json').read_text())['summary']
    text=f'''# Matched scenario comparison

{len(points)}-point terrain control preserved; same AOI, target mask, 2 km radius, endpoint
heights and 30-minute proposed observation sessions. These are desk hypotheses.

Exact M1 control error: {sensitivity['exact_control_max_error']} km².
Expert comparison: {prepared['expert_status']}.
Unknown vegetation fraction in eligible targets: {prepared['unknown_vegetation_target_fraction']:.3%}.
Seasonal range fractions: {prepared['seasonal_target_fraction']}.
30 m terrain comparison: {resolution['comparison']}.
Dense-reference diagnostics: {dense}.
Fine local diagnostics: {fine}.

Main glassability uses target-cover, distance-task curves, perspective, stipulated
morning light and a finite uniform-inspection surrogate. Foreground/intervening
stress penalties are off by default; sparse ray tests are not vegetation validation.
Weighted area is not occupancy, sighting probability or predicted sightings per hour.
Terrain and habitat arms retain their unbounded geometry scores and all arms report
an equal-effort coverage surrogate separately; no empirical search-rate claim is made.

See component_scores.csv, sensitivity.json, canopy_stress.json, resolution.json,
dense_reference.json and alternatives.csv. Five alternatives are explanations for
review, not legal field-ready plans. Random selection uses the same technically
eligible common pool; legally feasible random comparison awaits access verification.
Actionable targets are separate from reachable observers; absent evidence remains
unknown. Road proxies/preferences are not hunter counts and are not habitat scores.

No independent expert rankings, field observations, imagery adjudications or sightings
were used to validate these models. Blank blinded sheets and collection protocol are
provided. Changed ranks alone do not justify added complexity. Recommend only a
small independent geometry/access/manual review before any further model expansion.
'''
    (root/'COMPARISON_REPORT.md').write_text(text)
