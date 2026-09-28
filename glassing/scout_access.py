"""Single-opportunity approach evidence. No timed or multi-stop itinerary."""
import json,math,heapq
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
from scipy.spatial import cKDTree
from scipy.ndimage import map_coordinates,gaussian_filter
from shapely.geometry import shape,Point,LineString,box,mapping
from shapely.ops import transform,unary_union
from shapely.validation import make_valid
from osgeo import gdal,ogr,osr
from .acquire import dump,srs
from . import core,compare
from .correction_access import projector
from .correct import csvwrite


def normalized_id(value):
    s=str(value or '').strip().upper()
    return s[1:] if len(s)==4 and s[0] in '79' and s.isdigit() else s


def route_name(value):
    return ' '.join(w for w in str(value or '').upper().replace('-', ' ').split() if w not in ['ROAD','RD','TRAIL','TR','CR','FS','NFSR','NFST'])


def insert_supported_vertices(records,tolerance=5):
    """Insert projected endpoint junctions only on the same named/numbered route.

    Source endpoints establish continuity evidence; geometric crossings alone do not.
    """
    from shapely.strtree import STRtree
    from shapely.ops import substring
    lines=[r['geometry'] for r in records];tree=STRtree(lines);inserts=defaultdict(list)
    for ri,line in enumerate(lines):
        a=records[ri]
        for coord in [line.coords[0],line.coords[-1]]:
            point=Point(coord)
            for rj in tree.query(point.buffer(tolerance)):
                rj=int(rj)
                if ri==rj:continue
                b=records[rj];sameid=bool(a['route_id']) and normalized_id(a['route_id'])==normalized_id(b['route_id'])
                an,bn=route_name(a['name']),route_name(b['name']);samename=bool(an) and (an==bn or (an.replace(' DETOUR','')==bn.replace(' DETOUR','') and point.distance(lines[rj])<=2))
                if (sameid or samename) and point.distance(lines[rj])<=tolerance:
                    d=lines[rj].project(point);inserts[rj].append(d)
    for j,values in inserts.items():
        line=lines[j];coords=list(line.coords);positions=[0.]
        for a,b in zip(coords[:-1],coords[1:]):positions.append(positions[-1]+math.dist(a,b))
        merged=sorted(list(zip(positions,coords))+[(d,line.interpolate(d).coords[0]) for d in values])
        records[j]['geometry']=LineString([p for d,p in merged])
    return records


def build_network(records,tolerance=5):
    """Connect shared source vertices, not arbitrary geometric crossings.

    Repair only near endpoints with identical route ID or nonempty exact route name.
    Full coincident segments deduplicated, with source membership retained.
    """
    vertices=[];index={};edges={};ends=[];logs=[]
    def node(xy):
        key=tuple(round(float(v),2) for v in xy)
        if key not in index:index[key]=len(vertices);vertices.append(key)
        return index[key]
    for rid,r in enumerate(records):
        coords=list(r['geometry'].coords);nodes=[node(xy) for xy in coords]
        ends.extend([(nodes[0],rid),(nodes[-1],rid)])
        for u,v in zip(nodes[:-1],nodes[1:]):
            if u==v:continue
            pair=tuple(sorted((u,v)))
            if pair in edges:edges[pair]['records'].add(rid)
            else:edges[pair]=dict(length=math.dist(vertices[u],vertices[v]),records={rid},repair=False)
    # Endpoint-to-source-vertex continuity only; never node an arbitrary crossing.
    membership=defaultdict(set)
    for (u,v),edge in edges.items():
        membership[u].update(edge['records']);membership[v].update(edge['records'])
    tree=cKDTree(vertices);existing=len(edges)
    for u,ri in ends:
        for v in tree.query_ball_point(vertices[u],tolerance):
            if u==v:continue
            for rj in membership[v]:
                if ri==rj:continue
                a,b=records[ri],records[rj]
                sameid=bool(a['route_id']) and normalized_id(a['route_id'])==normalized_id(b['route_id'])
                an,bn=route_name(a['name']),route_name(b['name'])
                samename=bool(an) and (an==bn or (an.replace(' DETOUR','')==bn.replace(' DETOUR','') and math.dist(vertices[u],vertices[v])<=2))
                if not(sameid or samename):continue
                pair=tuple(sorted((u,v)))
                if pair not in edges:
                    length=math.dist(vertices[u],vertices[v]);edges[pair]=dict(length=length,records={ri,rj},repair=True)
                    logs.append(dict(xy1=vertices[u],xy2=vertices[v],gap_m=length,source_records=[ri,rj],routes=[dict(source=z.get('kind','fixture'),id=z['route_id'],name=z['name']) for z in [a,b]],evidence='same route ID' if sameid else 'same route name (Sun Creek/Detour endpoint exception <=2m)' if an!=bn else 'same nonempty route name',status='endpoint to source vertex continuity hypothesis; no bridge/junction certification'))
    adj=defaultdict(list)
    for (u,v),e in edges.items():adj[u].append((v,e));adj[v].append((u,e))
    return np.array(vertices),adj,logs,len(edges)-existing


