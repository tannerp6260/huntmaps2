"""Provisional actual-hunt desktop opportunities, isolated from experimental controls."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1';os.environ.setdefault('GDAL_CACHEMAX','128')
import argparse,json,csv,time,resource,signal
from pathlib import Path
import numpy as np
from osgeo import gdal,ogr
from shapely.geometry import shape,mapping,box
from shapely.ops import transform,unary_union
from shapely.validation import make_valid
from . import core,compare,attention,comparison_models as model
from .acquire import dump,digest
from .correction_access import projector
from .correct import csvwrite


def control(c):
    entries=json.loads(Path(c['frozen_control']).read_text())
    for p,h in entries.items():
        if digest(p)!=h:raise ValueError('Frozen control changed: '+p)
    return len(entries)


def masks_for_hunt(c,ds,a,gt):
    xy=projector();gm=unary_union([transform(xy,shape(f['geometry'])) for f in json.load(open('data/gmu54/gmu54.geojson'))['features']]);gm=make_valid(gm) if not gm.is_valid else gm
    fs=[]
    for f in json.load(open(Path(c['inputs'])/'ownership.geojson'))['features']:
        if f['properties']['ownerclassification']=='USDA FOREST SERVICE':
            g=transform(xy,shape(f['geometry']));fs.append(make_valid(g) if not g.is_valid else g)
    private=[make_valid(transform(xy,shape(f['geometry']))) for f in json.load(open(Path(c['inputs'])/'surface_management.geojson'))['features'] if f['properties']['adm_code']=='PRI']
    forest=unary_union(fs).difference(unary_union(private))
    def burn(g):return core.polygon_mask(ogr.CreateGeometryFromWkb(g.wkb),a.shape,gt,ds.GetProjection())
    return gm,forest,burn(gm),burn(gm.intersection(forest))


def support(c):
    cc=json.load(open(c['comparison_config']));b,base,ds,a,gt,masks=compare.load(cc);layers=compare.read_layers(cc)
    root=Path(c['work']);root.mkdir(exist_ok=True);gm,forest,unit,public=masks_for_hunt(c,ds,a,gt)
    core.write_raster(root/'provisional_target_FS_GMU54.tif',public.astype('uint8'),gt,ds.GetProjection())
    core.write_raster(root/'target_permission_unknown.tif',(unit&~public).astype('uint8'),gt,ds.GetProjection())
    points={p['id']:p for p in json.load(open(base/'candidates.json'))};grad=np.gradient(a.astype('float64'),gt[1]);grad[0]*=-1
    rows=[];records={};m=c['attention']
    for i in c['candidates']+[c['random_control']]:
        p=points[i];records[i]={}
        for name,mask in [('frozen_pilot',masks['target']),('pilot_FS',public&masks['target']),('restored_FS',public),('unit_unresolved_upper',unit)]:
            cm=dict(masks,target=mask);v=compare.components(cc,b,base,ds,a,gt,cm,layers,p,grad,stress=False)
            hs=model.habitat(v['summer'],v['shrub'],v['herb'],'summer',cc['habitat_floor']);hw=model.habitat(v['winter'],v['shrub'],v['herb'],'winter',cc['habitat_floor'])
            reward=((1-m['winter_mix'])*hs+m['winter_mix']*hw)*v['search']*model.distance_response(v['d'],cc)*v['perspective']*model.sunlight(v['gx'],v['gy'],v['dx'],v['dy'],v['dz'],cc['light'],cc)
            ps=attention.patches(v['dx'],v['dy'],reward,.0001,m['width_deg'],m['band_m'],2000);sel=attention.select(ps,m['budget_minutes'],m['rate_km2_min'],m['overhead_minutes'])
            yy=gt[3]+(np.arange(a.shape[0])+.5)*gt[5];xx=gt[0]+(np.arange(a.shape[1])+.5)*gt[1];disk=(xx[None,:]-p['x'])**2+(yy[:,None]-p['y'])**2<=2000**2
            row=dict(id=i,support=name,full_disk_grid_km2=float(disk.sum()*.0001),terrain_missing_km2=float((disk&((a==-9999)|~np.isfinite(a))).sum()*.0001),target_support_km2=float((mask&disk).sum()*.0001),raw_visible_km2=v['total'],near_visible_km2=float((v['d']<=1000).sum()*.0001),far_visible_km2=float((v['d']>1000).sum()*.0001),open_cover_visible_km2=float((v['tree']<.1).sum()*.0001),sparse_cover_visible_km2=float(((v['tree']>=.1)&(v['tree']<.4)).sum()*.0001),selective_score=sel['score'],selected_patch_ids=','.join(map(str,sel['patch_ids'])),unknown_cover_fraction=float(v['uncertain'].mean()) if len(v['d']) else 0)
            rows.append(row);records[i][name]=dict(summary=row,patches=ps,selection=sel)
        f=records[i]['frozen_pilot']['summary'];r=records[i]['restored_FS']['summary']
        print(i,'pilot',round(f['raw_visible_km2'],4),'restored FS',round(r['raw_visible_km2'],4),flush=True)
    csvwrite(root/'support_comparison.csv',rows);dump(root/'support.json',records)
    pilot=shape(json.load(open(base/'study.json'))['geometry']);values=a[masks['target']]
    dump(root/'context.json',dict(pilot_selection=json.load(open('data/gmu54/pilot.json'))['selection'],pilot_km2=pilot.area/1e6,unit_km2=gm.area/1e6,pilot_fraction_unit=pilot.area/gm.area,pilot_elevation_m=[float(values.min()),float(np.median(values)),float(values.max())],pilot_FS_fraction=float(public[masks['target']].mean()),unit_geometry=mapping(gm),pilot_geometry=mapping(pilot),target_policy='Provisional FS land within official GMU54; exclude NON-FS/unknown from restored eligibility. No known intersecting closure identified in reviewed official index; current trip-date orders and permission verification remain outstanding. Unresolved upper bound is NOT eligible hunting land.',boundary_meaning='Experimental centroid crop; no hunting restriction along its edges. Terrain retained outside all target masks.'))


def fine(c):
    from .correction_geometry import sample,gridcheck
    cc=json.load(open(c['comparison_config']));b,base,ds,a,gt,masks=compare.load(cc);points={p['id']:p for p in json.load(open(base/'candidates.json'))}
    source=Path(cc['inputs'])/'fine_dem.tif'
    if digest(source)!=cc['fine_dem']['sha256']:raise ValueError('Fine terrain changed')
    root=Path(c['work'])/'fine';root.mkdir(exist_ok=True);rows=[]
    for i in ['C0068','C0095','C0049']:
        p=points[i];x,y=p['x'],p['y'];fine_ds=gdal.Warp(str(root/(i+'_dem1m.tif')),str(source),dstSRS=ds.GetProjection(),outputBounds=[x-450.5,y-450.5,x+450.5,y+450.5],xRes=1,yRes=1,resampleAlg='bilinear',dstNodata=-9999)
        dy,dx=np.mgrid[-360:361:10,-360:361:10];xx=x+dx;yy=y+dy;ok=dx*dx+dy*dy<=360**2
        for name,surf,ox,oy in [('control10m',ds,x,y),('fine_original',fine_ds,x,y)]+[(f'offset_{ox}_{oy}',fine_ds,x+ox,y+oy) for ox,oy in [(-20,0),(20,0),(0,-20),(0,20)]]:
            vs=core.viewshed(surf,root/f'{i}_{name}_view.tif',ox,oy,400,b['eye_m'],b['target_m'],b['curvature'])
            val=sample(vs,xx[ok],yy[ok])==1
            rr=int((oy-gt[3])/gt[5]);col=int((ox-gt[0])/gt[1])
            rows.append(dict(id=i,case=name,x=ox,y=oy,common_support_radius_m=360,visible_km2=float(val.sum()*.0001),technical_observer_mask=bool(masks['observer'][rr,col]),ground_m=float(sample(surf,ox,oy)),field_feasible='unverified'))
    csvwrite(root/'checks.csv',rows);dump(root/'summary.json',dict(cases=rows,source=str(source),source_project='CO_WestCentral_2019_A19',vertical='metres NAVD88 catalog; no vertical correction',warning='Matched 360m disk, 400m viewshed calculation. Common target centres; no full-radius re-ranking. Bare earth does not measure foreground branches or safe footing. C0064 prior investigation preserved, not repeated.'))
    print('Fine checks:',len(rows),flush=True)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['acquire','support','fine','access','packet','all','verify']);ap.add_argument('--config',default='configs/scouting.json');args=ap.parse_args();c=json.load(open(args.config));root=Path(c['work']);root.mkdir(parents=True,exist_ok=True)
    signal.alarm(c['runtime_s']);resource.setrlimit(resource.RLIMIT_AS,(c['memory_mb']*1024**2,resource.RLIM_INFINITY));start=time.monotonic();n=control(c)
    if args.stage!='acquire':
        for name,entry in json.load(open('configs/scouting_sources.lock.json')).items():
            if digest(Path(c['inputs'])/name)!=entry['sha256']:raise ValueError('Locked source changed '+name)
    for stage in ['support','fine','access','packet'] if args.stage=='all' else [args.stage]:
        if stage=='acquire':
            from .scout_data import acquire
            acquire(c)
        elif stage=='support':support(c)
        elif stage=='fine':fine(c)
        elif stage=='access':
            from .scout_access import run
            run(c)
        elif stage=='packet':
            from .scout_packet import run
            run(c)
    control(c)
    manifest=Path(c['inputs'])/'manifest.json'
    for name,entry in json.load(open(manifest)).items():
        if digest(Path(c['inputs'])/name)!=entry['sha256']:raise ValueError('Source changed '+name)
    size=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    if size>c['disk_bytes']:raise ValueError('Output budget exceeded')
    sourcefiles=list(Path('glassing').glob('scout*.py'))+[Path(args.config),Path('configs/scouting_sources.lock.json'),manifest,Path(c['frozen_control'])]
    dump(root/'identity.json',dict(config=c,sha256={str(p):digest(p) for p in sourcefiles},gdal=gdal.__version__,numpy=np.__version__))
    metrics=dict(stage=args.stage,wall_s=time.monotonic()-start,peak_rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,output_bytes=size,frozen_files=n)
    with open(root/'execution.jsonl','a') as f:f.write(json.dumps(metrics)+'\n')
    print(json.dumps(metrics),flush=True)

if __name__=='__main__':main()
