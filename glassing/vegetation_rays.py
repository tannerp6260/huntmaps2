"""Ground-endpoint ray diagnostics, not an optical transmission model."""
import numpy as np
from scipy.ndimage import map_coordinates

def ray(ground,height,res,observer,target,eye=1.7,deer=.8,curvature=6/7,near_m=30,target_m=30):
    r0,c0=observer;r1,c1=target;distance=float(np.hypot(r1-r0,c1-c0)*res)
    if distance==0:return dict(observer=False,intermediate=False,target=False,unknown=False,terrain=False,distance_m=0)
    t=np.linspace(0,1,max(3,int(np.ceil(distance/(res/2))))+1)[1:-1]
    rows=r0+t*(r1-r0);cols=c0+t*(c1-c0)
    rr=np.floor(rows+.5).astype(int);cc=np.floor(cols+.5).astype(int)
    z=map_coordinates(ground,[rows,cols],order=1,mode='nearest');h=height[rr,cc]
    start=ground[r0,c0]+eye;end=ground[r1,c1]+deer-curvature*distance**2/(2*6378137.)
    line=start*(1-t)+end*t;adjusted=z-curvature*(distance*t)**2/(2*6378137.)
    # Endpoint cells cannot resolve where within-cell vegetation lies. Do not raise endpoints.
    outside_endpoints=~(((rr==r0)&(cc==c0))|((rr==r1)&(cc==c1)))
    unknown=(~np.isfinite(h)|~np.isfinite(z))&outside_endpoints
    hit=(h>0)&(adjusted+h>line)&outside_endpoints
    near=(t*distance<=near_m);last=((1-t)*distance<=target_m)&~near;middle=~near&~last
    endpoint_unknown=not(np.isfinite(ground[r0,c0]) and np.isfinite(ground[r1,c1]) and np.isfinite(height[r0,c0]) and np.isfinite(height[r1,c1]))
    return dict(observer=bool(np.any(hit&near)),intermediate=bool(np.any(hit&middle)),target=bool(np.any(hit&last) or (np.isfinite(height[r1,c1]) and height[r1,c1]>deer)),unknown=bool(np.any(unknown) or endpoint_unknown),terrain=bool(np.any((adjusted>line+1e-6)&outside_endpoints)),distance_m=distance,observer_cell_height=float(height[r0,c0]) if np.isfinite(height[r0,c0]) else None,ground_start=float(start),ground_target=float(ground[r1,c1]+deer))