def shortest(adj,source,records,vehicle=False):
    dist={source:0.};prev={};heap=[(0.,source)]
    while heap:
        cost,u=heapq.heappop(heap)
        if cost!=dist[u]:continue
        for v,e in adj[u]:
            if vehicle and not any(records[j]['motor'] for j in e['records']):continue
            new=cost+e['length']
            if new<dist.get(v,float('inf')):dist[v]=new;prev[v]=(u,e);heapq.heappush(heap,(new,v))
    return dist,prev


def trace(prev,target):
    nodes=[target];sources=set();repairs=0
    while target in prev:
        target,e=prev[target];nodes.append(target);sources.update(e['records']);repairs+=int(e['repair'])
    return nodes[::-1],sources,repairs


def route_profile(coords,dem):
    line=LineString(coords);ds=dem;gt=ds.GetGeoTransform();a=ds.ReadAsArray();d=np.arange(0,line.length,20);d=np.r_[d,line.length]
    xy=np.array([line.interpolate(float(t)).coords[0] for t in d]);rr=(xy[:,1]-gt[3])/gt[5]-.5;cc=(xy[:,0]-gt[0])/gt[1]-.5
    valid=(rr>=0)&(cc>=0)&(rr<a.shape[0]-1)&(cc<a.shape[1]-1)
    if not valid.all():return dict(distance_m=line.length,gain_m=None,loss_m=None,dem_coverage=float(valid.mean()))
    z=map_coordinates(a,[rr,cc],order=1,mode='nearest');z=gaussian_filter(z,1);dz=np.diff(z)
    return dict(distance_m=line.length,gain_m=float(np.maximum(dz,0).sum()),loss_m=float(np.maximum(-dz,0).sum()),dem_coverage=1.)


def terrain_connector(a,allowed,gt,start,end,max_slope=30):
    """20m terrain-screened corridor; no private/unknown cells or >threshold slopes.

    A local least-cost connector is an exploratory desktop leg, not navigation truth.
    No diagonal corner-cutting; slope penalty is a travel hypothesis, not safety rating.
    """
    gy,gx=np.gradient(a,gt[1]);slope=np.degrees(np.arctan(np.hypot(gx,gy)));ok=allowed&(slope<=max_slope)&np.isfinite(a)&(a>0)
    cell=lambda p:(int((p[1]-gt[3])/gt[5]),int((p[0]-gt[0])/gt[1]))
    src,dst=cell(start),cell(end);h,w=a.shape
    if not all(0<=r<h and 0<=col<w and ok[r,col] for r,col in [src,dst]):return None
    dist={src:0.};prev={};heap=[(0.,src)];directions=[(dr,dc) for dr in [-1,0,1] for dc in [-1,0,1] if dr or dc]
    while heap:
        cost,u=heapq.heappop(heap)
        if cost!=dist[u]:continue
        if u==dst:break
        r,col=u
        for dr,dc in directions:
            v=(r+dr,col+dc);rr,co=v
            if not(0<=rr<h and 0<=co<w and ok[rr,co]):continue
            if dr and dc and not(ok[r,co] and ok[rr,col]):continue
            length=gt[1]*math.hypot(dr,dc);grade=abs(float(a[rr,co]-a[r,col]))/length
            if math.degrees(math.atan(grade))>max_slope:continue
            new=cost+length*(1+(slope[rr,co]/15)**2)
            if new<dist.get(v,float('inf')):dist[v]=new;prev[v]=u;heapq.heappush(heap,(new,v))
    if dst not in dist:return None
    path=[dst]
    while path[-1]!=src:path.append(prev[path[-1]])
    path.reverse();coords=[(gt[0]+(col+.5)*gt[1],gt[3]+(r+.5)*gt[5]) for r,col in path]
    # Exact endpoints lie inside their tested cells; local subcell terrain remains unknown.
    coords=[tuple(start)]+coords+[tuple(end)]
    return dict(coords=coords,max_cell_slope_deg=float(max(slope[r,col] for r,col in path)),cost=dist[dst])


