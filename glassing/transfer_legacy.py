"""Thin AOI/import adapter over the frozen terrain and attention experiment."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
os.environ.setdefault('GDAL_CACHEMAX','96')
import argparse,csv,json,math,time,resource,signal,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from osgeo import gdal,ogr,osr
from shapely.geometry import shape,Point,box,mapping
from shapely.ops import transform,unary_union
from . import core,compare,attention,comparison_models as model
from .acquire import digest,dump,srs,Fetcher


def read(path):return json.loads(Path(path).read_text())
def project(src,dst):
    tr=osr.CoordinateTransformation(srs(src),srs(dst))
    return lambda x,y,z=None:tr.TransformPoint(float(x),float(y))[:2]


def polygon(path,epsg,allow_empty=False):
    value=read(path)
    if value.get('crs'):raise ValueError('Use RFC7946 longitude/latitude GeoJSON; remove ambiguity by exporting WGS84')
    fs=value.get('features',[]) if value.get('type')=='FeatureCollection' else [value]
    gs=[]
    for f in fs:
        g=shape(f.get('geometry',f))
        if g.geom_type not in ['Polygon','MultiPolygon'] or not g.is_valid or g.is_empty:raise ValueError('Valid nonempty polygon required: '+str(path))
        xmin,ymin,xmax,ymax=g.bounds
        if not(-180<=xmin<=xmax<=180 and -90<=ymin<=ymax<=90):raise ValueError('GeoJSON must use lon/lat degrees')
        gs.append(transform(project(4326,epsg),g))
    if not gs:
        if allow_empty:return __import__('shapely.geometry',fromlist=['Polygon']).Polygon()
        raise ValueError('Empty polygon collection')
    return unary_union(gs)


def manual(path,epsg,area,provenance):
    path=Path(path);records=[]
    if path.suffix.lower()=='.gpx':
        for k,w in enumerate(ET.parse(path).findall('.//{*}wpt')):
            name=w.find('{*}name');records.append(dict(id=name.text if name is not None and name.text else f'unnamed_{k+1}',longitude=w.attrib['lon'],latitude=w.attrib['lat'],gpx_xml=ET.tostring(w,encoding='unicode')))
    elif path.suffix.lower()=='.csv':
        with path.open(newline='') as f:records=list(csv.DictReader(f))
    elif path.suffix.lower() in ['.geojson','.json']:
        data=read(path)
        if data.get('crs'):raise ValueError('Manual GeoJSON must be RFC7946')
        for f in data['features']:
            if f['geometry']['type']!='Point':raise ValueError('Manual collection must contain only points')
            lo,la=f['geometry']['coordinates'][:2];records.append(dict(f['properties'],id=f['properties'].get('id',f.get('id')),longitude=lo,latitude=la))
    else:raise ValueError('Manual format must be GPX waypoints, GeoJSON points or CSV')
    if not records:raise ValueError('No manual waypoints; GPX tracks are not waypoint selections')
    points=[];ids=set()
    for n,r in enumerate(records):
        if not r.get('id'):raise ValueError('Manual point needs an id/name')
        ident=str(r['id'])
        if ident in ids:raise ValueError('Duplicate manual ID/name: '+ident)
        ids.add(ident);lo,la=float(r['longitude']),float(r['latitude'])
        if not(math.isfinite(lo) and math.isfinite(la) and -180<=lo<=180 and -90<=la<=90):raise ValueError('Invalid manual coordinates')
        x,y=project(4326,epsg)(lo,la)
        if not area.covers(Point(x,y)):raise ValueError('Manual point outside observer polygon: '+ident+'; revise explicit search boundary, never move the point')
        points.append(dict(id=f'M{n+1:04}',group='manual',original_id=ident,longitude=lo,latitude=la,x=x,y=y,source_record=r,source_sha256=digest(path),source_path=str(path),selection_provenance=provenance,provenance=['user_manual_import'],access=core.UNKNOWN))
    return points


def work(c):
    root=Path(c['work']).resolve()
    protected={Path(p).resolve().parent for p in read(c['frozen_control'])}
    if any(root==p or root in p.parents or p in root.parents for p in protected):raise ValueError('Output path overlaps preserved artifacts')
    marker=root/'transfer_owner.json'
    if root.exists() and any(root.iterdir()) and not marker.exists():raise ValueError('Nonempty output directory is not owned by transfer adapter')
    root.mkdir(parents=True,exist_ok=True)
    if not marker.exists():dump(marker,dict(component='glassing.transfer',input_kind=c['input_kind']))
    return root


def verify(c):
    frozen=read(c['frozen_control'])
    for p,h in frozen.items():
        if digest(p)!=h:raise ValueError('Preserved artifact changed: '+p)
    for p,h in read(c['model_lock'])['implementation'].items():
        if digest(p)!=h:raise ValueError('Frozen model implementation changed: '+p)
    return len(frozen)


def intake(c):
    root=work(c)
    if not 0<=c['season']['winter_mix']<=1 or c['observation_minutes']<=0:raise ValueError('Invalid common seasonal mixture or effort budget')
    if c['radius_m']%read(c['model_lock'])['attention']['band_m']:raise ValueError('Radius must be a multiple of the frozen 500m patch band')
    missing=[c[k] for k in ['observer_polygon','manual_points'] if not c.get(k) or not Path(c[k]).is_file()]
    if missing:
        result=dict(status='WAITING_FOR_HUNTER_INPUTS',missing=missing,message='No replacement AOI or generated manual selections will be chosen. Supply polygon and manual waypoints; see docs/glassing/transfer/INPUTS.md.')
        dump(root/'intake.json',result);return result
    sr=srs(c['epsg'])
    if not sr.IsProjected() or abs(sr.GetLinearUnits()-1)>1e-9:raise ValueError('Analysis EPSG must be projected metres')
    if c['radius_m']<=0 or c['resolution_m']<=0:raise ValueError('Positive radius and resolution required')
    area=polygon(c['observer_polygon'],c['epsg']);pts=manual(c['manual_points'],c['epsg'],area,c['manual_provenance'])
    # Observer domain and target support are deliberately different geometries.
    domain=area.buffer(c['radius_m'],resolution=64);targets=domain
    if c.get('target_limit'):targets=targets.intersection(polygon(c['target_limit'],c['epsg']))
    for p in c['target_exclusions']:targets=targets.difference(polygon(p,c['epsg']))
    observers=area
    for p in c['observer_exclusions']:observers=observers.difference(polygon(p,c['epsg']))
    for p in pts:
        if not observers.covers(Point(p['x'],p['y'])):raise ValueError('Manual point excluded by observer policy: '+p['original_id'])
    halo=domain.buffer(2*c['resolution_m']);access=polygon(c['access']['extent_polygon'],c['epsg']) if c['access'].get('extent_polygon') else area.buffer(max(c['access']['buffer_m'],c['radius_m']))
    if not access.covers(domain):raise ValueError('Access-data extent must encompass observation context; enlarge it explicitly')
    result=dict(status='INPUTS_IMPORTED',kind=c['input_kind'],manual_count=len(pts),observer_area_km2=observers.area/1e6,target_area_km2=targets.area/1e6,target_policy=c['target_policy'],source_hashes={str(p):digest(p) for p in [c['observer_polygon'],c['manual_points']]+c['target_exclusions']+c['observer_exclusions']+([c['target_limit']] if c.get('target_limit') else [])+([c['access']['extent_polygon']] if c['access'].get('extent_polygon') else [])},geometry={k:mapping(g) for k,g in [('observer',observers),('target',targets),('target_context',domain),('terrain_halo',halo),('access_extent',access)]},acquisition_requests={k:dict(epsg=c['epsg'],bounds=list(g.bounds),wgs84_bounds=list(transform(project(c['epsg'],4326),g).bounds)) for k,g in [('terrain',halo),('access',access)]},warning='Permission/actionability unknown unless explicitly evidenced. Terrain halo never masked by ownership. Access buffer is an initial query extent, not proof of connectivity.')
    dump(root/'intake.json',result);dump(root/'manual_import.json',pts)
    return result


def source(spec):
    if not spec or not spec.get('path'):raise ValueError('Missing configured source descriptor')
    if not spec.get('sha256') or digest(spec['path'])!=spec['sha256']:raise ValueError('Source checksum missing or changed: '+spec['path'])
    return spec['path']


def fetch(c):
    """Optional bounded adapter for exact requests prepared from intake extents."""
    root=work(c);f=Fetcher(root/'downloads',c['download_bytes'])
    for spec in c.get('downloads',[]):
        p=f.get(spec['name'],spec['url'],provider=spec['provider'],acquisition_date=spec.get('acquisition_date','unknown'),license=spec.get('license','not stated'))
        if digest(p)!=spec['sha256']:raise ValueError('Downloaded source differs from pinned revision')
    return dict(new_bytes=f.used,requests=len(c.get('downloads',[])),note='No automatic centroid selection; exact provider requests depend on hunter intake geometry.')


def prepare(c):
    root=work(c);inp=intake(c)
    if inp['status']!='INPUTS_IMPORTED':raise ValueError('Supply hunter inputs before prepare')
    dem=c['data']['dem'];path=source(dem)
    if dem.get('vertical_units')!='m':raise ValueError('Explicit metre vertical units required')
    res=c['resolution_m'];g=shape(inp['geometry']['terrain_halo']);xmin,ymin,xmax,ymax=g.bounds;bounds=[math.floor(xmin/res)*res,math.floor(ymin/res)*res,math.ceil(xmax/res)*res,math.ceil(ymax/res)*res]
    if (bounds[2]-bounds[0])*(bounds[3]-bounds[1])/res**2>c['max_cells']:raise ValueError('Grid budget exceeded; narrow hunter AOI or explicitly adjust budget')
    ds=gdal.Warp(str(root/'dem.tif'),path,dstSRS=srs(c['epsg']).ExportToWkt(),outputBounds=bounds,xRes=res,yRes=res,resampleAlg='bilinear',dstNodata=-9999,outputType=gdal.GDT_Float32,warpMemoryLimit=96,creationOptions=['COMPRESS=DEFLATE'])
    a,gt,_=core.validate(ds,'m',c['max_cells']);masks={}
    for name in ['observer','target']:
        masks[name]=core.polygon_mask(ogr.CreateGeometryFromJson(json.dumps(inp['geometry'][name])),a.shape,gt,ds.GetProjection());core.write_raster(root/(name+'.tif'),masks[name].astype('uint8'),gt,ds.GetProjection())
        if not masks[name].any():raise ValueError('Empty '+name+' mask')
    # Core candidate generator consumes its existing contract, with no manual seeds.
    bc=dict(work=str(root),resolution_m=res,epsg=c['epsg'],vertical_units='m',max_cells=c['max_cells'],seed=c['seed'],candidate_count=c['candidate_count'],spacing_m=c['spacing_m'],manual_points=[])
    dump(root/'core_config.json',bc);dump(root/'prepared.json',dict(config=bc,implementation_sha256=digest(core.__file__),dem_sha256=digest(root/'dem.tif'),target_sha256=digest(root/'target.tif'),observer_sha256=digest(root/'observer.tif')))
    unknown=np.zeros(a.shape,bool)
    for name in ['tree','shrub','herb','summer','winter']:
        spec=c['data'][name];path=source(spec)
        if name in ['summer','winter']:
            geom=polygon(path,c['epsg'],allow_empty=True);v=core.polygon_mask(ogr.CreateGeometryFromWkb(geom.wkb),a.shape,gt,ds.GetProjection()).astype('uint8') if not geom.is_empty else np.zeros(a.shape,'uint8')
        else:
            tmp=gdal.Warp('',path,format='MEM',dstSRS=ds.GetProjection(),outputBounds=bounds,width=a.shape[1],height=a.shape[0],resampleAlg='near',outputType=gdal.GDT_Float32,dstNodata=-9999);v=tmp.ReadAsArray();valid=np.isfinite(v)&(v>=0)&(v<=100);unknown|=~valid;v=np.where(valid,v/100.,-9999).astype('float32')
        core.write_raster(root/(name+'.tif'),v,gt,ds.GetProjection(),-9999 if name in ['tree','shrub','herb'] else None)
    core.write_raster(root/'vegetation_unknown.tif',unknown.astype('uint8'),gt,ds.GetProjection());core.write_raster(root/'actionability.tif',np.zeros(a.shape,'uint8'),gt,ds.GetProjection())
    dump(root/'input_identity.json',dict(config=c,adapter_sha256=digest(__file__),runtime=dict(gdal=gdal.__version__,numpy=np.__version__),config_hash=__import__('hashlib').sha256(json.dumps(c,sort_keys=True).encode()).hexdigest(),sources=c['data'],model_sha256=digest(c['model_lock']),intake=inp,vertical_reference=dem.get('vertical_datum','unknown; no correction performed')))


def candidates(c):
    root=work(c);core.generate(read(root/'core_config.json'));auto=read(root/'candidates.json');ds,a,gt,masks=core.load_grid(read(root/'core_config.json'))
    for p in auto:p.update(group='automated',id='A'+p['id'][1:])
    man=read(root/'manual_import.json')
    for p in man:
        p['row']=math.floor((p['y']-gt[3])/gt[5]);p['col']=math.floor((p['x']-gt[0])/gt[1]);x,y=core.xy(gt,p['row'],p['col']);p['containing_cell_centre_offset_m']=math.hypot(x-p['x'],y-p['y'])
        if not masks['observer'][p['row'],p['col']]:raise ValueError('Manual location falls in a raster-excluded boundary cell; inspect boundary, never snap silently')
    dump(root/'pool.json',auto+man)


def evaluate(c,points):
    root=work(c);bc=read(root/'core_config.json');ds,a,gt,masks=core.load_grid(bc);layers={}
    for k in ['tree','shrub','herb','summer','winter','vegetation_unknown','actionability']:
        v=gdal.Open(str(root/(k+'.tif'))).ReadAsArray();layers[k]=np.where(v<0,np.nan,v) if k in ['tree','shrub','herb'] else v
    lock=read(c['model_lock']);mc=dict(lock['comparison'],work=str(root),light=c['season']['light']);b=dict(bc,baseline_radius_m=c['radius_m'],eye_m=c['eye_m'],target_m=c['target_m'],curvature=c['curvature']);grad=np.gradient(a.astype('float64'),gt[1]);grad[0]*=-1;settings=lock['attention'];area=gt[1]**2/1e6;rows=[];patches={}
    for p in points:
        v=compare.components(mc,b,root,ds,a,gt,masks,layers,p,grad,original=False,stress=False);mix=c['season']['winter_mix']
        reward=((1-mix)*model.habitat(v['summer'],v['shrub'],v['herb'],'summer',mc['habitat_floor'])+mix*model.habitat(v['winter'],v['shrub'],v['herb'],'winter',mc['habitat_floor']))*v['search']*model.distance_response(v['d'],mc)*v['perspective']*model.sunlight(v['gx'],v['gy'],v['dx'],v['dy'],v['dz'],mc['light'],mc)
        ps=attention.patches(v['dx'],v['dy'],reward,area,settings['width_deg'],settings['band_m'],c['radius_m']);sel=attention.select(ps,c['observation_minutes'],settings['rate_km2_min'],settings['overhead_minutes']);patches[p['id']]=dict(patches=ps,selection=sel)
        rows.append(dict(p,raw_km2=v['total'],within_1km_km2=float((v['d']<=1000).sum()*area),beyond_1km_km2=float((v['d']>1000).sum()*area),low_tree_cover_km2=float(((v['tree']<.1)&~v['uncertain']).sum()*area),unknown_cover_fraction=float(v['uncertain'].mean()) if len(v['d']) else None,selective_score=sel['score'],foreground_cover_mean=v['foreground_cover_mean'],foreground_unknown_fraction=v['foreground_unknown_fraction'],light=c['season']['light_label']))
    return rows,patches


def score(c):
    root=work(c);rows,ps=evaluate(c,read(root/'pool.json'));dump(root/'scores.json',rows);dump(root/'patches.json',ps)
    # Refinement is diagnostic only: symmetric around each group's leaders, never
    # folded into the predeclared primary candidate pool or retuned coefficients.
    ds,a,gt,masks=core.load_grid(read(root/'core_config.json'));q=c['refinement'];extra=[];centres=[];seen=set()
    for group in ['automated','manual']:
        leaders=sorted([r for r in rows if r['group']==group],key=lambda r:(-r['selective_score'],r['id']))[:q['max_centres_per_group']]
        for p in leaders:
            centres.append(p['id'])
            for dx in range(-q['radius_m'],q['radius_m']+1,q['spacing_m']):
                for dy in range(-q['radius_m'],q['radius_m']+1,q['spacing_m']):
                    if not(dx or dy) or dx*dx+dy*dy>q['radius_m']**2:continue
                    x,y=p['x']+dx,p['y']+dy;r=math.floor((y-gt[3])/gt[5]);col=math.floor((x-gt[0])/gt[1])
                    if not(0<=r<a.shape[0] and 0<=col<a.shape[1] and masks['observer'][r,col]):continue
                    key=(p['id'],r,col)
                    if key in seen:continue
                    seen.add(key);extra.append(dict(id=f'R{len(extra)+1:04}',group='refinement',parent=p['id'],x=x,y=y,row=r,col=col,provenance=['symmetric_local_density_diagnostic'],access=core.UNKNOWN))
    if len(extra)>q['max_points']:raise ValueError('Refinement budget exceeded; reduce BOTH groups symmetrically in configuration')
    refined,_=evaluate(c,extra)
    dump(root/'refinement.json',dict(points=refined,centres=centres,primary_pool_unchanged=True,warning='Local resolution/candidate-density sensitivity only; no field evidence'))
    leading=sorted([p for p in rows if p['group']=='automated'],key=lambda p:(-p['selective_score'],p['id']))[:min(5,c['review']['max_automated'])]+[p for p in rows if p['group']=='manual'];overlap=[];vis={}
    for p in leading:
        vs=gdal.Open(str(root/'additional_visibility'/f'{p["id"]}_{c["radius_m"]}.tif'));_,_,mask=core.score_mask(vs,gt,a.shape,masks['target'],p['x'],p['y'],c['radius_m']);vg=vs.GetGeoTransform();r=round((vg[3]-gt[3])/gt[5]);co=round((vg[0]-gt[0])/gt[1]);rr,cc=np.where(mask);vis[p['id']]=set(((rr+r)*a.shape[1]+cc+co).tolist())
    for n,p in enumerate(leading):
        for other in leading[n+1:]:
            u,v=vis[p['id']],vis[other['id']];inter=len(u&v);union=len(u|v);overlap.append(dict(a=p['id'],b=other['id'],shared_km2=inter*gt[1]**2/1e6,jaccard=inter/union if union else None,fraction_a=inter/len(u) if u else None,fraction_b=inter/len(v) if v else None,distance_m=math.hypot(p['x']-other['x'],p['y']-other['y'])))
    dump(root/'leading.json',leading);dump(root/'overlap.json',overlap)


def guard_products(root):
    for name,h in read(root/'products.json').items():
        if digest(root/name)!=h:raise ValueError('Derived product changed: '+name+'; rerun producing stage')

def guard_prepared(c):
    root=work(c);old=read(root/'input_identity.json')
    if old.get('adapter_sha256')!=digest(__file__) or old.get('runtime')!=dict(gdal=gdal.__version__,numpy=np.__version__):raise ValueError('Adapter/runtime changed; prepare again')
    if old['config']!=c or old['model_sha256']!=digest(c['model_lock']):raise ValueError('Configuration/model changed; prepare again')
    for k,h in old['intake']['source_hashes'].items():
        if digest(k)!=h:raise ValueError('Hunter input changed; prepare again')
    for k in ['dem','tree','shrub','herb','summer','winter']:source(c['data'][k])


def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['intake','fetch','prepare','candidates','score','access','packet','all','verify']);ap.add_argument('--config',default='configs/transfer.template.json');args=ap.parse_args();c=read(args.config);root=work(c);start=time.monotonic();signal.alarm(c['runtime_s']);resource.setrlimit(resource.RLIMIT_AS,(c['memory_mb']*1024**2,resource.RLIM_INFINITY));n=verify(c)
    for stage in ['prepare','candidates','score','access','packet'] if args.stage=='all' else [args.stage]:
        if stage in ['candidates','score','access','packet']:
            guard_prepared(c);guard_products(root)
        if stage=='intake':print(json.dumps(intake(c)),flush=True)
        elif stage=='verify' and (root/'input_identity.json').exists():
            guard_prepared(c);guard_products(root)
        elif stage=='fetch':print(json.dumps(fetch(c)),flush=True)
        elif stage=='prepare':prepare(c)
        elif stage=='candidates':candidates(c)
        elif stage=='score':score(c)
        elif stage=='access':
            from .transfer_access import run
            run(c)
        elif stage=='packet':
            from .transfer_packet import run
            run(c)
        products=read(root/'products.json') if (root/'products.json').exists() else {}
        if stage=='prepare':products={}
        names={'prepare':['manual_import.json','prepared.json','core_config.json','input_identity.json']+[k+'.tif' for k in ['dem','target','observer','tree','shrub','herb','summer','winter','vegetation_unknown','actionability']], 'candidates':['pool.json'], 'score':['scores.json','patches.json','refinement.json','leading.json','overlap.json'], 'access':['approaches.json']}.get(stage,[])
        for name in names:products[name]=digest(root/name)
        if names:dump(root/'products.json',products)
    verify(c);size=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    if size>c['disk_bytes']:raise ValueError('Output disk budget exceeded')
    metrics=dict(stage=args.stage,wall_s=time.monotonic()-start,peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,output_bytes=size,preserved_files=n,input_kind=c['input_kind'])
    with (root/'execution.jsonl').open('a') as f:f.write(json.dumps(metrics)+'\n')
    dump(root/'implementation.json',{str(p):digest(p) for p in [Path(args.config),Path(c['model_lock'])]+list(Path('glassing').glob('transfer*.py'))});print(json.dumps(metrics),flush=True)

if __name__=='__main__':main()
