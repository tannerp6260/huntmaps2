"""Display-only Soap Creek pilot. No historical writes or visibility-score changes."""
import hashlib
import json
import math
import re
import uuid
from functools import lru_cache
from pathlib import Path
import numpy as np
from osgeo import gdal
from .catalog import ROOT, STATE, Run, read, check_hash
from .jobs import write

PILOT = ('A0075', 'V010', 'V008', 'A0031')
RUN = 'soap-creek-decision-review-v2'
HOME = STATE / 'first-person'
VERSION = 3
CURVATURE = 6/7
EARTH = 6378137.
LIMIT = 500_000_000

def stage(text):
    print('STAGE '+text, flush=True)

def candidate(ident, cid):
    if ident != RUN or cid not in PILOT:
        raise ValueError('First-person is a Soap Creek pilot: A0075, V010, V008 and A0031 only.')
    return Run(ident).candidate(cid)

def plan(ident):
    if not re.fullmatch(r'[a-f0-9]{32}', ident):
        raise ValueError('Unknown first-person preparation plan')
    p = read(HOME/'plans'/(ident+'.json'))
    if not p:
        raise ValueError('Unknown first-person preparation plan')
    return p

def new_plan():
    ident = uuid.uuid4().hex
    write(HOME/'plans'/(ident+'.json'), dict(id=ident, kind='first-person', prepared=False, radius_m=300,
        download_cap_bytes=LIMIT, candidates=list(PILOT), version=VERSION))
    return ident

def verify_file(path, expected):
    st = path.stat()
    check_hash(str(path), st.st_mtime_ns, st.st_size, expected)

def scene(ident, cid):
    p = candidate(ident, cid)
    pointer = read(HOME/'ready'/(cid+'.json'))
    if not pointer:
        return dict(status='unprepared', candidate=cid, observer=p, reason='Prepare the local lidar pilot before opening a fine view.')
    folder = HOME/'bundles'/pointer['key']
    meta = read(folder/'scene.json')
    if not meta or meta.get('version') != VERSION or meta['observer']['longitude'] != p['longitude'] or meta['observer']['latitude'] != p['latitude']:
        raise ValueError('First-person bundle is stale. Prepare the pilot again.')
    for name, h in meta['hashes'].items():
        verify_file(folder/name, h)
    # Orientation only: face the first saved inspection sector, not a new score.
    r=Run(ident);sectors=r.sectors(cid).get('features',[])
    bearing=0.
    if sectors:
        from shapely.geometry import shape
        from pyproj import Transformer
        centre=shape(sectors[0]['geometry']).centroid
        x,y=Transformer.from_crs(4326,r.config['epsg'],always_xy=True).transform(centre.x,centre.y)
        observer=r.points[cid]
        bearing=(math.degrees(math.atan2(x-observer['x'],y-observer['y']))+360)%360
    return dict(meta,initial_bearing_deg=bearing,initial_facing_note='Initial facing is the centre of the first saved inspection sector, for orientation only; sectors may include hidden terrain.')

def bundle(cid):
    meta = scene(RUN, cid)
    if meta['status'] == 'unprepared':
        raise ValueError('Prepare this setup first')
    return HOME/'bundles'/meta['key'], meta

@lru_cache(maxsize=12)
def grid(path, mtime):
    with np.load(path) as z:
        return z['heights'], float(z['res']), float(z['x0']), float(z['y0'])

def sample(heights, res, x0, y0, x, y):
    """Same fixed diagonal triangles as render mesh; exact within grid triangle."""
    u=(x-x0)/res; v=(y0-y)/res
    c=np.floor(u).astype(int); r=np.floor(v).astype(int)
    good=(u>=0)&(v>=0)&(u<=heights.shape[1]-1)&(v<=heights.shape[0]-1)
    rr=np.clip(r,0,heights.shape[0]-2); cc=np.clip(c,0,heights.shape[1]-2)
    fx=u-cc; fy=v-rr
    a=heights[rr,cc]; b=heights[rr,cc+1]; d=heights[rr+1,cc]; e=heights[rr+1,cc+1]
    # a,b,e for fy<=fx; a,e,d otherwise. No fallback through missing corners.
    top=fy<=fx
    z=np.where(top,a*(1-fx)+b*(fx-fy)+e*fy,a*(1-fy)+e*fx+d*(fy-fx))
    valid=good&np.isfinite(a)&np.isfinite(e)&np.where(top,np.isfinite(b),np.isfinite(d))
    return np.where(valid,z,np.nan)

