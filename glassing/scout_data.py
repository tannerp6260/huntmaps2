"""Small official-source acquisition for the provisional hunt packet."""
import json,urllib.parse
from pathlib import Path
from .acquire import Fetcher,dump
from .correction_data import SERVICES


def query(f,name,url,bounds):
    meta=f.json(name+'_meta.json',url+'?f=json',provider='Official agency GIS')
    if 'fields' not in meta:raise ValueError('Not a feature layer: '+url)
    params=dict(f='geojson',where='1=1',geometry=','.join(map(str,bounds)),geometryType='esriGeometryEnvelope',inSR=32613,spatialRel='esriSpatialRelIntersects',outFields='*',outSR=4326)
    data=f.json(name+'.geojson',url+'/query?'+urllib.parse.urlencode(params),provider=('USGS National Map NHD' if 'nationalmap.gov' in url else 'Colorado Department of Transportation' if 'codot.gov' in url else 'USFS/BLM official GIS'),crs='EPSG:4326',license=meta.get('copyrightText') or 'not stated by layer',acquisition_date='unknown unless source attributes provide date')
    if data.get('exceededTransferLimit'):raise ValueError('Truncated query '+name)
    print(name,len(data.get('features',[])),flush=True)
    return data


def initial_acquire(c):
    f=Fetcher(c['inputs'],c['download_bytes']);bounds=c['access_extents'][-1]
    for name,(service,layer) in SERVICES.items():
        query(f,name,f'https://apps.fs.usda.gov/arcx/rest/services/EDW/{service}/MapServer/{layer}',bounds)
    for name,url in [('rec_sites','https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecInfraRecreationSites_02/MapServer/0'),('rec_subsites','https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecInfraRecreationSites_02/MapServer/1'),('blm_routes','https://gis.blm.gov/arcgis/rest/services/transportation/BLM_Natl_GTLF/MapServer/0')]:query(f,name,url,bounds)
    dump(Path(c['inputs'])/'adaptive_extent.json',dict(previous_bounds=c['access_extents'][0],expanded_bounds=bounds,reason='Previous 30km inventory had zero recreation points and missing BLM/county connecting travel. Expanded to 50km and added BLM routes plus alternate USFS recreation inventory; not an inference of inaccessibility.',new_download_bytes=f.used))




def acquire(c):
    """Reconstruct exactly the accepted official-source snapshot, or fail on change."""
    from .acquire import digest
    lock=json.load(open('configs/scouting_sources.lock.json'));f=Fetcher(c['inputs'],c['download_bytes'])
    for name,entry in lock.items():
        meta={k:v for k,v in entry.items() if k not in ['url','sha256','bytes','elapsed_since_fetcher_start_s','retrieved_utc']}
        path=f.get(name,entry['url'],**meta)
        if digest(path)!=entry['sha256']:raise ValueError('Live source changed: '+name+'; retain archived snapshot; do not silently replace controls')
    print('Verified/retrieved',len(lock),'locked source files; new bytes',f.used,flush=True)

if __name__=='__main__':acquire(json.loads(Path('configs/scouting.json').read_text()))
