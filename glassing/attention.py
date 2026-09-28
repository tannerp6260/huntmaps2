"""Selective attention over fixed spatial patches, not a calibrated detection model."""
import math
import numpy as np


def uniform_score(reward,visible_area,budget,rate):
    return reward*min(1.,budget*rate/visible_area) if visible_area>0 else 0.


def patches(dx,dy,reward,cell_area_km2,width_deg=30,band_m=500,radius_m=2000):
    if 360%width_deg or radius_m%band_m:raise ValueError('Patch tiling must divide full circle and radius')
    angle=np.mod(np.degrees(np.arctan2(dx,dy)),360)
    sector=np.minimum((angle/width_deg).astype(int),int(360/width_deg)-1)
    ring=np.minimum((np.hypot(dx,dy)/band_m).astype(int),int(radius_m/band_m)-1)
    ids=ring*int(360/width_deg)+sector
    count=int(360/width_deg)*int(radius_m/band_m)
    values=np.bincount(ids,weights=reward*cell_area_km2,minlength=count)
    visible=np.bincount(ids,minlength=count)*cell_area_km2
    result=[]
    for i in range(count):
        band=i//int(360/width_deg);az=i%int(360/width_deg)*width_deg
        inner,outer=band*band_m,(band+1)*band_m
        area=math.radians(width_deg)*(outer**2-inner**2)/2/1e6
        result.append(dict(id=i,azimuth_start=az,azimuth_end=az+width_deg,inner_m=inner,outer_m=outer,
                           full_area_km2=area,visible_area_km2=float(visible[i]),reward=float(values[i])))
    return result


def select(patches,budget,rate=.02,overhead=.5,quantum=.25):
    """Exact binary knapsack on conservative rounded time costs.

    Full patch footprints/costs remain fixed as visibility changes. Nonnegative
    additional optional rewards cannot lower the attainable optimum. No partial cells.
    """
    if budget<0 or rate<=0 or overhead<0 or quantum<=0:raise ValueError('Invalid attention budget or costs')
    capacity=int(math.floor(budget/quantum+1e-9))
    best=np.zeros(capacity+1);choices=[0]*(capacity+1);costs=[]
    for idx,p in enumerate(patches):
        if p['reward']<0:raise ValueError('Patch rewards must be nonnegative')
        units=max(1,int(math.ceil((p['full_area_km2']/rate+overhead)/quantum-1e-9)))
        costs.append(units)
        for t in range(capacity,units-1,-1):
            value=best[t-units]+p['reward']
            if value>best[t]+1e-14:best[t]=value;choices[t]=choices[t-units]|(1<<idx)
    chosen=[p['id'] for idx,p in enumerate(patches) if choices[capacity]&(1<<idx)]
    return dict(score=float(best[capacity]),patch_ids=chosen,
                minutes_used=sum(costs[i]*quantum for i,p in enumerate(patches) if p['id'] in chosen),
                budget_minutes=budget,rate_assumption_km2_per_min=rate,overhead_minutes=overhead)


def paradox():
    before=uniform_score(.6,.6,30,.02);after=uniform_score(.6+.06,1.2,30,.02)
    base=[dict(id=0,full_area_km2=.6,reward=.6)]
    extra=base+[dict(id=1,full_area_km2=.6,reward=.06)]
    return dict(uniform_before=before,uniform_after=after,
                selective_before=select(base,30,.02,0)['score'],selective_after=select(extra,30,.02,0)['score'],
                explanation='Add optional 0.6km² terrain with relative value 0.1; uniform value drops 0.60 to 0.33, selective can retain 0.60.')