def season_covers(interval,dates):
    """Conservative one-interval MM/DD range, all legal hunt dates inclusive."""
    import datetime,re
    match=re.fullmatch(r'(\d{2}/\d{2})-(\d{2}/\d{2})',str(interval))
    if not match:return False
    year=int(dates[0][:4])
    try:a,b=[datetime.datetime.strptime(f'{year}/'+v,'%Y/%m/%d').date() for v in match.groups()]
    except ValueError:return False
    first,last=[datetime.date.fromisoformat(v) for v in dates]
    return a<=first<=last<=b


def records_load(c):
    xy=projector();records=[];mv=json.load(open(Path(c['inputs'])/'mvum_roads.geojson'))['features'];mv_ids={f['properties']['id'] for f in mv if f['properties'].get('highclearancevehicle')=='open' and season_covers(f['properties'].get('highclearancevehicle_datesopen'),c['hunt']['legal_dates'])}
    for kind in ['roads','trails','blm_co_routes','cdot_local']:
        for f in json.load(open(Path(c['inputs'])/(kind+'.geojson')))['features']:
            p=f['properties'];g=transform(xy,shape(f['geometry']))
            if kind=='blm_co_routes':
                rid=p.get('ROUTE_PRMRY_NUM');name=p.get('ROUTE_PRMRY_NM') or ''
                if p.get('PLAN_OHV_ROUTE_DSGNTN')=='Closed' or p.get('PLAN_ACCESS_RSTRCT') not in ['None',None,'','Unknown']:continue
                motor=p.get('PLAN_ALLOW_MODE_TRNSPRT')=='ALL_MOTO_VEH' and p.get('PLAN_OHV_ROUTE_DSGNTN') in ['Open','Limited']
            elif kind=='cdot_local':
                rid=p.get('ROUTE');name=p.get('ROUTENAME','');motor=str(p.get('GOVLEVEL'))=='2'
            else:
                rid=p.get('id',p.get('trail_no'));name=p.get('name',p.get('trail_name','')) or '';motor=kind=='roads' and rid in mv_ids
            for part in list(g.geoms) if hasattr(g,'geoms') else [g]:
                if part.geom_type=='LineString':records.append(dict(geometry=part,kind=kind,route_id=str(rid),name=name,motor=bool(motor),properties=dict(p,mvum_evidence=[f['properties'] for f in mv if f['properties'].get('id')==rid]) if kind=='roads' else p))
    return records


