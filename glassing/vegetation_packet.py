"""Data-driven vegetation review; imagery remains unobscured in paired panels."""
import json,math,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from osgeo import gdal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle,Patch
from matplotlib.colors import ListedColormap,LightSource
from .acquire import dump,digest
from .transfer import project
from .correction_packet import extent,draw_lines,wedge
from .vegetation_experiment import read,csvwrite

def render(cfg,c,rows,details,lookup,indices,tree,shrub,ds):
    out=Path(cfg['output']);root=Path(c['work']);gt=ds.GetGeoTransform();shape_=tree.shape;area=abs(gt[1]*gt[5])/1e6;images=read(Path(cfg['review'])/'imagery.json');p=lookup[cfg['audit_candidate']];pdf=PdfPages(out/'vegetation_review.pdf');count=0;ll=project(c['epsg'],4326)
    def save(fig,name):
        nonlocal count
        count+=1;fig.savefig(out/f'{count:02}_{name}.png',dpi=145);pdf.savefig(fig);plt.close(fig)
    # Exact old neighborhood: 3 cells either side + centre, edges at +/-35m.
    r,co=p['row'],p['col'];legacy=tree[r-3:r+4,co-3:co+4];bounds=[p['x']-35,p['y']-35,p['x']+35,p['y']+35];source=gdal.Open(c['data']['tree']['path']);sg=source.GetGeoTransform();src=source.ReadAsArray();weights={};errors=[]
    for rr in range(r-3,r+4):
        for cc in range(co-3,co+4):
            x=gt[0]+(cc+.5)*gt[1];y=gt[3]+(rr+.5)*gt[5];sc=math.floor((x-sg[0])/sg[1]);sr=math.floor((y-sg[3])/sg[5]);key=f'{sr},{sc}';weights[key]=weights.get(key,0)+1;errors.append(abs(float(src[sr,sc])/100-float(tree[rr,cc])))
    audit=dict(id=p['id'],legacy_square_bounds=bounds,legacy_shape=[7,7],legacy_mean=float(np.nanmean(legacy)),reported_mean=p['foreground_cover_mean'],legacy_unknown=int((~np.isfinite(legacy)).sum()),delivered_source_transform=sg,delivered_source_nodata=source.GetRasterBand(1).GetNoDataValue(),source_pixel_sample_counts=weights,max_nearest_sample_error=max(errors),source_date=c['data']['tree']['acquisition_date'],imagery_dates=images[p['id']+'_setup']['dates'],interpretation='Reproduced coarse product sampling, not proof of a usable ground-level opening. Legacy square 70x70m, not a 30m radius circle.')
    assert abs(audit['legacy_mean']-audit['reported_mean'])<1e-7 and max(errors)<1e-7;dump(out/'observer_audit.json',audit)
    im=gdal.Open(images[p['id']+'_setup']['path']);rgb=im.ReadAsArray()[:3].transpose(1,2,0);fig,axes=plt.subplots(1,3,figsize=(16,7))
    for ax in axes[:2]:
        ax.imshow(rgb,extent=extent(im));ax.plot(p['x'],p['y'],'r^',mec='white');ax.add_patch(Rectangle((bounds[0],bounds[1]),70,70,fill=False,color='red',lw=2,ls='--'));ax.set_xlim(p['x']-120,p['x']+120);ax.set_ylim(p['y']-120,p['y']+120);ax.set_aspect('equal');ax.ticklabel_format(style='plain',useOffset=False);ax.tick_params(labelsize=7)
    axes[0].set_title('Unobscured NAIP, '+', '.join(images[p['id']+'_setup']['dates'])+'\nRed: exact legacy averaging square',fontsize=10)
    inv=gdal.InvGeoTransform(sg);sc,sr=gdal.ApplyGeoTransform(inv,p['x'],p['y']);sc,sr=int(sc),int(sr)
    for rr in range(sr-5,sr+6):
        for cc in range(sc-5,sc+6):
            x=sg[0]+cc*sg[1];y=sg[3]+(rr+1)*sg[5];axes[1].add_patch(Rectangle((x,y),sg[1],-sg[5],fill=False,color='yellow',lw=.6));axes[1].text(x+sg[1]/2,y-sg[5]/2,str(src[rr,cc]),ha='center',va='center',fontsize=7,color='white',bbox=dict(facecolor='black',alpha=.6,pad=.2),clip_on=True)
    axes[1].set_title('Delivered RCMAP 2023 pixel values (%)\n~30m pixels; WCS already reprojected',fontsize=10)
    axes[2].imshow(legacy*100,cmap='YlGn',vmin=0,vmax=100)
    for (rr,cc),v in np.ndenumerate(legacy):axes[2].text(cc,rr,f'{100*v:.0f}',ha='center',va='center',fontsize=11)
    axes[2].set_title(f'Prepared 10m samples: mean {100*audit["legacy_mean"]:.1f}%\n49 repeated samples, not independent measurements',fontsize=10)
    fig.suptitle(p['id']+' foreground audit — sampling verified, ground-level gap unresolved',fontsize=14);fig.text(.05,.04,'Annual fractional cover is not crown geometry or optical transmittance. Image and cover dates differ.\nNearest-neighbor resampling repeats source pixels; the 49 samples are not 49 independent canopy measurements.',fontsize=10);fig.subplots_adjust(bottom=.18,wspace=.25);save(fig,'source_audit')
    # Review diverse parents and top new alternatives; each page keeps imagery panel clear.
    ids=read(out/'review_ids.json');z=ds.ReadAsArray();shade=LightSource(315,45).hillshade(z,dx=gt[1],dy=abs(gt[5]));allrows={r['id']:r for r in rows}
    classes=np.where(~np.isfinite(tree),4,np.where(tree<.1,1,np.where(tree<.4,2,3)))
    for ident in ids:
        point=lookup[ident];row=allrows[ident];b=[point['x']-500,point['y']-500,point['x']+500,point['y']+500];fig,axes=plt.subplots(1,2,figsize=(13,8));baseid=point.get('parent',ident);record=images.get(baseid+'_context',{})
        for ax in axes:
            if record.get('path'):
                im=gdal.Open(record['path']);ax.imshow(im.ReadAsArray()[:3].transpose(1,2,0),extent=extent(im),interpolation='nearest');date=', '.join(record['dates'])
            else:ax.imshow(shade,extent=extent(ds),cmap='gray');date='IMAGERY PENDING; hillshade only'
            ax.plot(point['x'],point['y'],'r^',mec='white');ax.set_xlim(b[0],b[2]);ax.set_ylim(b[1],b[3]);ax.set_aspect('equal');ax.ticklabel_format(style='plain',useOffset=False);ax.tick_params(labelsize=7);ax.annotate('Grid N',xy=(.94,.96),xytext=(.94,.84),xycoords='axes fraction',ha='center',color='white',arrowprops=dict(color='white',arrowstyle='->'))
        vis=np.zeros(shape_,bool);vis.ravel()[indices[ident]]=True
        mapped=np.ma.masked_where(~vis,classes);axes[1].imshow(mapped,extent=extent(ds),cmap=ListedColormap(['#65d59e','#ffc04f','#d653b7','#929292']),vmin=1,vmax=4,alpha=.75,interpolation='nearest')
        # Native-resolution directional diagnostic sectors, only a diagnostic outline.
        for az in sorted(set(t['azimuth_start'] for t in details[ident]['patches'] if t['id'] in details[ident]['selections']['target_heuristic']['patch_ids'])):
            w=wedge(point,dict(azimuth_start=az,azimuth_end=az+30,inner_m=10,outer_m=60));draw_lines(axes[1],w.boundary,color='cyan',lw=1)
        axes[1].set_xlim(point['x']-2100,point['x']+2100);axes[1].set_ylim(point['y']-2100,point['y']+2100)
        axes[0].set_title('Unobscured imagery / setup context\n'+date,fontsize=10);axes[1].set_title('Tree-cover classes ONLY within saved terrain-visible targets\nCyan: 10–60m directional sampling toward selected sectors',fontsize=10)
        handles=[Patch(color=k,label=v) for k,v in zip(['#65d59e','#ffc04f','#d653b7','#929292'],['tree <10%','tree 10–40%','tree ≥40%','tree unknown'])];axes[1].legend(handles=handles,fontsize=8,loc='lower right')
        lo,la=ll(point['x'],point['y']);shrub_label=f'{row["shrub_mean_pct"]:.1f}%' if row['shrub_mean_pct'] is not None else 'unknown'
        fig.suptitle(f'{ident} ({row["kind"]}; parent {row["parent"] or "none"}) | {la:.6f}, {lo:.6f}\nTerrain {row["raw_km2"]:.3f} km²; shrub mean {shrub_label}; unknown {row["cover_unknown_km2"]:.3f} km²',fontsize=12)
        fig.text(.06,.055,f'Target heuristic rank {row["target_heuristic_rank"]}; directional-screen20 rank {row["directional_20_rank"]}. Rankings are sensitivity results, not deer-finding validation.\nLow tree cover is not guaranteed glassability. Tree classes do not depict habitat value. Foreground/native cover cannot resolve branches.\nAccess, footing and ground-level openings remain unknown. All displayed imagery is from 2019 where available.',fontsize=9);fig.subplots_adjust(bottom=.18,top=.83,wspace=.2);save(fig,ident)
        fig,axes=plt.subplots(1,3,figsize=(16,7))
        raw=np.ma.masked_where(~vis,np.ones(shape_))
        shclass=np.where(~np.isfinite(shrub),3,np.where(shrub>.3,2,1))
        axes[0].imshow(shade,extent=extent(ds),cmap='gray')
        axes[0].imshow(raw,extent=extent(ds),cmap=ListedColormap(['cyan']),vmin=0,vmax=1,alpha=.7)
        axes[0].set_title('Bare-earth visible eligible targets\nNo vegetation screen')
        axes[1].imshow(shade,extent=extent(ds),cmap='gray')
        axes[1].imshow(np.ma.masked_where(~vis,shclass),extent=extent(ds),cmap=ListedColormap(['#85df95','#dc9248','#929292']),vmin=1,vmax=3)
        axes[1].set_title('Shrub classes in terrain-visible targets')
        axes[1].legend(handles=[Patch(color=k,label=v) for k,v in zip(['#85df95','#dc9248','#929292'],['shrub ≤30%','shrub >30%','shrub unknown'])],fontsize=8)
        if record.get('path'):
            axes[2].imshow(im.ReadAsArray()[:3].transpose(1,2,0),extent=extent(im))
        else:axes[2].imshow(shade,extent=extent(ds),cmap='gray')
        selected={t['azimuth_start'] for t in details[ident]['patches'] if t['id'] in details[ident]['selections']['target_heuristic']['patch_ids']}
        for d in details[ident]['directions']:
            if d['start'] not in selected:continue
            w=wedge(point,dict(azimuth_start=d['start'],azimuth_end=d['end'],inner_m=d['inner_m'],outer_m=d['outer_m']))
            draw_lines(axes[2],w.boundary,color='cyan',lw=1)
            angle=math.radians((d['start']+d['end'])/2);radius=(d['inner_m']+d['outer_m'])/2
            label=f'{100*d["mean_tree"]:.0f}%' if d['mean_tree'] is not None else '?'
            axes[2].text(point['x']+radius*math.sin(angle),point['y']+radius*math.cos(angle),label,fontsize=7,bbox=dict(facecolor='white',alpha=.8,pad=.2),ha='center')
        axes[2].set_title('Directional tree means: selected sectors\n10–60m / 60–120m; native ~30m data')
        for i,ax in enumerate(axes):
            radius=150 if i==2 else 2100
            ax.set_xlim(point['x']-radius,point['x']+radius);ax.set_ylim(point['y']-radius,point['y']+radius)
            ax.plot(point['x'],point['y'],'r^',mec='white');ax.set_aspect('equal');ax.ticklabel_format(style='plain',useOffset=False);ax.tick_params(labelsize=7)
        fig.suptitle(ident+' — separate terrain, target shrub and observer diagnostics')
        fig.text(.04,.04,'Percent cover is not blockage probability. Sector means use repeated 10m samples of ~30m source pixels.\nUnknown cover is gray; unknown access and within-cell gaps require review. Imagery pending where no cached clip covers the position.',fontsize=9)
        fig.tight_layout(rect=[0,.12,1,.92]);save(fig,ident+'_diagnostics')
        core_write=__import__('glassing.core',fromlist=['write_raster']).write_raster
        core_write(out/(ident+'_target_classes.tif'),np.where(vis,classes,0).astype('uint8'),gt,ds.GetProjection(),0)
    pdf.close()
    # Neutral point exports and point-only KML: originals vs distinct setup alternatives.
    gp=ET.Element('gpx',version='1.1',creator='vegetation sensitivity experiment',xmlns='http://www.topografix.com/GPX/1/1');km=ET.Element('kml',xmlns='http://www.opengis.net/kml/2.2');doc=ET.SubElement(km,'Document')
    for ident in ids:
        point=lookup[ident];lo,la=ll(point['x'],point['y']);kind='SETUP ALTERNATIVE' if point.get('parent') else 'ORIGINAL';label=f'PROVISIONAL {kind} {ident}'
        w=ET.SubElement(gp,'wpt',lat=repr(la),lon=repr(lo));ET.SubElement(w,'name').text=label;ET.SubElement(w,'desc').text='Unknown access; vegetation sensitivity only; parent '+point.get('parent','none')
        pm=ET.SubElement(doc,'Placemark');ET.SubElement(pm,'name').text=label;ET.SubElement(ET.SubElement(pm,'Point'),'coordinates').text=f'{lo},{la},0'
    ET.ElementTree(gp).write(out/'review.gpx',encoding='utf-8',xml_declaration=True);ET.ElementTree(km).write(out/'review.kml',encoding='utf-8',xml_declaration=True)
    for w,ident in zip(ET.parse(out/'review.gpx').findall('{*}wpt'),ids):
        x,y=project(4326,c['epsg'])(float(w.attrib['lon']),float(w.attrib['lat']));assert math.hypot(x-lookup[ident]['x'],y-lookup[ident]['y'])<.01

