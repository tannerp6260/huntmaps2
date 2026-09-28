"""Matched desk experiment. Usage: python -m glassing.compare all --config configs/comparison.json"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
os.environ.setdefault('GDAL_CACHEMAX','128')
import argparse
import copy
import csv
import hashlib
import json
import math
from pathlib import Path
import resource
import signal
import time
import numpy as np
from scipy.stats import spearmanr
from osgeo import gdal,ogr,osr
from . import core,comparison_models as model
from .acquire import digest,dump,srs
from .comparison_data import acquire


def load(c):
    b=json.loads(Path(c['baseline_config']).read_text())
    ds,a,gt,masks=core.load_grid(b)
    return b,Path(b['work']),ds,a,gt,masks


def identity(c):
    b,base,*_=load(c)
    sources=Path(c['inputs'])/'manifest.json'
    files=[base/x for x in ['dem.tif','target.tif','observer.tif','candidates.json','scores.json']]
    files += [Path(__file__),Path(model.__file__),Path(__file__).with_name('comparison_review.py'),Path(c['protocol']),sources,Path(c['source_lock'])]
    files += [Path(c[k]) for k in ['expert_csv','access_csv','actionable_target_geojson'] if c.get(k)]
    return dict(config=c,sha256={str(p):digest(p) for p in files},gdal=gdal.__version__)


def vector_mask(path,shape,gt,projection,epsg,actionable=False,repair_log=None):
    data=json.loads(Path(path).read_text());combined=None
    for feature in data['features']:
        if actionable and not(feature['properties'].get('followup_verified') is True and feature['properties'].get('evidence')):
            raise ValueError('Actionability polygon requires verified follow-up evidence')
        geom=ogr.CreateGeometryFromJson(json.dumps(feature['geometry']))
        geom.Transform(osr.CoordinateTransformation(srs(4326),srs(epsg)))
        if not geom.IsValid():
            if actionable:raise ValueError('Invalid actionability polygon; independent evidence needs correction')
            original=core.polygon_mask(geom,shape,gt,projection)
            before=geom.GetArea();geom=geom.MakeValid()
            if not geom.IsValid():raise ValueError('Source geometry repair failed')
            corrected=core.polygon_mask(geom,shape,gt,projection)
            if repair_log is not None:repair_log.append(dict(path=str(path),method='OGR MakeValid; source preserved',original_area_m2=before,repaired_area_m2=geom.GetArea(),changed_analysis_cells=int(np.count_nonzero(original!=corrected))))
        combined=geom if combined is None else combined.Union(geom)
    return np.zeros(shape,bool) if combined is None else core.polygon_mask(combined,shape,gt,projection)


def prepare(c):
    b,base,ds,a,gt,masks=load(c);root=Path(c['work']);root.mkdir(parents=True,exist_ok=True)
    # No reads from unverified downloaded inputs.
    manifest=json.loads((Path(c['inputs'])/'manifest.json').read_text())
    locked=json.loads(Path(c['source_lock']).read_text())
    for name,checksum in locked.items():
        if digest(Path(c['inputs'])/name)!=checksum:raise ValueError('Input differs from locked comparison: '+name)
    for name,entry in manifest.items():
        if digest(Path(c['inputs'])/name)!=entry['sha256']:raise ValueError('Source checksum mismatch: '+name)
    bounds=[gt[0],gt[3]+a.shape[0]*gt[5],gt[0]+a.shape[1]*gt[1],gt[3]]
    unknown=np.zeros(a.shape,bool);arrays={}
    for name in ['tree','shrub','herb']:
        tmp=gdal.Warp('',str(Path(c['inputs'])/(name+'.tif')),format='MEM',dstSRS=ds.GetProjection(),outputBounds=bounds,width=a.shape[1],height=a.shape[0],resampleAlg='near',outputType=gdal.GDT_Float32,dstNodata=-9999)
        values=tmp.ReadAsArray();valid=np.isfinite(values)&(values>=0)&(values<=100)
        unknown |= ~valid
        arrays[name]=np.where(valid,values/100.,np.nan).astype('float32')
        core.write_raster(root/(name+'.tif'),np.where(valid,arrays[name],-9999),gt,ds.GetProjection(),-9999)
    repairs=[]
    for name in ['summer','winter']:
        arrays[name]=vector_mask(Path(c['inputs'])/(name+'.geojson'),a.shape,gt,ds.GetProjection(),b['epsg'],repair_log=repairs)
        core.write_raster(root/(name+'.tif'),arrays[name].astype('uint8'),gt,ds.GetProjection())
    core.write_raster(root/'vegetation_unknown.tif',unknown.astype('uint8'),gt,ds.GetProjection())
    target_action=vector_mask(c['actionable_target_geojson'],a.shape,gt,ds.GetProjection(),b['epsg'],True) if c['actionable_target_geojson'] else np.zeros(a.shape,bool)
    core.write_raster(root/'actionability.tif',np.where(masks['target'],np.where(target_action,1,2),0).astype('uint8'),gt,ds.GetProjection())
    for season in ['summer','winter']:
        h=model.habitat(arrays[season],np.nan_to_num(arrays['shrub'],nan=.3),np.nan_to_num(arrays['herb'],nan=.3),season,c['habitat_floor'])
        core.write_raster(root/('habitat_'+season+'.tif'),h,gt,ds.GetProjection())
    search=model.searchability(np.nan_to_num(arrays['tree'],nan=.25),np.nan_to_num(arrays['shrub'],nan=.3))
    core.write_raster(root/'target_searchability.tif',search,gt,ds.GetProjection())
    pool=json.loads((base/'candidates.json').read_text())
    experts=model.import_experts(c['expert_csv'],gt,masks['observer'],b['epsg'])
    # Expert points form a separate pool comparison; original common pool never changes.
    access_rows={r['id']:r for r in csv.DictReader(open(c['access_csv'],newline=''))} if c['access_csv'] else {}
    for ev in access_rows.values():
        if ev.get('reachable')=='verified' and not ev.get('evidence'):ev['reachable']='unknown'
    chosen=model.eligible_points(pool,c['preferences'],access_rows)
    if not chosen:raise ValueError('No candidates meet required access evidence; comparison cannot claim feasible alternatives')
    dump(root/'pool.json',chosen);dump(root/'experts.json',experts);dump(root/'access_evidence.json',access_rows)
    dump(root/'prepared.json',dict(raster_sha256={name:digest(root/name) for name in ['tree.tif','shrub.tif','herb.tif','summer.tif','winter.tif','vegetation_unknown.tif','actionability.tif','habitat_summer.tif','habitat_winter.tif','target_searchability.tif']},identity=identity(c),geometry_repairs=repairs,unknown_vegetation_target_fraction=float(unknown[masks['target']].mean()),
        seasonal_target_fraction={x:float(arrays[x][masks['target']].mean()) for x in ['summer','winter']},
        expert_status='imported; independence remains reviewer-attested' if experts else 'PENDING: no independent expert points supplied',
        access_status='unknown unless independently supplied; no inferred road/route legality',common_pool_count=len(chosen)))


def read_layers(c):
    root=Path(c['work']);meta=json.loads((root/'prepared.json').read_text())
    if meta['identity']!=identity(c):raise ValueError('Changed comparison inputs/configuration: run prepare again')
    layers={}
    for name,checksum in meta['raster_sha256'].items():
        if digest(root/name)!=checksum:raise ValueError('Prepared comparison raster changed: '+name)
    for name in ['tree','shrub','herb','summer','winter','vegetation_unknown','actionability']:
        ds=gdal.Open(str(root/(name+'.tif')));a=ds.ReadAsArray()
        if name in ['tree','shrub','herb']:a=np.where(a<0,np.nan,a)
        layers[name]=a
    return layers


def scenarios(c):
    result={'M1_raw':dict(c,arm='raw'),'M2_habitat':dict(c,arm='habitat'),'M3_glass':dict(c,arm='glass')}
    def variant(name,**changes):result[name]=dict(c,arm='glass',**changes)
    for f in c['features']:
        if c['features'][f]:
            toggles=dict(c['features']);toggles[f]=False;variant('without_'+f,features=toggles)
    for mode in ['open','dense']:variant('unknown_cover_'+mode,unknown_cover=mode)
    for season in ['winter','background']:variant('season_'+season,season=season)
    for floor in [.1,.5]:variant('habitat_floor_'+str(floor),habitat_floor=floor)
    for scale in [.75,1.25]:variant('distance_scale_'+str(scale),distance_scale=scale)
    for task in ['classify','judge']:variant('task_'+task,task=task)
    for light in ['evening','none']:variant('light_'+light,light=light)
    for minutes in [15,60]:variant('dwell_'+str(minutes),observation_minutes=minutes)
    for kind in ['foreground','intervening']:
        toggles=dict(c['features']);toggles[kind]=True;variant('stress_'+kind,features=toggles)
    for height in c['canopy_heights_m']:
        toggles=dict(c['features']);toggles['foreground']=True;toggles['intervening']=True
        variant('canopy_stress_'+str(height),features=toggles,canopy_height=height)
    return result


def get_view(c,b,base,ds,p,radius,original=True):
    if original:
        path=core.visibility_dir(b)/f'{p["id"]}_{radius}.tif'
        if path.exists():
            if not path.with_suffix('.sha256').exists() or path.with_suffix('.sha256').read_text().strip()!=digest(path):raise ValueError('Baseline viewshed checksum failed')
            return gdal.Open(str(path))
    root=Path(c['work'])/'additional_visibility';root.mkdir(exist_ok=True)
    # Compute supplemental products afresh: small and no stale-cache ambiguity.
    return core.viewshed(ds,root/f'{p["id"]}_{radius}.tif',p['x'],p['y'],radius,b['eye_m'],b['target_m'],b['curvature'])


def components(c,b,base,ds,a,gt,masks,layers,p,gradients,original=True,stress=True):
    radius=b['baseline_radius_m'];vs=get_view(c,b,base,ds,p,radius,original)
    vg=vs.GetGeoTransform();r0=int(round((vg[3]-gt[3])/gt[5]));c0=int(round((vg[0]-gt[0])/gt[1]))
    total,_,visible=core.score_mask(vs,gt,a.shape,masks['target'],p['x'],p['y'],radius)
    rr,cc=np.where(visible);rr+=r0;cc+=c0
    x=gt[0]+(cc+.5)*gt[1];y=gt[3]+(rr+.5)*gt[5]
    dx=x-p['x'];dy=y-p['y'];d=np.hypot(dx,dy)
    dz=a[rr,cc]+b['target_m']-(a[p['row'],p['col']]+b['eye_m'])
    gy,gx=gradients
    values={k:v[rr,cc] for k,v in layers.items()}
    uncertain=values['vegetation_unknown']>0
    tree=np.nan_to_num(values['tree'],nan=.25);shrub=np.nan_to_num(values['shrub'],nan=.3);herb=np.nan_to_num(values['herb'],nan=.3)
    common=dict(total=total,d=d,dx=dx,dy=dy,dz=dz,gx=gx[rr,cc],gy=gy[rr,cc],tree=tree,shrub=shrub,herb=herb,
        summer=values['summer'],winter=values['winter'],search=model.searchability(tree,shrub),uncertain=uncertain,
        actionable=values['actionability']==1)
    common['perspective']=model.perspective(common['gx'],common['gy'],-dx,-dy,-dz,c['perspective_floor'])
    fg_cells=int(math.ceil(c['foreground_radius_m']/gt[1]))
    foreground=layers['tree'][max(0,p['row']-fg_cells):p['row']+fg_cells+1,max(0,p['col']-fg_cells):p['col']+fg_cells+1]
    finite=foreground[np.isfinite(foreground)]
    common['foreground_cover_mean']=float(finite.mean()) if finite.size else None
    common['foreground_unknown_fraction']=float(1-finite.size/foreground.size)
    common['stress']={}
    if stress and len(rr):
        rng=np.random.default_rng(c['seed']+int.from_bytes(hashlib.sha256(p['id'].encode()).digest()[:4],'big'))
        indices=rng.choice(len(rr),min(c['rays_per_candidate'],len(rr)),replace=False)
        for height in c['canopy_heights_m']:
            rays=[model.canopy_ray(a,layers['tree'],gt,(p['row'],p['col']),(rr[i],cc[i]),b['eye_m'],b['target_m'],b['curvature'],height,c['canopy_threshold'],c['foreground_radius_m']) for i in indices]
            blocked=sum(r['blocked'] for r in rays);fg=sum(r['foreground'] for r in rays)
            common['stress'][str(height)]=dict(n=len(rays),blocked=blocked,foreground=fg,unknown=sum(r['unknown'] for r in rays),blocked_fraction=blocked/len(rays),unknown_path_upper_fraction=sum(r['blocked'] or r['unknown'] for r in rays)/len(rays),wilson95=model.wilson(blocked,len(rays)))
    return common


def score(comp,s,res):
    area=res*res/1e6;f=s['features'];arm=s['arm']
    shrub,herb,tree=comp['shrub'],comp['herb'],comp['tree']
    if s.get('unknown_cover'):
        u=comp['uncertain'];dense=s['unknown_cover']=='dense'
        tree=np.where(u,1. if dense else 0.,tree);shrub=np.where(u,.6 if dense else .3,shrub);herb=np.where(u,0. if dense else .3,herb)
    target_search=model.searchability(tree,shrub)
    h=model.habitat(comp[s['season']] if s['season']!='background' else comp['summer'],shrub,herb,s['season'],s['habitat_floor']) if f['habitat'] else np.ones_like(comp['d'])
    v=np.ones_like(h)
    if arm!='raw':v*=h
    if arm=='glass':
        if f['searchability']:v*=target_search
        if f['distance']:v*=model.distance_response(comp['d'],s)
        if f['perspective']:v*=comp['perspective']
        if f['light']:v*=model.sunlight(comp['gx'],comp['gy'],comp['dx'],comp['dy'],comp['dz'],s['light'],s)
    full=float(v.sum()*area)
    effort=model.inspection_fraction(comp['total'],s['observation_minutes'],s['scan_km2_per_minute'])
    value=full*(effort if arm=='glass' and f['inspection'] else 1)
    height=str(s.get('canopy_height',15));rays=comp['stress'].get(height)
    if arm=='glass' and f['foreground']:
        value*=1-s['foreground_stress_penalty']*(rays['foreground']/rays['n'] if rays else 1.)
    if arm=='glass' and f['intervening']:
        value*=1-(rays['blocked_fraction'] if rays else 1.)
    # Export component means separately; no claims that each is independently calibrated.
    return dict(score=value,unlimited_score=full,equal_effort_score=full*effort,inspection_fraction=effort,raw_km2=comp['total'],
        habitat_mean=float(h.mean()) if len(h) else 0,searchability_mean=float(target_search.mean()) if len(h) else 0,
        distance_mean=float(model.distance_response(comp['d'],s).mean()) if len(h) else 0,
        perspective_mean=float(comp['perspective'].mean()) if len(h) else 0,
        light_mean=float(model.sunlight(comp['gx'],comp['gy'],comp['dx'],comp['dy'],comp['dz'],s['light'],s).mean()) if len(h) else 0,
        unknown_vegetation_fraction=float(comp['uncertain'].mean()) if len(h) else 0,
        actionable_visible_km2=float(comp['actionable'].sum()*area),foreground_cover_mean=comp['foreground_cover_mean'],
        foreground_unknown_fraction=comp['foreground_unknown_fraction'])


def rank_metrics(reference,other):
    ids=sorted(set(reference)&set(other));a=np.array([reference[i] for i in ids]);b=np.array([other[i] for i in ids])
    rho=float(spearmanr(a,b).statistic) if len(ids)>1 and np.ptp(a)>0 and np.ptp(b)>0 else None
    order=lambda d:sorted(ids,key=lambda i:(-d[i],i))[:min(10,len(ids))]
    return dict(spearman=rho,top10_overlap=len(set(order(reference))&set(order(other))),n=len(ids))


def random_baseline(c,points,scores):
    rng=np.random.default_rng(c['seed']);xs=[p['x'] for p in points];ys=[p['y'] for p in points]
    # Four non-overlapping spatial strata; one common-pool candidate per stratum.
    xm=(min(xs)+max(xs))/2;ym=(min(ys)+max(ys))/2
    strata={}
    for p in points:strata.setdefault((p['x']>=xm,p['y']>=ym),[]).append(p['id'])
    draws=[]
    for _ in range(c['random_replicates']):draws.append([str(rng.choice(sorted(v))) for _,v in sorted(strata.items())])
    return dict(status='TECHNICALLY_ELIGIBLE_ONLY; legal feasibility pending unless supplied evidence verifies approach',
        first_draw=draws[0],replicates=draws,
        mean_single_position_scores={arm:[float(np.mean([scores[arm][i] for i in draw])) for draw in draws] for arm in ['M1_raw','M2_habitat','M3_glass']},
        warning='Each position is a separate equal 30-minute session; do not sum four viewsheds as a route or equal-time portfolio')


def run(c):
    b,base,ds,a,gt,masks=load(c);layers=read_layers(c);root=Path(c['work'])
    points=json.loads((root/'pool.json').read_text());experts=json.loads((root/'experts.json').read_text())
    all_scenarios=scenarios(c);rows=[];stress_records={};grad=np.gradient(a.astype('float64'),gt[1]);grad[0]*=-1
    access=json.loads((root/'access_evidence.json').read_text())
    component_start=time.monotonic()
    for p in points+experts:
        comp=components(c,b,base,ds,a,gt,masks,layers,p,grad,original=p in points)
        stress_records[p['id']]=comp['stress']
        for name,s in all_scenarios.items():
            row=dict(id=p['id'],scenario=name,**score(comp,s,gt[1]))
            row['reachable_status']=access.get(p['id'],{}).get('reachable','unknown')
            row['actionability_status']='supplied evidence polygons' if c['actionable_target_geojson'] else 'unknown; zero certified area is not zero possible area'
            row['flags']='UNCALIBRATED;COARSE_COVER;NO_HORIZON_SHADOW;NO_VALIDATED_CANOPY;'+('UNKNOWN_ACCESS;' if row['reachable_status']!='verified' else '')
            rows.append(row)
    original_ids={p['id'] for p in points}
    score_maps={name:{r['id']:r['score'] for r in rows if r['scenario']==name and r['id'] in original_ids} for name in all_scenarios}
    # Mandatory exact M1 control equality before interpreting any new ranks.
    baseline={p['id']:p['visible_km2'] for p in json.loads((base/'scores.json').read_text())}
    error=max(abs(score_maps['M1_raw'][i]-baseline[i]) for i in original_ids)
    if error>1e-10:raise ValueError('Comparison raw control differs from baseline')
    for name in all_scenarios:
        ordered=sorted([r for r in rows if r['scenario']==name and r['id'] in original_ids],key=lambda r:(-r['score'],r['id']))
        for rank,row in enumerate(ordered,1):row['rank_common_pool']=rank
    dump(root/'component_scores.json',rows);write_csv(root/'component_scores.csv',rows)
    dump(root/'canopy_stress.json',stress_records)
    sensitivity={name:rank_metrics(score_maps['M3_glass'],m) for name,m in score_maps.items()}
    matched={arm:{r['id']:round(r['equal_effort_score'],12) for r in rows if r['scenario']==arm and r['id'] in original_ids} for arm in ['M1_raw','M2_habitat','M3_glass']}
    for arm in matched:
        order=sorted(matched[arm],key=lambda i:(-matched[arm][i],i))
        for row in rows:
            if row['scenario']==arm and row['id'] in original_ids:row['matched_effort_rank']=order.index(row['id'])+1
    dump(root/'component_scores.json',rows);write_csv(root/'component_scores.csv',rows)
    pairwise={a+'__'+b:rank_metrics(score_maps[a],score_maps[b]) for a,b in [('M1_raw','M2_habitat'),('M1_raw','M3_glass'),('M2_habitat','M3_glass')]}
    dump(root/'sensitivity.json',dict(reference='M3_glass',metrics=sensitivity,pairwise=pairwise,
         matched_effort={a+'__M3_glass':rank_metrics(matched[a],matched['M3_glass']) for a in ['M1_raw','M2_habitat']},
         raw_effort_ties=len(matched['M1_raw'])-len(set(matched['M1_raw'].values())),exact_control_max_error=error))
    random=random_baseline(c,points,score_maps)
    dump(root/'random_baseline.json',random)
    count=len(random['first_draw'])
    nominations={arm:sorted(score_maps[arm],key=lambda i:(-score_maps[arm][i],i))[:count] for arm in ['M1_raw','M2_habitat','M3_glass']}
    nominations['stratified_random']=random['first_draw']
    cross=[]
    for nominator,ids in nominations.items():
        row=dict(nominator=nominator,ids=ids,sessions=len(ids),minutes_per_session=c['observation_minutes'],total_observation_minutes=len(ids)*c['observation_minutes'])
        for evaluator in ['M1_raw','M2_habitat','M3_glass']:
            row[evaluator+'_mean']=float(np.mean([score_maps[evaluator][i] for i in ids]))
            row[evaluator+'_equal_effort_mean']=float(np.mean([matched[evaluator][i] for i in ids]))
        cross.append(row)
    dump(root/'selection_comparison.json',dict(nominations=cross,warning='Model cross-scores only, not independent validation. Equal session count/dwell; approach travel unverified and not modeled. No summation of overlapping coverage or route claim.'))
    # Accessible preferences do not corrupt scientific arm scores; expose separately.
    pref=[]
    for p in points:
        ev=access.get(p['id'],{});bonus=0.
        for key,column in [('roadlessness_weight','road_distance_km'),('pressure_weight','road_pressure_proxy')]:
            w=c['preferences'][key]
            if w:
                if not ev.get(column):raise ValueError('Missing supplied preference metric '+column)
                bonus+=w*float(ev[column])*(1 if key=='roadlessness_weight' else -1)
        pref.append(dict(id=p['id'],preference_adjustment=bonus,warning='Separate preference only; road proxy is not hunter counts'))
    dump(root/'preferences.json',pref)
    main_seconds=time.monotonic()-component_start;component_start=time.monotonic()
    # Coarser terrain: same coordinates, target polygon, heights and radius.
    coarse=root/'dem_30m.tif'
    coarse_ds=gdal.Warp(str(coarse),ds,xRes=30,yRes=30,resampleAlg='average',outputType=gdal.GDT_Float32,creationOptions=['COMPRESS=DEFLATE'])
    ca,cgt,_=core.validate(coarse_ds);study=ogr.CreateGeometryFromJson(json.dumps(json.loads((base/'study.json').read_text())['geometry']))
    ct=core.polygon_mask(study,ca.shape,cgt,ds.GetProjection());cr={}
    coarse_dir=root/'coarse_visibility';coarse_dir.mkdir(exist_ok=True)
    for p in points:
        v=core.viewshed(coarse_ds,coarse_dir/(p['id']+'.tif'),p['x'],p['y'],2000,b['eye_m'],b['target_m'],b['curvature'])
        cr[p['id']]=core.score_mask(v,cgt,ca.shape,ct,p['x'],p['y'],2000)[0]
    dump(root/'resolution.json',dict(coarse_m=30,resampling='area average of control 10m DEM; 30m pixel observer snapping, same input coordinate',comparison=rank_metrics(score_maps['M1_raw'],cr),raw30_km2=cr,coarse_target_km2=float(ct.sum()*900/1e6)))
    coarse_seconds=time.monotonic()-component_start;component_start=time.monotonic()
    dense_reference(c,b,base,ds,a,gt,masks,layers,grad,points,score_maps)
    dense_seconds=time.monotonic()-component_start;component_start=time.monotonic()
    fine_reference(c,b,base,ds,a,gt,masks,points,score_maps)
    dump(root/'component_timings.json',dict(main_s=main_seconds,coarse_s=coarse_seconds,dense_s=dense_seconds,fine_s=time.monotonic()-component_start))
    dump(root/'run_identity.json',identity(c))


def dense_reference(c,b,base,ds,a,gt,masks,layers,grad,points,scores):
    root=Path(c['work']);study=json.loads((base/'study.json').read_text());geom=ogr.CreateGeometryFromJson(json.dumps(study['geometry']));cent=geom.Centroid();x,y=cent.GetX(),cent.GetY();half=c['dense_side_m']/2
    dense=[]
    for yy in np.arange(y-half,y+half,c['dense_spacing_m']):
        for xx in np.arange(x-half,x+half,c['dense_spacing_m']):
            row=int((yy-gt[3])/gt[5]);col=int((xx-gt[0])/gt[1])
            if masks['observer'][row,col]:
                xx2,yy2=core.xy(gt,row,col);dense.append(dict(id=f'D{len(dense)+1:04}',x=xx2,y=yy2,row=row,col=col))
    if len(dense)>441:raise ValueError('Dense reference exceeds declared 441-point cap')
    results=[];setting=dict(c,arm='glass')
    # Canopy stress excluded here: candidate recall tests exactly main M3, not unvalidated bounds.
    for p in dense:
        comp=components(c,b,base,ds,a,gt,masks,layers,p,grad,original=False,stress=False)
        results.append(dict(p,raw_km2=comp['total'],glass_score=score(comp,setting,gt[1])['score']))
    local=[p for p in points if abs(p['x']-x)<half and abs(p['y']-y)<half]
    summary=dict(area_km2=c['dense_side_m']**2/1e6,dense_count=len(dense),original_count=len(local),spacing_m=c['dense_spacing_m'],status='technical-domain recall only; no access verification')
    for label,col,arm in [('raw','raw_km2','M1_raw'),('glass','glass_score','M3_glass')]:
        best=max(r[col] for r in results);old=max([scores[arm][p['id']] for p in local],default=0)
        summary[label]=dict(dense_best=best,original_local_best=old,relative_best_opportunity=(best/old-1) if old else None)
    dump(root/'dense_reference.json',dict(summary=summary,candidates=results))


def fine_reference(c,b,base,ds,a,gt,masks,points,scores):
    root=Path(c['work']);path=Path(c['inputs'])/'fine_dem.tif'
    if not path.exists():
        dump(root/'fine_resolution.json',dict(status='pending: selected 1m terrain not acquired'));return
    src=gdal.Open(str(path));info=gdal.Info(src,format='json');dump(root/'fine_source_info.json',info)
    checks=[];byid={p['id']:p for p in points}
    selected=list(dict.fromkeys(max(scores[arm],key=lambda i:scores[arm][i]) for arm in ['M1_raw','M3_glass']))
    for i in selected:
        p=byid[i];radius=400;halo=420
        bounds=[p['x']-halo-.5,p['y']-halo-.5,p['x']+halo+.5,p['y']+halo+.5]
        fd=gdal.Warp(str(root/(i+'_dem1m.tif')),src,dstSRS=ds.GetProjection(),outputBounds=bounds,xRes=1,yRes=1,resampleAlg='bilinear',dstNodata=-9999,outputType=gdal.GDT_Float32,creationOptions=['COMPRESS=DEFLATE'])
        fa,fgt,_=core.validate(fd)
        fv=core.viewshed(fd,root/(i+'_viewshed1m.tif'),p['x'],p['y'],radius,b['eye_m'],b['target_m'],b['curvature'])
        # Compare on the original 10m target grid to separate resolution from area accounting.
        cv=core.viewshed(ds,root/(i+'_viewshed10m_local.tif'),p['x'],p['y'],radius,b['eye_m'],b['target_m'],b['curvature'])
        vg=cv.GetGeoTransform();vv=cv.ReadAsArray();h,w=vv.shape
        common=gdal.Warp('',fv,format='MEM',dstSRS=ds.GetProjection(),outputBounds=[vg[0],vg[3]+h*vg[5],vg[0]+w*vg[1],vg[3]],width=w,height=h,resampleAlg='near').ReadAsArray()
        rr=int(round((vg[3]-gt[3])/gt[5]));cc=int(round((vg[0]-gt[0])/gt[1]))
        yy=vg[3]+(np.arange(h)+.5)*vg[5];xx=vg[0]+(np.arange(w)+.5)*vg[1]
        eligible=masks['target'][rr:rr+h,cc:cc+w] & (np.hypot(yy[:,None]-p['y'],xx[None,:]-p['x'])<=radius)
        fine=common==1;coarse=vv==1
        # Independent profiles on deterministic target cells in the common 10m comparison.
        eligible_indices=np.argwhere(eligible);rng=np.random.default_rng(c['seed'])
        ray_checks=[]
        for sample in rng.choice(len(eligible_indices),min(40,len(eligible_indices)),replace=False):
            vr,vc=eligible_indices[sample];tx=vg[0]+(vc+.5)*vg[1];ty=vg[3]+(vr+.5)*vg[5]
            tr=int((ty-fgt[3])/fgt[5]);tc=int((tx-fgt[0])/fgt[1]);pr=int((p['y']-fgt[3])/fgt[5]);pc=int((p['x']-fgt[0])/fgt[1])
            margin=core.profile_clearance(fa,fgt,dict(row=pr,col=pc),tr,tc,b['eye_m'],b['target_m'],b['curvature'])
            ray_checks.append(dict(row=int(tr),col=int(tc),clearance_m=margin,gdal_visible=bool(fine[vr,vc]),agreement=bool((margin>=0)==fine[vr,vc])))
        dump(root/(i+'_fine_ray_checks.json'),ray_checks)
        checks.append(dict(id=i,radius_m=radius,fine_observer_elevation_m=float(fa[pr,pc]),control_observer_elevation_m=float(a[p['row'],p['col']]),independent_ray_agreements=sum(r['agreement'] for r in ray_checks),independent_ray_count=len(ray_checks),eligible_cells=int(eligible.sum()),disagreement_fraction=float(np.mean((fine!=coarse)[eligible])),fine_area_on10m_km2=float((fine&eligible).sum()/10000),control_area_km2=float((coarse&eligible).sum()/10000),
            warning='2019 1m source versus seamless 10m control: source vintage/datum and sampling confounded; local check only'))
    dump(root/'fine_resolution.json',dict(status='exploratory 400m local terrain comparison; no fine canopy model',checks=checks,
        vertical_reference='See source info; horizontal warp is not a vertical transformation; no cross-source elevation offsets applied'))


def write_csv(path,rows):
    if not rows:return
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with open(path,'w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader();writer.writerows(rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['acquire','prepare','run','review','all']);parser.add_argument('--config',required=True)
    args=parser.parse_args();c=json.loads(Path(args.config).read_text());root=Path(c['work']);root.mkdir(parents=True,exist_ok=True)
    resource.setrlimit(resource.RLIMIT_AS,(c['memory_mb']*1024**2,)*2)
    def timeout(*_):raise TimeoutError('Comparison runtime budget exceeded')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(c['runtime_s'])
    from .comparison_review import review
    actions=dict(acquire=acquire,prepare=prepare,run=run,review=review)
    for stage in ['prepare','run','review'] if args.stage=='all' else [args.stage]:
        start=time.monotonic();status='ok'
        try:
            used=sum(p.stat().st_size for folder in [root,Path(c['inputs'])] for p in folder.rglob('*') if p.is_file())
            if used>c['disk_bytes']:raise ValueError('Comparison disk budget exceeded')
            actions[stage](c)
        except Exception as e:status=f'{type(e).__name__}: {e}';raise
        finally:
            entry=dict(stage=stage,status=status,wall_s=time.monotonic()-start,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                work_bytes=sum(p.stat().st_size for p in root.rglob('*') if p.is_file()))
            with open(root/'metrics.jsonl','a') as f:f.write(json.dumps(entry)+'\n')
            print(json.dumps(entry),flush=True)


if __name__=='__main__':main()
