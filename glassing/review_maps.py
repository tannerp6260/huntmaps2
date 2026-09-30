"""Derived, read-only visualization of saved scouting results; never rescores."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/glassing-review-mpl')
import argparse,json,datetime as dt,time,urllib.parse
from pathlib import Path
import numpy as np
from osgeo import gdal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import LightSource,ListedColormap
from matplotlib.patches import Circle,Patch
from matplotlib.lines import Line2D
from shapely.geometry import shape
from .acquire import Fetcher,digest,dump
from .transfer import project
from .correction_packet import extent,draw_lines,wedge
from . import core

SERVICE='https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer'
def read(p):return json.loads(Path(p).read_text())

def visible_mask(vs,dem,target,p,radius):
    gt=dem.GetGeoTransform();vg=vs.GetGeoTransform()
    if not vs.GetSpatialRef().IsSame(dem.GetSpatialRef()):raise ValueError('Viewshed and analysis CRS differ')
    if not np.allclose([vg[1],vg[2],vg[4],vg[5]],[gt[1],gt[2],gt[4],gt[5]],atol=1e-9):raise ValueError('Viewshed grid differs')
    co=(vg[0]-gt[0])/gt[1];ro=(vg[3]-gt[3])/gt[5]
    if max(abs(co-round(co)),abs(ro-round(ro)))>1e-8:raise ValueError('Nonintegral viewshed origin offset')
    co,ro=round(co),round(ro);h,w=vs.RasterYSize,vs.RasterXSize
    if ro<0 or co<0 or ro+h>target.shape[0] or co+w>target.shape[1]:raise ValueError('Viewshed exceeds target grid')
    # Read original pixels, no resampling or vector smoothing of visibility.
    x=vg[0]+(np.arange(w)+.5)*vg[1];y=vg[3]+(np.arange(h)+.5)*vg[5]
    local=(vs.ReadAsArray()==1)&target[ro:ro+h,co:co+w]&(np.hypot(x[None,:]-p['x'],y[:,None]-p['y'])<=radius)
    full=np.zeros(target.shape,bool);full[ro:ro+h,co:co+w]=local
    area=int(full.sum())*abs(gt[1]*gt[5])/1e6
    if abs(area-p['raw_km2'])>1e-9:raise ValueError(f'Visible area mismatch {p["id"]}: {area} != {p["raw_km2"]}')
    return full,dict(id=p['id'],origin_offset_cells=[co,ro],source_transform=vg,analysis_transform=gt,visible_cells=int(full.sum()),mapped_km2=area,reported_km2=p['raw_km2'],difference_km2=area-p['raw_km2'],tolerance_km2=1e-9)

def imagery(fetch,p,bounds,size,epsg,tag):
    name=p['id']+'_'+tag
    query=dict(f='json',where='Category=1',geometry=','.join(map(str,bounds)),geometryType='esriGeometryEnvelope',inSR=epsg,spatialRel='esriSpatialRelIntersects',outFields='*',returnGeometry='false')
    data=fetch.json(name+'_records.json',SERVICE+'/query?'+urllib.parse.urlencode(query),provider='USGS/USDA NAIP',purpose='date/source lock for derived review')
    if data.get('exceededTransferLimit'):raise ValueError('NAIP catalog truncated')
    fs=data.get('features',[])
    if not fs:raise ValueError('No intersecting NAIP records')
    year=max(f['attributes']['Year'] for f in fs);chosen=[f['attributes'] for f in fs if f['attributes']['Year']==year]
    ids=[f['OBJECTID'] for f in chosen];dates=sorted(set(dt.datetime.fromtimestamp(f['acquisition_date']/1000,dt.timezone.utc).date().isoformat() if f.get('acquisition_date') else 'unknown' for f in chosen))
    args=dict(f='image',bbox=','.join(map(str,bounds)),bboxSR=epsg,imageSR=epsg,size=f'{size},{size}',format='tiff',mosaicRule=json.dumps(dict(mosaicMethod='esriMosaicLockRaster',lockRasterIds=ids)),renderingRule=json.dumps(dict(rasterFunction='NaturalColor')))
    path=fetch.get(name+'.tif',SERVICE+'/exportImage?'+urllib.parse.urlencode(args),provider='USGS/USDA NAIP',acquisition_dates=dates,object_ids=ids,license='USDA/USGS public-domain imagery; service terms in service.json',export_resolution_m=(bounds[2]-bounds[0])/size)
    ds=gdal.Open(str(path))
    if ds is None or ds.RasterCount<3:raise ValueError('Invalid orthophoto response')
    gt=ds.GetGeoTransform();returned=[gt[0],gt[3]+ds.RasterYSize*gt[5],gt[0]+ds.RasterXSize*gt[1],gt[3]]
    if ds.GetSpatialRef().GetAuthorityCode(None)!=str(epsg) or not np.allclose(returned,bounds,atol=.05):raise ValueError('Imagery footprint/CRS does not match request')
    valid=np.ones((ds.RasterYSize,ds.RasterXSize),bool)
    for n in range(1,4):valid&=ds.GetRasterBand(n).GetMaskBand().ReadAsArray()>0
    rgb=ds.ReadAsArray()[:3].transpose(1,2,0)
    # Reject gaps even if service omitted NoData metadata; black pixels are conservatively suspect.
    valid&=np.any(rgb!=0,axis=2)
    if not valid.all():raise ValueError(f'Incomplete imagery valid footprint: {valid.mean():.3%}; use hillshade fallback')
    return dict(path=str(path),dates=dates,year=year,object_ids=ids,source_records=chosen,bounds=returned,resolution_m=gt[1],valid_fraction=float(valid.mean()),native_resolution_m=sorted(set(f.get('resolution_value') for f in chosen if f.get('resolution_units')=='METER')))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',default='results/soap-creek-v1');ap.add_argument('--out',default='results/soap-creek-v1-review-v2');ap.add_argument('--download',action='store_true');ap.add_argument('--redraw',action='store_true',help='replace only this derived packet, reusing checked image cache');a=ap.parse_args()
    run=Path(a.run);out=Path(a.out)
    if out.resolve()==run.resolve() or run.resolve() in out.resolve().parents:raise ValueError('Use a separate derived-review directory')
    out.mkdir(parents=True,exist_ok=True)
    if (out/'review_packet.pdf').exists() and not a.redraw:raise ValueError('Completed review exists; choose a new output folder')
    c=read(run/'scouting.json');root=Path(c['work']);points=read(root/'leading.json');patches=read(root/'patches.json');domains=read(root/'intake.json')['geometry'];overlap=read(root/'overlap.json')
    # Read-only validation before drawing; preserve every source byte.
    original=read(run/'manifest.json')
    for path,h in original.items():
        if digest(path)!=h:raise ValueError('Current run integrity failure: '+path)
    dem=gdal.Open(str(root/'dem.tif'));z=dem.ReadAsArray();target=gdal.Open(str(root/'target.tif')).ReadAsArray().astype(bool);gt=dem.GetGeoTransform();masks={};checks=[]
    (out/'visible_masks').mkdir(exist_ok=True)
    for p in points:
        vs=gdal.Open(str(root/'additional_visibility'/f'{p["id"]}_{c["radius_m"]}.tif'));mask,check=visible_mask(vs,dem,target,p,c['radius_m']);masks[p['id']]=mask;checks.append(check)
        core.write_raster(out/'visible_masks'/f'{p["id"]}.tif',mask.astype('uint8'),gt,dem.GetProjection())
    for pair in overlap:
        shared=int((masks[pair['a']]&masks[pair['b']]).sum())*abs(gt[1]*gt[5])/1e6
        if abs(shared-pair['shared_km2'])>1e-9:raise ValueError('Overlap differs from saved result')
    dump(out/'alignment_checks.json',checks)
    fetch=Fetcher(out/'imagery',120000000);images={};print('Imagery estimate: 10 RGB clips, about 40 MB uncompressed including an alpha band, plus metadata; hard cap 120 MB.',flush=True)
    if a.download:
        try:fetch.json('service.json',SERVICE+'?f=json',provider='USGS NAIP ImageServer')
        except Exception as e:print('Imagery service metadata:',e,flush=True)
    for p in points:
        for tag,r,size in [('context',2200,1000),('setup',250,1000)]:
            key=p['id']+'_'+tag;b=[p['x']-r,p['y']-r,p['x']+r,p['y']+r]
            try:
                if not a.download:raise ValueError('Network imagery not requested')
                images[key]=imagery(fetch,p,b,size,c['epsg'],tag);print(key,images[key]['dates'],flush=True)
            except Exception as e:images[key]=dict(error=str(e));print(key,'IMAGERY PENDING:',e,flush=True)
    dump(out/'imagery.json',images)
    shade=LightSource(azdeg=315,altdeg=45).hillshade(z,dx=gt[1],dy=abs(gt[5]));ll=project(c['epsg'],4326)
    pdf=PdfPages(out/'review_packet.pdf');page=0
    def save(fig,name):
        nonlocal page
        page+=1;fig.savefig(out/(f'{page:02}_'+name+'.png'),dpi=140);pdf.savefig(fig);plt.close(fig)
    def north(ax):
        ax.annotate('Grid N',xy=(.955,.96),xytext=(.955,.86),xycoords='axes fraction',ha='center',fontsize=10,fontweight='bold',arrowprops=dict(facecolor='white',edgecolor='black',width=2,headwidth=9),bbox=dict(facecolor='white',alpha=.85,edgecolor='none'))
    def base(ax,bounds,im=None):
        if im and im.get('path'):
            ds=gdal.Open(im['path']);ax.imshow(ds.ReadAsArray()[:3].transpose(1,2,0),extent=extent(ds),interpolation='nearest');caption='NAIP '+', '.join(im['dates'])+f' | native {im["native_resolution_m"]} m; export {im["resolution_m"]:.1f} m/pixel'
        else:
            ax.imshow(shade,extent=extent(dem),cmap='gray',vmin=0,vmax=1);caption='IMAGERY PENDING — shaded terrain, not habitat'
        ax.set_xlim(bounds[0],bounds[2]);ax.set_ylim(bounds[1],bounds[3]);ax.set_aspect('equal');ax.ticklabel_format(style='plain',useOffset=False);ax.tick_params(labelsize=8);north(ax);return caption
    fig,ax=plt.subplots(figsize=(11.7,8.3));base(ax,[extent(dem)[0],extent(dem)[2],extent(dem)[1],extent(dem)[3]])
    draw_lines(ax,shape(domains['observer']).boundary,color='#00e5ff',lw=2);draw_lines(ax,shape(domains['target']).boundary,color='#c26aff',lw=1)
    for n,p in enumerate(points):
        ax.plot(p['x'],p['y'],'r^',mec='white',ms=9);ax.annotate(f'{n+1}. {p["id"]}',(p['x'],p['y']),xytext=(8,8),textcoords='offset points',bbox=dict(facecolor='white',alpha=.8,edgecolor='none'),fontsize=10)
    ax.set_title(run.name+' — unchanged provisional alternatives\nCyan: your observer-search polygon | purple: evaluated target support\nHillshade is terrain context, not habitat; imagery follows on individual pages',fontsize=12)
    ax.set_xlabel(f'Easting (m), EPSG:{c["epsg"]}');ax.set_ylabel('Northing (m)');fig.tight_layout();save(fig,'overview')
    for rank,p in enumerate(points,1):
        lo,la=ll(p['x'],p['y']);chosen=[t for t in patches[p['id']]['patches'] if t['id'] in patches[p['id']]['selection']['patch_ids']]
        bearings='; '.join(f'{t["azimuth_start"]}–{t["azimuth_end"]}° / {t["inner_m"]/1000:g}–{t["outer_m"]/1000:g} km' for t in chosen)
        for tag,r in [('context',2200),('setup',250)]:
            fig=plt.figure(figsize=(11.7,8.3));ax=fig.add_axes([.07,.20,.64,.69]);notes=fig.add_axes([.75,.18,.23,.70]);notes.axis('off');bounds=[p['x']-r,p['y']-r,p['x']+r,p['y']+r]
            caption=base(ax,bounds,images[p['id']+'_'+tag])
            overlay=np.ma.masked_where(~masks[p['id']],masks[p['id']]);ax.imshow(overlay,extent=extent(dem),cmap=ListedColormap(['#00f3ff']),vmin=0,vmax=1,alpha=.38,interpolation='nearest')
            draw_lines(ax,shape(domains['observer']).boundary,color='white',lw=1.2,ls=':')
            for t in chosen:
                g=wedge(p,t).intersection(shape(domains['target']));draw_lines(ax,g.boundary,color='#ff9500',lw=1.5)
            for dist in ([500,1000,1500,2000] if tag=='context' else [50,100,200]):
                ax.add_patch(Circle((p['x'],p['y']),dist,fill=False,color='white',lw=.7,ls='--'))
                ax.text(p['x'],p['y']-dist,f'{dist} m',ha='center',va='top',fontsize=8,bbox=dict(facecolor='black',alpha=.6,edgecolor='none'),color='white')
            ax.plot(p['x'],p['y'],'r^',mec='white',ms=10);ax.set_xlabel('Easting (m)');ax.set_ylabel('Northing (m)')
            fig.suptitle(f'{rank}. {p["id"]} — '+('visible target terrain and inspection sectors' if tag=='context' else 'immediate setup / foreground review')+f'\n{la:.6f}° N, {abs(lo):.6f}° W',fontsize=14,y=.97)
            ax.set_title(caption,fontsize=9)
            handles=[Patch(facecolor='#00f3ff',alpha=.6,label='Terrain-visible targets'),Line2D([0],[0],color='#ff9500',lw=2,label='Inspection footprints'),Line2D([0],[0],color='gray',ls='--',label='Distance rings'),Line2D([0],[0],color='gray',ls=':',label='Observer search boundary')]
            notes.legend(handles=handles,loc='upper left',fontsize=9,frameon=False,borderaxespad=0)
            def percent(v):return 'unknown' if v is None else f'{100*v:.1f}%'
            text=f'Visible target area: {p["raw_km2"]:.4f} km²\nWithin 1 km: {p["within_1km_km2"]:.3f} km²\nLow-tree-cover terrain: {p["low_tree_cover_km2"]:.3f} km²\n\nForeground cover proxy: {percent(p["foreground_cover_mean"])}\nForeground unknown: {percent(p["foreground_unknown_fraction"])}\nVisible cover unknown: {percent(p["unknown_cover_fraction"])}\n\nCover fractions are not measured sightline blockage.\n\nCyan pixels are the saved bare-earth viewshed, clipped to target support and 2 km radius.\n\nOrange sectors are attention footprints: they include hidden terrain.\n\nUncolored terrain is not an absence-of-deer claim.\n\nAccess / ground sightlines remain unverified.'
            import textwrap
            notes.text(0,.76,'\n'.join(textwrap.fill(line,37) if line else '' for line in text.split('\n')),va='top',fontsize=9)
            fig.text(.07,.10,'Selected sector bearings (clockwise from grid north):\n'+textwrap.fill(bearings,125),fontsize=9,va='top')
            fig.text(.07,.025,'10 m terrain visibility; bare-earth endpoints preserved. Aerial canopy appearance does not establish ground-level visibility.\nNorth arrow indicates UTM grid north. Imagery dates are source acquisition dates; pixel size is export sampling.',fontsize=8)
            save(fig,p['id']+'_'+tag)
    fig,ax=plt.subplots(figsize=(11.7,8.3));ax.axis('off');rows=[]
    for v in overlap:rows.append([v['a'],v['b'],f'{v["shared_km2"]:.4f}',f'{v["fraction_a"]:.1%}',f'{v["fraction_b"]:.1%}',f'{v["jaccard"]:.1%}'])
    table=ax.table(cellText=rows,colLabels=['Point A','Point B','Shared km²','% of A visible','% of B visible','Intersection / union'],bbox=[.02,.29,.96,.59]);table.auto_set_font_size(False);table.set_fontsize(11)
    ax.set_title('Complementarity — existing pairwise terrain overlap, unchanged',fontsize=15,pad=20)
    independent=[p['id'] for p in points if all(v['shared_km2']==0 for v in overlap if p['id'] in [v['a'],v['b']])]
    shared=sorted([v for v in overlap if v['shared_km2']>0],key=lambda v:-v['shared_km2'])
    summary=('No shared scored cells with other leaders: '+', '.join(independent)+'.\n') if independent else ''
    if shared:
        v=shared[0];summary+=f"Largest shared area: {v['a']} / {v['b']} ({v['shared_km2']:.4f} km²). Compare foreground and approach practicality.\n"
    summary+='Zero overlap means different modeled target cells, not independent deer opportunities or better access.'
    ax.text(.02,.19,summary,fontsize=11,va='top')
    ax.text(.02,.06,'Human review: inspect openings, immediate tree/branch obstruction and possible nearby setup adjustments.\nField checks: ground-level sightlines, footing, connected legal approach and actual deer-detection performance.',fontsize=11,va='top');save(fig,'overlap')
    pdf.close()
    for path,h in original.items():
        if digest(path)!=h:raise ValueError('Original run changed during review: '+path)
    provenance=dict(source_run=str(run),original_manifest_sha256=digest(run/'manifest.json'),source_hashes={str(p):digest(p) for p in root.rglob('*') if p.is_file()},script_sha256=digest(__file__),new_download_bytes=fetch.used,download_cap_bytes=120000000,area_checks=checks,original_integrity_passed=True,notes='Visualization only. Scores, ranking, original packet and all source files unchanged.')
    dump(out/'provenance.json',provenance);dump(out/'manifest.json',{str(p):digest(p) for p in out.rglob('*') if p.is_file() and p.name!='manifest.json'})
    print('Review ready:',out/'review_packet.pdf',flush=True)
if __name__=='__main__':main()
