"""Bounded public access inventory, retaining provider attributes and limitations."""
import json
from pathlib import Path
import urllib.parse
from .acquire import Fetcher,dump

SERVICES={
 'trails':('EDW_TrailNFSPublish_01',0),
 'roads':('EDW_RoadBasic_01',0),
 'closed_roads':('EDW_RoadBasic_01',1),
 'ownership':('EDW_BasicOwnership_01',0),
 'access_points':('EDW_RecreationOpportunities_01',0),
 'mvum_roads':('EDW_MVUM_01',1),
 'mvum_trails':('EDW_MVUM_01',2)}


def acquire(c):
    root=Path(c['inputs']);f=Fetcher(root,c['download_bytes'])
    for name,(service,layer) in SERVICES.items():
        url=f'https://apps.fs.usda.gov/arcx/rest/services/EDW/{service}/MapServer/{layer}'
        meta=f.json(name+'_metadata.json',url+'?f=json',provider='USFS Enterprise Data Warehouse')
        params=dict(f='geojson',where='1=1',geometry=','.join(map(str,c['access_bounds_utm'])),geometryType='esriGeometryEnvelope',inSR=32613,spatialRel='esriSpatialRelIntersects',outFields='*',outSR=4326)
        data=f.json(name+'.geojson',url+'/query?'+urllib.parse.urlencode(params),provider='USFS EDW',crs='EPSG:4326',acquisition_date='unknown; provider attributes and last-edit metadata retained',license=meta.get('copyrightText','unknown'),purpose='mapped evidence only; not legal/physical access certification')
        if data.get('exceededTransferLimit'):raise ValueError(name+' query truncated; narrow AOI or paginate before using')
        print(name,len(data.get('features',[])),flush=True)
    dump(root/'acquisition.json',dict(new_bytes=f.used,bounds_utm=c['access_bounds_utm']))


def imagery(c,wide=False):
    """Small orthophoto clips with locked source records; human review only."""
    import datetime as dt
    root=Path(c['inputs']);f=Fetcher(root,c['download_bytes']);work=Path(c['work'])
    cc=json.loads(Path(c['comparison_config']).read_text());points={p['id']:p for p in json.loads((Path(cc['work'])/'pool.json').read_text())}
    ids=json.loads((work/'attention_summary.json').read_text())['review_ids']
    service='https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer'
    f.json('naip_service.json',service+'?f=json',provider='USGS NAIP imagery service')
    records=[]
    for i in ids:
        p=points[i];radius=2000 if wide else 300;tag='_wide' if wide else '';size=1000 if wide else 600
        bbox=[p['x']-radius,p['y']-radius,p['x']+radius,p['y']+radius]
        params=dict(f='json',where="Category=1",geometry=','.join(map(str,bbox)),geometryType='esriGeometryEnvelope',inSR=32613,spatialRel='esriSpatialRelIntersects',outFields='*',returnGeometry='false')
        data=f.json(i+tag+'_naip_records.json',service+'/query?'+urllib.parse.urlencode(params),provider='USGS/USDA NAIP',purpose='source date and image lock for review')
        fs=data.get('features',[])
        if not fs:records.append(dict(id=i,status='No intersecting source records'));continue
        year=max(x['attributes']['Year'] for x in fs);chosen=[x['attributes'] for x in fs if x['attributes']['Year']==year]
        imageids=[x['OBJECTID'] for x in chosen]
        params=dict(f='image',bbox=','.join(map(str,bbox)),bboxSR=32613,imageSR=32613,size=f'{size},{size}',format='tiff',mosaicRule=json.dumps(dict(mosaicMethod='esriMosaicLockRaster',lockRasterIds=imageids)),renderingRule=json.dumps(dict(rasterFunction='NaturalColor')))
        dates=[dt.datetime.fromtimestamp(x['acquisition_date']/1000,dt.timezone.utc).date().isoformat() if x.get('acquisition_date') else 'unknown' for x in chosen]
        path=f.get(i+tag+'_naip.tif',service+'/exportImage?'+urllib.parse.urlencode(params),provider='USGS/USDA NAIP',license='Public domain USDA/USGS; service terms retained',acquisition_dates=dates,year=year,object_ids=imageids,crs='EPSG:32613',export_resolution_m=2*radius/size,purpose='Review imagery only, not independent adjudication')
        from osgeo import gdal
        ds=gdal.Open(str(path))
        if ds is None or ds.RasterCount<3:raise ValueError('Invalid imagery response')
        records.append(dict(id=i,status='acquired; human review pending',path=str(path),dates=dates,source_records=chosen,export_resolution_m=2*radius/size))
    dump(work/('wide_imagery.json' if wide else 'imagery.json'),records)
    if not wide:imagery(c,wide=True)