def profile_grid(heights,res,x0,y0,target_x,target_y,eye,target_height,curvature=CURVATURE):
    distance=math.hypot(target_x,target_y)
    if distance < .1:
        raise ValueError('Choose an inspection target away from the observer')
    # Include all grid and diagonal crossings, and interior samples at <= quarter cell.
    ts=list(np.linspace(0,1,max(2,math.ceil(distance/(res/4)))+1))
    for origin,delta in [((-x0)/res,target_x/res),(y0/res,-target_y/res),
                         ((-x0-y0)/res,(target_x+target_y)/res)]:
        if abs(delta)>1e-12:
            lo,hi=sorted([origin,origin+delta])
            ts.extend((k-origin)/delta for k in range(math.ceil(lo),math.floor(hi)+1))
    t=np.unique(np.clip(ts,0,1)); x=t*target_x; y=t*target_y
    z=sample(heights,res,x0,y0,x,y)
    drop=curvature*(distance*t)**2/(2*EARTH)
    ground=z-drop
    start=z[0]+eye; end=z[-1]+target_height-curvature*distance**2/(2*EARTH)
    line=start*(1-t)+end*t
    finite=np.isfinite(ground)&np.isfinite(line)
    interior=(t>1e-8)&(t<1-1e-8)
    clearance=line-ground
    hits=np.where(finite&interior&(clearance < -1e-6))[0]
    unknown=not np.all(finite)
    valid_clear=clearance[finite&interior]
    minimum=float(valid_clear.min()) if len(valid_clear) else None
    result='incomplete data' if unknown else ('modeled ground obstruction' if len(hits) else 'no obstruction found in this ground model')
    obstruction=None
    if len(hits):
        k=hits[0]
        obstruction=dict(distance_m=float(distance*t[k]),east_m=float(x[k]),north_m=float(y[k]),ground_m=float(ground[k]))
    # Bounded SVG chart transport. Keep unknown/blocking samples while thinning others.
    stride=max(1,len(t)//1000); keep=set(range(0,len(t),stride))|{0,len(t)-1}
    keep.update(np.flatnonzero(~finite).tolist()); keep.update(hits[:1].tolist())
    points=[dict(distance_m=float(distance*t[k]),ground_m=float(ground[k]) if np.isfinite(ground[k]) else None,
                 line_m=float(line[k]) if np.isfinite(line[k]) else None) for k in sorted(keep)]
    return dict(result=result,distance_m=distance,minimum_clearance_m=minimum,borderline=minimum is not None and abs(minimum)<=.05,
                first_obstruction=obstruction,points=points,eye_m=eye,target_height_m=target_height,
                unknown=unknown,curvature=curvature,warning='Terrain-model diagnostic only. Trees, brush, footing and current field sightlines remain unverified.')

def profile(ident,cid,body):
    candidate(ident,cid)
    try:
        x=float(body['east_m']); y=float(body['north_m']); eye=float(body.get('eye_m',1.7)); h=float(body.get('target_height_m',.8))
    except (KeyError,TypeError,ValueError):
        raise ValueError('Choose a valid target and viewing heights')
    if not all(math.isfinite(v) for v in [x,y,eye,h]) or not .8<=eye<=2.2 or not 0<=h<=2.5 or math.hypot(x,y)>2000:
        raise ValueError('Use eye height 0.8–2.2 m, target height 0–2.5 m and targets within 2 km.')
    folder,meta=bundle(cid)
    source='fine' if math.hypot(x,y)<=300 and meta['fine_observer_available'] else 'baseline'
    path=folder/(source+'.npz'); a,res,x0,y0=grid(str(path),path.stat().st_mtime_ns)
    result=profile_grid(a,res,x0,y0,x,y,eye,h)
    result.update(source=source,source_label='Local lidar-derived ground' if source=='fine' else 'Separate baseline-only profile; both endpoints use baseline ground',resolution_m=res)
    return result

def mesh(a,res,x0,y0,ground,radius,inner=0):
    rows,cols=np.indices(a.shape); x=x0+cols*res; n=y0-rows*res; d=np.hypot(x,n)
    a=np.where((d<=radius)&(d>=inner),a,np.nan)
    positions=np.stack([x,np.nan_to_num(a-ground-CURVATURE*d*d/(2*EARTH),nan=0),-n],axis=-1).astype('<f4').reshape(-1,3)
    index=np.arange(a.size,dtype=np.uint32).reshape(a.shape)
    tl=index[:-1,:-1]; tr=index[:-1,1:]; bl=index[1:,:-1]; br=index[1:,1:]
    good=np.isfinite(a)
    one=good[:-1,:-1]&good[:-1,1:]&good[1:,1:]
    two=good[:-1,:-1]&good[1:,1:]&good[1:,:-1]
    # Correct upward winding in east / height / south coordinates.
    faces=np.concatenate([np.stack([tl[one],br[one],tr[one]],1),np.stack([tl[two],bl[two],br[two]],1)]).astype('<u4')
    return positions,faces
