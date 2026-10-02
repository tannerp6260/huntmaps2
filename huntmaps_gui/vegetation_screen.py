"""Experimental display/screen geometry; never changes terrain models or scores."""
from functools import lru_cache
import numpy as np

SCENARIOS={'sparse':1.,'medium':1.5,'dense':2.}
MAX_CELLS=500000

def cells(points,ground,observer_ground,neighbor_support=False):
    from .first_person import sample,CURVATURE,EARTH
    eligible=points[np.isin(points[:,3],[0,1,3,4,5])& (np.hypot(points[:,0],points[:,1])<=300)]
    # Sort by XYZ then classification; duplicate spatial returns count only once.
    xyz,index=np.unique(eligible[:,:3],axis=0,return_index=True)
    eligible=eligible[index]
    z=sample(ground,1,-300,300,xyz[:,0],xyz[:,1])
    eligible=eligible[np.isfinite(z)&(xyz[:,2]-z>.5)]
    keys=np.floor(eligible[:,:3]-[0,0,observer_ground]).astype(np.int32)
    unique,inverse,count=np.unique(keys,axis=0,return_inverse=True,return_counts=True)
    inferred=np.zeros(len(unique),dtype=np.uint8)
    np.maximum.at(inferred,inverse,np.isin(eligible[:,3],[0,1]).astype(np.uint8))
    keep=count>=4
    if neighbor_support and keep.any():
        from scipy.spatial import cKDTree
        weak=np.flatnonzero((count>=2)&(count<4))
        # Integer lattice: Euclidean sqrt(3) is exactly the 26-neighborhood.
        distances,_=cKDTree(unique[keep]).query(unique[weak],k=2,distance_upper_bound=np.sqrt(3)+1e-7)
        keep[weak]=np.isfinite(distances[:,1])
    if keep.sum()>MAX_CELLS:raise ValueError('Vegetation screen exceeds 500,000 supported cells; prior scene retained. No cells were silently discarded.')
    local=unique[keep].astype(np.float64)+.5
    distance=np.hypot(local[:,0],local[:,1])
    centres=np.column_stack([local[:,0],local[:,2]-CURVATURE*distance**2/(2*EARTH),-local[:,1]]).astype('<f4')
    return centres,inferred[keep],count[keep].astype('<u4'),len(eligible)

@lru_cache(maxsize=4)
def load_centres(path,mtime):
    return np.fromfile(path,dtype='<f4').reshape(-1,3)

def intersect(centres,start,end,side):
    """Exact slab intersection with the same float32-centred boxes as Three.js."""
    centres=np.asarray(centres,dtype=np.float64);start=np.asarray(start,float);end=np.asarray(end,float)
    low=centres-side/2;high=centres+side/2;delta=end-start
    enter=np.zeros(len(centres));leave=np.ones(len(centres));possible=np.ones(len(centres),dtype=bool)
    for axis in range(3):
        if abs(delta[axis])<1e-12:
            possible&=(start[axis]>=low[:,axis])&(start[axis]<=high[:,axis])
        else:
            a=(low[:,axis]-start[axis])/delta[axis];b=(high[:,axis]-start[axis])/delta[axis]
            enter=np.maximum(enter,np.minimum(a,b));leave=np.minimum(leave,np.maximum(a,b))
    hit=possible&(enter<=leave)
    inside_start=bool(np.any(np.all((start>=low)&(start<=high),axis=1)))
    inside_end=bool(np.any(np.all((end>=low)&(end<=high),axis=1)))
    first=float(enter[hit].min()) if hit.any() else None
    return first,int(hit.sum()),inside_start,inside_end

def evaluate(centres,start,end,distance,ground,scenario,unknown=False,shape=None,radius=None):
    if radius is not None:centres=centres[nearby(centres,radius)]
    results={}
    for name,side in SCENARIOS.items():
        t,count,inside_start,inside_end=poly_intersect(centres,start,end,side,shape) if shape else intersect(centres,start,end,side)
        point=None
        if t is not None:
            p=np.asarray(start)+(np.asarray(end)-start)*t
            point=dict(distance_m=distance*t,east_m=float(p[0]),north_m=float(-p[2]),line_m=float(p[1]+ground))
        results[name]=dict(result='intersects inferred vegetation' if count else 'no modeled intersection',
            intersected_cells=count,first_intersection=point,observer_inside=inside_start,target_inside=inside_end,side_m=side)
    return dict(status='evaluated',selected_scenario=scenario,scenarios=results,unknown_ground=unknown,
                evaluated_radius_m=radius,included_cell_count=len(centres),geometry_identifier=shape['identifier'] if shape else 'legacy-box',farther_vegetation_unevaluated=radius is not None and distance>radius,
                warning='Experimental opaque-foliage assumption, not verified vegetation or a clear field sightline. Missing returns do not mean open space.')

