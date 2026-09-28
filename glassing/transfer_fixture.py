"""Offline, explicitly artificial portability fixture; never hunter selections."""
from pathlib import Path
import json
import numpy as np
from shapely.geometry import box,mapping,Point
from shapely.ops import transform
from .transfer import project,read
from .acquire import dump,digest,srs
from . import core


def create(config_path='configs/transfer.fixture.json',folder='runs/transfer_fixture_inputs',epsg=32612):
    root=Path(folder);root.mkdir(parents=True,exist_ok=True);x,y=450000,4200000;res=10;n=190;gt=(x-600,res,0,y+1300,0,-res);yy,xx=np.mgrid[:n,:n];z=(2100+80*np.sin(xx/18)+50*np.cos(yy/22)+.2*yy).astype('float32');proj=srs(epsg).ExportToWkt()
    def geo(name,g):dump(root/name,dict(type='FeatureCollection',features=[dict(type='Feature',properties={'fixture':'synthetic; not a selected hunting area'},geometry=mapping(transform(project(epsg,4326),g)))]))
    geo('observer.geojson',box(x,y,x+600,y+600));geo('range.geojson',box(x-2000,y-2000,x+3000,y+3000));geo('target_limit.geojson',box(x-400,y-500,x+1200,y+1200))
    core.write_raster(root/'dem.tif',z,gt,proj,-9999)
    for name,value in [('tree',12),('shrub',25),('herb',40)]:core.write_raster(root/(name+'.tif'),np.full((n,n),value,dtype='float32'),gt,proj,-9999)
    points=[]
    for ident,px,py in [('Fixture west',x+103.25,y+202.75),('Fixture east',x+482.6,y+389.2)]:
        lo,la=project(epsg,4326)(px,py);points.append(dict(type='Feature',properties={'id':ident,'selector':'synthetic generator'},geometry=mapping(Point(lo,la))))
    dump(root/'manual.geojson',dict(type='FeatureCollection',features=points))
    def spec(name):return dict(path=str(root/name),sha256=digest(root/name),provider='synthetic offline fixture',acquisition_date='not applicable',license='project fixture',vertical_units='m',vertical_datum='arbitrary synthetic zero')
    c=read('configs/transfer.template.json');c.update(work='runs/transfer_fixture',input_kind='synthetic_fixture',observer_polygon=str(root/'observer.geojson'),manual_points=str(root/'manual.geojson'),manual_provenance=dict(selector='synthetic generator',independent_human_selection=False),epsg=epsg,radius_m=500,candidate_count=24,spacing_m=60)
    c['data'].update(dem=spec('dem.tif'),tree=spec('tree.tif'),shrub=spec('shrub.tif'),herb=spec('herb.tif'),summer=spec('range.geojson'),winter=spec('range.geojson'));c['refinement'].update(radius_m=100,spacing_m=50,max_points=60)
    dump(Path(config_path),c);print('Synthetic fixture config:',config_path)

if __name__=='__main__':create()
