"""Single-tile local lidar diagnostic. Opaque return columns are not optical truth."""
import sys,json,math,shutil
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from osgeo import gdal
from .acquire import dump,digest,srs,Fetcher
from .vegetation_rays import ray
from . import core

def run(cfg,c,p):
    out=Path(cfg['output']);path=out/'downloads/local_A0031.laz'
    (out/'downloads').mkdir(exist_ok=True)
    for source in Path(cfg.get('lidar_metadata_dir',str(out/'downloads'))).glob('*.json'):
        dest=out/'downloads'/source.name
        if source.resolve()!=dest.resolve():shutil.copyfile(source,dest)
    if cfg.get('lidar_source'):
        spec=cfg['lidar_source'];cached=Path(spec['path'])
        if cached.exists():path=cached
        elif spec['bytes']<=cfg['download_bytes']:
            f=Fetcher(out/'downloads',cfg['download_bytes']);path=f.get('local_A0031.laz',spec['url'],provider='USGS3DEP',acquisition_date='2019 project; exact days in original metadata',license='USGS public domain')
        if digest(path)!=spec['sha256']:raise ValueError('Pinned lidar checksum mismatch')
    if not path.exists():dump(out/'fine_lidar.json',dict(status='unavailable',reason='Pinned local tile missing; coarse diagnostics completed'));return
    sys.path.insert(0,str(Path('.cache/vegetation-deps').resolve()))
    try:import laspy;import pyproj
    except ImportError as e:dump(out/'fine_lidar.json',dict(status='unavailable',reason=str(e)+'; install laspy2.6.1/lazrs0.7.0 in .cache/vegetation-deps'));return
    res=2.;n=301;gt=(p['x']-(n/2)*res,res,0,p['y']+(n/2)*res,0,-res);xy=[];zz=[];cls=[];hist={}
    with laspy.open(path,laz_backend=laspy.LazBackend.Lazrs) as f:
        crs=f.header.parse_crs();count=f.header.point_count
        if crs is None:raise ValueError('Lidar CRS missing')
        axes=crs.axis_info;vertical=[a for a in axes if a.direction.lower()=='up'];unit=vertical[0].unit_conversion_factor if vertical else None
        if unit is None:raise ValueError('Explicit lidar vertical units required; no datum/unit guess')
        tr=pyproj.Transformer.from_crs(crs,pyproj.CRS.from_epsg(c['epsg']),always_xy=True)
        for chunk in f.chunk_iterator(100000):
            classes=np.asarray(chunk.classification);unique,num=np.unique(classes,return_counts=True)
            for k,v in zip(unique,num):hist[str(k)]=hist.get(str(k),0)+int(v)
            x,y=tr.transform(np.asarray(chunk.x),np.asarray(chunk.y));z=np.asarray(chunk.z)*unit
            keep=(x>=gt[0])&(x<gt[0]+n*res)&(y<=gt[3])&(y>gt[3]-n*res)&~np.asarray(chunk.withheld,dtype=bool)&~np.isin(classes,[7,18])
            xy.append(np.c_[x[keep],y[keep]]);zz.append(z[keep]);cls.append(classes[keep])
    pts=np.concatenate(xy);z=np.concatenate(zz);classes=np.concatenate(cls);groundpts=pts[classes==2];groundz=z[classes==2]
    if not len(groundpts):raise ValueError('No classified ground returns in local subset')
    yy,xx=np.mgrid[:n,:n];centres=np.c_[gt[0]+(xx.ravel()+.5)*res,gt[3]+(yy.ravel()+.5)*-res];dist,idx=cKDTree(groundpts).query(centres);ground=np.where(dist<=5,groundz[idx],np.nan).reshape(n,n)
    rows=np.floor((pts[:,1]-gt[3])/-res).astype(int);cols=np.floor((pts[:,0]-gt[0])/res).astype(int);flat=rows*n+cols;countgrid=np.bincount(flat,minlength=n*n).reshape(n,n);top=np.full(n*n,-np.inf);np.maximum.at(top,flat,z);top=top.reshape(n,n)
    height=np.where((countgrid>0)&np.isfinite(ground),np.maximum(0,top-ground),np.nan);height=np.where(height>=.5,height,0)*np.where(np.isfinite(height),1,np.nan)
    for name,a in [('ground',ground),('return_column_height',height),('return_count',countgrid)]:core.write_raster(out/('lidar_'+name+'.tif'),np.where(np.isfinite(a),a,-9999).astype('float32'),gt,srs(c['epsg']).ExportToWkt(),-9999)
    observer=(n//2,n//2);d=np.hypot(xx-observer[1],yy-observer[0])*res;eligible=(d>=40)&(d<=200)&np.isfinite(ground)&np.isfinite(height);choices=np.flatnonzero(eligible);rng=np.random.default_rng(cfg['seed']);chosen=rng.choice(choices,min(96,len(choices)),replace=False);scenarios=[]
    bare_results=None
    for scale in [0.,.5,1.]:
        h=height*scale;results=[ray(ground,h,res,observer,tuple(np.unravel_index(v,ground.shape)),c['eye_m'],c['target_m'],c['curvature']) for v in chosen]
        if scale==0:bare_results=results
        bare_clear=[not r['terrain'] and not r['unknown'] for r in bare_results]
        conditional_clear=sum(keep and not any(r[k] for k in ['observer','intermediate','target','unknown','terrain']) for keep,r in zip(bare_clear,results))
        counts={k:sum(r[k] for r in results) for k in ['observer','intermediate','target','unknown','terrain']};scenarios.append(dict(column_scale=scale,n=len(results),bare_clear_n=sum(bare_clear),clear_among_bare_clear=conditional_clear,**counts,clear=sum(not any(r[k] for k in ['observer','intermediate','target','unknown','terrain']) for r in results)))
    localmask=(abs(xx-n//2)*res<=35)&(abs(yy-n//2)*res<=35);localvalid=localmask&np.isfinite(height)
    info=dict(legacy_square_lidar_known_fraction=float(localvalid.sum()/localmask.sum()),legacy_square_returns_above_2m_fraction=float((height[localvalid]>=2).mean()),minimum_column_height_m=.5,status='local_return_column_sensitivity_only',path=str(path),sha256=digest(path),crs_wkt=crs.to_wkt(),vertical_axes=[str(a) for a in vertical],vertical_unit_to_m=unit,vertical_reference=str(crs),download_bytes=path.stat().st_size,point_count=count,local_points=len(z),classification_counts=hist,grid_resolution_m=res,bounds=[gt[0],gt[3]-n*res,gt[0]+n*res,gt[3]],ground_interpolation='nearest classified-ground point within5m; farther cells unknown',no_return_cell_fraction=float((countgrid==0).mean()),ground_beyond_5m_fraction=float((dist>5).mean()),horizontal_transform_description=tr.description,horizontal_transform_accuracy_m=tr.accuracy,unknown_cell_fraction=float((~np.isfinite(height)).mean()),observer_ground_m=float(ground[observer]),observer_return_column_height_m=float(height[observer]),scenarios=scenarios,source_date='2019-08-21 through 2019-09-19 project metadata interval; individual return acquisition times not interpreted',limitations='All nonnoise returns form max-elevation columns; not verified vegetation-only or optical blockage. Opaque and half-height scenarios ignore crown gaps/understory. Observer and target are ground-based. No vertical correction to baseline performed; matched local arms share lidar-derived ground.')
    dump(out/'fine_lidar.json',info)
    import matplotlib.pyplot as plt
    from .correction_packet import extent
    fig,axes=plt.subplots(1,3,figsize=(15,6));ims=json.loads((Path(cfg['review'])/'imagery.json').read_text());im=gdal.Open(ims[p['id']+'_setup']['path']);axes[0].imshow(im.ReadAsArray()[:3].transpose(1,2,0),extent=extent(im));axes[0].set_title('Unobscured NAIP2019 (0.6m source)')
    ext=[gt[0],gt[0]+n*res,gt[3]-n*res,gt[3]];m=axes[1].imshow(np.ma.masked_invalid(height),extent=ext,vmin=0,vmax=25,cmap='YlGn');fig.colorbar(m,ax=axes[1],label='Return-column height above local ground (m)');axes[1].set_title('2m max-return-column proxy\nWhite cells unknown')
    tree=gdal.Open(str(Path(c['work'])/'tree.tif'));m=axes[2].imshow(tree.ReadAsArray()*100,extent=extent(tree),vmin=0,vmax=100,cmap='YlGn');fig.colorbar(m,ax=axes[2],label='RCMAP2023 tree cover (%)');axes[2].set_title('~30m source, repeated on10m grid')
    for ax in axes:ax.plot(p['x'],p['y'],'r^',mec='white');ax.set_xlim(p['x']-200,p['x']+200);ax.set_ylim(p['y']-200,p['y']+200);ax.ticklabel_format(style='plain',useOffset=False);ax.tick_params(labelsize=7)
    fig.suptitle(p['id']+' — local lidar comparison, not measured deer visibility');fig.text(.03,.02,'Ground endpoints; no canopy-top targets. Local ground interpolated only within5m of ground returns. Solid columns overstate obstruction through crowns.\nUnknown lidar cells remain unknown; 2019 vegetation may differ today. Different products/resolutions are not interchangeable ground truth.',fontsize=9);fig.tight_layout(rect=[0,.1,1,.93]);fig.savefig(out/'fine_lidar_review.png',dpi=160);plt.close(fig)
