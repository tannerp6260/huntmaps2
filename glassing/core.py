"""Grid, candidate and visibility contracts. All scores are planimetric area."""
import csv
import json
import math
from pathlib import Path
import time
import xml.etree.ElementTree as ET
import numpy as np
from scipy.ndimage import gaussian_filter, uniform_filter, map_coordinates
from osgeo import gdal, ogr, osr
from .acquire import digest, dump, srs

gdal.UseExceptions()
ogr.UseExceptions()
UNKNOWN = 'UNKNOWN_ACCESS_NOT_FIELD_READY'


def write_raster(path, a, gt, projection, nodata=None):
    dtype = gdal.GDT_Byte if a.dtype == np.uint8 else gdal.GDT_Float32
    ds = gdal.GetDriverByName('GTiff').Create(str(path), a.shape[1], a.shape[0], 1, dtype,
          options=['COMPRESS=DEFLATE','TILED=YES'])
    ds.SetGeoTransform(gt); ds.SetProjection(projection)
    b = ds.GetRasterBand(1)
    if nodata is not None:
        b.SetNoDataValue(nodata)
    b.WriteArray(a)
    ds.FlushCache()
    return ds


def validate(ds, units='m', max_cells=3000000):
    if ds is None or ds.RasterCount != 1:
        raise ValueError('Expected one-band DEM')
    if ds.RasterXSize * ds.RasterYSize > max_cells:
        raise ValueError('Grid cell budget exceeded')
    sr = osr.SpatialReference(wkt=ds.GetProjection())
    if not sr.IsProjected() or abs(sr.GetLinearUnits()-1) > 1e-9:
        raise ValueError('DEM must have projected metric CRS')
    gt = ds.GetGeoTransform()
    if gt[2] or gt[4] or gt[1] <= 0 or gt[5] >= 0 or abs(gt[1]+gt[5]) > 1e-8:
        raise ValueError('Expected north-up square grid')
    if units != 'm':
        raise ValueError('Vertical units must explicitly be metres; convert before use')
    a = ds.ReadAsArray()
    nd = ds.GetRasterBand(1).GetNoDataValue()
    if not np.isfinite(a).all() or (nd is not None and np.any(a == nd)):
        raise ValueError('NoData terrain: cannot infer unobstructed sightlines; supply complete DEM')
    return a, gt, sr


def polygon_mask(geometry, shape, gt, projection):
    vector = ogr.GetDriverByName('Memory').CreateDataSource('')
    layer = vector.CreateLayer('polygon', srs=osr.SpatialReference(wkt=projection), geom_type=ogr.wkbUnknown)
    feat = ogr.Feature(layer.GetLayerDefn()); feat.SetGeometry(geometry); layer.CreateFeature(feat)
    ds = gdal.GetDriverByName('MEM').Create('',shape[1],shape[0],1,gdal.GDT_Byte)
    ds.SetGeoTransform(gt); ds.SetProjection(projection)
    gdal.RasterizeLayer(ds,[1],layer,burn_values=[1])
    return ds.ReadAsArray().astype(bool)


def rect(x0,y0,x1,y1):
    return ogr.CreateGeometryFromWkt(f'POLYGON (({x0} {y0},{x1} {y0},{x1} {y1},{x0} {y1},{x0} {y0}))')


