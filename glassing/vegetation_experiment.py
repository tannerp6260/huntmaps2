"""Bounded vegetation diagnostics over an immutable terrain experiment."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
os.environ.setdefault('MPLCONFIGDIR','/tmp/glassing-vegetation-mpl')
import argparse,json,math,time,resource,signal,csv
from pathlib import Path
import numpy as np
from osgeo import gdal
from . import core,attention,comparison_models as model
from .acquire import digest,dump
from .vegetation_rays import ray

def read(p):return json.loads(Path(p).read_text())
def csvwrite(path,rows):
    if not rows:return
    with Path(path).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def directional(p,tree,gt,rings):
    pad=math.ceil(max(r[1] for r in rings)/gt[1]);r,c=p['row'],p['col'];r0=max(0,r-pad);c0=max(0,c-pad);v=tree[r0:r+pad+1,c0:c+pad+1];rr,cc=np.indices(v.shape)
    dx=gt[0]+(cc+c0+.5)*gt[1]-p['x'];dy=gt[3]+(rr+r0+.5)*gt[5]-p['y'];d=np.hypot(dx,dy);az=np.degrees(np.arctan2(dx,dy))%360;rows=[]
    for inner,outer in rings:
        for start in range(0,360,30):
            m=(d>=inner)&(d<outer)&(az>=start)&(az<start+30);vals=v[m];ok=np.isfinite(vals)
            rows.append(dict(start=start,end=start+30,inner_m=inner,outer_m=outer,cells=int(m.sum()),mean_tree=float(vals[ok].mean()) if ok.any() else None,unknown_fraction=float((~ok).mean()) if vals.size else 1.))
    return rows

def summarize(p,indices,tree,shrub,gt,shape_,c,lock,rings,thresholds):
    rr,cc=np.unravel_index(indices,shape_);tr=tree[rr,cc];sh=shrub[rr,cc];valid=np.isfinite(tr)&np.isfinite(sh);area=abs(gt[1]*gt[5])/1e6
    dx=gt[0]+(cc+.5)*gt[1]-p['x'];dy=gt[3]+(rr+.5)*gt[5]-p['y'];dist=np.hypot(dx,dy)
    search=model.searchability(np.nan_to_num(tr,nan=.25),np.nan_to_num(sh,nan=.3));distance=model.distance_response(dist,lock['comparison']);settings=lock['attention']
    dirs=directional(p,tree,gt,rings);near={d['start']:d for d in dirs if d['inner_m']==rings[0][0]}
    rewards={'distance_control':distance,'target_heuristic':distance*search,'unknown_low':distance*np.where(valid,search,0),'unknown_high':distance*np.where(valid,search,1)};scores={};selections={};allpatches={}
    for label,reward in rewards.items():
        ps=attention.patches(dx,dy,reward,area,settings['width_deg'],settings['band_m'],c['radius_m']);sel=attention.select(ps,c['observation_minutes'],settings['rate_km2_min'],settings['overhead_minutes']);scores[label]=sel['score'];selections[label]=sel;allpatches[label]=ps
    for th in thresholds:
        ps=[dict(t,reward=t['reward'] if near[t['azimuth_start']]['mean_tree'] is not None and near[t['azimuth_start']]['mean_tree']<=th and near[t['azimuth_start']]['unknown_fraction']==0 else 0) for t in allpatches['target_heuristic']]
        sel=attention.select(ps,c['observation_minutes'],settings['rate_km2_min'],settings['overhead_minutes']);scores[f'directional_{int(th*100)}']=sel['score'];selections[f'directional_{int(th*100)}']=sel
    row=dict(id=p['id'],parent=p.get('parent',''),kind=p.get('kind','original'),x=p['x'],y=p['y'],raw_km2=len(indices)*area,tree_lt10_km2=float((tr<.1).sum()*area),tree_10to40_km2=float(((tr>=.1)&(tr<.4)).sum()*area),tree_ge40_km2=float((tr>=.4).sum()*area),tree_unknown_km2=float((~np.isfinite(tr)).sum()*area),shrub_mean_pct=float(np.nanmean(sh)*100) if np.isfinite(sh).any() else None,shrub_gt30_km2=float((sh>.3).sum()*area),shrub_unknown_km2=float((~np.isfinite(sh)).sum()*area),cover_unknown_km2=float((~valid).sum()*area),searchability_integral=float(search.sum()*area),searchability_integral_low=float(np.where(valid,search,0).sum()*area),searchability_integral_high=float(np.where(valid,search,1).sum()*area),baseline_score=p.get('selective_score'),**scores)
    assert abs(sum(row[k] for k in ['tree_lt10_km2','tree_10to40_km2','tree_ge40_km2','tree_unknown_km2'])-row['raw_km2'])<1e-9
    return row,dict(directions=dirs,selections=selections,patches=allpatches['target_heuristic'])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',default='configs/vegetation.soap-creek-v1.json');ap.add_argument('--output',help='new versioned output folder for a repeat');args=ap.parse_args();cfg=read(args.config)
    if args.output:cfg['output']=args.output
    out=Path(cfg['output']);out.mkdir(parents=True,exist_ok=True)
    if (out/'COMPLETE.json').exists():raise ValueError('Version complete; choose a new output directory')
    start=time.monotonic();signal.alarm(cfg['runtime_s']);resource.setrlimit(resource.RLIMIT_AS,(cfg['memory_mb']*1024**2,resource.RLIM_INFINITY))
    baseline=Path(cfg['baseline']);review=Path(cfg['review']);c=read(baseline/'scouting.json');root=Path(c['work']);lock=read(c['model_lock'])
    preserved={str(p):digest(p) for folder in [baseline,review]+[Path(v) for v in cfg.get('preserve_extra',[])] for p in folder.rglob('*') if p.is_file()};dump(out/'PRESERVED.json',preserved)
    for p,h in read(baseline/'manifest.json').items():
        if digest(p)!=h:raise ValueError('Baseline integrity failed: '+p)
    ds=gdal.Open(str(root/'dem.tif'));z=ds.ReadAsArray();gt=ds.GetGeoTransform();target=gdal.Open(str(root/'target.tif')).ReadAsArray().astype(bool);observer=gdal.Open(str(root/'observer.tif')).ReadAsArray().astype(bool)
    def cover(k):
        d=gdal.Open(str(root/(k+'.tif')))
        if (d.RasterYSize,d.RasterXSize)!=z.shape or d.GetGeoTransform()!=gt or not d.GetSpatialRef().IsSame(ds.GetSpatialRef()):raise ValueError('Cover alignment mismatch')
        v=d.ReadAsArray();return np.where(np.isfinite(v)&(v>=0)&(v<=1),v,np.nan)
    tree,shrub=cover('tree'),cover('shrub');points=read(root/'scores.json');rows=[];details={};indices={};lookup={p['id']:p for p in points};(out/'viewsheds').mkdir(exist_ok=True)
    def process(p,path):
        vs=gdal.Open(str(path));
        if not vs.GetSpatialRef().IsSame(ds.GetSpatialRef()) or vs.GetGeoTransform()[1:3]!=gt[1:3] or vs.GetGeoTransform()[4:]!=gt[4:]:raise ValueError('Viewshed grid mismatch')
        for axis in [0,3]:
            offset=(vs.GetGeoTransform()[axis]-gt[axis])/gt[1 if axis==0 else 5]
            if abs(offset-round(offset))>1e-7:raise ValueError('Viewshed origin mismatch')
        _,_,m=core.score_mask(vs,gt,z.shape,target,p['x'],p['y'],c['radius_m']);vg=vs.GetGeoTransform();r0=round((vg[3]-gt[3])/gt[5]);c0=round((vg[0]-gt[0])/gt[1]);rr,cc=np.where(m);ind=(rr+r0)*z.shape[1]+cc+c0
        row,detail=summarize(p,ind,tree,shrub,gt,z.shape,c,lock,cfg['direction_rings_m'],cfg['direction_thresholds']);rows.append(row);details[p['id']]=detail;indices[p['id']]=ind
        if 'raw_km2' in p and abs(row['raw_km2']-p['raw_km2'])>1e-9:raise ValueError('Original mask/area mismatch')
    for p in points:process(p,root/'additional_visibility'/f'{p["id"]}_{c["radius_m"]}.tif')
    # Diverse parent selection independent of later obstruction outcomes.
    parents=[]
    def add(p,min_distance=400):
        if all(math.hypot(p['x']-q['x'],p['y']-q['y'])>=min_distance for q in parents):parents.append(p)
    for p in sorted(points,key=lambda p:-p['selective_score'])[:3]:add(p,0)
    for row in sorted(rows,key=lambda r:-r['directional_20']):
        if len(parents)>=6:break
        add(lookup[row['id']])
    while len(parents)<cfg['parent_count']:
        remaining=[p for p in points if p not in parents]
        if not remaining:break
        add(max(remaining,key=lambda p:min(math.hypot(p['x']-q['x'],p['y']-q['y']) for q in parents)))
    seen={(p['row'],p['col']) for p in points};alternatives=[]
    from shapely.geometry import shape,Point
    domain=shape(read(root/'intake.json')['geometry']['observer'])
    for parent in parents:
        for dx in [-cfg['offset_m'],0,cfg['offset_m']]:
            for dy in [-cfg['offset_m'],0,cfg['offset_m']]:
                if not(dx or dy):continue
                x,y=parent['x']+dx,parent['y']+dy;r=math.floor((y-gt[3])/gt[5]);co=math.floor((x-gt[0])/gt[1])
                x,y=core.xy(gt,r,co)
                if (r,co) in seen or not(0<=r<z.shape[0] and 0<=co<z.shape[1] and observer[r,co]) or not domain.covers(Point(x,y)):continue
                if len(alternatives)>=cfg['max_alternatives']:break
                p=dict(id=f'V{len(alternatives)+1:03}',kind='setup_alternative',parent=parent['id'],x=x,y=y,row=r,col=co,access=core.UNKNOWN);seen.add((r,co));alternatives.append(p);lookup[p['id']]=p
                path=out/'viewsheds'/f'{p["id"]}.tif';core.viewshed(ds,path,x,y,c['radius_m'],c['eye_m'],c['target_m'],c['curvature']);process(p,path)
    directional_rows=[dict(id=ident,selected_target_sector=any(t['azimuth_start']==d['start'] and t['id'] in detail['selections']['target_heuristic']['patch_ids'] for t in detail['patches']),**d) for ident,detail in details.items() for d in detail['directions']]
    csvwrite(out/'directional_cover.csv',directional_rows)
    dump(out/'parents.json',parents);dump(out/'alternatives.json',alternatives);dump(out/'details.json',details)
    for key in ['baseline_score','distance_control','target_heuristic','directional_20','directional_40']:
        for n,r in enumerate(sorted([r for r in rows if r[key] is not None],key=lambda r:(-r[key],r['id'])),1):r[key+'_rank']=n
        for r in rows:r.setdefault(key+'_rank',None)
    csvwrite(out/'components.csv',rows);dump(out/'components.json',rows)
    # Coarse sampled rays: same target samples across all obstruction scenarios.
    bestalts=sorted([r for r in rows if r['kind']=='setup_alternative'],key=lambda r:-r['directional_20'])[:2];subset=parents+[lookup[r['id']] for r in bestalts];rayrows=[];samples={};rng=np.random.default_rng(cfg['seed'])
    for p in subset:
        ids=indices[p['id']];sample=np.sort(rng.choice(ids,min(cfg['ray_count'],len(ids)),replace=False)) if len(ids) else []
        samples[p['id']]=list(map(int,sample))
        for height in cfg['canopy_heights_m']:
            for threshold in cfg['canopy_thresholds']:
                heights=np.where(np.isfinite(tree),np.where(tree>=threshold,height,0),np.nan)
                result=[ray(z,heights,gt[1],(p['row'],p['col']),tuple(np.unravel_index(int(v),z.shape)),c['eye_m'],c['target_m'],c['curvature']) for v in sample]
                sr,sc=np.unravel_index(sample,z.shape)
                weights=model.searchability(np.nan_to_num(tree[sr,sc],nan=.25),np.nan_to_num(shrub[sr,sc],nan=.3))*model.distance_response(np.hypot(sr-p['row'],sc-p['col'])*gt[1],lock['comparison'])
                path_clear=np.array([not any(v[k] for k in ['observer','intermediate','unknown','terrain']) for v in result])
                counts={key:sum(r[key] for r in result) for key in ['observer','intermediate','target','unknown','terrain']}
                known_clear=sum(not any(r[k] for k in ['observer','intermediate','target','unknown','terrain']) for r in result)
                rayrows.append(dict(id=p['id'],height_m=height,threshold=threshold,n=len(result),sampled_target_index=float(weights.mean()) if len(weights) else 0.,sampled_path_screen_index=float((weights*path_clear).mean()) if len(weights) else 0.,**counts,scenario_clear_rays=known_clear,clear_fraction=known_clear/len(result) if result else None))
    for height in cfg['canopy_heights_m']:
        for threshold in cfg['canopy_thresholds']:
            scenario=[r for r in rayrows if r['height_m']==height and r['threshold']==threshold]
            for rank,row in enumerate(sorted(scenario,key=lambda r:-r['sampled_path_screen_index']),1):row['subset_screen_rank']=rank
    csvwrite(out/'coarse_ray_scenarios.csv',rayrows);dump(out/'ray_samples.json',dict(grid_shape=list(z.shape),flat_cell_indices=samples,seed=cfg['seed']))
    # Overlap based on complete known low-tree target pixels, never extrapolated sampled rays.
    leaders=sorted(rows,key=lambda r:-r['directional_20'])[:5];reviewids=list(dict.fromkeys([p['id'] for p in parents]+[r['id'] for r in leaders]+[r['id'] for r in bestalts]));pairs=[]
    for i,ident in enumerate(reviewids):
        aa=indices[ident];aa=aa[(tree.ravel()[aa]<.1)&np.isfinite(shrub.ravel()[aa])];a=set(aa.tolist())
        for other in reviewids[i+1:]:
            bb=indices[other];bb=bb[(tree.ravel()[bb]<.1)&np.isfinite(shrub.ravel()[bb])];b=set(bb.tolist());pairs.append(dict(a=ident,b=other,known_low_tree_shared_km2=len(a&b)*abs(gt[1]*gt[5])/1e6,jaccard=len(a&b)/len(a|b) if a|b else None))
    csvwrite(out/'overlap_low_tree.csv',pairs);dump(out/'review_ids.json',reviewids)
    from .vegetation_packet import render
    render(cfg,c,rows,details,lookup,indices,tree,shrub,ds)
    import gc
    gc.collect()
    from .vegetation_lidar import run as fine
    fine(cfg,c,lookup[cfg['audit_candidate']])
    from .vegetation_packet import report
    report(cfg,c,rows,rayrows,parents)
    for p,h in preserved.items():
        if digest(p)!=h:raise ValueError('Preserved evidence changed: '+p)
    size=sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
    if size>cfg['disk_bytes']:raise ValueError('Output budget exceeded')
    dump(out/'COMPLETE.json',dict(wall_s=time.monotonic()-start,peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,total_bytes=size,original_count=len(points),alternative_count=len(alternatives),source_config=cfg,script_hashes={str(p):digest(p) for p in Path('glassing').glob('vegetation*.py')},original_integrity_passed=True))
    dump(out/'manifest.json',{str(p):digest(p) for p in out.rglob('*') if p.is_file() and p.name!='manifest.json'});print('Completed',out,flush=True)
if __name__=='__main__':main()
