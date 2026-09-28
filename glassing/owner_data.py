"""Small, bounded source planner. Never creates a substitute study area."""
import json, math, time, urllib.parse, urllib.request
from pathlib import Path
from osgeo import gdal
from shapely.geometry import box
from shapely.ops import transform
from .transfer import source,project
from .acquire import Fetcher,digest,dump,TNM

KEYS=['dem','tree','shrub','herb','summer','winter']
CPW='https://services5.arcgis.com/ttNGmDvKQA7oeDQ3/arcgis/rest/services/CPWSpeciesData/FeatureServer'

def covers(path,bounds,epsg):
    ds=gdal.Open(str(path))
    if not ds:return False
    # Warp a coarse coverage probe; final prepare validates every DEM cell.
    probe=gdal.Warp('',ds,format='MEM',dstSRS=f'EPSG:{epsg}',outputBounds=bounds,width=32,height=32,dstNodata=-9999,outputType=gdal.GDT_Float32)
    import numpy as np
    a=probe.ReadAsArray();return bool(np.isfinite(a).all() and (a!=-9999).all())

def grid_bounds(c,inp):
    x,y,X,Y=inp['acquisition_requests']['terrain']['bounds'];r=c['resolution_m']
    return [math.floor(x/r)*r,math.floor(y/r)*r,math.ceil(X/r)*r,math.ceil(Y/r)*r]

def cached(c,inp):
    bounds=grid_bounds(c,inp);found={}
    for manifest in sorted(Path('data').glob('**/manifest.json')):
        for name,meta in json.loads(manifest.read_text()).items():
            p=manifest.parent/name
            if not p.is_file():continue
            key=next((k for k in KEYS if name==k+'.tif' or name==k+'.geojson'),None)
            if name.startswith('USGS_13_') and name.endswith('.tif'):key='dem'
            if key is None or c['data'].get(key):continue
            if key in ['summer','winter']:
                query=urllib.parse.parse_qs(urllib.parse.urlparse(meta.get('url','')).query)
                try:
                    b=list(map(float,query['geometry'][0].split(',')));sr=int(query['inSR'][0]);region=transform(project(c['epsg'],sr),box(*bounds))
                    if not box(*b).covers(region):continue
                except (KeyError,ValueError):continue
            elif not covers(p,bounds,c['epsg']):continue
            if digest(p)!=meta.get('sha256'):raise ValueError('Corrupt cached source: '+str(p))
            spec=dict(meta,path=str(p))
            if key=='dem':spec['vertical_units']='m';spec.setdefault('vertical_datum','Unknown; confirm source metadata, no vertical correction')
            found[key]=spec
    c['data'].update(found);return found

def plan(c,inp):
    b=grid_bounds(c,inp);epsg=c['epsg'];ll=transform(project(epsg,4326),box(*b)).bounds;items=[]
    # Only the existing Colorado range hypothesis is supported automatically.
    if not box(-109.06,36.99,-102.04,41.01).covers(box(*ll)):
        return [],['Automatic seasonal range selection supports Colorado only. Supply data.summer and data.winter authoritative polygon descriptors, or use a Colorado area.']
    for key in ['tree','shrub','herb']:
        if c['data'].get(key):continue
        layer=f'{key}_westernconus_year_data';params=dict(service='WCS',version='1.0.0',request='GetCoverage',coverage=f'mrlc_{layer}:{layer}',crs=f'EPSG:{epsg}',response_crs=f'EPSG:{epsg}',bbox=','.join(map(str,b)),resx=30,resy=30,format='GeoTIFF',time='2023-01-01T00:00:00Z',interpolation='nearest neighbor')
        items.append(dict(key=key,name=key+'.tif',url=f'https://dmsdata.cr.usgs.gov/geoserver/mrlc_{layer}/wcs?'+urllib.parse.urlencode(params),estimated_bytes=math.ceil((b[2]-b[0])/30)*math.ceil((b[3]-b[1])/30)*8,provider='USGS RCMAP',acquisition_date='2023 annual product',license='USGS public domain',units='percent fractional cover; not optical transmission'))
    for key,layer in [('summer',99),('winter',105)]:
        if c['data'].get(key):continue
        params=dict(where='1=1',geometry=','.join(map(str,b)),geometryType='esriGeometryEnvelope',inSR=epsg,outSR=4326,spatialRel='esriSpatialRelIntersects',outFields='*',returnGeometry='true',f='geojson')
        items.append(dict(key=key,name=key+'.geojson',url=f'{CPW}/{layer}/query?'+urllib.parse.urlencode(params),estimated_bytes=10000000,provider='Colorado Parks and Wildlife',acquisition_date='unknown; service current at retrieval',license='CPW source terms; verify redistribution'))
    errors=[]
    if not c['data'].get('dem'):
        params=dict(datasets='National Elevation Dataset (NED) 1/3 arc-second',bbox=','.join(map(str,ll)),prodFormats='GeoTIFF',max=50)
        url=TNM+'?'+urllib.parse.urlencode(params)
        print('Querying USGS catalog metadata (no DEM download yet):',url,flush=True)
        try:
            with urllib.request.urlopen(url,timeout=45) as response:
                raw=response.read(5000001)
            if len(raw)>5000000:raise ValueError('catalog metadata exceeds 5 MB limit')
            catalog=json.loads(raw);eligible=[]
            for p in catalog.get('items',[]):
                bb=p.get('boundingBox',{})
                if all(k in bb for k in ['minX','minY','maxX','maxY']) and box(bb['minX'],bb['minY'],bb['maxX'],bb['maxY']).covers(box(*ll)):eligible.append(p)
            if not eligible:errors.append('No single USGS 1/3 arc-second tile covers the terrain halo. Supply a mosaicked bare-earth DEM at data.dem in scouting.json with metre elevations, vertical datum and SHA256. Catalog: '+url)
            else:
                p=max(eligible,key=lambda p:p.get('publicationDate',''));size=p.get('sizeInBytes')
                if not size:errors.append('USGS tile has no download size. Inspect catalog and configure data.dem; no unestimated DEM download will start: '+url)
                else:items.append(dict(key='dem',name='dem.tif',url=p['downloadURL'],estimated_bytes=int(size),provider='USGS 3DEP',acquisition_date=p.get('dateCreated','unknown'),publication_date=p.get('publicationDate','unknown'),license='USGS public domain',vertical_units='m',vertical_datum='NAVD88 per CONUS 3DEP specification; tile-specific confirmation pending',catalog_request=url,title=p.get('title','unknown'),resolution='1/3 arc-second',horizontal_crs='read from GeoTIFF'))
        except Exception as e:errors.append('USGS catalog unavailable: '+str(e)+'. Supply data.dem descriptor in scouting.json. Catalog request: '+url)
    return items,errors