def prepare(c):
    root = Path(c['work']); root.mkdir(parents=True,exist_ok=True)
    res = c['resolution_m']; halo = max(c['radii_m'])+2*res
    projection = srs(c['epsg']).ExportToWkt()
    if c['mode'] == 'synthetic':
        # Fictitious metric terrain, deliberately never presented as real Colorado terrain.
        study = rect(320000,4300000,328000,4308000)
        gt = (320000-halo,res,0,4308000+halo,0,-res)
        n = int((8000+2*halo)/res)
        yy,xx = np.mgrid[:n,:n]*res
        a = (2500 + 220*np.sin(xx/800)*np.cos(yy/1300)
             + 380*np.exp(-((xx-7000)/350)**2) + 0.012*yy).astype('float32')
        ds = write_raster(root/'dem.tif',a,gt,projection,-9999)
        source = {'kind':'synthetic fixture','acquisition_date':'not applicable','vertical_datum':c['vertical_datum']}
    else:
        inputs = json.loads((Path(c['inputs'])/'inputs.json').read_text())
        pilot = json.loads(Path(inputs['pilot']).read_text())
        if pilot['epsg'] != c['epsg']:
            raise ValueError('Pilot CRS must match configured grid')
        study = ogr.CreateGeometryFromJson(json.dumps(pilot['geometry']))
        xmin,xmax,ymin,ymax = study.GetEnvelope()
        bounds = [math.floor((xmin-halo)/res)*res,math.floor((ymin-halo)/res)*res,
                  math.ceil((xmax+halo)/res)*res,math.ceil((ymax+halo)/res)*res]
        if (bounds[2]-bounds[0])*(bounds[3]-bounds[1])/res**2 > c['max_cells']:
            raise ValueError('Grid cell budget exceeded before warp')
        manifest = json.loads((Path(c['inputs'])/'manifest.json').read_text())
        for path in inputs['dem']:
            if digest(path) != manifest[Path(path).name]['sha256']:
                raise ValueError('Source checksum mismatch')
        ds = gdal.Warp(str(root/'dem.tif'), inputs['dem'], dstSRS=projection, outputBounds=bounds,
                       xRes=res,yRes=res,resampleAlg='bilinear',dstNodata=-9999,outputType=gdal.GDT_Float32,
                       multithread=False,warpMemoryLimit=128,creationOptions=['COMPRESS=DEFLATE','TILED=YES'])
        source = {'kind':'USGS 3DEP real terrain','inputs':inputs,'vertical_datum':c['vertical_datum'],
                  'source_manifest_sha256':digest(Path(c['inputs'])/'manifest.json')}
    a,gt,sr = validate(ds,c['vertical_units'],c['max_cells'])
    study_mask = polygon_mask(study,a.shape,gt,ds.GetProjection())
    target = study_mask.copy()
    observer = study_mask.copy()
    # Optional explicit exclusion polygons in the grid CRS; never applied to DEM.
    for key, mask in [('target_exclusions',target),('observer_exclusions',observer)]:
        for geom in c.get(key,[]):
            mask[polygon_mask(ogr.CreateGeometryFromJson(json.dumps(geom)),a.shape,gt,projection)] = False
    for name,mask in [('study',study_mask),('target',target),('observer',observer)]:
        write_raster(root/(name+'.tif'),mask.astype('uint8'),gt,projection)
    # Unknown feasibility is separate from the technical observer-domain mask.
    access = np.where(observer,2,0).astype('uint8')  # 0 outside/excluded; 2 unknown; no verified cells
    write_raster(root/'access.tif',access,gt,projection)
    dump(root/'study.json',dict(epsg=c['epsg'],geometry=json.loads(study.ExportToJson()),area_m2=study.GetArea()))
    dump(root/'prepared.json',dict(source=source,grid=dict(shape=list(a.shape),geotransform=gt,epsg=c['epsg']),
        dem_sha256=digest(root/'dem.tif'),target_sha256=digest(root/'target.tif'),observer_sha256=digest(root/'observer.tif'),
        config=c,implementation_sha256=digest(__file__),warning='No vertical transformation performed; terrain-only; unknown connected legal access'))


