"""Local FastAPI application. No external basemap, arbitrary commands or run writes."""
import io
import json
import re
import sys
import threading
import uuid
import xml.etree.ElementTree as ET
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import Response,FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from shapely.geometry import mapping
from .catalog import ROOT,STATE,Run,runs,read,collection,feature
from .jobs import Jobs,write
from .tiles import tile
from .terrain import metadata, elevation_tile
from glassing.owner_area import choices,convert,LIMIT

STORE_LOCK=threading.RLock()

def valid_name(name):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}',name or ''):raise ValueError('Use a run name of 1–64 letters, digits, hyphens or underscores')
    return name

def create_app():
    jobs=Jobs()
    @asynccontextmanager
    async def life(app):
        yield
        jobs.shutdown()
    app=FastAPI(lifespan=life)
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','testserver'])
    app.state.jobs=jobs
    @app.middleware('http')
    async def local_only(request,call_next):
        if request.method not in ['GET','HEAD','OPTIONS']:
            origin=request.headers.get('origin')
            if request.headers.get('x-huntmaps')!='local' or (origin and urlparse(origin).netloc!=request.headers.get('host')):
                return Response('Local app request required',status_code=403)
        return await call_next(request)
    @app.exception_handler(ValueError)
    async def invalid(request,error):
        return __import__('fastapi').responses.JSONResponse(status_code=400,content={'detail':str(error)})

    @app.get('/api/runs')
    def get_runs():return runs()
    @app.get('/api/runs/{ident}')
    def get_run(ident):return Run(ident).summary()
    @app.get('/api/runs/{ident}/candidates/{candidate}')
    def get_candidate(ident,candidate):return Run(ident).candidate(candidate,True)
    @app.get('/api/runs/{ident}/sectors/{candidate}')
    def get_sectors(ident,candidate):return Run(ident).sectors(candidate)
    @app.get('/api/runs/{ident}/tiles/{layer}/{candidate}/{z}/{x}/{y}.png')
    def get_tile(ident,layer,candidate,z:int,x:int,y:int,color:int=0):
        return Response(tile(Run(ident),layer,candidate,z,x,y,color),media_type='image/png',headers={'Cache-Control':'private, max-age=3600'})
    @app.get('/api/runs/{ident}/terrain')
    def terrain_info(ident):return metadata(Run(ident))
    @app.get('/api/runs/{ident}/terrain/{z}/{x}/{y}.png')
    def terrain_tile(ident,z:int,x:int,y:int):
        return Response(elevation_tile(Run(ident),z,x,y),media_type='image/png',headers={'Cache-Control':'private, max-age=3600'})
    @app.get('/api/runs/{ident}/overlap')
    def overlap(ident,ids:str):
        r=Run(ident);selected=ids.split(',')
        if not 1<=len(selected)<=3 or len(set(selected))!=len(selected):raise ValueError('Compare one to three distinct setups')
        masks={i:r.mask(i)[0] for i in selected};area=abs(r.dem.GetGeoTransform()[1]*r.dem.GetGeoTransform()[5])/1e6
        return [dict(a=a,b=b,shared_km2=float((masks[a]&masks[b]).sum()*area)) for n,a in enumerate(selected) for b in selected[n+1:]]
    @app.get('/api/runs/{ident}/annotations')
    def annotations(ident):
        Run(ident);return read(STATE/'annotations'/(ident+'.json'),{})
    @app.put('/api/runs/{ident}/annotations/{candidate}')
    def annotate(ident,candidate,body:dict):
        r=Run(ident)
        if candidate not in r.points:raise ValueError('Unknown candidate')
        if body.get('status') not in ['unmarked','keep','reject','needs inspection']:raise ValueError('Choose keep, reject or needs inspection')
        if len(body.get('notes',''))>10000:raise ValueError('Notes are limited to 10,000 characters')
        path=STATE/'annotations'/(ident+'.json')
        with STORE_LOCK:
            data=read(path,{});data[candidate]=dict(status=body['status'],notes=body.get('notes',''));write(path,data)
        return data[candidate]
    @app.get('/api/runs/{ident}/export/{fmt}')
    def export(ident,fmt,ids:str):
        if fmt not in ['gpx','kml']:raise ValueError('Choose GPX or KML')
        r=Run(ident);selected=ids.split(',')
        if not selected or len(selected)>250 or len(set(selected))!=len(selected):raise ValueError('Select distinct observer waypoints')
        notes=read(STATE/'annotations'/(ident+'.json'),{})
        if fmt=='gpx':root=ET.Element('gpx',version='1.1',creator='HuntMaps2 local GUI',xmlns='http://www.topografix.com/GPX/1/1');doc=root
        else:root=ET.Element('kml',xmlns='http://www.opengis.net/kml/2.2');doc=ET.SubElement(root,'Document')
        for i in selected:
            p=r.candidate(i);name=f'{p["neighborhood"]+" / " if p["neighborhood"] else ""}{i}'+(f' (alternative to {p["parent"]})' if p['parent'] else '')
            desc='Provisional observer setup; legal access and sightlines unresolved. '+notes.get(i,{}).get('notes','')
            if fmt=='gpx':
                w=ET.SubElement(doc,'wpt',lat=str(p['latitude']),lon=str(p['longitude']));ET.SubElement(w,'name').text=name;ET.SubElement(w,'desc').text=desc
            else:
                w=ET.SubElement(doc,'Placemark');ET.SubElement(w,'name').text=name;ET.SubElement(w,'description').text=desc;ET.SubElement(ET.SubElement(w,'Point'),'coordinates').text=f'{p["longitude"]},{p["latitude"]},0'
        return Response(ET.tostring(root,encoding='utf-8',xml_declaration=True),media_type='application/xml',headers={'Content-Disposition':f'attachment; filename="{ident}-observers.{fmt}"'})

    @app.post('/api/imports')
    async def import_area(file:UploadFile=File(...),practice:bool=False):
        ext=Path(file.filename or '').suffix.lower()
        if ext not in ['.geojson','.json','.kml','.kmz']:raise ValueError('Import GeoJSON, KML or KMZ')
        data=await file.read(LIMIT+1)
        if len(data)>LIMIT:raise ValueError('Area file exceeds 10 MB')
        ident=uuid.uuid4().hex;folder=STATE/('practice-areas' if practice else 'imports')/ident;folder.mkdir(parents=True);path=folder/('area'+ext);path.write_bytes(data)
        items=choices(path)
        result=dict(id=ident,path=str(path),choices=[dict(number=str(n+1),name=name,geometry=mapping(g)) for n,(name,g) in enumerate(items)])
        write(folder/'import.json',result);return result
    @app.post('/api/plans')
    def prepare(body:dict):
        name=valid_name(body.get('name'));imp=body.get('import_id','')
        if not re.fullmatch('[a-f0-9]{32}',imp):raise ValueError('Import your observer polygon first')
        imported=read(STATE/'imports'/imp/'import.json')
        if not imported:raise ValueError('Import not found; import the area again')
        selection=str(body.get('polygon',''))
        if selection not in [v['number'] for v in imported['choices']]+['all']:raise ValueError('Explicitly select a polygon number or all')
        radius=int(body.get('radius_m',2000));minutes=int(body.get('observation_minutes',30));budget=int(body.get('max_download_mb',600));count=int(body.get('candidate_count',150))
        if radius not in [500,1000,1500,2000,2500,3000] or not 5<=minutes<=120 or not 1<=budget<=1900 or not 12<=count<=200:raise ValueError('Use a supported radius, 5–120 minutes, 12–200 candidates and 1–1900 MB download budget')
        ident=uuid.uuid4().hex;folder=STATE/'plans';folder.mkdir(parents=True,exist_ok=True)
        root=ROOT/'results'/name
        if root.exists():raise ValueError('This run name already exists. Resume its GUI job or use a new name.')
        c=read(ROOT/'configs/transfer.template.json');geometry=convert(imported['path'],folder/(ident+'-observer.geojson'),selection);lon,lat=geometry.centroid.coords[0]
        c.update(epsg=(32600 if lat>=0 else 32700)+min(60,int((lon+180)//6)+1),radius_m=radius,observation_minutes=minutes,candidate_count=count,normal_scouting=True,manual_points=None,download_bytes=budget*1000000)
        config=folder/(ident+'-config.json');write(config,c)
        p=dict(id=ident,name=name,area=imported['path'],polygon=selection,config=str(config),max_download_mb=budget,prepared=False)
        write(folder/(ident+'.json'),p)
        return jobs.start([sys.executable,'-u','-m','huntmaps_gui.worker','prepare',ident],'prepare',name,ident)
    @app.get('/api/plans/{ident}')
    def plan(ident):
        if not re.fullmatch('[a-f0-9]{32}',ident):raise ValueError('Unknown plan')
        p=read(STATE/'plans'/(ident+'.json'))
        if not p:raise ValueError('Unknown plan')
        return dict(p,boundary=read(ROOT/'results'/p['name']/'observer.geojson'),settings={k:v for k,v in read(p['config']).items() if k in ['radius_m','observation_minutes','candidate_count']})
    @app.post('/api/plans/{ident}/start')
    def start(ident,body:dict):
        p=plan(ident)
        if not p.get('prepared'):raise ValueError('Prepare and review the acquisition plan first')
        return jobs.start([sys.executable,'-u','-m','huntmaps_gui.worker','run',ident]+(['--download'] if body.get('download') is True else []),'baseline',p['name'],ident)
    @app.post('/api/plans/{ident}/prepare')
    def reprepare(ident):
        p=plan(ident)
        return jobs.start([sys.executable,'-u','-m','huntmaps_gui.worker','prepare',ident],'prepare',p['name'],ident)
    @app.get('/api/jobs')
    def get_jobs():return jobs.list()
    @app.post('/api/jobs/{ident}/cancel')
    def cancel(ident):
        if not re.fullmatch('[a-f0-9]{32}',ident):raise ValueError('Unknown job')
        return jobs.cancel(ident)

    dist=ROOT/'gui/frontend/dist'
    if dist.exists():
        app.mount('/assets',StaticFiles(directory=dist/'assets'),name='assets')
        @app.get('/')
        def index():return FileResponse(dist/'index.html')
    return app

