"""Read-only neighborhood review of completed vegetation calculations; no scoring."""
import argparse, csv, itertools, json, math, xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from scipy.ndimage import label
from osgeo import gdal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import ListedColormap, LightSource
from .acquire import digest, dump
from .transfer import project
from .review_maps import visible_mask
from .correction_packet import extent

GROUPS = {
 'West': ['A0075','V010','V008','A0081','A0033','A0139'],
 'East': ['A0031','V004'],
 'North': ['A0140','V014'],
}
REASONS = {
 'West': 'First ground-inspection priority, conditional on access: A0075/V010/V008 retain their target index under both screens; compare actual foreground gaps at these three setups. A0081 is the target-searchability leader among originals and must survive review despite its 20% penalty. A0033 and A0139 are southern setup choices within this same neighborhood, not additional destinations.',
 'East': 'Spatially separate historical leader A0031; retain its eastern target support despite lower target rank. V004 is a 50 m north setup fallback, not a new destination. Local lidar is available here only and warns that coarse low foreground cover cannot establish usable sightlines.',
 'North': 'Separate historical leader A0140, conditional inspection rather than automatic rejection: 20% gives zero but 40% restores its entire target index. V014 offers a nearby 50–71 m setup comparison with nonzero scores under both screens. Inspect whether either has a real ground-level opening before spending a session here.',
}

