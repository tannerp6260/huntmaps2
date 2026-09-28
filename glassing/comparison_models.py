"""Explicit, uncalibrated scenario functions. None return deer probabilities."""
import csv
import math
from pathlib import Path
import numpy as np
from scipy.ndimage import map_coordinates
from osgeo import osr
from .acquire import srs


def habitat(range_mask,shrub,herb,season='summer',floor=.25):
    if not 0<floor<=1:raise ValueError('Habitat background must remain positive')
    if season=='background':return np.ones_like(shrub,dtype=float)
    # One vegetation composite; not several correlated independent bonuses.
    browse=np.clip((.5*shrub+.5*herb if season=='summer' else shrub)/.6,0,1)
    return floor+(1-floor)*(.6*range_mask+.4*browse)


def searchability(tree,shrub):
    # Areal classes, not transmission probabilities; explicitly uncalibrated.
    return np.where(tree<.1,1.,np.where(tree<.4,.6,.25))*np.where(shrub>.3,.75,1.)


def distance_response(distance,c,task=None,scale=None):
    task=task or c['task'];scale=scale or c['distance_scale']
    if scale<=0:raise ValueError('Distance scale must be positive')
    return np.interp(distance,np.array(c['distance_curves']['knots_m'])*scale,c['distance_curves'][task])


def perspective(gx,gy,dx,dy,dz,floor=.3):
    length=np.sqrt(dx*dx+dy*dy+dz*dz)
    normal=np.sqrt(gx*gx+gy*gy+1)
    incidence=(-gx*dx-gy*dy+dz)/np.maximum(length*normal,1e-9)
    return floor+(1-floor)*np.clip(incidence,0,1)


def sunlight(gx,gy,view_dx,view_dy,view_dz,scenario,c):
    if scenario=='none':return np.ones_like(gx)
    sun=c['sun_scenarios'][scenario];az,el=np.radians([sun['azimuth_deg'],sun['elevation_deg']])
    sx,sy,sz=np.sin(az)*np.cos(el),np.cos(az)*np.cos(el),np.sin(el)
    illumination=.5+.5*np.clip((-gx*sx-gy*sy+sz)/np.sqrt(1+gx*gx+gy*gy),0,1)
    dot=(view_dx*sx+view_dy*sy+view_dz*sz)/np.maximum(np.sqrt(view_dx**2+view_dy**2+view_dz**2),1e-9)
    separation=np.degrees(np.arccos(np.clip(dot,-1,1)))
    glare=1-c['glare_strength']*np.clip(1-separation/c['glare_cone_deg'],0,1)
    return illumination*glare


def inspection_fraction(visible_km2,minutes,rate):
    if minutes<=0 or rate<=0:raise ValueError('Inspection budget/rate must be positive')
    return min(1.,minutes*rate/max(visible_km2,1e-12))


def wilson(success,n):
    if n==0:return [0.,1.]
    p=success/n;z=1.96;den=1+z*z/n
    mid=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0.,mid-half),min(1.,mid+half)]


def canopy_ray(a,tree,gt,observer,target,eye,target_height,curvature,canopy_height,threshold=.2,foreground_m=30):
    """Stress test on ONE ray with ground endpoints and assumed solid canopy columns.

    Tree fraction only chooses potential columns; it is never ray transmittance.
    Aerial cover cannot establish which ray intersects a crown. Ray/height outcomes
    are scenario diagnostics, not verified canopy occlusion.
    """
    r0,c0=observer;r1,c1=target
    distance=math.hypot(r1-r0,c1-c0)*gt[1]
    if distance==0:return dict(blocked=False,foreground=False,unknown=False)
    n=max(3,int(distance/(gt[1]/2)))
    t=np.linspace(0,1,n+1)[1:-1]
    coords=[r0+t*(r1-r0),c0+t*(c1-c0)]
    ground=map_coordinates(a,coords,order=1,mode='nearest')
    cover=map_coordinates(tree,coords,order=0,mode='nearest')
    adjusted=ground-curvature*(t*distance)**2/(2*6378137.)
    end=float(a[r1,c1])+target_height-curvature*distance**2/(2*6378137.)
    line=(float(a[r0,c0])+eye)*(1-t)+end*t
    obstacle=adjusted+np.where(cover>=threshold,canopy_height,0)
    canopy_hit=(cover>=threshold)&(obstacle>line)
    # Target's last 30m belongs to target-side uncertainty, not double-counted path stress.
    middle=(t*distance>foreground_m)&((1-t)*distance>30)
    near=t*distance<=foreground_m
    return dict(blocked=bool(np.any(canopy_hit&middle)),foreground=bool(np.any(canopy_hit&near)),unknown=bool(np.any(~np.isfinite(cover))))


def import_experts(path,gt,allowed,epsg):
    if not path:return []
    with open(path,newline='') as source:
        rows=list(csv.DictReader(source))
    result=[];seen=set()
    for row in rows:
        for key in ['id','longitude','latitude','expert_id','selected_utc','rationale']:
            if not row.get(key):raise ValueError('Expert CSV requires '+key)
        if row['id'] in seen:raise ValueError('Duplicate expert id')
        seen.add(row['id'])
        lon,lat=float(row['longitude']),float(row['latitude'])
        if not(-180<=lon<=180 and -90<=lat<=90):raise ValueError('Invalid expert lon/lat')
        x,y,_=osr.CoordinateTransformation(srs(4326),srs(epsg)).TransformPoint(lon,lat)
        r=math.floor((y-gt[3])/gt[5]);col=math.floor((x-gt[0])/gt[1])
        if not(0<=r<allowed.shape[0] and 0<=col<allowed.shape[1] and allowed[r,col]):raise ValueError('Expert point outside technical observer domain')
        result.append(dict(id='E_'+row['id'],x=gt[0]+(col+.5)*gt[1],y=gt[3]+(r+.5)*gt[5],row=r,col=col,
            expert_id=row['expert_id'],selected_utc=row['selected_utc'],rationale=row['rationale'],
            original_longitude=lon,original_latitude=lat,provenance=['independent_expert_import'],access='UNKNOWN_ACCESS_NOT_FIELD_READY'))
    return result


def eligible_points(points,preferences,access_rows):
    """Evaluate supplied evidence; never infer connected access from land ownership."""
    result=[]
    need_metrics=any(preferences[k] is not None for k in ['max_hike_km','max_gain_m']) or any(preferences[k]!=0 for k in ['roadlessness_weight','pressure_weight'])
    if need_metrics and not access_rows:raise ValueError('Travel/road preferences need supplied route evidence; no invented estimates')
    for p in points:
        evidence=access_rows.get(p['id'],{})
        if evidence.get('reachable') in ['prohibited','denied','excluded']:continue
        verified=evidence.get('reachable')=='verified' and bool(evidence.get('evidence'))
        if preferences['require_verified_access'] and not verified:continue
        allowed=True
        for key,column in [('max_hike_km','hike_km'),('max_gain_m','gain_m')]:
            if preferences[key] is not None:
                if not verified or not evidence.get(column):allowed=False
                elif float(evidence[column])>preferences[key]:allowed=False
        if allowed:result.append(p)
    return result
