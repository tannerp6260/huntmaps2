"""AOI-neutral mapped pedestrian witnesses; source adapters are configuration fields."""
import math
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import shape,Point,LineString
from shapely.ops import transform
from osgeo import ogr
from .transfer import work,read,source,polygon,project
from .acquire import dump
from . import core
from .scout_access import build_network,insert_supported_vertices,shortest,trace,terrain_connector,route_profile


def run(c):
    root=work(c);cfg=c['access'];points=read(root/'leading.json');summaries={};features=[]
    if not all(cfg.get(k) for k in ['entries','routes','offtrail_allowed']):
        dump(root/'approaches.json',{p.get('original_id',p['id']):'PENDING documented entry points, mapped routes and off-trail permission/terrain evidence' for p in points});return
    entries=read(source(cfg['entries']))['features'];records=[];xy=project(4326,c['epsg'])
    for spec in cfg['routes']:
        for f in read(source(spec))['features']:
            prop=f['properties'];g=transform(xy,shape(f['geometry']))
            if prop.get(spec.get('prohibited_field','prohibited')) is True:continue
            for part in list(g.geoms) if hasattr(g,'geoms') else [g]:
                if part.geom_type!='LineString':raise ValueError('Route source must contain line strings')
                records.append(dict(geometry=part,kind=spec['path'],route_id=str(prop.get(spec.get('id_field','id'),'')),name=str(prop.get(spec.get('name_field','name'),'')),motor=False,properties=prop))
    if not records:raise ValueError('No usable mapped-route records; not proof of inaccessibility')
    records=insert_supported_vertices(records,cfg.get('repair_tolerance_m',5));v,adj,repairs,_=build_network(records,cfg.get('repair_tolerance_m',5));tree=cKDTree(v);starts=[]
    for f in entries:
        p=f['properties'];g=transform(xy,shape(f['geometry']))
        if g.geom_type!='Point' or not p.get('id') or not p.get('evidence'):raise ValueError('Entries need Point geometry, id and documentary evidence')
        gap,n=tree.query([g.x,g.y]);d,prev=shortest(adj,int(n),records);starts.append(dict(id=p['id'],gap_m=float(gap),node=int(n),dist=d,prev=prev,evidence=p['evidence']))
    ds,a,gt,masks=core.load_grid(read(root/'core_config.json'));allowed_g=polygon(source(cfg['offtrail_allowed']),c['epsg'])
    for spec in cfg.get('barriers',[]):allowed_g=allowed_g.difference(polygon(source(spec),c['epsg']))
    allowed=core.polygon_mask(ogr.CreateGeometryFromWkb(allowed_g.wkb),a.shape,gt,ds.GetProjection())
    for p in points:
        choices=[]
        for node in tree.query_ball_point([p['x'],p['y']],cfg.get('max_final_leg_m',2000)):
            for e in starts:
                if node in e['dist'] and e['gap_m']<=cfg.get('entry_gap_review_m',50):choices.append((e['dist'][node]+math.dist(v[node],[p['x'],p['y']]),node,e))
        result=None
        for _,node,e in sorted(choices,key=lambda t:t[0])[:6]:
            con=terrain_connector(a,allowed,gt,v[node],(p['x'],p['y']),cfg.get('max_slope_deg',30))
            if not con:continue
            off=LineString(con['coords'])
            if not allowed_g.covers(off):continue
            nodes,ids,count=trace(e['prev'],node);coords=v[nodes].tolist()
            if len(coords)<2:coords*=2
            line=LineString(coords);mp=route_profile(coords,ds);op=route_profile(con['coords'],ds);valid=mp['dem_coverage']==1 and op['dem_coverage']==1
            length=mp['distance_m']+op['distance_m'];gain=mp['gain_m']+mp['loss_m']+op['gain_m']+op['loss_m'] if valid else None
            result=dict(entry=e['id'],entry_gap_m=e['gap_m'],mapped_oneway_km=mp['distance_m']/1000,offtrail_oneway_km=op['distance_m']/1000,roundtrip_miles=2*length/1609.344,roundtrip_gain_ft=gain*3.28084 if valid else None,hours_range=[2*length/(1000*cfg.get('walking_kmh',[1.5,3])[1])+gain/cfg.get('ascent_m_per_hour',[300,600])[1],2*length/(1000*cfg.get('walking_kmh',[1.5,3])[0])+gain/cfg.get('ascent_m_per_hour',[300,600])[0]] if valid else None,status='Mapped pedestrian witness only; legal/physical/parking unverified',dem_profile_complete=valid,repairs_used=count,evidence=e['evidence'])
            for kind,g in [('mapped',line),('offtrail_hypothesis',off)]:features.append(dict(type='Feature',geometry=g.__geo_interface__,properties=dict(id=p['id'],kind=kind)))
            break
        summaries[p.get('original_id',p['id'])]=result or 'No supported witness in supplied inventory/search budget; NOT a finding of inaccessibility'
    dump(root/'approaches.json',summaries);dump(root/'approach_geometry.json',dict(epsg=c['epsg'],features=features));dump(root/'access_topology.json',dict(repairs=repairs,entries=[{k:v for k,v in e.items() if k not in ['dist','prev']} for e in starts]))