def read(p): return json.loads(Path(p).read_text())
def writecsv(p, rows):
 with Path(p).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',default='results/soap-creek-vegetation-v2');ap.add_argument('--out',default='results/soap-creek-decision-review-v2');a=ap.parse_args()
 src=Path(a.source);out=Path(a.out)
 if out.exists(): raise ValueError('Choose a new output directory; reviews never replace outputs')
 cfg=read('configs/vegetation.soap-creek-v1.json');base=Path(cfg['baseline']);review=Path(cfg['review']);c=read(base/'scouting.json');root=Path(c['work'])
 preserved={str(p):digest(p) for folder in [src,base,review,Path('results/soap-creek-vegetation-v1')] for p in folder.rglob('*') if p.is_file()}
 for folder in [src,base,review]:
  for p,h in read(folder/'manifest.json').items():
   if digest(p)!=h: raise ValueError('Source integrity failed: '+p)
 rows={r['id']:r for r in read(src/'components.json')};points={p['id']:p for p in read(root/'scores.json')+read(src/'alternatives.json')};details=read(src/'details.json');images=read(review/'imagery.json');ids=sum(GROUPS.values(),[])
 dem=gdal.Open(str(root/'dem.tif'));gt=dem.GetGeoTransform();target=gdal.Open(str(root/'target.tif')).ReadAsArray().astype(bool);tree=gdal.Open(str(root/'tree.tif')).ReadAsArray();shrub=gdal.Open(str(root/'shrub.tif')).ReadAsArray();ll=project(c['epsg'],4326);masks={};checks=[]
 out.mkdir();dump(out/'PRESERVED.json',preserved)
 openings=[];table=[];foreground=[]
 for ident in ids:
  p=points[ident];r=rows[ident];path=src/'viewsheds'/f'{ident}.tif' if ident.startswith('V') else root/'additional_visibility'/f'{ident}_{c["radius_m"]}.tif'
  masks[ident],check=visible_mask(gdal.Open(str(path)),dem,target,{**p,'raw_km2':r['raw_km2']},c['radius_m']);checks.append(check)
  lo,la=ll(p['x'],p['y']);neighborhood=next(k for k,v in GROUPS.items() if ident in v)
  table.append(dict(neighborhood=neighborhood,id=ident,parent=r['parent'],latitude=la,longitude=lo,easting=p['x'],northing=p['y'],terrain_km2=r['raw_km2'],tree_lt10_km2=r['tree_lt10_km2'],historical_rank=r['baseline_score_rank'],target_rank=r['target_heuristic_rank'],direction20_rank=r['directional_20_rank'],direction40_rank=r['directional_40_rank'],target_index=r['target_heuristic'],direction20_index=r['directional_20'],direction40_index=r['directional_40'],retained20=r['directional_20']/r['target_heuristic'],retained40=r['directional_40']/r['target_heuristic'],access='UNRESOLVED'))
  foreground.append(dict(id=ident,legacy_foreground_mean=points.get(ident,{}).get('foreground_cover_mean','not calculated for alternative'),directions=details[ident]['directions']))
  # Connected known <10% tree-cover visible pixels: structural summaries, not a new reward.
  low=masks[ident]&(tree>=0)&(tree<.1)&np.isfinite(shrub)&(shrub>=0)&(shrub<=1)
  labs,n=label(low);counts=np.bincount(labs.ravel());counts[0]=0
  for order,k in enumerate(np.argsort(counts)[-2:][::-1],1):
   if not counts[k]: continue
   rr,cc=np.where(labs==k);center=np.array([rr.mean(),cc.mean()]);j=np.argmin((rr-center[0])**2+(cc-center[1])**2);y=gt[3]+(rr[j]+.5)*gt[5];x=gt[0]+(cc[j]+.5)*gt[1];lon,lat=ll(x,y)
   openings.append(dict(id=ident,opening=f'{ident}-O{order}',latitude=lat,longitude=lon,easting=x,northing=y,area_km2=int(counts[k])*abs(gt[1]*gt[5])/1e6,grid_bearing_deg=math.degrees(math.atan2(x-p['x'],y-p['y']))%360,distance_m=math.hypot(x-p['x'],y-p['y']),definition='4-connected terrain-visible tree<10% pixels with known shrub; representative pixel, not verified gap'))
 writecsv(out/'shortlist.csv',table);writecsv(out/'target_openings.csv',openings);dump(out/'foreground_diagnostics.json',foreground);dump(out/'alignment_checks.json',checks)
 sampled=list(csv.DictReader((src/'coarse_ray_scenarios.csv').open()));sampled=[r for r in sampled if r['id'] in ids];writecsv(out/'sampled_obstruction.csv',sampled)
 overlap=[]
 for aa,bb in itertools.combinations(ids,2):
  ma,mb=masks[aa],masks[bb];shared=(ma&mb).sum()*abs(gt[1]*gt[5])/1e6;low=(ma&mb&(tree>=0)&(tree<.1)&np.isfinite(shrub)&(shrub>=0)&(shrub<=1)).sum()*abs(gt[1]*gt[5])/1e6
  overlap.append(dict(a=aa,b=bb,separation_m=math.hypot(points[aa]['x']-points[bb]['x'],points[aa]['y']-points[bb]['y']),shared_terrain_km2=float(shared),fraction_a=float(shared/rows[aa]['raw_km2']),fraction_b=float(shared/rows[bb]['raw_km2']),shared_known_low_tree_km2=float(low)))
 writecsv(out/'overlap.csv',overlap)
 # Finest cached clip covering complete requested frame, regardless of nominal parent.
 shade=LightSource(315,45).hillshade(dem.ReadAsArray(),dx=gt[1],dy=abs(gt[5]));image_used=[]
 def background(ax,b):
  candidates=[(k,r) for k,r in images.items() if r.get('path') and r['bounds'][0]<=b[0] and r['bounds'][1]<=b[1] and r['bounds'][2]>=b[2] and r['bounds'][3]>=b[3]]
  if candidates:
   k,r=min(candidates,key=lambda v:v[1]['resolution_m']);im=gdal.Open(r['path']);ax.imshow(im.ReadAsArray()[:3].transpose(1,2,0),extent=extent(im),interpolation='nearest');caption=f'NAIP {", ".join(r["dates"])}; native {r["native_resolution_m"]} m; clip {r["resolution_m"]:g} m/pixel';image_used.append(dict(frame=b,key=k,**r))
  else: ax.imshow(shade,extent=extent(dem),cmap='gray');caption='No cached clip covers frame — hillshade; imagery pending'
  ax.set_xlim(b[0],b[2]);ax.set_ylim(b[1],b[3]);ax.set_aspect('equal');ax.ticklabel_format(useOffset=False,style='plain');ax.tick_params(labelsize=7);ax.set_title(caption,fontsize=8);ax.set_xlabel('UTM 13N easting m',fontsize=8);ax.set_ylabel('Northing m',fontsize=8)
  return caption
 def marks(ax,group,opening=False):
  for i,ident in enumerate(group):
   p=points[ident];ax.plot(p['x'],p['y'],'^',ms=8,mec='white',color=colors[ident]);ax.annotate(ident,(p['x'],p['y']),xytext=(6,6+i%2*10),textcoords='offset points',fontsize=8,bbox=dict(facecolor='white',alpha=.9,edgecolor='none'))
   if opening:
    for o in [v for v in openings if v['id']==ident]:
     ax.plot(o['easting'],o['northing'],'o',mfc='none',mec=colors[ident],ms=9);ax.annotate(o['opening'],(o['easting'],o['northing']),xytext=(5,-12),textcoords='offset points',fontsize=7,bbox=dict(facecolor='white',alpha=.8,edgecolor='none'))
 colors={ident:plt.get_cmap('tab10')(i%10) for i,ident in enumerate(ids)};pdf=PdfPages(out/'decision_review.pdf');pages=[]
 def save(fig,name):
  fig.savefig(out/(name+'.png'),dpi=170);pdf.savefig(fig);plt.close(fig);pages.append(name)
 fig,ax=plt.subplots(figsize=(11.7,8.3));ax.imshow(shade,extent=extent(dem),cmap='gray');marks(ax,ids);ax.set_aspect('equal');ax.ticklabel_format(useOffset=False,style='plain');ax.set_title('Three provisional glassing neighborhoods — terrain context\nWest: all western setups together; East: A0031; North: A0140');fig.tight_layout();save(fig,'01_neighborhoods')
 for number,(name,group) in enumerate([('West_north',GROUPS['West'][:3]),('West_south',GROUPS['West'][3:]),('East',GROUPS['East']),('North',GROUPS['North'])],2):
  p=points[group[0]];b=[p['x']-2100,p['y']-2100,p['x']+2100,p['y']+2100];fig,axs=plt.subplots(1,len(group)+1,figsize=(5*(len(group)+1),7));background(axs[0],b);marks(axs[0],group,True);axs[0].set_title('Unobscured imagery; opening markers\n'+axs[0].get_title(),fontsize=8)
  for ax,ident in zip(axs[1:],group):
   q=points[ident];own=[q['x']-2000,q['y']-2000,q['x']+2000,q['y']+2000];background(ax,own);m=masks[ident];ax.imshow(np.ma.masked_where(~m,np.ones(m.shape)),extent=extent(dem),cmap=ListedColormap(['#00bfff']),vmin=0,vmax=1,alpha=.35,interpolation='nearest');low=m&(tree>=0)&(tree<.1)&np.isfinite(shrub)&(shrub>=0)&(shrub<=1);ax.contour(low.astype(int),levels=[.5],extent=extent(dem),origin='upper',colors='#ffcf00',linewidths=.5);marks(ax,[ident],True);ax.set_title(f'{ident}: saved terrain {rows[ident]["raw_km2"]:.4f} km²\nBlue = actual visible target cells; yellow = known low-tree boundary',fontsize=9)
  fig.suptitle(name+' — individual visibility preserved; circles are candidate target openings',fontsize=14);fig.text(.03,.025,'Opening coordinates, areas, bearings and distances: target_openings.csv. Low cover is a coarse hypothesis, not a field-verified gap. Imagery remains clear in the first panel.',fontsize=10);fig.subplots_adjust(bottom=.13,top=.9,wspace=.27);save(fig,f'{number:02}_{name}_targets')
 for number,(name,group) in enumerate([('A0075_V010_V008',GROUPS['West'][:3]),('A0081_A0033', ['A0081','A0033']),('A0139',['A0139']),('A0031_V004',GROUPS['East']),('A0140_V014',GROUPS['North'])],6):
  xs=[points[v]['x'] for v in group];ys=[points[v]['y'] for v in group];b=[min(xs)-90,min(ys)-90,max(xs)+90,max(ys)+90];fig=plt.figure(figsize=(16,11) if len(group)==3 else (11.7,8.3));ax=fig.add_subplot(2,2,1) if len(group)==3 else fig.add_subplot(1,1,1);caption=background(ax,b);marks(ax,group)
  if len(group)==3:
   for slot,ident in enumerate(group,2):
    other=fig.add_subplot(2,2,slot);q=points[ident];own=[q['x']-2000,q['y']-2000,q['x']+2000,q['y']+2000];background(other,own);m=masks[ident];other.imshow(np.ma.masked_where(~m,np.ones(m.shape)),extent=extent(dem),cmap=ListedColormap(['#00bfff']),vmin=0,vmax=1,alpha=.35,interpolation='nearest');marks(other,[ident],True);other.set_title(f'{ident}: individual saved visibility {rows[ident]["raw_km2"]:.4f} km²\nBlue target pixels; circles reference target openings',fontsize=10)
  text=[]
  for ident in group:
   p=points[ident];r=rows[ident];lon,lat=ll(p['x'],p['y']);text.append(f'{ident}: {lat:.6f}, {lon:.6f} | terrain {r["raw_km2"]:.4f} km² | target {r["target_heuristic"]:.4f} | D20/D40 {r["directional_20"]:.4f}/{r["directional_40"]:.4f}')
  ax.set_title(name+' — finest covering cached imagery\n'+caption,fontsize=11);fig.text(.06,.04,'\n'.join(text)+'\nInspect branches, eye-height gap, stable footing and safe movement between marked setups; access unresolved.',fontsize=9);fig.subplots_adjust(bottom=.23,top=.89,hspace=.40,wspace=.30);save(fig,f'{number:02}_{name}_setup')
 pdf.close();dump(out/'imagery_used.json',image_used)
 gpx=ET.Element('gpx',version='1.1',creator='Soap Creek decision review',xmlns='http://www.topografix.com/GPX/1/1');kml=ET.Element('kml',xmlns='http://www.opengis.net/kml/2.2');doc=ET.SubElement(kml,'Document')
 for t in table:
  name=t['neighborhood']+' / '+t['id'];desc='Provisional setup; access and sightlines unresolved; neighborhood alternatives, not routes.';w=ET.SubElement(gpx,'wpt',lat=f'{t["latitude"]:.9f}',lon=f'{t["longitude"]:.9f}');ET.SubElement(w,'name').text=name;ET.SubElement(w,'desc').text=desc;pm=ET.SubElement(doc,'Placemark');ET.SubElement(pm,'name').text=name;ET.SubElement(pm,'description').text=desc;ET.SubElement(ET.SubElement(pm,'Point'),'coordinates').text=f'{t["longitude"]:.9f},{t["latitude"]:.9f},0'
 ET.ElementTree(gpx).write(out/'shortlist.gpx',encoding='utf-8',xml_declaration=True);ET.ElementTree(kml).write(out/'shortlist.kml',encoding='utf-8',xml_declaration=True)
 for t,w in zip(table,ET.parse(out/'shortlist.gpx').getroot()):
  assert abs(float(w.attrib['lat'])-t['latitude'])<1e-8 and abs(float(w.attrib['lon'])-t['longitude'])<1e-8
 lines=['# Soap Creek decision review','', 'Inspect three neighborhoods, not ten independent destinations. West has the strongest cross-diagnostic case; East preserves the historical leader and distinct targets; North preserves a separate historical leader whose ranking is cutoff-sensitive. No new score or model is introduced. All exports are provisional.','', '## Concise comparison','', 'Ranks use the saved experiment: historical rank among 150 originals; other ranks among 202 original/alternative points. T/D20/D40 are heuristic indices, not acres or detection probability.','', '| Neighborhood / setup | Latitude, longitude (WGS84) | Terrain / low-tree km² | Historical / target / D20 / D40 ranks | T / D20 / D40 |','|---|---|---|---|---|']
 for t in table: lines.append(f'| {t["neighborhood"]} / {t["id"]} | {t["latitude"]:.6f}, {t["longitude"]:.6f} | {t["terrain_km2"]:.3f} / {t["tree_lt10_km2"]:.3f} | {t["historical_rank"] or "—"} / {t["target_rank"]} / {t["direction20_rank"]} / {t["direction40_rank"]} | {t["target_index"]:.3f} / {t["direction20_index"]:.3f} / {t["direction40_index"]:.3f} |')
 lines+=['','## Ground-inspection decisions']
 for name,group in GROUPS.items():
  lines+=['',f'### {name}', '',REASONS[name], '', 'Target openings below are the two largest contiguous known low-tree areas in each saved viewshed; coordinates are representative visible 10 m cells, not a surveyed aim point. Areas describe the entire connected component, not a view from the coordinate itself. Bearings are clockwise from UTM grid north. Check the exact rays from observer eye height to these openings, ridge-edge clearance, intermediate crowns/understory and target concealment.','']
  for o in [v for v in openings if v['id'] in group]: lines.append(f'- {o["opening"]}: {o["latitude"]:.6f}, {o["longitude"]:.6f}; {o["area_km2"]:.4f} km², {o["grid_bearing_deg"]:.0f}°, {o["distance_m"]:.0f} m.')
  lines+=['', 'Specific checks: '+({'West':'Compare A0075/V010/V008 over the same openings; verify whether 50–71 m movement improves actual branches/gap or only coarse-pixel sampling. At A0081, inspect selected sectors near the 20–40% foreground transition rather than rejecting it. Compare A0033/A0139 southern target overlap before treating them as added coverage. Establish a permitted entry and approach to this western group; verify off-trail permission, crossings, slope/footing and safe local movement.', 'East':'At A0031/V004 verify eye-height branch clearance toward the listed eastern openings. Inspect the lidar-supported immediate foreground: conservative columns left 9/50 or 0/50 local clear rays under half/full heights, with substantial local unknown support; these are not full-radius obstruction measurements. Confirm a connected permitted approach to the eastern setup and whether the 50 m north fallback is physically usable.', 'North':'At A0140 inspect the selected foreground sectors between the two cutoffs and the intermediate ridgeline/canopy toward its openings. Compare V014 over the same target support: do not assume its nonzero 20% index demonstrates a real gap. Verify a separate permitted northern approach, final slope and stable footing.'}[name])]
 lines+=['','## Overlap and sensitivity','', 'All pairwise raw-terrain overlap and known low-tree overlap, with separation and fractions, are in overlap.csv. These reuse saved visibility pixels; no complementarity optimizer was run.']
 for aa,bb in [('A0075','V010'),('A0075','V008'),('V010','V008'),('A0081','A0033'),('A0081','A0139'),('A0031','V004'),('A0140','V014'),('A0075','A0031'),('A0075','A0140'),('A0031','A0140')]:
  v=next(v for v in overlap if v['a']==aa and v['b']==bb or v['a']==bb and v['b']==aa);lines.append(f'- {v["a"]}/{v["b"]}: {v["separation_m"]:.0f} m apart; shared terrain {v["shared_terrain_km2"]:.4f} km² ({v["fraction_a"]:.1%}/{v["fraction_b"]:.1%}); shared known low-tree {v["shared_known_low_tree_km2"]:.4f} km².')
 lines+=['', 'A0081 retains only 42% of its target index at 20% but 100% at 40%; A0140 retains 0% versus 100%. Their apparent disadvantage depends strongly on an arbitrary screen. A0075/V010/V008 retain 100% under both; this is scenario stability, not field validation. V014 retains a partial index at 20%; see exact ratios in shortlist.csv. North alternative V015 has target rank 13 but both directional scores zero: it is not promoted just for its target gain. Original A0135 ranks 28 on target searchability but both directional screens zero; it adds no compelling cross-diagnostic reason for a fourth destination. No candidate is excluded solely because of D20.', '', '## Separate diagnostics and unresolved access','', 'foreground_diagnostics.json preserves the historical square mean where calculated and both directional annuli for each setup. These are fractional-cover diagnostics, not obstruction probabilities. sampled_obstruction.csv contains only the existing sampled column scenarios for selected points. A0081 and V004/V014 were not in that sampled subset; missing scenarios do not mean clear sightlines. Observer/intermediate/target/unknown counts can overlap and must not be added as independent blockers. These samples are correlated and cannot be extrapolated to full-area vegetation-visible acreage. Full experiment diagnostics remain at '+str(src)+'.','', 'No neighborhood has documented connected legal access in the current run. Resolve public/authorized entry, current restrictions and road/parking status, continuous permitted approach, final off-trail permission, stream crossings and safe footing separately from visibility. Maps and waypoints are not navigation routes. No updated access claim, itinerary, new coefficients, imagery download or bulk acquisition is made. 2019 imagery and 2023 cover may differ from current conditions.','', '## Review and export commands','', 'From /home/tanner/Desktop/huntmaps2:', '', '```sh', '.venv/bin/python -m glassing.decision_review --source results/soap-creek-vegetation-v2 --out results/soap-creek-decision-review-v2', '# For a repeat, choose a fresh --out directory.', 'xdg-open results/soap-creek-decision-review-v2/decision_review.pdf', 'cat results/soap-creek-decision-review-v2/REPORT.md', 'mkdir -p /tmp/soap-creek-shortlist-export', 'cp results/soap-creek-decision-review-v2/shortlist.gpx results/soap-creek-decision-review-v2/shortlist.kml results/soap-creek-decision-review-v2/shortlist.csv results/soap-creek-decision-review-v2/target_openings.csv /tmp/soap-creek-shortlist-export/', '```','', 'GPX/KML contain the ten observer setups grouped by neighborhood in their names; target-opening coordinates are in the CSV. PDF and individual PNGs show unobscured imagery and each saved viewshed separately. Setup frames select the finest cached clip that covers the frame: 0.5 m exported setup clips (0.6 m native imagery), rather than enlarged 4.4 m context clips. imagery_used.json records exact clips/dates/resolutions. alignment_checks.json verifies all ten areas against saved calculations. PRESERVED.json verifies existing outputs byte-for-byte; manifest.json covers this derived review.','']
 lines=[line.replace('results/soap-creek-decision-review-v2',str(out)) for line in lines]
 (out/'REPORT.md').write_text('\n'.join(lines))
 for p,h in preserved.items():
  if digest(p)!=h: raise ValueError('Existing output changed: '+p)
 dump(out/'provenance.json',dict(source=str(src),script_sha256=digest(__file__),preserved_files=len(preserved),new_download_bytes=0,viewshed_recalculations=0,scoring_changes=0,pages=pages,export_coordinate_checks='10 GPX points passed'))
 dump(out/'manifest.json',{str(p):digest(p) for p in out.rglob('*') if p.is_file() and p.name!='manifest.json'})
 print('Review ready:',out/'REPORT.md',out/'decision_review.pdf')
if __name__=='__main__': main()
