"""QGIS products, analyst maps, and separately blinded human review sheets."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/glassing-correction-mpl')
import json,csv,math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle,Polygon as PlotPolygon
from osgeo import gdal,ogr,osr
from shapely.geometry import Polygon,shape,Point,box
from shapely.validation import make_valid
from shapely.ops import transform
from .acquire import dump,srs
from . import compare,core
from .correction_access import projector


def wedge(p,t):
    az=np.radians(np.linspace(t['azimuth_start'],t['azimuth_end'],31))
    outer=list(zip(p['x']+t['outer_m']*np.sin(az),p['y']+t['outer_m']*np.cos(az)))
    inner=list(zip(p['x']+t['inner_m']*np.sin(az[::-1]),p['y']+t['inner_m']*np.cos(az[::-1])))
    return Polygon(outer+inner)


def extent(ds):
    g=ds.GetGeoTransform();return [g[0],g[0]+ds.RasterXSize*g[1],g[3]+ds.RasterYSize*g[5],g[3]]


def draw_lines(ax,g,**kwargs):
    if g.geom_type in ['LineString','LinearRing']:ax.plot(*g.xy,**kwargs)
    elif hasattr(g,'geoms'):
        for sub in g.geoms:draw_lines(ax,sub,**kwargs)


def imagery_ax(ax,record):
    ds=gdal.Open(record['path']);im=ds.ReadAsArray()[:3].transpose(1,2,0)
    ax.imshow(im,extent=extent(ds));ax.set_aspect('equal')


def run(c):
    from .correct import csvwrite
    root=Path(c['work']);analyst=root/'analyst';blind=root/'blinded';analyst.mkdir(exist_ok=True);blind.mkdir(exist_ok=True)
    cc=json.loads(Path(c['comparison_config']).read_text());b,base,ds,a,gt,masks=compare.load(cc)
    pts=json.loads((Path(cc['work'])/'pool.json').read_text());points={p['id']:p for p in pts}
    summary=json.loads((root/'attention_summary.json').read_text());ids=summary['review_ids'];patches=json.loads((root/'patches.json').read_text())
    rows=list(csv.DictReader(open(root/'attention_scores.csv')));nom={r['id']:float(r['score']) for r in rows if r['scenario']=='selective_winter0.5_minutes30'}
    order=sorted(nom,key=lambda i:(-nom[i],i));ranks={i:n+1 for n,i in enumerate(order)}
    comps={r['id']:r for r in csv.DictReader(open(root/'components.csv'))}
    access={r['id']:r for r in json.loads((root/'access_summary.json').read_text())['candidates']}
    ims={r['id']:r for r in json.loads((root/'imagery.json').read_text())} if (root/'imagery.json').exists() else {}
    wide={r['id']:r for r in json.loads((root/'wide_imagery.json').read_text())} if (root/'wide_imagery.json').exists() else {}
    features=json.loads((root/'access_geometry.json').read_text())['features']
    gpkg=root/'review.gpkg'
    if gpkg.exists():gpkg.unlink()
    out=ogr.GetDriverByName('GPKG').CreateDataSource(str(gpkg))
    def layer(name,fields):
        lay=out.CreateLayer(name,srs=srs(32613),geom_type=ogr.wkbUnknown)
        for key,kind in fields:lay.CreateField(ogr.FieldDefn(key,kind))
        return lay
    def add(lay,geom,values):
        f=ogr.Feature(lay.GetLayerDefn());f.SetGeometry(ogr.CreateGeometryFromWkb(geom.wkb))
        for k,v in values.items():f.SetField(k,v)
        if lay.CreateFeature(f)!=0:raise ValueError('Export failed')
    l=layer('candidates_UNKNOWN_ACCESS',[('id',ogr.OFTString),('score',ogr.OFTReal),('rank',ogr.OFTInteger),('access',ogr.OFTString),('raw_km2',ogr.OFTReal)])
    for p in pts:add(l,Point(p['x'],p['y']),dict(id=p['id'],score=nom[p['id']],rank=ranks[p['id']],access='UNKNOWN',raw_km2=float(comps[p['id']]['raw_km2'])))
    l=layer('selected_attention_patches',[('candidate',ogr.OFTString),('patch',ogr.OFTInteger),('reward',ogr.OFTReal),('cost_minutes',ogr.OFTReal)])
    for i in ids:
        selected=patches[i]['selection']['patch_ids']
        for t in patches[i]['patches']:
            if t['id'] in selected:add(l,wedge(points[i],t),dict(candidate=i,patch=t['id'],reward=t['reward'],cost_minutes=math.ceil((t['full_area_km2']/c['scan_km2_per_minute']+c['patch_overhead_minutes'])/c['time_quantum_minutes']-1e-9)*c['time_quantum_minutes']))
    l=layer('distance_bands',[('candidate',ogr.OFTString),('outer_m',ogr.OFTInteger)])
    for i in ids:
        p=Point(points[i]['x'],points[i]['y'])
        for r in [500,1000,1500,2000]:add(l,p.buffer(r).difference(p.buffer(r-500)) if r>500 else p.buffer(r),dict(candidate=i,outer_m=r))
    l=layer('access_EVIDENCE_NOT_ROUTES',[('id',ogr.OFTString),('kind',ogr.OFTString)])
    for f in features:add(l,shape(f['geometry']),f['properties'])
    xy=projector();network=[]
    for typ in ['roads','trails','closed_roads']:
        l=layer('USFS_'+typ,[('source_id',ogr.OFTString),('name',ogr.OFTString),('attributes',ogr.OFTString)])
        for f in json.loads((Path(c['inputs'])/(typ+'.geojson')).read_text())['features']:
            g=transform(xy,shape(f['geometry']));prop=f['properties'];network.append((typ,g))
            add(l,g,dict(source_id=str(prop.get('id',prop.get('trail_no'))),name=prop.get('name',prop.get('trail_name','')),attributes=json.dumps(prop)))
    l=layer('ownership_FS_NONFS_not_permissions',[('class',ogr.OFTString)])
    for f in json.loads((Path(c['inputs'])/'ownership.geojson').read_text())['features']:
        g=transform(xy,shape(f['geometry']));g=make_valid(g) if not g.is_valid else g
        add(l,g.intersection(box(*c['access_bounds_utm'])),{'class':f['properties']['ownerclassification']})
    study=shape(json.loads((base/'study.json').read_text())['geometry'])
    l=layer('study_target_boundary',[('meaning',ogr.OFTString)]);add(l,study,{'meaning':'target support; obstruction terrain remains outside'})
    l=layer('C0064_local_setup_samples',[('case',ogr.OFTString),('visible_km2',ogr.OFTReal),('status',ogr.OFTString)])
    for q in json.loads((root/'geometry/summary.json').read_text())['cases']:
        if q['case'].startswith('nearby_'):add(l,Point(q['observer_x'],q['observer_y']),dict(case=q['case'],visible_km2=q['visible_km2'],status='10m technical mask only; physical/legal unknown; fixed 360m support'))
    out=None
    read=ogr.Open(str(gpkg));l=read.GetLayerByName('candidates_UNKNOWN_ACCESS')
    if l.GetFeatureCount()!=150 or not l.GetSpatialRef().IsSame(srs(32613)):raise ValueError('GPKG CRS/count failure')
    for f in l:
        p=points[f.GetField('id')];g=f.GetGeometryRef()
        if math.hypot(g.GetX()-p['x'],g.GetY()-p['y'])>1e-6:raise ValueError('Export coordinate mismatch')
    dump(root/'export_checks.json',dict(epsg=32613,candidate_count=150,read_back_passed=True,layers=read.GetLayerCount()))
    read=None
    # Analyst-only full-radius terrain masks, bands and attention patches.
    fig,axes=plt.subplots(2,3,figsize=(15,10))
    for ax,i in zip(axes.flat,ids):
        p=points[i];vs=compare.get_view(cc,b,base,ds,p,2000)
        vg=vs.GetGeoTransform();v=vs.ReadAsArray();r=int(round((vg[3]-gt[3])/gt[5]));col=int(round((vg[0]-gt[0])/gt[1]));h,w=v.shape
        ax.imshow(a[r:r+h,col:col+w],extent=extent(vs),cmap='gray',alpha=.85)
        _,_,eligible=core.score_mask(vs,gt,a.shape,masks['target'],p['x'],p['y'],2000)
        ax.imshow(np.ma.masked_where(~eligible,v),extent=extent(vs),cmap='Blues',vmin=0,vmax=1,alpha=.3)
        for t in patches[i]['patches']:
            if t['id'] in patches[i]['selection']['patch_ids']:
                ax.add_patch(PlotPolygon(np.array(wedge(p,t).exterior.coords),fill=False,edgecolor='darkorange',linewidth=1.2))
        for radius in [500,1000,1500,2000]:ax.add_patch(Circle((p['x'],p['y']),radius,fill=False,color='black',lw=.4,ls='--'))
        for typ,g in network:draw_lines(ax,g,color='crimson' if typ=='closed_roads' else '#333333',lw=.6,alpha=.8)
        draw_lines(ax,study.boundary,color='magenta',lw=1.2)
        ax.plot(p['x'],p['y'],'k^');ax.set_xlim(p['x']-2050,p['x']+2050);ax.set_ylim(p['y']-2050,p['y']+2050);ax.set_aspect('equal')
        ax.set_title(f'{i}: selective rank {ranks[i]} | ACCESS UNKNOWN\nMapped-network gap {access[i]["mapped_network_gap_m"]:g} m',fontsize=10)
        ax.ticklabel_format(useOffset=False,style='plain');ax.tick_params(labelsize=7)
    fig.suptitle('Analyst review: eligible visible targets blue; chosen patches orange; 500m bands; study boundary magenta\nEPSG:32613 metres. Roads/trails gray, closed roads red. Mapped lines do not establish access.');fig.tight_layout();fig.savefig(analyst/'overview.png',dpi=150);plt.close(fig)
    # Regional mapped-connectivity context with gaps explicitly distinguished.
    fig,ax=plt.subplots(figsize=(10,10))
    for typ,g in network:draw_lines(ax,g,color='lightgray' if typ!='closed_roads' else 'salmon',lw=.7)
    for f in features:
        g=shape(f['geometry']);kind=f['properties']['kind']
        if g.geom_type=='Point':ax.plot(g.x,g.y,'ks');ax.annotate(kind.split(';')[0],(g.x,g.y),fontsize=7)
        else:draw_lines(ax,g,color='red' if kind.startswith('unmapped') else 'blue',lw=1.5,ls='--' if kind.startswith('unmapped') else '-')
    for i in ids:p=points[i];ax.plot(p['x'],p['y'],'ko');ax.annotate(i,(p['x'],p['y']),fontsize=8)
    ax.set_xlim(c['access_bounds_utm'][0],c['access_bounds_utm'][2]);ax.set_ylim(c['access_bounds_utm'][1],c['access_bounds_utm'][3]);ax.set_aspect('equal');ax.ticklabel_format(useOffset=False,style='plain');ax.set_title('Mapped connectivity only: blue witness, red straight UNKNOWN gaps\nNo navigation route; no certified entry, parking or current closure clearance.');fig.tight_layout();fig.savefig(analyst/'access.png',dpi=150);plt.close(fig)
    # Matched 400m views + profiles, deliberately diagnostic rather than held-out checks.
    gr=root/'geometry';fig,axes=plt.subplots(2,2,figsize=(10,9));p=points['C0064']
    for ax,name in zip(axes.flat,['control10m','fine1m','fine_averaged10m','averaged_upsampled1m']):
        v=gdal.Open(str(gr/(name+'_view.tif')));ax.imshow(v.ReadAsArray()==1,extent=extent(v),cmap='Blues',vmin=0,vmax=1);ax.plot(p['x'],p['y'],'r^');ax.set_title(name);ax.set_aspect('equal');ax.ticklabel_format(useOffset=False,style='plain');ax.tick_params(labelsize=7)
    fig.suptitle('C0064: 400m local geometry, NOT a full 2km rank correction');fig.tight_layout();fig.savefig(analyst/'C0064_geometry.png',dpi=150);plt.close(fig)
    pr=list(csv.DictReader(open(gr/'profiles.csv')));fig,axes=plt.subplots(2,2,figsize=(12,8))
    for n,ax in enumerate(axes.flat):
        for name,color in [('fine1m','black'),('control10m','tab:orange'),('fine_averaged10m','tab:blue')]:
            rs=[r for r in pr if int(r['profile'])==n and r['surface']==name]
            ax.plot([float(r['distance_m']) for r in rs],[float(r['ground_m']) for r in rs],color=color,label=name)
            ax.plot([float(r['distance_m']) for r in rs],[float(r['sightline_m']) for r in rs],color=color,ls='--',lw=.8)
        ax.set_title(f'Diagnostic ray {n}, bearing {float(rs[0]["azimuth_deg"]):.1f}°');ax.set_xlabel('Distance m');ax.set_ylabel('Elevation m');ax.legend(fontsize=7)
    fig.suptitle('Selected disagreement rays: ground solid, curvature-adjusted LOS dashed; same bare-earth endpoints');fig.tight_layout();fig.savefig(analyst/'C0064_profiles.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,8));p=points['C0064']
    if 'C0064' in ims:imagery_ax(ax,ims['C0064'])
    for q in json.loads((gr/'summary.json').read_text())['cases']:
        if q['case'].startswith('nearby_'):
            ax.plot(q['observer_x'],q['observer_y'],'o',color='cyan');ax.annotate(q['case'].replace('nearby_','')+'\n'+f'{q["visible_km2"]:.4f}',(q['observer_x'],q['observer_y']),xytext=(0,5),textcoords='offset points',color='white',fontsize=8,ha='center')
    ax.set_xlim(p['x']-65,p['x']+65);ax.set_ylim(p['y']-65,p['y']+65);ax.ticklabel_format(useOffset=False,style='plain');ax.set_title('C0064: 20m-offset setups, local visible km² on SAME 360m disk\n2019-09-14 NAIP; technical mask only, physical/legal access UNKNOWN');fig.tight_layout();fig.savefig(analyst/'C0064_setups.png',dpi=150);plt.close(fig)
    # Blinding is for independent humans; automated chart inspection is not adjudication.
    rng=np.random.default_rng(c['seed']);review=[];targets=[];keys=[];tr=osr.CoordinateTransformation(srs(32613),srs(4326))
    for n,i in enumerate(rng.permutation(ids),1):
        i=str(i);p=points[i];label=f'R{n:03}';lon,lat,_=tr.TransformPoint(p['x'],p['y']);keys.append(dict(blind_id=label,candidate_id=i,selective_rank=ranks[i]))
        review.append(dict(blind_id=label,longitude=lon,latitude=lat,imagery_review_minutes=15,proposed_field_dwell_minutes=30,eye_m=1.7,target_m=.8,split='development' if p['y']>=4279720 else 'held_out',access_verified='',setup_usable='',target_patches_inspectable='',critical_false_visible='',planning_minutes='',reviewer='',reviewed_utc='',notes=''))
        fig,axes=plt.subplots(1,2,figsize=(13,6));ax,local=axes
        if i in wide and wide[i].get('path'):imagery_ax(ax,wide[i])
        else:ax.text(.1,.5,'Wide imagery unavailable',transform=ax.transAxes)
        if i in ims and ims[i].get('path'):imagery_ax(local,ims[i])
        else:local.text(.1,.5,'Setup imagery unavailable',transform=local.transAxes)
        for k,az in enumerate(np.arange(0,360,45)):
            distance=500 if k%2==0 else 1500;x=p['x']+distance*np.sin(np.radians(az));y=p['y']+distance*np.cos(np.radians(az));lo,la,_=tr.TransformPoint(x,y)
            r=math.floor((y-gt[3])/gt[5]);col=math.floor((x-gt[0])/gt[1]);targetid=f'P{k+1}'
            targets.append(dict(blind_id=label,patch_id=targetid,longitude=lo,latitude=la,in_study=bool(masks['target'][r,col]),patch_radius_m=30,terrain_visible='',vegetation_blocks='',can_detect_deer_sized_object='',can_classify='',can_judge_antlers='',evidence='',notes=''))
            ax.add_patch(Circle((x,y),30,fill=False,color='yellow'));ax.annotate(targetid,(x,y),color='yellow',fontsize=9)
        for axis in axes:axis.plot(p['x'],p['y'],'^',color='cyan');axis.ticklabel_format(useOffset=False,style='plain');axis.tick_params(labelsize=7)
        ax.set_title(label+' — fixed target patches, 4km context');local.set_title(label+' — 600m setup context')
        dates=', '.join(sorted(set(ims.get(i,{}).get('dates',['unknown']))));fig.suptitle(f'{label} | USDA NAIP acquired {dates} | EPSG:32613 metres\nImagery alone cannot establish deer detection, legal access or current vegetation.');fig.tight_layout();fig.savefig(blind/(label+'.png'),dpi=150);plt.close(fig)
    csvwrite(blind/'REVIEW.csv',review);csvwrite(blind/'TARGETS.csv',targets);dump(analyst/'DO_NOT_SHARE_KEY.json',keys)
    (blind/'INSTRUCTIONS.md').write_text((Path(cc['work'])/'REVIEW_INSTRUCTIONS.md').read_text().replace('BLINDED_REVIEW.csv','REVIEW.csv').replace('BLINDED_TARGETS.csv','TARGETS.csv')+'\nCorrection packet: give reviewers ONLY this directory. The six unique positions are diagnostic additions; preserve the earlier full comparison packet. Images show fixed, score-independent patches and a setup inset; no predicted visibility or selected sectors. NAIP is from 2019, exported at 4m context / 1m setup, native metadata 0.6m. It cannot show present-day obstructions or resolve antlers. Leave unassessable geometry/detection fields unknown. No human observations have been collected. This pass does not change the predeclared development/held-out split or continue gates.\n')
    reasons={'C0068':'Leading nominal selective scenario; survives attention/season sensitivity top tens; access and fine terrain unverified.','C0095':'Winter-like/selective alternative; top-two nominal; no expert validation.','C0090':'Original uniform winner; near mapped road, but connected entry/parking and setup unverified.','C0064':'Raw terrain control; strong local source/setup sensitivity; do not extrapolate 400m difference to 2km.','C0025':'Preserved original stratified-random review position, a counterexample rather than a weighted-score winner.'}
    alternatives=[]
    for i,why in reasons.items():alternatives.append(dict(id=i,reason=why,selective_rank=ranks[i],selective_score=nom[i],raw_km2=float(comps[i]['raw_km2']),mapped_network_gap_m=access[i]['mapped_network_gap_m'],access='UNKNOWN',field_ready=False))
    csvwrite(root/'alternatives.csv',alternatives);dump(root/'field_ready_shortlist.json',dict(candidates=[],reason='All connected legal/physical approaches and setups unverified.'))
    print('Packet: QGIS read-back passed; 5 alternatives, 6 blinded reviews, 48 fixed targets; no human ratings.',flush=True)
