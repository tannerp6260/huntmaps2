"""Mapped connectivity witnesses, not navigation routes or legal certification."""
import json
from pathlib import Path
from collections import defaultdict
from shapely.geometry import shape,Point,LineString,box,mapping
from shapely.ops import transform,unary_union,nearest_points,substring
from shapely.validation import make_valid
from osgeo import osr
from .acquire import dump,srs


def projector():
    tr=osr.CoordinateTransformation(srs(4326),srs(32613))
    def xy(x,y,z=None):
        try:return tuple(zip(*[tr.TransformPoint(a,b)[:2] for a,b in zip(x,y)]))
        except TypeError:return tr.TransformPoint(x,y)[:2]
    return xy


def graph(lines):
    """Exact mapped intersections only. No assumed connection across small gaps."""
    network=unary_union(lines);edges=list(network.geoms) if hasattr(network,'geoms') else [network]
    adj=defaultdict(list)
    key=lambda xy:tuple(round(v,6) for v in xy)
    for i,e in enumerate(edges):
        u,v=key(e.coords[0]),key(e.coords[-1]);adj[u].append((v,i));adj[v].append((u,i))
    return edges,adj,key


def witness(adj,start,target):
    # Deterministic depth-first spanning-tree trace; no cost minimization.
    parent={start:None};stack=[start]
    while stack:
        u=stack.pop()
        if u==target:break
        for v,e in sorted(adj[u],reverse=True):
            if v not in parent:parent[v]=(u,e);stack.append(v)
    if target not in parent:return None
    out=[];v=target
    while parent[v] is not None:v,e=parent[v];out.append(e)
    return list(reversed(out))


