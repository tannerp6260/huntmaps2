"""Portable side-by-side review, with explicit pending imagery/access evidence."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/glassing-transfer-mpl')
import json,csv,math,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from osgeo import gdal,ogr
from shapely.geometry import shape,Point,Polygon
from shapely.ops import transform
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Circle
from .acquire import dump,srs
from .correction_packet import wedge,extent,draw_lines
from .transfer import read,work,project,source
from .correct import csvwrite


def run(c):
    root=work(c);leading=read(root/'leading.json');allpoints=read(root/'scores.json');patches=read(root/'patches.json');inp=read(root/'intake.json');target=shape(inp['geometry']['target']);ref=read(root/'refinement.json');overlap=read(root/'overlap.json');to_ll=project(c['epsg'],4326)
    fields=['id','group','original_id','longitude','latitude','raw_km2','within_1km_km2','beyond_1km_km2','low_tree_cover_km2','unknown_cover_fraction','selective_score','foreground_cover_mean','foreground_unknown_fraction'];table=[]
    for p in allpoints:
        lo,la=to_ll(p['x'],p['y']);table.append({k:p.get(k,lo if k=='longitude' else la if k=='latitude' else '') for k in fields})
    csvwrite(root/'components.csv',table);csvwrite(root/'overlap.csv',overlap) if overlap else (root/'overlap.csv').write_text('a,b,shared_km2,jaccard,fraction_a,fraction_b,distance_m\n')
    # Manual positions retained exactly in lon/lat exports; no rank-based manual removal.
    gp=ET.Element('gpx',version='1.1',creator='provisional transfer review',xmlns='http://www.topografix.com/GPX/1/1');km=ET.Element('kml',xmlns='http://www.opengis.net/kml/2.2');doc=ET.SubElement(km,'Document');sectors=[]
    for p in leading:
        lo,la=(p['longitude'],p['latitude']) if p['group']=='manual' else to_ll(p['x'],p['y']);w=ET.SubElement(gp,'wpt',lat=repr(la),lon=repr(lo));ET.SubElement(w,'name').text='PROVISIONAL '+p.get('original_id',p['id']);ET.SubElement(w,'desc').text=f"{p['group']}; {c['input_kind']}; access and detection unverified; source identity retained in manual_import.json"
        for t in patches[p['id']]['patches']:
            if t['id'] not in patches[p['id']]['selection']['patch_ids']:continue
            g=wedge(p,t).intersection(target).simplify(c['resolution_m'],preserve_topology=True).intersection(target)
            geoms=[g] if g.geom_type=='Polygon' else list(g.geoms) if hasattr(g,'geoms') else []
            for poly in geoms:
                if poly.geom_type!='Polygon' or poly.is_empty:continue
                sectors.append((p['id'],t,poly));pm=ET.SubElement(doc,'Placemark');ET.SubElement(pm,'name').text=f"PROVISIONAL {p.get('original_id',p['id'])} sector {t['id']}";ET.SubElement(pm,'description').text='Inspection footprint contains hidden/wooded terrain. No access/permission guarantee.';pg=ET.SubElement(pm,'Polygon')
                for tag,ring in [('outerBoundaryIs',poly.exterior)]+[('innerBoundaryIs',r) for r in poly.interiors]:
                    node=ET.SubElement(ET.SubElement(pg,tag),'LinearRing');ET.SubElement(node,'coordinates').text=' '.join(f'{lo:.9f},{la:.9f},0' for lo,la in [to_ll(x,y) for x,y in ring.coords])
    ET.ElementTree(gp).write(root/'review.gpx',encoding='utf-8',xml_declaration=True);ET.ElementTree(km).write(root/'sectors.kml',encoding='utf-8',xml_declaration=True)
    gpkg=root/'comparison.gpkg'
    if gpkg.exists():gpkg.unlink()
    ds=ogr.GetDriverByName('GPKG').CreateDataSource(str(gpkg))
    def layer(name,items):
        lay=ds.CreateLayer(name,srs=srs(c['epsg']),geom_type=ogr.wkbUnknown)
        for k in ['id','details']:lay.CreateField(ogr.FieldDefn(k,ogr.OFTString))
        for ident,g,info in items:
            f=ogr.Feature(lay.GetLayerDefn());f.SetField('id',ident);f.SetField('details',json.dumps(info));f.SetGeometry(ogr.CreateGeometryFromWkb(g.wkb));assert lay.CreateFeature(f)==0
    layer('review_points',[(p['id'],Point(p['x'],p['y']),p) for p in leading]);layer('target_sectors',[(i+'_'+str(t['id']),g,t) for i,t,g in sectors]);layer('spatial_domains',[(k,shape(g),{'role':k}) for k,g in inp['geometry'].items()]);ds=None
    rds=ogr.Open(str(gpkg));lay=rds.GetLayerByName('review_points');assert lay.GetFeatureCount()==len(leading) and lay.GetSpatialRef().IsSame(srs(c['epsg']))
    for f,p,w in zip(lay,leading,ET.parse(root/'review.gpx').findall('{*}wpt')):
        g=f.GetGeometryRef();assert math.hypot(g.GetX()-p['x'],g.GetY()-p['y'])<1e-6;xx,yy=project(4326,c['epsg'])(float(w.attrib['lon']),float(w.attrib['lat']));assert math.hypot(xx-p['x'],yy-p['y'])<.01
        if p['group']=='manual':assert float(w.attrib['lon'])==p['longitude'] and float(w.attrib['lat'])==p['latitude']
    for pg in ET.parse(root/'sectors.kml').findall('.//{*}Polygon'):
        rings=[[tuple(map(float,q.split(',')[:2])) for q in coords.text.split()] for coords in pg.findall('.//{*}coordinates')];assert Polygon(rings[0],rings[1:]).is_valid
    dump(root/'export_checks.json',dict(passed=True,point_count=len(leading),automated_count=sum(p['group']=='automated' for p in leading),manual_count=sum(p['group']=='manual' for p in leading),epsg=c['epsg'],manual_coordinates_unchanged=True,kml_polygons=len(sectors)))
    # Comparison language is descriptive, never an independent ecological evaluation.
    auto=[p for p in allpoints if p['group']=='automated'];classification=[]
    for p in [p for p in allpoints if p['group']=='manual']:
        nearest=min(auto,key=lambda q:math.hypot(q['x']-p['x'],q['y']-p['y']));d=math.hypot(nearest['x']-p['x'],nearest['y']-p['y']);classification.append(dict(manual=p['original_id'],nearest_automated=nearest['id'],distance_m=d,interpretation='recovers nearby setup hypothesis' if d<=c['review']['recovery_distance_m'] else 'different sampled opportunity; possible candidate-generation miss requires imagery/human review'))
    summary=[]
    for parent in ref['centres']:
        base=next(p for p in allpoints if p['id']==parent);near=[p for p in ref['points'] if p['parent']==parent];best=max([base]+near,key=lambda p:p['selective_score']);summary.append(dict(parent=parent,best=best['id'],relative_gain=(best['selective_score']/base['selective_score']-1) if base['selective_score'] else None))
    dump(root/'comparison_review.json',dict(recovery=classification,refinement=summary,obvious_useful_misses='PENDING independent imagery/hunter assessment',questionable_reasons='Inspect foreground cover, unknown vegetation, inherited hypothetical light, and attention/raw ordering; high model score is not superiority.',recommendation='Real-area assisted-scouting usefulness pending hunter inputs and review' if c['input_kind']!='hunter' else 'Engineering comparison available; human/field usefulness not established'))
    # Actual imagery only when a checked source is supplied; never synthesize a photo.
    terrain=gdal.Open(str(root/'dem.tif'));pdf=PdfPages(root/'review_packet.pdf');approaches=read(root/'approaches.json') if (root/'approaches.json').exists() else {}
    if c['data'].get('approach_evidence'):
        spec=c['data']['approach_evidence'];approaches=read(source(spec))
    for p in leading:
        fig,axes=plt.subplots(1,2,figsize=(12,6));radius=c['radius_m'];bounds=[p['x']-radius,p['y']-radius,p['x']+radius,p['y']+radius]
        ax=axes[0];matched=False
        for spec in c['data']['imagery']:
            path=source(spec);im=gdal.Warp('',path,format='MEM',dstSRS=srs(c['epsg']).ExportToWkt(),outputBounds=bounds,width=700,height=700,resampleAlg='bilinear');v=im.ReadAsArray()
            if v.ndim==3 and v.shape[0]>=3 and np.any(v[:3]):ax.imshow(v[:3].transpose(1,2,0),extent=extent(im));ax.set_title('Actual source imagery: '+spec.get('acquisition_date','date unknown'),fontsize=9);matched=True;break
        if not matched:ax.imshow(terrain.ReadAsArray(),extent=extent(terrain),cmap='terrain');ax.set_title('IMAGERY PENDING — terrain context only',fontsize=10)
        for ident,t,g in sectors:
            if ident==p['id']:draw_lines(ax,g.boundary,color='orange',lw=1)
        for r in range(500,radius+1,500):ax.add_patch(Circle((p['x'],p['y']),r,fill=False,color='black',lw=.4,ls='--'))
        ax.plot(p['x'],p['y'],'r+');ax.set_xlim(bounds[0],bounds[2]);ax.set_ylim(bounds[1],bounds[3]);ax.set_aspect('equal');ax.ticklabel_format(style='plain',useOffset=False);ax.tick_params(labelsize=7)
        axes[1].axis('off');lines=[f"{p['group']} | {p.get('original_id',p['id'])}",f"Terrain visible {p['raw_km2']:.3f} km²",f"Within 1km {p['within_1km_km2']:.3f}; beyond {p['beyond_1km_km2']:.3f} km²",f"Low-tree-cover proxy {p['low_tree_cover_km2']:.3f} km²",f"Selective hypothesis {p['selective_score']:.5f}",f"Foreground cover proxy: {p['foreground_cover_mean']}",f"Effort: {approaches.get(p.get('original_id',p['id']), 'PENDING documented entries / route / terrain evidence')}",'','Foreground branches / ground sightlines require human review.','Same target support, eye/target heights, radius and budget.','Old light angles are hypothetical, not a dated sun forecast.','Agreement with manual points is not independent validation.','Unknown access; no field-ready or hunting-value claim.']
        axes[1].text(0,1,'\n\n'.join(lines),va='top',fontsize=9,wrap=True);fig.suptitle(c['input_kind'].upper()+' — matched provisional comparison');fig.tight_layout();pdf.savefig(fig,bbox_inches='tight');plt.close(fig)
    pdf.close()