def load_grid(c):
    root = Path(c['work'])
    meta = json.loads((root/'prepared.json').read_text())
    # Stage outputs cannot silently mix configurations.
    if meta['config'] != c or meta['implementation_sha256'] != digest(__file__):
        raise ValueError('Configuration changed: rerun prepare and downstream stages')
    ds = gdal.Open(str(root/'dem.tif'))
    a,gt,sr = validate(ds,c['vertical_units'],c['max_cells'])
    masks = {}
    for name in ['target','observer']:
        m = gdal.Open(str(root/(name+'.tif')))
        if m.GetGeoTransform() != gt or m.GetProjection() != ds.GetProjection() or (m.RasterYSize,m.RasterXSize) != a.shape:
            raise ValueError('Mask grid mismatch')
        if digest(root/(name+'.tif')) != meta[name+'_sha256']:
            raise ValueError('Mask changed: rerun prepare')
        masks[name] = m.ReadAsArray().astype(bool)
    if digest(root/'dem.tif') != meta['dem_sha256']:
        raise ValueError('DEM changed: rerun prepare')
    return ds,a,gt,masks


def xy(gt,r,col):
    return gt[0]+(col+.5)*gt[1],gt[3]+(r+.5)*gt[5]


def generate(c):
    ds,a,gt,masks = load_grid(c)
    res = gt[1]; allowed = masks['observer']
    smooth = gaussian_filter(a.astype('float64'),sigma=3)
    gy,gx = np.gradient(smooth,res)
    slope = np.degrees(np.arctan(np.hypot(gx,gy)))
    tpi = smooth-uniform_filter(smooth,size=max(3,int(500/res)))
    bend = np.hypot(*np.gradient(slope,res))
    categories = {
        'bench_proxy':allowed & (slope<12) & (tpi>-10),
        'shoulder_proxy':allowed & (tpi>5) & (slope>=8) & (slope<30),
        'ridge_break_proxy':allowed & (tpi>8) & (bend>np.percentile(bend[allowed],60)),
        'background':allowed}
    rng = np.random.default_rng(c['seed'])
    points=[]; limit=c['candidate_count']; spacing=c['spacing_m']
    def add(r,col,provenance):
        x,y=xy(gt,r,col)
        nearest = next((p for p in points if (p['x']-x)**2+(p['y']-y)**2 < spacing**2),None)
        if nearest:
            nearest['provenance']=sorted(set(nearest['provenance']+[provenance]))
            return False
        if len(points)>=limit:
            return False
        points.append(dict(id=f'C{len(points)+1:04}',row=int(r),col=int(col),x=x,y=y,
                           provenance=[provenance],access=UNKNOWN,slope_deg=float(slope[r,col])))
        return True
    for point in c.get('manual_points',[]):
        r=int(math.floor((point['y']-gt[3])/gt[5])); col=int(math.floor((point['x']-gt[0])/res))
        if not (0<=r<a.shape[0] and 0<=col<a.shape[1] and allowed[r,col]):
            raise ValueError('Manual point outside observer domain or wrong coordinates')
        add(r,col,'manual:'+point.get('name','unnamed'))
    # One point per spatial stratum before terrain sampling protects broad coverage.
    rows,cols=np.where(allowed); side=max(2,int(math.sqrt(limit*.4)))
    for rr in np.array_split(np.arange(rows.min(),rows.max()+1),side):
        for cc in np.array_split(np.arange(cols.min(),cols.max()+1),side):
            sub=np.argwhere(allowed[np.ix_(rr,cc)])
            if len(sub):
                pick=sub[rng.integers(len(sub))]; add(rr[pick[0]],cc[pick[1]],'background_stratified')
    pools={k:rng.permutation(np.argwhere(v)) for k,v in categories.items()}
    cursors={k:0 for k in pools}
    while len(points)<limit:
        progressed=False
        for name,pool in pools.items():
            for _ in range(100):
                i=cursors[name]
                if i>=len(pool): break
                cursors[name]+=1; progressed=True
                r,col=pool[i]
                if add(r,col,name): break
        if not progressed: break
    if len(points)<limit:
        raise ValueError(f'Only {len(points)} separated candidates; reduce count/spacing explicitly')
    # Preserve all applicable terrain categories at the final snapped locations.
    for p in points:
        p['provenance']=sorted(set(p['provenance']+[k for k,m in categories.items() if k!='background' and m[p['row'],p['col']]]))
    dump(Path(c['work'])/'candidates.json',points)
    dump(Path(c['work'])/'candidates_meta.json',dict(prepared_sha256=digest(Path(c['work'])/'prepared.json'), candidates_sha256=digest(Path(c['work'])/'candidates.json')))