RANGES=(30,60,120)
DEFAULT_RADIUS=120
DISPLAY_CAP=25000
GEOMETRY='icosahedron-20-v1'

def nearby(centres,radius):
    if isinstance(radius,bool) or radius not in RANGES:raise ValueError('Choose nearby foliage range 30, 60 or 120 m')
    selected=np.flatnonzero(np.hypot(centres[:,0],centres[:,2])<=radius)
    if len(selected)>DISPLAY_CAP:raise ValueError('Nearby foliage exceeds the lightweight 25,000-clump limit; choose a smaller range. No clumps were silently discarded.')
    return selected

def primitive():
    from scipy.spatial import ConvexHull
    t=(1+np.sqrt(5))/2
    vertices=np.array([[-1,t,0],[1,t,0],[-1,-t,0],[1,-t,0],[0,-1,t],[0,1,t],[0,-1,-t],[0,1,-t],[t,0,-1],[t,0,1],[-t,0,-1],[-t,0,1]],dtype=float)
    vertices=(vertices/np.linalg.norm(vertices,axis=1)[:,None]).astype('<f4')
    faces=ConvexHull(vertices).simplices.copy()
    for f in faces:
        a,b,c=vertices[f]
        if np.dot(np.cross(b-a,c-a),a)<0:f[1],f[2]=f[2],f[1]
    return dict(identifier=GEOMETRY,vertices=vertices.tolist(),faces=faces.tolist())

@lru_cache(maxsize=4)
def load_primitive(path,mtime):
    import json
    return json.load(open(path))

def poly_intersect(centres,start,end,diameter,shape):
    vertices=np.asarray(shape['vertices'],float)*diameter/2
    faces=np.asarray(shape['faces'],int)
    centres=np.asarray(centres,float);start=np.asarray(start,float);end=np.asarray(end,float)
    enter=np.zeros(len(centres));leave=np.ones(len(centres));possible=np.ones(len(centres),dtype=bool)
    inside_start=np.ones(len(centres),dtype=bool);inside_end=inside_start.copy()
    delta=end-start
    for face in faces:
        a,b,c=vertices[face];normal=np.cross(b-a,c-a);normal/=np.linalg.norm(normal)
        boundary=np.dot(normal,a)
        origin=(start-centres)@normal-boundary;finish=(end-centres)@normal-boundary
        inside_start&=origin<=1e-9;inside_end&=finish<=1e-9
        denom=np.dot(delta,normal)
        if abs(denom)<1e-12:possible&=origin<=1e-9
        elif denom>0:leave=np.minimum(leave,-origin/denom)
        else:enter=np.maximum(enter,-origin/denom)
    hits=possible&(enter<=leave+1e-9)
    return (float(enter[hits].min()) if hits.any() else None,int(hits.sum()),bool(inside_start.any()),bool(inside_end.any()))

def foliage_colors(centres,kinds,rgba,radius=300):
    fallback=np.where(kinds[:,None]!=0,np.array([72,108,53]),np.array([49,91,53])).astype(np.uint8)
    output=fallback.copy();height,width=rgba.shape[:2];used=np.zeros(len(centres),bool)
    for start in range(0,len(centres),10000):
        c=centres[start:start+10000];col=np.floor((c[:,0]+radius)/(2*radius)*width).astype(int)
        row=np.floor((c[:,2]+radius)/(2*radius)*height).astype(int)
        samples=[]
        for dy in [-1,0,1]:
            for dx in [-1,0,1]:
                x=col+dx;y=row+dy;valid=(x>=0)&(x<width)&(y>=0)&(y<height)
                pixels=rgba[np.clip(y,0,height-1),np.clip(x,0,width-1)]
                valid&=pixels[:,3]>0;samples.append(np.where(valid[:,None],pixels[:,:3],np.nan))
        values=np.stack(samples,axis=1);has=np.isfinite(values[:,:,0]).any(axis=1)
        if has.any():
            med=np.nanmedian(values[has],axis=1)
            dest=np.flatnonzero(has)+start;output[dest]=np.rint(.75*med+.25*fallback[dest]).astype(np.uint8);used[dest]=True
    return output,used