def provision(c,inp,root,download):
    start=time.monotonic()
    b=grid_bounds(c,inp)
    if (b[2]-b[0])*(b[3]-b[1])/c['resolution_m']**2>c['max_cells']:raise ValueError('Buffered grid exceeds max_cells; reduce observer area before acquiring data')
    reused=cached(c,inp)
    for k in KEYS:
        if c['data'].get(k):source(c['data'][k])
    missing=[k for k in KEYS if not c['data'].get(k)]
    items=[];errors=[];used=0
    if missing:items,errors=plan(c,inp)
    estimate=sum(p['estimated_bytes'] for p in items)
    dump(root/'download_plan.json',dict(items=items,estimated_bytes=estimate,estimate_note='DEM catalog bytes; cover raster conservative uncompressed estimate; ranges 10 MB allowance each. Streaming cap still enforced.',errors=errors))
    print(f'Acquisition plan: {len(items)} files, estimated {estimate/1e6:.1f} MB; cap {c["download_bytes"]/1e6:.0f} MB. Cached sources reused: {list(reused)}',flush=True)
    if download and not errors and items:
        if estimate>c['download_bytes']:errors.append('Estimate exceeds --max-download-mb; no bulk downloads started.')
        else:
            f=Fetcher(root/'downloads',c['download_bytes'])
            for item in items:
                meta={k:v for k,v in item.items() if k not in ['key','name','url','estimated_bytes']}
                try:
                    p=f.get(item['name'],item['url'],**meta)
                    if item['key'] in ['summer','winter']:
                        v=json.loads(p.read_text())
                        if v.get('error') or v.get('exceededTransferLimit') or v.get('type')!='FeatureCollection':raise ValueError('Incomplete or invalid agency polygon response')
                    elif not covers(p,grid_bounds(c,inp),c['epsg']):raise ValueError('Downloaded raster does not cover terrain support')
                    c['data'][item['key']]=dict(f.entries[item['name']],path=str(p))
                except Exception as e:errors.append(item['key']+': '+str(e));break
            used=f.used
    missing=[k for k in KEYS if not c['data'].get(k)]
    dump(root/'acquisition.json',dict(new_download_bytes=used,cached_keys=list(reused),elapsed_s=time.monotonic()-start,missing=missing,errors=errors,paid_cost_usd=0))
    if missing or errors:
        text='# Required data\n\nNothing missing was substituted. Missing: '+', '.join(missing)+'.\n\n'+'\n'.join(errors)+'\n\nReview download_plan.json. Repeat the same command with --download to execute the plan, or supply each missing data.KEY in scouting.json as {"path":"...", "sha256":"...", "provider":"...", "acquisition_date":"unknown", "license":"..."}. DEM also needs vertical_units="m" and vertical_datum.\n\nImagery and access are optional: data.imagery takes checked raster descriptors; access.entries, access.routes and access.offtrail_allowed require documented sources. No approach is inferred when these are absent. See docs/glassing/transfer/INPUTS.md.\n'
        (root/'DATA_REQUIRED.md').write_text(text)
        return False
    return True