def viewshed(ds,path,x,y,radius,eye,target,curvature):
    """Small backend boundary; GDAL is the sole implemented engine."""
    a,gt,_=validate(ds)
    col=int((x-gt[0])/gt[1]); row=int((y-gt[3])/gt[5])
    if not (0<=row<a.shape[0] and 0<=col<a.shape[1]):
        raise ValueError('Observer outside terrain')
    if min(x-gt[0],gt[0]+a.shape[1]*gt[1]-x,gt[3]-y,y-(gt[3]+a.shape[0]*gt[5])) < radius:
        raise ValueError('Insufficient terrain halo for radius')
    result=gdal.ViewshedGenerate(ds.GetRasterBand(1),'GTiff',str(path),None,
        x,y,eye,target,1,0,0,255,curvature,gdal.GVM_Edge,radius)
    if result is None: raise RuntimeError('GDAL viewshed failed')
    result.FlushCache()
    return result


def score_mask(vs,gt,shape,target,x,y,radius):
    vg=vs.GetGeoTransform()
    col=int(round((vg[0]-gt[0])/gt[1])); row=int(round((vg[3]-gt[3])/gt[5]))
    v=vs.ReadAsArray()==1
    h,w=v.shape
    yy=vg[3]+(np.arange(h)+.5)*vg[5]; xx=vg[0]+(np.arange(w)+.5)*vg[1]
    d=np.hypot(yy[:,None]-y,xx[None,:]-x)
    visible=v & target[row:row+h,col:col+w] & (d<=radius)
    area=abs(gt[1]*gt[5])
    bands=[float(np.count_nonzero(visible & (d>lo) & (d<=hi))*area/1e6) for lo,hi in [(0,1000),(1000,2000),(2000,3000)]]
    # Include observer cell in the nearest band if eligible.
    bands[0]+=float(np.count_nonzero(visible & (d==0))*area/1e6)
    return float(visible.sum()*area/1e6),bands,visible


def visibility_dir(c):
    root=Path(c['work'])
    import hashlib
    signature=hashlib.sha256((digest(root/'prepared.json')+digest(root/'candidates.json')+
                             digest(__file__)+gdal.__version__).encode()).hexdigest()
    return root/'visibility'/signature[:20]


def compute(c):
    root=Path(c['work']); ds,a,gt,masks=load_grid(c)
    cm=json.loads((root/'candidates_meta.json').read_text())
    if cm != dict(prepared_sha256=digest(root/'prepared.json'),candidates_sha256=digest(root/'candidates.json')):
        raise ValueError('Stale candidates; rerun candidates')
    points=json.loads((root/'candidates.json').read_text()); cache=visibility_dir(c);cache.mkdir(parents=True,exist_ok=True)
    signature=digest(root/'prepared.json')+digest(root/'candidates.json')+gdal.__version__
    cache_meta=cache/'cache.json'
    if cache_meta.exists() and json.loads(cache_meta.read_text())['signature']!=signature:
        raise ValueError('Visibility cache belongs to different inputs; use a new work directory')
    dump(cache_meta,dict(signature=signature))
    results=[]; times=[]; reused=0
    for p in points:
        record=dict(p)
        for radius in c['radii_m']:
            t=time.monotonic(); path=cache/f'{p["id"]}_{radius}.tif'
            checksum=path.with_suffix('.sha256')
            if path.exists() and checksum.exists() and checksum.read_text().strip()==digest(path):
                vs=gdal.Open(str(path));reused+=1
            else:
                vs=viewshed(ds,path,p['x'],p['y'],radius,c['eye_m'],c['target_m'],c['curvature'])
                vs=None
                checksum.write_text(digest(path)+'\n');vs=gdal.Open(str(path))
            total,bands,_=score_mask(vs,gt,a.shape,masks['target'],p['x'],p['y'],radius)
            record[f'visible_km2_{radius}']=total
            if radius==c['baseline_radius_m']:
                record['visible_km2']=total
                record['bands_km2']=bands
            times.append(dict(radius_m=radius,seconds=time.monotonic()-t))
        results.append(record)
    results.sort(key=lambda p:(-p['visible_km2'],p['id']))
    for rank,p in enumerate(results,1):
        p.update(rank=rank,eye_m=c['eye_m'],target_m=c['target_m'],radius_m=c['baseline_radius_m'],curvature=c['curvature'])
        p['reason']=f'Terrain baseline: {p["visible_km2"]:.3f} km2 eligible target visible within {c["baseline_radius_m"]} m; no deer/access weighting'
    dump(root/'scores.json',results)
    dump(root/'visibility_metrics.json',dict(cache_directory=str(cache),cached=reused,evaluations=len(times),timings=times,
        seconds_by_radius={str(r):sum(t['seconds'] for t in times if t['radius_m']==r) for r in c['radii_m']}))
    dump(root/'scores_meta.json',dict(candidates_sha256=digest(root/'candidates.json'),prepared_sha256=digest(root/'prepared.json'),scores_sha256=digest(root/'scores.json')))