def run(c):
    root=Path(c['work']);cc=json.load(open(c['comparison_config']));b,base,ds,a,gt,masks=compare.load(cc);points={p['id']:p for p in json.load(open(base/'candidates.json'))};xy=projector()
    records=insert_supported_vertices(records_load(c),c['topology']['same_route_endpoint_tolerance_m']);vertices,adj,repairs,_=build_network(records,c['topology']['same_route_endpoint_tolerance_m']);tree=cKDTree(vertices)
    entries=[];entry_screen=[]
    for f in json.load(open(Path(c['inputs'])/'rec_sites.geojson'))['features']:
        p=f['properties'];site=transform(xy,shape(f['geometry']));entry_screen.append(dict(name=p['site_name'],nearest_primary_straight_km=round(min(site.distance(Point(points[i]['x'],points[i]['y'])) for i in ['C0068','C0095','C0049'])/1000,2),selected_for_network_review=p['site_name'] in ['MILL CASTLE','RAINBOW'],attributes=p))
        if p['site_name'] not in ['MILL CASTLE','RAINBOW']:continue
        g=transform(xy,shape(f['geometry']));entries.append(dict(id=p['site_name'].replace(' ','_'),name=p['site_name']+' trailhead',x=g.x,y=g.y,evidence='USFS Recreation Sites INFRA point; site status OPEN in inventory, not trip-day clearance',source='rec_sites.geojson',parking='trailhead inventory only; parking conditions/capacity unverified',last_update=p['infra_last_update']))
    dump(root/'entry_screen.json',sorted(entry_screen,key=lambda r:r['nearest_primary_straight_km']))
    # CPW website Get Directions explicitly links this entrance coordinate; not a selected camp.
    tr=osr.CoordinateTransformation(srs(4326),srs(32613));x,y,_=tr.TransformPoint(-107.0318,38.505)
    entries.append(dict(id='GUNNISON_SWA',name='Gunnison SWA signed entrance',x=x,y=y,evidence='CPW Gunnison SWA Get Directions 38.505,-107.0318; CPW 2019 georeferenced map documents parking along entrance corridor',source='gunnison_swa.html / gunnison_swa.pdf',parking='documented parking symbols; precise pull-in/overnight suitability must be checked',last_update='map 2019-02-22 / regulations page 2023-10-31'))
    # Two documented parking symbols digitized from the CPW geospatial PDF, not invented sites.
    pdf=gdal.Open(str(Path(c['inputs'])/'gunnison_swa.pdf'));pg=pdf.GetGeoTransform()
    # Viewed /tmp/swa.png width1400; marker centres measured in exported raster pixels.
    for label,px,py in [('SWA_UPPER_PARKING',660,1131),('SWA_MIDDLE_PARKING',670,1185)]:
        sx=px*pdf.RasterXSize/1400;sy=py*pdf.RasterXSize/1400;x=pg[0]+sx*pg[1]+sy*pg[2];y=pg[3]+sx*pg[4]+sy*pg[5]
        ptr=osr.CoordinateTransformation(srs(26913),srs(32613));x,y,_=ptr.TransformPoint(x,y)
        entries.append(dict(id=label,name=label.replace('_',' ').title(),x=x,y=y,evidence='CPW georeferenced 2019 map parking icon digitization; approximate ±100m symbol/registration uncertainty',source='gunnison_swa.pdf',parking='parking symbol documented; not a surveyed stall or current condition check',last_update='2019-02-22'))
    # Broader terrain for mapped approach profiles; no new DEM download.
    bounds=[310000,4260000,326000,4288000]
    profdem=gdal.Warp(str(root/'approach_dem20m.tif'),str(Path(b['inputs'])/b['dem_product']),dstSRS=ds.GetProjection(),outputBounds=bounds,xRes=20,yRes=20,resampleAlg='bilinear',dstNodata=-9999)
    forest=[];private=[]
    for f in json.load(open(Path(c['inputs'])/'surface_management.geojson'))['features']:
        g=transform(xy,shape(f['geometry']));g=make_valid(g) if not g.is_valid else g
        if f['properties']['adm_code'] in ['USFS','BLM']:forest.append(g)
        elif f['properties']['adm_code']=='PRI':private.append(g)
    private=unary_union(private);public=unary_union(forest).difference(private)
    water=unary_union([make_valid(transform(xy,shape(f['geometry']))) for f in json.load(open(Path(c['inputs'])/'waterbodies.geojson'))['features']])
    flows=[(transform(xy,shape(f['geometry'])),f['properties']) for f in json.load(open(Path(c['inputs'])/'flowlines.geojson'))['features']]
    public=public.difference(water.buffer(20))
    # Snap entry to inventory only as a recorded gap; never call it an established connection.
    for e in entries:
        gap,node=tree.query([e['x'],e['y']]);e['network_snap_m']=float(gap);e['node']=int(node)
    paths={e['id']:shortest(adj,e['node'],records) for e in entries};vehiclepaths={e['id']:shortest(adj,e['node'],records,vehicle=True) for e in entries}
    features=[];rows=[];details=[]
    for i in c['candidates']:
        p=points[i];point=Point(p['x'],p['y']);idx=tree.query_ball_point([p['x'],p['y']],c['offtrail']['max_connector_m']);dist=np.linalg.norm(vertices[idx]-[p['x'],p['y']],axis=1)
        choices=[]
        for d,node in zip(np.atleast_1d(dist),np.atleast_1d(idx)):
            for e in entries:
                mapped=paths[e['id']][0].get(int(node))
                if mapped is not None:choices.append((float(d)+mapped*.12,float(d),int(node),e,mapped))
        if not choices:
            rows.append(dict(id=i,status='No mapped entry connection in expanded inventory'));continue
        # At most three candidate departures; path success matters more than nearest Euclidean gap.
        tested=[];seen=set();chosen=None
        for _,gap,node,e,mapped in sorted(choices,key=lambda z:z[0]):
            bucket=(round(vertices[node,0]/100),round(vertices[node,1]/100),e['id'])
            if bucket in seen:continue
            seen.add(bucket)
            if len(tested)>=6:break
            if gap>c['offtrail']['max_connector_m']:continue
            start=vertices[node];xmin=min(start[0],p['x'])-400;ymin=min(start[1],p['y'])-400;xmax=max(start[0],p['x'])+400;ymax=max(start[1],p['y'])+400
            dem=gdal.Warp('',profdem,format='MEM',outputBounds=[math.floor(xmin/20)*20,math.floor(ymin/20)*20,math.ceil(xmax/20)*20,math.ceil(ymax/20)*20],xRes=20,yRes=20,resampleAlg='bilinear',dstNodata=-9999);da=dem.ReadAsArray();dg=dem.GetGeoTransform()
            allowed=core.polygon_mask(ogr.CreateGeometryFromWkb(public.wkb),da.shape,dg,dem.GetProjection())
            con=terrain_connector(da,allowed,dg,start,(p['x'],p['y']),c['offtrail']['max_slope_deg']);tested.append(dict(entry=e['id'],gap_m=gap,corridor_found=con is not None))
            if con:
                chosen=(node,e,mapped,con);break
        if chosen is None:
            rows.append(dict(id=i,status='No tested terrain-screened connector; inspect other departures',tests=tested));continue
        node,e,mapped,con=chosen;nodes,sourceids,nrepairs=trace(paths[e['id']][1],node);coords=vertices[nodes].tolist()
        line=LineString(coords);off=LineString(con['coords']);mp=route_profile(coords,profdem);op=route_profile(con['coords'],profdem)
        # Candidate approach has separate motor-designation chain and pedestrian remainder.
        vehicle_dist,vehicle_prev=vehiclepaths[e['id']];vehicle_nodes=[(k,n) for k,n in enumerate(nodes) if n in vehicle_dist]
        # Furthest along this pedestrian witness with a continuous designated-motor chain.
        departure_index,departure_node=vehicle_nodes[-1] if vehicle_nodes else (0,nodes[0])
        motor_nodes,motor_sources,motor_repairs=trace(vehicle_prev,departure_node)
        walk_coords=vertices[nodes[departure_index:]].tolist();walk_coords=walk_coords if len(walk_coords)>1 else [walk_coords[0],walk_coords[0]]
        wp=route_profile(walk_coords,profdem);motorcoords=vertices[motor_nodes].tolist()
        distance=wp['distance_m']+op['distance_m'];gain=(wp['gain_m'] or 0)+(op['gain_m'] or 0);loss=(wp['loss_m'] or 0)+(op['loss_m'] or 0)
        roundtrip_miles=2*distance/1609.344;roundtrip_gain_ft=(gain+loss)*3.28084
        low=2*distance/1000/c['offtrail']['walking_kmh'][1]+(gain+loss)/c['offtrail']['ascent_m_per_hour'][1]
        high=2*distance/1000/c['offtrail']['walking_kmh'][0]+(gain+loss)/c['offtrail']['ascent_m_per_hour'][0]
        row=dict(id=i,status='Provisional approach option; driving endpoint/parking unresolved',entry=e['id'],entry_snap_m=round(e['network_snap_m'],1),mapped_from_entry_km=round(mp['distance_m']/1000,2),vehicle_designated_km=round(sum(math.dist(u,v) for u,v in zip(motorcoords[:-1],motorcoords[1:]))/1000,2),pedestrian_mapped_km=round(wp['distance_m']/1000,2),offtrail_km=round(op['distance_m']/1000,2),offtrail_max_slope_deg=round(con['max_cell_slope_deg'],1),oneway_walk_gain_m=round(gain),conditional_roundtrip_miles=round(roundtrip_miles,1),conditional_roundtrip_gain_ft=round(roundtrip_gain_ft),conditional_roundtrip_hours_low=round(low,1),conditional_roundtrip_hours_high=round(high,1),mapped_private_crossing_m=round(line.intersection(private).length),offtrail_private_crossing_m=round(off.intersection(private).length),topology_repairs_used=nrepairs,parking_status='UNVERIFIED at conditional motor departure',field_verification='not done')
        foot_distance=mp['distance_m']+op['distance_m'];foot_gain=(mp['gain_m'] or 0)+(mp['loss_m'] or 0)+(op['gain_m'] or 0)+(op['loss_m'] or 0)
        row.update(entrance_roundtrip_miles=round(2*foot_distance/1609.344,1),entrance_roundtrip_gain_ft=round(foot_gain*3.28084),entrance_roundtrip_hours_low=round(2*foot_distance/3000+foot_gain/600,1),entrance_roundtrip_hours_high=round(2*foot_distance/1500+foot_gain/300,1))
        from .correction_geometry import sample
        sample_points=[off.interpolate(t) for t in np.arange(0,off.length+1,20)];tree_ds=gdal.Open(str(Path(cc['work'])/'tree.tif'));tree_values=sample(tree_ds,np.array([p.x for p in sample_points]),np.array([p.y for p in sample_points]));tree_ok=(tree_values>=0)&(tree_values<=1)
        crossings=[dict(name=prop.get('gnis_name'),fcode=prop.get('fcode'),feature_date=prop.get('fdate')) for stream,prop in flows if off.intersects(stream)]
        row.update(offtrail_NHD_crossed_features=len(crossings),offtrail_tree_cover_mean=float(tree_values[tree_ok].mean()) if tree_ok.any() else None,offtrail_cover_unknown_fraction=float((~tree_ok).mean()),offtrail_waterbody_intersection_m=round(off.intersection(water).length))
        if off.intersection(private).length>0 or off.intersection(water).length>0:raise ValueError('Offtrail barrier intersection '+i)
        rows.append(row)
        details.append(dict(summary=row,stream_crossings=crossings,departure_xy=vertices[departure_node].tolist(),entry=e,mapped_profile=mp,pedestrian_profile=wp,offtrail_profile=op,connector_tests=tested,route_sources=[dict(kind=records[j]['kind'],route_id=records[j]['route_id'],name=records[j]['name'],motor=records[j]['motor'],attributes=records[j]['properties']) for j in sorted(sourceids)],warning='Vehicle chain describes mapped designations, not drivability, parking permission, trip-day opening or continuous right-of-way. Effort is conditional on that departure; entrance-foot alternative is longer. Off-trail slope screening does not detect fences, cliff microterrain, snow, deadfall or all water crossings.'))
        for kind,g in [('mapped_approach',line),('offtrail_terrain_hypothesis',off),('conditional_vehicle_departure',Point(vertices[departure_node]))]:features.append(dict(type='Feature',geometry=mapping(g),properties=dict(id=i,kind=kind)))
        if len(motorcoords)>1:features.append(dict(type='Feature',geometry=mapping(LineString(motorcoords)),properties=dict(id=i,kind='conditional_motor_designation_chain')))
    dump(root/'approach_details.json',details);dump(root/'approach_rows.json',rows);dump(root/'approach_geometry.json',dict(crs='EPSG:32613',features=features));dump(root/'entry_options.json',entries)
    dump(root/'topology.json',dict(vertices=len(vertices),records=len(records),repairs=repairs,policy='Shared vertices rounded to centimetres; no noding of unshared crossings. Same-route endpoint to vertex/projected segment <=5m; Sun Creek/Detour name exception <=2m. Source endpoints required, not arbitrary crossings. No arbitrary nearest-line bridges. Entry gaps remain explicit, not repairs.',duplicate_segments='Exact coincident vertex-segments consolidated, source membership retained',extent='50km expanded; network data queried by intersect, full returned geometries retained without clipping',blocked_input='National BLM layer had zero local routes; Colorado BLM layer supplies 981 features.'))
    for r in rows:print('Approach',r,flush=True)
