"""Labeled provisional desktop review products; never independent blinded evidence."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/glassing-scout-mpl')
import json,math,csv,textwrap,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Circle,Polygon as PlotPolygon
from matplotlib.backends.backend_pdf import PdfPages
from osgeo import gdal,ogr,osr
from shapely.geometry import shape,Point,box,Polygon
from shapely.ops import transform,unary_union
from shapely.validation import make_valid
from . import compare,core
from .acquire import dump,srs
from .correction_access import projector
from .correction_packet import wedge,extent,draw_lines
from .correct import csvwrite

NOTES={
'C0068':('Primary review: treeline / open slope','Treeline transition with scattered crowns to the south; dense crown texture immediately north. Check the original position and 20m south/east alternatives for clear foreground.','Strong broad terrain support and retained selective-attention hypothesis; extra support changes little. Remote/low-pressure use is unmeasured.'),
'C0095':('Primary review: track-side opening','Visible track and opening at the original point; dense trees to the south/southeast. The original fine-terrain setup beats the tested 20m offsets. The visible track is not proof of permission.','More near terrain and shortest screened final leg of the leading three; its proximity to mapped travel weakens any assumption of low pressure.'),
'C0049':('Primary review: opening / slope break','Elongated light-textured opening with scattered trees, bordered by dense forest. Test 20m west/east if branches obstruct the original point.','Restoring support exposes substantially more terrain beyond the artificial crop. It provides a different southward setup, with a longer walking leg.'),
'C0090':('Reserve: open-meadow alternative','Broad opening near a visible track; forest to the west and scattered trees east. Retain as the earlier attention-model alternative.','Smaller terrain footprint. Direct Sun Creek mapped connection remains incomplete; the long off-trail witness is a fallback hypothesis, not the preferred approach.'),
'C0064':('Control only: defer scouting export','Dense crown texture around the original setup. Prior fine-terrain discrepancy and foreground uncertainty remain material.','High raw area does not overcome setup uncertainty. No terrain-screened connector found in the bounded search; this is not evidence of inaccessibility.')}
MAIN=['C0068','C0095','C0049']


def ll(x,y):
    return osr.CoordinateTransformation(srs(32613),srs(4326)).TransformPoint(float(x),float(y))[:2]


def polygons(g):
    if g.geom_type=='Polygon':return [g]
    if hasattr(g,'geoms'):return [p for child in g.geoms for p in polygons(child)]
    return []


def export_field(folder,points,sectors,entries):
    folder.mkdir(exist_ok=True)
    def gpx(name,ids):
        root=ET.Element('gpx',version='1.1',creator='GMU54 provisional desktop review',xmlns='http://www.topografix.com/GPX/1/1')
        for i in ids:
            p=points[i];lon,lat=ll(p['x'],p['y']);w=ET.SubElement(root,'wpt',lat=f'{lat:.8f}',lon=f'{lon:.8f}');ET.SubElement(w,'name').text='PROVISIONAL '+i;ET.SubElement(w,'desc').text='Desktop setup hypothesis. Access, foreground and field performance unverified. No camp or itinerary selected.'
        ET.ElementTree(root).write(folder/name,encoding='utf-8',xml_declaration=True)
    gpx('opportunities.gpx',MAIN);gpx('reserve_C0090.gpx',['C0090'])
    root=ET.Element('gpx',version='1.1',creator='GMU54 provisional desktop review',xmlns='http://www.topografix.com/GPX/1/1')
    for e in entries:
        lon,lat=ll(e['x'],e['y']);w=ET.SubElement(root,'wpt',lat=f'{lat:.8f}',lon=f'{lon:.8f}');ET.SubElement(w,'name').text='ENTRY REVIEW '+e['id'];ET.SubElement(w,'desc').text=e['evidence']+'; '+e['parking']
    ET.ElementTree(root).write(folder/'entry_options.gpx',encoding='utf-8',xml_declaration=True)
    root=ET.Element('kml',xmlns='http://www.opengis.net/kml/2.2');doc=ET.SubElement(root,'Document')
    for i,t,g in sectors:
        if i not in MAIN:continue
        g=g.simplify(10,preserve_topology=True).intersection(g)  # Never enlarge into excluded support.
        pm=ET.SubElement(doc,'Placemark');ET.SubElement(pm,'name').text=f'PROVISIONAL {i} sector {t["id"]}'
        ET.SubElement(pm,'description').text=f'{t["azimuth_start"]}-{t["azimuth_end"]} degrees true; {t["inner_m"]}-{t["outer_m"]}m. Mapped FS/GMU target support only; contains hidden and wooded terrain. Not a visibility guarantee or permission. Simplified 10m; use analysis layer for boundary review.'
        mg=ET.SubElement(pm,'MultiGeometry')
        for p in polygons(g):
            poly=ET.SubElement(mg,'Polygon');ET.SubElement(poly,'altitudeMode').text='clampToGround'
            for tag,ring in [('outerBoundaryIs',p.exterior)]+[('innerBoundaryIs',r) for r in p.interiors]:
                b=ET.SubElement(poly,tag);r=ET.SubElement(b,'LinearRing');ET.SubElement(r,'coordinates').text=' '.join(f'{lo:.8f},{la:.8f},0' for lo,la in [ll(x,y) for x,y in ring.coords])
    ET.ElementTree(root).write(folder/'viewing_sectors.kml',encoding='utf-8',xml_declaration=True)
    # Read-back compares true coordinates, and reconstructs valid KML polygons.
    checks={}
    for name,ids in [('opportunities.gpx',MAIN),('reserve_C0090.gpx',['C0090'])]:
        ws=ET.parse(folder/name).findall('{*}wpt');assert len(ws)==len(ids)
        for w,i in zip(ws,ids):
            lo,la=ll(points[i]['x'],points[i]['y']);assert abs(float(w.attrib['lon'])-lo)<1e-7 and abs(float(w.attrib['lat'])-la)<1e-7
        checks[name]=len(ws)
    count=0
    for p in ET.parse(folder/'viewing_sectors.kml').findall('.//{*}Polygon'):
        rings=[]
        for coords in p.findall('.//{*}coordinates'):
            vals=[tuple(map(float,s.split(',')[:2])) for s in coords.text.split()];assert all(-180<x<180 and -90<y<90 for x,y in vals);rings.append(vals)
        geom=Polygon(rings[0],rings[1:]);assert geom.is_valid and geom.area>0;count+=1
    checks['kml_valid_polygons']=count
    return checks


def run(c):
    root=Path(c['work']);analyst=root/'analyst';analyst.mkdir(exist_ok=True);outdir=root/'field_review';outdir.mkdir(exist_ok=True)
    cc=json.load(open(c['comparison_config']));b,base,ds,a,gt,masks=compare.load(cc);points={p['id']:p for p in json.load(open(base/'candidates.json'))}
    support=json.load(open(root/'support.json'));context=json.load(open(root/'context.json'));access={r['id']:r for r in json.load(open(root/'approach_rows.json'))};entries=json.load(open(root/'entry_options.json'));features=json.load(open(root/'approach_geometry.json'))['features'];details={d['summary']['id']:d for d in json.load(open(root/'approach_details.json'))}
    gm=shape(context['unit_geometry']);pilot=shape(context['pilot_geometry']);xy=projector();ownership=[]
    for f in json.load(open(Path(c['inputs'])/'surface_management.geojson'))['features']:
        g=transform(xy,shape(f['geometry']));ownership.append((f['properties']['adm_code'],make_valid(g) if not g.is_valid else g))
    forest=[]
    for f in json.load(open(Path(c['inputs'])/'ownership.geojson'))['features']:
        if f['properties']['ownerclassification']=='USDA FOREST SERVICE':forest.append(make_valid(transform(xy,shape(f['geometry']))))
    eligible=gm.intersection(unary_union(forest)).difference(unary_union([g for typ,g in ownership if typ=='PRI']))
    sectors=[];rows=[];visible={}
    for i in c['candidates']:
        p=points[i];r=support[i]['restored_FS'];sel=r['selection']['patch_ids'];latlon=ll(p['x'],p['y']);orig=support[i]['frozen_pilot']['summary'];v=r['summary']
        for t in r['patches']:
            if t['id'] in sel:
                g=wedge(p,t).intersection(eligible)
                if not g.is_empty:sectors.append((i,t,g))
        vs=compare.get_view(cc,b,base,ds,p,2000);public=gdal.Open(str(root/'provisional_target_FS_GMU54.tif')).ReadAsArray().astype(bool);_,_,mask=core.score_mask(vs,gt,a.shape,public,p['x'],p['y'],2000)
        path=root/(i+'_restored_visible.tif');core.write_raster(path,mask.astype('uint8'),vs.GetGeoTransform(),ds.GetProjection());visible[i]=path
        chosen=[t for t in r['patches'] if t['id'] in sel];bearings='; '.join(f'{t["azimuth_start"]}-{t["azimuth_end"]}deg / {t["inner_m"]}-{t["outer_m"]}m' for t in chosen)
        oldset=set(support[i]['frozen_pilot']['selection']['patch_ids']);newset=set(sel)
        rows.append(dict(id=i,role=NOTES[i][0],latitude=latlon[1],longitude=latlon[0],pilot_raw_km2=orig['raw_visible_km2'],restored_FS_raw_km2=v['raw_visible_km2'],added_visible_km2=v['raw_visible_km2']-orig['raw_visible_km2'],pilot_target_support_km2=orig['target_support_km2'],restored_target_support_km2=v['target_support_km2'],outside_pilot_disk_fraction=1-orig['target_support_km2']/orig['full_disk_grid_km2'],near_1km_visible_km2=v['near_visible_km2'],far_1_2km_visible_km2=v['far_visible_km2'],low_tree_cover_visible_km2=v['open_cover_visible_km2'],selective_hypothesis=v['selective_score'],changed_selected_patches=len(oldset^newset),selected_bearings=bearings,approach_status=access[i]['status'],desktop_review='dated imagery and terrain reviewed; human adjudication pending',field_review='not performed'))
    csvwrite(analyst/'decision_table.csv',rows);dump(root/'shortlist.json',dict(primary=MAIN,reserve=['C0090'],terrain_control=['C0064'],random_control=c['random_control'],candidates=rows))
    gpkg=root/'scouting.gpkg'
    if gpkg.exists():gpkg.unlink()
    out=ogr.GetDriverByName('GPKG').CreateDataSource(str(gpkg))
    def layer(name,items):
        l=out.CreateLayer(name,srs=srs(32613),geom_type=ogr.wkbUnknown)
        l.CreateField(ogr.FieldDefn('id',ogr.OFTString));l.CreateField(ogr.FieldDefn('details',ogr.OFTString))
        for ident,g,attrs in items:
            if g.is_empty:continue
            if not g.is_valid:raise ValueError('Invalid export '+name)
            f=ogr.Feature(l.GetLayerDefn());f.SetGeometry(ogr.CreateGeometryFromWkb(g.wkb));f.SetField('id',str(ident));f.SetField('details',json.dumps(attrs));assert l.CreateFeature(f)==0
    layer('candidate_review',[(r['id'],Point(points[r['id']]['x'],points[r['id']]['y']),r) for r in rows])
    layer('entry_evidence',[(e['id'],Point(e['x'],e['y']),e) for e in entries])
    layer('target_sectors_hypothesis',[(i+'_'+str(t['id']),g,dict(t,candidate=i)) for i,t,g in sectors])
    layer('distance_bands',[(i+'_'+str(r),Point(points[i]['x'],points[i]['y']).buffer(r).difference(Point(points[i]['x'],points[i]['y']).buffer(max(0,r-500))),{'outer_m':r}) for i in c['candidates'] for r in [500,1000,1500,2000]])
    layer('GMU54',[('54',gm,{'source':'CPW'})]);layer('experimental_pilot',[('pilot',pilot,{'meaning':'experimental crop, not a hunting boundary'})])
    layer('provisional_FS_targets',[('FS_GMU54',eligible,{'access':'provisional ownership, not certified permissions'})])
    region=box(307000,4260000,329000,4286500)
    layer('ownership',[(str(k),g.intersection(region),{'agency':typ}) for k,(typ,g) in enumerate(ownership)])
    layer('approach_evidence_NOT_navigation',[(f['properties']['id'],shape(f['geometry']),f['properties']) for f in features])
    fine=json.load(open(root/'fine/summary.json'))['cases'];layer('nearby_setup_checks',[(p['id']+'_'+p['case'],Point(p['x'],p['y']),p) for p in fine])
    for name in ['roads','trails','cdot_local','blm_co_routes','flowlines','waterbodies','blm_seasonal_closures']:
        file=Path(c['inputs'])/(name+'.geojson')
        if file.exists():layer(name,[(str(k),make_valid(transform(xy,shape(f['geometry']))).intersection(region),f['properties']) for k,f in enumerate(json.load(open(file))['features']) if f['geometry']])
    out=None;read=ogr.Open(str(gpkg));l=read.GetLayerByName('candidate_review');assert l.GetFeatureCount()==5 and l.GetSpatialRef().IsSame(srs(32613))
    for f in l:
        p=points[f.GetField('id')];g=f.GetGeometryRef();assert math.hypot(g.GetX()-p['x'],g.GetY()-p['y'])<1e-6
    checks=export_field(outdir,points,sectors,entries);checks.update(gpkg_layers=read.GetLayerCount(),gpkg_crs=32613,gpkg_coordinate_readback=True);read=None;dump(root/'export_checks.json',checks)
    topo=plt.imread(Path(c['inputs'])/'unit_topo.png');ex=json.load(open(Path(c['inputs'])/'unit_topo_extent.json'))['extent'];te=[ex['xmin'],ex['xmax'],ex['ymin'],ex['ymax']]
    pdf=PdfPages(analyst/'review_packet.pdf')
    fig,axes=plt.subplots(1,2,figsize=(16,10),gridspec_kw={'width_ratios':[1,1.15]});ax=axes[0];ax.imshow(topo,extent=te);draw_lines(ax,gm.boundary,color='#92278f',lw=2);draw_lines(ax,pilot.boundary,color='#ff3300',lw=2);ax.set_title('Pilot within official GMU 54 (purple)\nRed crop is experimental; 64 km² / %.1f%% of unit'%(100*context['pilot_fraction_unit']));ax.set_xlim(te[:2]);ax.set_ylim(te[2:])
    ax=axes[1];ax.imshow(topo,extent=te)
    colors={'USFS':'#1b8a4b','BLM':'#d4b329','PRI':'#ab4040','STA':'#2785dd'}
    for typ,g in ownership:
        for p in polygons(g.intersection(region)):
            ax.add_patch(PlotPolygon(np.asarray(p.exterior.coords),facecolor=colors.get(typ,'gray'),edgecolor='none',alpha=.13))
    draw_lines(ax,pilot.boundary,color='magenta',lw=1.7)
    for f in features:
        if f['properties']['id'] not in MAIN:continue
        g=shape(f['geometry']);kind=f['properties']['kind']
        draw_lines(ax,g,color='#1555ce' if kind=='conditional_motor_designation_chain' else '#e76915',lw=1.2,ls='--' if 'offtrail' in kind else '-')
    for i in c['candidates']:
        p=points[i];ax.plot(p['x'],p['y'],'^',color='#111111' if i in MAIN else '#777777',ms=6);ax.annotate(i,(p['x'],p['y']),xytext=({'C0068':(-44,14),'C0095':(16,0),'C0049':(10,-18)}.get(i,(5,8))),textcoords='offset points',fontsize=9,bbox=dict(fc='white',alpha=.85,ec='none',pad=1))
    for e in entries:
        ax.plot(e['x'],e['y'],'s',color='#2255cc',ms=5);label=e['id'].replace('_',' ');offset=(5,-16) if 'MIDDLE' in label else (5,6);ax.annotate(label,(e['x'],e['y']),xytext=offset,textcoords='offset points',fontsize=7,bbox=dict(fc='white',alpha=.85,ec='none',pad=1))
    ax.set_xlim(308000,328000);ax.set_ylim(4261000,4286500);ax.set_title('Expanded entry investigation and provisional approaches\nFS green / BLM yellow / private red / state blue tint')
    for ax in axes:ax.set_aspect('equal');ax.ticklabel_format(style='plain',useOffset=False);ax.tick_params(labelsize=7);ax.set_xlabel('UTM 13N metres (north up)')
    fig.suptitle('GMU 54 • second rifle 24 October–1 November 2026 • personal trip dates not selected\nBlue: conditional designated road chain; orange: mapped foot / dashed terrain-screened leg. No parking or legal-access certification.',fontsize=13)
    fig.tight_layout(rect=[0,0,1,.94]);fig.savefig(analyst/'overview.png',dpi=150,bbox_inches='tight');pdf.savefig(fig,bbox_inches='tight');plt.close(fig)
    for row in rows:
        i=row['id'];p=points[i];r=access[i];fig=plt.figure(figsize=(15,11));gs=fig.add_gridspec(3,2,height_ratios=[1,1,.88]);ax=fig.add_subplot(gs[:2,0]);im=gdal.Open('data/correction/'+i+'_wide_naip.tif');ax.imshow(im.ReadAsArray()[:3].transpose(1,2,0),extent=extent(im));v=gdal.Open(str(visible[i]));va=v.ReadAsArray();ax.imshow(np.ma.masked_where(va==0,va),extent=extent(v),cmap=ListedColormap(['#00ddff']),vmin=0,vmax=1,alpha=.28)
        for ci,t,g in sectors:
            if ci==i:draw_lines(ax,g.boundary,color='#ffad18',lw=1.2)
        for radius in [500,1000,1500,2000]:ax.add_patch(Circle((p['x'],p['y']),radius,fill=False,ls='--',lw=.55,color='white'));ax.text(p['x']+30,p['y']+radius-55,f'{radius}m',color='white',fontsize=7)
        draw_lines(ax,pilot.boundary,color='magenta',lw=1)
        for f in features:
            if f['properties']['id']==i:draw_lines(ax,shape(f['geometry']),color='yellow',lw=1.2,ls='--' if 'offtrail' in f['properties']['kind'] else '-')
        if (Path(c['inputs'])/'flowlines.geojson').exists():
            for f in json.load(open(Path(c['inputs'])/'flowlines.geojson'))['features']:
                draw_lines(ax,transform(xy,shape(f['geometry'])),color='#39a5ff',lw=.5,alpha=.6)
        ax.plot(p['x'],p['y'],'r+',ms=10);ax.set_xlim(p['x']-2050,p['x']+2050);ax.set_ylim(p['y']-2050,p['y']+2050);ax.set_title('2 km inspection context • NAIP 2019-09-14\nCyan: terrain-visible FS targets; orange: attention sectors',fontsize=10)
        ax2=fig.add_subplot(gs[0,1]);im=gdal.Open('data/correction/'+i+'_naip.tif');ax2.imshow(im.ReadAsArray()[:3].transpose(1,2,0),extent=extent(im));ax2.plot(p['x'],p['y'],'r+',ms=11)
        for q in fine:
            if q['id']==i and q['case'].startswith('offset'):ax2.plot(q['x'],q['y'],'o',ms=3,mfc='none',mec='yellow')
        ax2.set_xlim(p['x']-150,p['x']+150);ax2.set_ylim(p['y']-150,p['y']+150);ax2.set_title('300 m setup window • original + red; ±20 m yellow\nNative NAIP 0.6 m, exported 1 m; ground branches unknown',fontsize=10)
        ax3=fig.add_subplot(gs[1,1]);dem=gdal.Open(str(root/'fine'/(i+'_dem1m.tif'))) if i in MAIN else ds
        from .correction_geometry import sample
        xx=p['x']+np.arange(-200,201,5);yy=np.full_like(xx,p['y']);ax3.plot(xx-p['x'],sample(ds,xx,yy),label='10 m baseline');ax3.plot(xx-p['x'],sample(dem,xx,yy),label='1 m source' if i in MAIN else 'same baseline',ls='--');ax3.axvline(0,color='red',lw=.6);ax3.set_xlabel('West ← offset east (m) → East');ax3.set_ylabel('Bare earth elevation (m)');ax3.legend(fontsize=8);ax3.set_title('Local east–west terrain profile; not a vegetation sightline',fontsize=10)
        for axes in [ax,ax2]:axes.set_aspect('equal');axes.ticklabel_format(style='plain',useOffset=False);axes.tick_params(labelsize=7)
        textax=fig.add_subplot(gs[2,:]);textax.axis('off');heading,observation,reason=NOTES[i]
        effort=(f"Conditional road-end walking return: {r['conditional_roundtrip_miles']} mi / {r['conditional_roundtrip_gain_ft']} ft gain / {r['conditional_roundtrip_hours_low']}–{r['conditional_roundtrip_hours_high']} h, excluding glassing. From documented entry on foot: {r['entrance_roundtrip_miles']} mi / {r['entrance_roundtrip_gain_ft']} ft. Final off-trail leg {r['offtrail_km']} km; parking/road condition unresolved." if 'conditional_roundtrip_miles' in r else r['status'])
        text='\n'.join(textwrap.fill(s,155) for s in [f"{row['latitude']:.6f}, {row['longitude']:.6f} | Original crop {row['pilot_raw_km2']:.3f} → restored FS {row['restored_FS_raw_km2']:.3f} km² terrain-visible. Within 1km {row['near_1km_visible_km2']:.3f}; 1–2km {row['far_1_2km_visible_km2']:.3f}. Low-tree-cover visible proxy {row['low_tree_cover_visible_km2']:.3f} km², not verified glassable area.",observation,reason,effort,'Selected true bearings / range: '+row['selected_bearings'],(f"Off-trail barrier review: {r.get('offtrail_NHD_crossed_features','unknown')} mapped stream features crossed; mean mapped tree cover {100*r.get('offtrail_tree_cover_mean',0):.0f}%. Stream depth, bank condition and understory are unmeasured." if 'offtrail_tree_cover_mean' in r else 'Off-trail connection remains unresolved.'),'Unknowns: trip-day orders, road/parking permissions, snow, stream crossings, deadfall, foreground branches and fall deer use. Old light angles are hypothetical. Labeled desktop review only; field verification pending.'])
        textax.text(0,1,text,va='top',fontsize=9,linespacing=1.35);fig.suptitle(i+' • '+heading,fontsize=16);fig.tight_layout(rect=[0,0,1,.96]);fig.savefig(analyst/(i+'_card.png'),dpi=150,bbox_inches='tight');pdf.savefig(fig,bbox_inches='tight');plt.close(fig)
    pdf.close();print('Packet: overview, five review cards, PDF, three primary GPX points, reserve, sectors and GPKG',flush=True)