def run(c):
    from .correct import csvwrite
    root=Path(c['work']);inputs=Path(c['inputs']);cc=json.loads(Path(c['comparison_config']).read_text())
    points={p['id']:p for p in json.loads((Path(cc['work'])/'pool.json').read_text())};ids=json.loads((root/'attention_summary.json').read_text())['review_ids']
    clip=box(*c['access_bounds_utm']);xy=projector();records=[]
    for typ in ['roads','trails']:
        for f in json.loads((inputs/(typ+'.geojson')).read_text())['features']:
            g=transform(xy,shape(f['geometry'])).intersection(clip)
            for part in list(g.geoms) if hasattr(g,'geoms') else [g]:
                if part.geom_type=='LineString' and part.length>0:records.append(dict(geometry=part,kind=typ,properties=f['properties']))
    edges,adj,key=graph([r['geometry'] for r in records])
    # A provider-named TH road documents a mapped access feature, not parking rights.
    # Steers Gulch endpoint at Little Mill junction is a separate mapped network entry,
    # explicitly NOT called a trailhead. Actual coordinates derived from provider geometry.
    entries=[]
    for name in ['RAINBOW LAKE TH','STEERS GULCH']:
        matches=[r for r in records if r['properties'].get('name')==name]
        for r in matches:
            ends=[Point(r['geometry'].coords[0]),Point(r['geometry'].coords[-1])]
            trails=[q['geometry'] for q in records if q['kind']=='trails']
            endpoint=min(ends,key=lambda p:min(p.distance(t) for t in trails))
            entries.append(dict(name=name,xy=list(endpoint.coords[0]),provider_road_id=r['properties']['id'],basis='USFS named TH road endpoint nearest mapped trail' if name.endswith('TH') else 'USFS Steers Gulch/Little Mill mapped junction; not a documented parking facility',parking_status='unknown',approach_to_entry='not verified',trail_endpoint_gap_m=min(endpoint.distance(t) for t in trails)))
    owners=[]
    for f in json.loads((inputs/'ownership.geojson').read_text())['features']:
        g=transform(xy,shape(f['geometry']));g=make_valid(g) if not g.is_valid else g
        owners.append((g.intersection(clip),f['properties']['ownerclassification']))
    mv=json.loads((inputs/'mvum_roads.geojson').read_text())['features'];mvbyid={f['properties'].get('id'):f['properties'] for f in mv}
    rows=[];features=[];details=[]
    for pid in ids:
        p=points[pid];point=Point(p['x'],p['y']);idx=min(range(len(edges)),key=lambda i:edges[i].distance(point));edge=edges[idx];q=nearest_points(point,edge)[1]
        pieces=[e for j,e in enumerate(edges) if j!=idx]
        at=edge.project(q)
        for lo,hi in [(0,at),(at,edge.length)]:
            if hi-lo>1e-7:pieces.append(substring(edge,lo,hi))
        local_edges,local_adj,local_key=graph(pieces)
        options=[]
        for entry in entries:
            start=min(local_adj,key=lambda v:Point(v).distance(Point(entry['xy'])))
            target=min(local_adj,key=lambda v:Point(v).distance(q));path=witness(local_adj,start,target)
            if path is not None:options.append((Point(entry['xy']).distance(point),entry,path))
        selected=min(options,key=lambda v:v[0]) if options else None
        gap=LineString([q,point]);trace=unary_union([local_edges[i] for i in selected[2]]) if selected else None
        own=[label for g,label in owners if g.covers(point)] or ['unknown']
        rec=min(records,key=lambda r:r['geometry'].distance(point));attrs=rec['properties']
        trace_sources=[]
        if trace:
            for r in records:
                overlap=r['geometry'].intersection(trace).length
                if overlap>1:trace_sources.append(dict(kind=r['kind'],overlap_m=overlap,attributes=r['properties'],mvum_attributes=mvbyid.get(r['properties'].get('id'))))
        row=dict(id=pid,mapped_network_gap_m=round(gap.length,1),mapped_entry=selected[1]['name'] if selected else 'no connected entry',entry_connectivity='mapped witness' if selected else 'disconnected',witness_network_length_m=round(trace.length,1) if trace else None,nearest_feature=attrs.get('name',attrs.get('trail_name')),candidate_ownership=';'.join(own),unmapped_gap_nonfs_m=round(sum(gap.intersection(g).length for g,label in owners if label=='NON-FS'),1),mapped_witness_nonfs_m=round(sum(trace.intersection(g).length for g,label in owners if label=='NON-FS'),1) if trace else None,legal_access='UNKNOWN',physical_feasibility='UNKNOWN',field_ready=False)
        rows.append(row);details.append(dict(**row,entry=selected[1] if selected else None,source_segments=trace_sources,nearest_feature_attributes=attrs))
        features.append(dict(type='Feature',geometry=mapping(gap),properties=dict(id=pid,kind='unmapped straight gap, NOT an approach')))
        if trace:features.append(dict(type='Feature',geometry=mapping(trace),properties=dict(id=pid,kind='mapped connectivity witness, NOT navigation')))
    for e in entries:features.append(dict(type='Feature',geometry=mapping(Point(e['xy'])),properties=dict(id=e['provider_road_id'],kind=e['name']+'; entry access/parking unverified')))
    dump(root/'access_geometry.json',dict(crs='EPSG:32613',features=features));dump(root/'access_details.json',details);csvwrite(root/'access_review.csv',rows)
    manifest=json.loads((inputs/'manifest.json').read_text())
    dump(root/'access_summary.json',dict(entries=entries,candidates=rows,source_retrieval_dates={k:v['retrieved_utc'] for k,v in manifest.items() if k.endswith('.geojson')},source_dates='Per-feature acquisition/update dates absent in this inventory; retrieval is not a currency guarantee.',recreation_point_count=0,limitations=['No downloaded recreation site points in query area. Named road endpoint and mapped junction entries explicitly distinguished from certified public parking.','Ownership layer distinguishes FS from NON-FS only; NON-FS is not synonymous with private. Easements/parcel permissions unavailable.','USFS MVUM records describe motor use/seasonal designations; do not establish pedestrian access rights. Full provider attributes retained.','Current forest alerts web request returned HTTP403. Current orders and trip-date restrictions require direct agency review.','No endpoint-gap bridging in network graph. Exact mapped intersections may have grade separation or topology errors.','Straight final gaps are unknown approach evidence, NOT suggested off-trail travel.','No hike/gain limit applied: preferences and dates not supplied. Full witness is not optimized or physically surveyed.'],field_ready=[]))
    print('Access gaps:',[(r['id'],r['mapped_network_gap_m'],r['entry_connectivity']) for r in rows],flush=True)