def report(cfg,c,rows,rayrows,parents):
    from scipy.stats import spearmanr
    out=Path(cfg['output']);orig=[r for r in rows if r['kind']=='original'];alts=[r for r in rows if r['parent']]
    audit=read(out/'observer_audit.json');fine=read(out/'fine_lidar.json');metrics=[]
    for a,b in [('baseline_score','distance_control'),('distance_control','target_heuristic'),('target_heuristic','directional_20'),('directional_20','directional_40'),('unknown_low','unknown_high')]:
        topa={r['id'] for r in sorted(orig,key=lambda r:(-r[a],r['id']))[:10]};topb={r['id'] for r in sorted(orig,key=lambda r:(-r[b],r['id']))[:10]}
        metrics.append(dict(a=a,b=b,top10_shared=len(topa&topb),spearman=float(spearmanr([r[a] for r in orig],[r[b] for r in orig]).statistic)))
    csvwrite(out/'matched_rank_stability.csv',metrics)
    lines=['# Bounded vegetation scouting comparison', '',f"Completed {len(orig)} original candidates and {len(alts)} distinct nearby alternatives. Historical scores, points and review files are preserved. New scores are heuristic indices, not literal visible acreage or detection probabilities.",'', '## Observer audit', '',f"{audit['id']}: the exact {audit['legacy_shape'][0]}×{audit['legacy_shape'][1]} prepared-cell footprint reproduces {100*audit['legacy_mean']:.5f}% mean tree cover; original reported value {100*audit['reported_mean']:.5f}%. Maximum delivered-source nearest-sample difference {audit['max_nearest_sample_error']:.2g}. See observer_audit.json and the first map for source pixel values and the footprint over unobscured imagery.", '',f"Cover source date: {audit['source_date']}; imagery dates: {', '.join(audit['imagery_dates'])}. RCMAP is annual ~30m fractional cover, repeated onto the 10m grid. Correct sampling does not prove a ground-level opening. The 70m square is omnidirectional; trees behind a hunter affect that mean but do not directly block forward rays. Directional_cover.csv and diagnostic maps instead show 30-degree sectors in 10–60m and 60–120m annuli toward selected target sectors. No percentage is converted into blockage probability.", '', '## Matched decision comparison', '', 'Distance-only control and target-searchability heuristic share the same bare-earth viewsheds, distance curve, patch costs and observation budget. Target searchability is applied once: tree <10% →1, 10–40% →0.6, ≥40% →0.25; shrub >30% multiplies by0.75. These inherited values are hypotheses. Habitat, perspective and light are absent from both matched arms. The historical composite is a separate reference; its differences cannot all be attributed to vegetation. Unknown tree/shrub cells retain low/high reward bounds; nominal defaults are 25%/30%.', '', '| Arms, original pool only | Shared top10 | Spearman |','|---|---:|---:|']
    for m in metrics:lines.append(f"| {m['a']} / {m['b']} | {m['top10_shared']} | {m['spearman']:.3f} |")
    lines+=['', '| ID | Parent | Terrain km² | Tree <10% km² | Historical rank | Target rank | Direction20 rank |','|---|---|---:|---:|---:|---:|---:|']
    for r in sorted(rows,key=lambda r:(-r['directional_20'],r['id']))[:10]:lines.append(f"| {r['id']} | {r['parent'] or 'original'} | {r['raw_km2']:.3f} | {r['tree_lt10_km2']:.3f} | {r['baseline_score_rank'] or '—'} | {r['target_heuristic_rank']} | {r['directional_20_rank']} |")
    lines+=['',f"The 20%/40% directional screens give zero scores to {sum(r['directional_20']==0 for r in orig)}/{sum(r['directional_40']==0 for r in orig)} originals. Their hard thresholds are sensitivity assumptions, not justified exclusions. All original candidates remain in components.csv, including candidates outside the historical top five. Tree classes, shrub mean/unknown area, raw terrain area and searchability bounds are separate. Low tree cover does not guarantee glassability; weighted indices are not acreage."]
    if alts:
        best=max(alts,key=lambda r:r['directional_20']);parent=next(r for r in rows if r['id']==best['parent'])
        lines+=['',f"Leading offset {best['id']} from {best['parent']}: target heuristic {parent['target_heuristic']:.5f} → {best['target_heuristic']:.5f}; direction20 {parent['directional_20']:.5f} → {best['directional_20']:.5f}. Local offsets can cross coarse pixels, so the change may reflect sampling assumptions. Alternatives retain distinct IDs, stay in the observer domain and have newly computed terrain viewsheds. None has verified access."]
    lines+=['', '## Intervening vegetation', '',f"Coarse sensitivity tests use the same up-to-{cfg['ray_count']} sampled targets per each of {len(set(r['id'] for r in rayrows))} subset positions under {cfg['canopy_heights_m']}m opaque-column heights and {cfg['canopy_thresholds']} cover thresholds. Coarse_ray_scenarios.csv separates observer, intermediate, target and unknown intersections. Endpoints remain bare ground plus eye/deer heights. Sampled_path_screen_index applies target searchability once and screens observer/intermediate/unknown intersections; target-column counts are separate, avoiding a second target penalty. Subset ranks are not full-pool ranks or extrapolated vegetation-visible acreage. Neighboring sampled rays are correlated.", '', 'Overlap_low_tree.csv recomputes common known low-tree target pixels. This coverage class remains a diagnostic, not guaranteed searchable terrain. The original raw-overlap baseline remains available.']
    if fine.get('status')=='local_return_column_sensitivity_only':
        bounds=fine['bounds']
        lines+=['',f"One cached USGS tile, {fine['download_bytes']:,} bytes and {fine['point_count']:,} points; {fine['local_points']:,} retained local returns. Subset {bounds[2]-bounds[0]:.0f}×{bounds[3]-bounds[1]:.0f}m, derived {fine['grid_resolution_m']}m grid. Source: {fine['source_date']}. Datum/units are recorded from the LAS compound CRS in fine_lidar.json. Ground uses classified-ground returns within5m; other cells remain unknown. All nonnoise returns form height columns; unclassified returns are not verified trees. No vertical correction or combination with baseline elevations is implied.", '',f"Unknown local fraction {fine['unknown_cell_fraction']:.1%}; legacy-footprint known support {fine['legacy_square_lidar_known_fraction']:.1%}; known footprint cells with columns≥2m {fine['legacy_square_returns_above_2m_fraction']:.1%}. The observer-cell column is {fine['observer_return_column_height_m']:.2f}m, which cannot locate branches relative to a person within that cell.", '', '| Local column scale | Bare-ground-clear rays | Remaining clear |','|---|---:|---:|']
        for v in fine['scenarios']:lines.append(f"| {v['column_scale']} | {v['bare_clear_n']} | {v['clear_among_bare_clear']} |")
        lines+=['', 'Local ray tests use shared lidar-derived ground and targets 40–200m away. Max-return and half-height columns are obstruction scenarios, not measured optical visibility; they ignore crown gaps and under-crown views. Missing returns are unknown, never evidence of an opening. These tests cannot establish vegetation obstruction along all2km rays.']
    else:lines+=['',f"Fine data unavailable: {fine.get('reason',fine['status'])}. Coarse diagnostics are complete."]
    lines+=['', '## Handoff', '', 'Review vegetation_review.pdf and fine_lidar_review.png. Unobscured imagery is paired with tree classes; separate diagnostic pages show raw terrain visibility, shrub classes and directional footprints. Imagery is pending for candidates beyond the cached clips. GPX/KML distinguish original points from setup alternatives; they are provisional waypoints, not routes.', '', 'Keep the baseline available and use the separate components for desktop review. Changed rankings do not demonstrate improved hunting performance. Unresolved: immediate branches and within-cell gaps, crown/understory transmission on long sightlines, contemporary vegetation, target concealment, footing and connected legal access. These need imagery and ground review; no field validation or itinerary was performed.', '', 'Reproduce from the repository root, choosing a fresh output name:', '', '```sh', '.venv/bin/python -m glassing.vegetation_experiment --config configs/vegetation.soap-creek-v1.json --output results/soap-creek-vegetation-repeat', '```', '', 'See docs/glassing/vegetation/README.md for isolated optional lidar dependencies. Exact catalog request, tile metadata, download provenance and hashes are retained in downloads/.', '', 'Sources: [USGS RCMAP](https://www.usgs.gov/centers/eros/science/rangeland-condition-monitoring-assessment-and-projection-rcmap), [USGS LidarExplorer](https://www.usgs.gov/tools/lidarexplorer). Tile-specific metadata is retained locally; fine_lidar.json records the exact source path and checksum.']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n')
