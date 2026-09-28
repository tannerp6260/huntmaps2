"""Matched local terrain diagnostics, never a replacement for full-radius scores."""
import json,math
from pathlib import Path
import numpy as np
from osgeo import gdal
from scipy.ndimage import map_coordinates,shift
from . import core,compare
from .acquire import dump,digest


def sample(ds,x,y):
    gt=ds.GetGeoTransform();a=ds.ReadAsArray()
    rr=np.floor((np.asarray(y)-gt[3])/gt[5]).astype(int);cc=np.floor((np.asarray(x)-gt[0])/gt[1]).astype(int)
    if np.any((rr<0)|(cc<0)|(rr>=a.shape[0])|(cc>=a.shape[1])):raise ValueError('Sample outside grid')
    return a[rr,cc]


def gridcheck(ds,x,y):
    gt=ds.GetGeoTransform();r=int((y-gt[3])/gt[5]);col=int((x-gt[0])/gt[1])
    return dict(transform=gt,requested_xy=[x,y],sample_center_xy=[gt[0]+(col+.5)*gt[1],gt[3]+(r+.5)*gt[5]],ground_m=float(sample(ds,x,y)))


def run(c):
    from .correct import csvwrite
    cc=json.loads(Path(c['comparison_config']).read_text());b,base,control,a,gt,masks=compare.load(cc)
    if digest(Path(cc['inputs'])/'fine_dem.tif')!=cc['fine_dem']['sha256']:raise ValueError('Fine source checksum changed')
    root=Path(c['work'])/'geometry';root.mkdir(parents=True,exist_ok=True)
    p=next(p for p in json.loads((base/'candidates.json').read_text()) if p['id']=='C0064');x,y=p['x'],p['y']
    # Native-derived fine centres coincide with control centres at integer coordinates.
    # Average warp goes onto the EXACT control grid; half-metre fine edge offset is explicit.
    fine=gdal.Warp(str(root/'fine1m.tif'),str(Path(cc['inputs'])/'fine_dem.tif'),dstSRS=control.GetProjection(),outputBounds=[x-460.5,y-460.5,x+460.5,y+460.5],xRes=1,yRes=1,resampleAlg='bilinear',dstNodata=-9999)
    bounds=[x-465,y-465,x+465,y+465]
    agg=gdal.Warp(str(root/'fine_averaged10m.tif'),str(Path(cc['inputs'])/'fine_dem.tif'),dstSRS=control.GetProjection(),outputBounds=bounds,xRes=10,yRes=10,resampleAlg='average',dstNodata=-9999)
    coarse=gdal.Warp(str(root/'control10m.tif'),control,dstSRS=control.GetProjection(),outputBounds=bounds,xRes=10,yRes=10,resampleAlg='near',dstNodata=-9999)
    up=gdal.Warp(str(root/'averaged_upsampled1m.tif'),agg,dstSRS=control.GetProjection(),outputBounds=[x-460.5,y-460.5,x+460.5,y+460.5],xRes=1,yRes=1,resampleAlg='bilinear',dstNodata=-9999)
    if agg.GetGeoTransform()!=coarse.GetGeoTransform():raise ValueError('Unmatched control grid')
    # Fixed target centre support: old 10m centres within 400m, including original mask.
    dy,dx=np.mgrid[-400:401:10,-400:401:10];xx=x+dx;yy=y+dy
    r=((yy-gt[3])/gt[5]).astype(int);cols=((xx-gt[0])/gt[1]).astype(int)
    support=(dx*dx+dy*dy<=400**2)&masks['target'][r,cols]
    near_support=(dx*dx+dy*dy<=360**2)&masks['target'][r,cols]
    rows=[];vis={};rasters={'control10m':coarse,'fine1m':fine,'fine_averaged10m':agg,'averaged_upsampled1m':up}
    def measure(name,ds,ox=x,oy=y,eye=1.7,target_support=support):
        vs=core.viewshed(ds,root/(name+'_view.tif'),ox,oy,400,eye,b['target_m'],b['curvature'])
        # Slightly shifted observer views can exclude targets beyond 400m. Nearby support
        # is deliberately 360m around ORIGINAL point, within 400m of all 3x3 setups.
        mask=np.zeros(support.shape,bool);mask[target_support]=sample(vs,xx[target_support],yy[target_support])==1
        result=dict(case=name,observer_x=ox,observer_y=oy,eye_m=eye,ground_m=float(sample(ds,ox,oy)),visible_km2=float(np.count_nonzero(mask&target_support)*.0001),support_km2=float(target_support.sum()*.0001),disagreement_vs_control=None)
        if 'control10m' in vis:result['disagreement_vs_control']=float(np.mean(mask[target_support]!=vis['control10m'][target_support]))
        rows.append(result);vis[name]=mask;return mask
    for name,ds in rasters.items():measure(name,ds)
    for eye in [1.,2.2]:measure('fine_eye'+str(eye),fine,eye=eye)
    fa=fine.ReadAsArray();fg=fine.GetGeoTransform()
    for axis in [0,1]:
        for offset in [-1,1]:
            moved=shift(fa,[offset if axis==0 else 0,offset if axis==1 else 0],order=1,mode='nearest',prefilter=False)
            path=root/f'fine_shift_axis{axis}_{offset}.tif';core.write_raster(path,moved,fg,fine.GetProjection(),-9999)
            measure(path.stem,gdal.Open(str(path)))
    for dx0 in [-20,0,20]:
        for dy0 in [-20,0,20]:
            nx,ny=x+dx0,y+dy0;rr=int((ny-gt[3])/gt[5]);col=int((nx-gt[0])/gt[1])
            name=f'nearby_{dx0}_{dy0}';measure(name,fine,nx,ny,target_support=near_support)
            rows[-1]['disagreement_vs_control']=float(np.mean(vis[name][near_support]!=vis['nearby_0_0'][near_support])) if 'nearby_0_0' in vis else None
            rows[-1]['technical_observer_mask']=bool(masks['observer'][rr,col])
    for row in rows:
        row.setdefault('technical_observer_mask',True)
        if row['case'].startswith('nearby_'):row['disagreement_vs_control']=float(np.mean(vis[row['case']][near_support]!=vis['nearby_0_0'][near_support]))
    csvwrite(root/'matched_checks.csv',rows)
    # Four long rays with greatest coarse/fine target disagreement, separated by >=40°.
    mismatch=support&(vis['control10m']!=vis['fine1m'])&(dx*dx+dy*dy>250**2)
    ids=np.argwhere(mismatch);chosen=[]
    for rr,col in sorted(ids.tolist(),key=lambda ij:-(dx[tuple(ij)]**2+dy[tuple(ij)]**2)):
        az=math.degrees(math.atan2(dx[rr,col],dy[rr,col]))%360
        if all(abs((az-q[2]+180)%360-180)>=40 for q in chosen):chosen.append((rr,col,az))
        if len(chosen)==4:break
    profile_rows=[];ray_checks=[]
    for k,(rr,col,az) in enumerate(chosen):
        length=math.hypot(dx[rr,col],dy[rr,col]);t=np.linspace(0,1,int(length)+1);tx=x+t*dx[rr,col];ty=y+t*dy[rr,col]
        for name,ds in [('fine1m',fine),('control10m',coarse),('fine_averaged10m',agg)]:
            dg=ds.GetGeoTransform();arr=ds.ReadAsArray()
            zz=map_coordinates(arr,[(ty-dg[3])/dg[5]-.5,(tx-dg[0])/dg[1]-.5],order=1,mode='nearest')
            adjusted=zz-b['curvature']*(length*t)**2/(2*6378137.)
            line=(zz[0]+1.7)*(1-t)+(zz[-1]+b['target_m']-b['curvature']*length**2/(2*6378137.))*t
            independently_visible=bool(np.all(adjusted[1:-1]<=line[1:-1]))
            ray_checks.append(dict(profile=k,surface=name,azimuth_deg=az,independent_visible=independently_visible,gdal_visible=bool(vis[name][rr,col]),agreement=independently_visible==bool(vis[name][rr,col])))
            for j in range(len(t)):profile_rows.append(dict(profile=k,surface=name,distance_m=float(t[j]*length),ground_m=float(zz[j]),sightline_m=float(line[j]+b['curvature']*(length*t[j])**2/(2*6378137.)),azimuth_deg=az))
    csvwrite(root/'profiles.csv',profile_rows);dump(root/'selected_ray_checks.json',ray_checks)
    delta=sample(fine,xx[support],yy[support])-sample(coarse,xx[support],yy[support])
    dump(root/'summary.json',dict(candidate='C0064',radius_m=400,fixed_target_centers=int(support.sum()),matched_grid=agg.GetGeoTransform()==coarse.GetGeoTransform(),grid_checks={n:gridcheck(d,x,y) for n,d in rasters.items()},fine_minus_control_ground_m=dict(mean=float(delta.mean()),median=float(np.median(delta)),p05=float(np.percentile(delta,5)),p95=float(np.percentile(delta,95))),cases=rows,independent_checks=ray_checks,source_warning='1m CO_WestCentral_2019_A19 vs frozen 1/3 arcsecond USGS mosaic; source vintage, datum realization, resampling and resolution differ. No datum correction; no 1m truth assumption.',interpretation='400m only; area estimates sampled on common 10m target centers. Nearby setups use a fixed 360m central disk, not full views. Upsampling isolates numerical/detail sensitivity imperfectly; bilinear interpolation changes surface. Horizontal shifts are sensitivity, not proven registration correction. Profiles deliberately selected at disagreements; not independent validation data.'))
    print('Geometry:',[(r['case'],round(r['visible_km2'],4)) for r in rows[:4]],flush=True)