def profile_clearance(a,gt,p,r,col,eye,target,curvature):
    """Independent oversampled bilinear ray; excludes endpoint cells.

    A diagnostic, not a second viewshed engine. Near-tangent ray classifications
    can disagree with GDAL's inter-cell horizon interpolation.
    """
    r0,c0=p['row'],p['col']; dist=math.hypot(r-r0,col-c0)*gt[1]
    steps=max(3,int(math.hypot(r-r0,col-c0)*4))
    t=np.linspace(0,1,steps+1)[1:-1]
    z=map_coordinates(a.astype('float64'),[r0+t*(r-r0),c0+t*(col-c0)],order=1,mode='nearest')
    z=z-curvature*(t*dist)**2/(2*6378137.)
    end=float(a[r,col])+target-curvature*dist**2/(2*6378137.)
    line=(float(a[r0,c0])+eye)*(1-t)+end*t
    return float(np.min(line-z))


def inspect(c):
    root=Path(c['work']);ds,a,gt,masks=load_grid(c)
    points=json.loads((root/'scores.json').read_text());checks=[]
    rng=np.random.default_rng(543)
    for p in [points[0],points[len(points)//2],points[-1]]:
        vs=gdal.Open(str(visibility_dir(c)/f'{p["id"]}_{c["baseline_radius_m"]}.tif'))
        vg=vs.GetGeoTransform();v=vs.ReadAsArray()
        ro=int(round((vg[3]-gt[3])/gt[5]));co=int(round((vg[0]-gt[0])/gt[1]))
        rows,cols=np.where(masks['target'])
        d=np.hypot(rows-p['row'],cols-p['col'])*gt[1]
        eligible=np.where((d>200)&(d<c['baseline_radius_m']))[0]
        for i in rng.choice(eligible,min(40,len(eligible)),replace=False):
            r,col=int(rows[i]),int(cols[i]);clear=profile_clearance(a,gt,p,r,col,c['eye_m'],c['target_m'],c['curvature'])
            predicted=bool(v[r-ro,col-co]==1)
            checks.append(dict(kind='random',id=p['id'],row=r,col=col,clearance_m=clear,gdal_visible=predicted,ray_visible=clear>=0,agreement=predicted==(clear>=0)))
        for dr,dc in [(1,0),(-1,0),(0,1),(0,-1)]:
            for distance in [200,500,1000,1500]:
                r=p['row']+int(distance/gt[1])*dr;col=p['col']+int(distance/gt[1])*dc
                if not (0<=r<a.shape[0] and 0<=col<a.shape[1] and masks['target'][r,col]):continue
                clear=profile_clearance(a,gt,p,r,col,c['eye_m'],c['target_m'],c['curvature'])
                predicted=bool(v[r-ro,col-co]==1)
                checks.append(dict(kind='cardinal',id=p['id'],row=r,col=col,clearance_m=clear,
                                   gdal_visible=predicted,ray_visible=clear>=0,agreement=predicted==(clear>=0)))
    dump(root/'sightline_checks.json',dict(method='quarter-cell bilinear profile, explicit curvature, endpoints excluded',checks=checks,
        agreements=sum(x['agreement'] for x in checks),count=len(checks),
        warning='Discrete surface models differ; inspect disagreements, especially near-tangent rays. Not field validation.'))
    # Standard static artifact for human inspection; not another product UI.
    import os
    os.environ.setdefault('MPLCONFIGDIR',str(root/'.mplcache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    p=points[0];vs=gdal.Open(str(visibility_dir(c)/f'{p["id"]}_{c["baseline_radius_m"]}.tif'))
    vg=vs.GetGeoTransform();v=vs.ReadAsArray();extent=[gt[0],gt[0]+a.shape[1]*gt[1],gt[3]+a.shape[0]*gt[5],gt[3]]
    fig,axes=plt.subplots(1,2,figsize=(12,6))
    for ax in axes:
        ax.imshow(a,extent=extent,cmap='terrain');ax.set_aspect('equal');ax.set_xlabel('UTM easting (m)');ax.set_ylabel('UTM northing (m)')
        ax.contour(masks['target'],levels=[.5],extent=extent,origin='upper',colors='black',linewidths=.7)
    axes[0].scatter([q['x'] for q in points],[q['y'] for q in points],s=6,c='black')
    axes[0].set_title(f'{c["mode"]}: {len(points)} candidates, terrain context')
    overlay=np.ma.masked_where(v!=1,v)
    axes[1].imshow(overlay,extent=[vg[0],vg[0]+v.shape[1]*vg[1],vg[3]+v.shape[0]*vg[5],vg[3]],cmap='spring',alpha=.6,vmin=0,vmax=1)
    axes[1].scatter([p['x']],[p['y']],marker='*',s=100,c='red')
    axes[1].set_title(f'{p["id"]}: raw terrain visibility, UNKNOWN ACCESS')
    fig.tight_layout();fig.savefig(root/'review.png',dpi=150);plt.close(fig)


def export(c):
    root=Path(c['work']);load_grid(c)
    expected=dict(candidates_sha256=digest(root/'candidates.json'),prepared_sha256=digest(root/'prepared.json'),scores_sha256=digest(root/'scores.json'))
    if json.loads((root/'scores_meta.json').read_text())!=expected:raise ValueError('Stale scores')
    points=json.loads((root/'scores.json').read_text())
    transform=osr.CoordinateTransformation(srs(c['epsg']),srs(4326))
    rows=[]
    for p in points:
        lon,lat,_=transform.TransformPoint(p['x'],p['y'])
        row=dict(p,longitude=lon,latitude=lat,epsg=c['epsg'],vertical_datum=c['vertical_datum'])
        row['provenance']=';'.join(p['provenance'])
        row.pop('bands_km2')
        row.update({f'band_{i}_{i+1}_km_km2':v for i,v in enumerate(p['bands_km2'])})
        rows.append(row)
    with open(root/'candidates.csv','w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    gpkg=root/'baseline.gpkg'
    if gpkg.exists():gpkg.unlink()  # solely this command's generated output
    ds=ogr.GetDriverByName('GPKG').CreateDataSource(str(gpkg))
    layer=ds.CreateLayer('candidates_UNKNOWN_ACCESS',srs=srs(c['epsg']),geom_type=ogr.wkbPoint)
    for k,v in rows[0].items():
        typ=ogr.OFTInteger if isinstance(v,int) else ogr.OFTReal if isinstance(v,float) else ogr.OFTString
        layer.CreateField(ogr.FieldDefn(k,typ))
    for row in rows:
        feat=ogr.Feature(layer.GetLayerDefn())
        for k,v in row.items():feat.SetField(k,v)
        geom=ogr.Geometry(ogr.wkbPoint);geom.AddPoint_2D(row['x'],row['y']);feat.SetGeometry(geom);layer.CreateFeature(feat)
    study=json.loads((root/'study.json').read_text())
    sl=ds.CreateLayer('study_technical_test_only',srs=srs(c['epsg']),geom_type=ogr.wkbUnknown)
    feat=ogr.Feature(sl.GetLayerDefn());feat.SetGeometry(ogr.CreateGeometryFromJson(json.dumps(study['geometry'])));sl.CreateFeature(feat)
    ds=None
    gpx=ET.Element('gpx',version='1.1',creator='glassing terrain baseline',xmlns='http://www.topografix.com/GPX/1/1')
    for row in rows:
        wpt=ET.SubElement(gpx,'wpt',lat=str(row['latitude']),lon=str(row['longitude']))
        ET.SubElement(wpt,'name').text=row['id']+' UNKNOWN ACCESS'
        ET.SubElement(wpt,'desc').text=f'{row["reason"]}; provenance={row["provenance"]}; eye={c["eye_m"]}m target={c["target_m"]}m curvature={c["curvature"]}; {UNKNOWN}. Field-app review only.'
    ET.ElementTree(gpx).write(root/'review_only.gpx',encoding='utf-8',xml_declaration=True)
    dump(root/'field_ready_shortlist.json',dict(candidates=[],reason='No connected permitted approach or current closure evidence supplied'))
    # Native-format read-back, including CRS, counts and coordinates.
    ds=ogr.Open(str(gpkg));layer=ds.GetLayerByName('candidates_UNKNOWN_ACCESS')
    assert layer.GetFeatureCount()==len(rows) and layer.GetSpatialRef().IsSame(srs(c['epsg']))
    inverse=osr.CoordinateTransformation(srs(4326),srs(c['epsg']))
    for feat,row,wpt in zip(layer,rows,ET.parse(root/'review_only.gpx').getroot()):
        geom=feat.GetGeometryRef();assert abs(geom.GetX()-row['x'])<1e-6 and abs(geom.GetY()-row['y'])<1e-6
        x,y,_=inverse.TransformPoint(float(wpt.attrib['lon']),float(wpt.attrib['lat']))
        assert math.hypot(x-row['x'],y-row['y'])<.01
    dump(root/'export_validation.json',dict(candidate_count=len(rows),gpkg_epsg=c['epsg'],gpx_crs='EPSG:4326 lon/lat attributes',roundtrip_tolerance_m=.01,passed=True))
    report=f'''# {c['mode']} terrain baseline\n\n{len(rows)} candidates; baseline radius {c['baseline_radius_m']} m; eye {c['eye_m']} m;
target {c['target_m']} m; curvature coefficient {c['curvature']}.\n\nTop terrain-area candidate: {rows[0]['id']}, {rows[0]['visible_km2']:.3f} km².
This is not deer probability, glassability, habitat quality or hunting quality.
All candidates: **UNKNOWN ACCESS — NOT FIELD READY**. No field-ready shortlist.
The obstruction DEM includes the halo and is independent of excluded targets.
Vertical reference: {c['vertical_datum']}; no vertical datum transformation.
Trees, setup footing, connected access, closures, season and optics remain unverified.\n\nOpen baseline.gpkg and dem.tif / target.tif / observer.tif / access.tif in QGIS.
visibility/ contains content-keyed raw radius-bounded terrain masks (1 visible, 0 invisible/outside;
255 reserved NoData); score uses target.tif intersection and exact centre distance.
review.png shows terrain and representative raw visibility. review_only.gpx is for
field-app review; successful onX import has not been tested.\n\nSee metrics.jsonl for measured stage resources, visibility_metrics.json for per-radius
timing, sightline_checks.json for independent geometry diagnostics, and prepared.json
for frozen inputs/configuration. No manual or field performance comparison completed.\n'''
    (root/'REPORT.md').write_text(report)
