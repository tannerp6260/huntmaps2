"""Explicit local polygon conversion; no network links or silent feature choice."""
import json,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
from shapely.geometry import shape,Polygon,mapping
from shapely.ops import unary_union
from .acquire import digest,dump

LIMIT=10_000_000

def choices(path):
    path=Path(path)
    if path.stat().st_size>LIMIT:raise ValueError('Area export exceeds 10MB; export only the intended polygon(s)')
    items=[]
    if path.suffix.lower() in ['.json','.geojson']:
        data=json.loads(path.read_text())
        if data.get('crs'):raise ValueError('GeoJSON must use WGS84 longitude/latitude (RFC7946)')
        fs=data.get('features',[]) if data['type']=='FeatureCollection' else [data]
        for n,f in enumerate(fs):
            g=shape(f.get('geometry',f));label=f.get('properties',{}).get('name',str(n+1))
            if g.geom_type=='Polygon':items.append((label,g))
            elif g.geom_type=='MultiPolygon':items.extend((f'{label} / part {k+1}',p) for k,p in enumerate(g.geoms))
    elif path.suffix.lower() in ['.kml','.kmz']:
        if path.suffix.lower()=='.kmz':
            with zipfile.ZipFile(path) as z:
                names=[n for n in z.infolist() if n.filename.lower().endswith('.kml')]
                if sum(n.file_size for n in names)>LIMIT:raise ValueError('Expanded KMZ exceeds 10MB')
                documents=[(n.filename,z.read(n)) for n in names]
        else:documents=[(path.name,path.read_bytes())]
        for name,data in documents:
            if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise ValueError('KML entity declarations unsupported; export a plain polygon file')
            tree=ET.fromstring(data)
            for pm in tree.findall('.//{*}Placemark'):
                label=pm.find('{*}name');label=label.text if label is not None else name
                for n,pg in enumerate(pm.findall('.//{*}Polygon')):
                    def ring(tag):
                        el=pg.find('.//{*}'+tag+'/{*}LinearRing/{*}coordinates')
                        if el is None or not el.text:raise ValueError('KML polygon has no ring coordinates')
                        return [tuple(map(float,q.split(',')[:2])) for q in el.text.split()]
                    outer=ring('outerBoundaryIs');holes=[]
                    for inner in pg.findall('{*}innerBoundaryIs'):
                        el=inner.find('{*}LinearRing/{*}coordinates');holes.append([tuple(map(float,q.split(',')[:2])) for q in el.text.split()])
                    items.append((f'{label} / polygon {n+1}',Polygon(outer,holes)))
    else:raise ValueError('Use .geojson, .kml or .kmz for the observer-search area')
    if not items:raise ValueError('No polygons found; tracks, points and remote NetworkLinks are not an area')
    for name,g in items:
        if g.is_empty or not g.is_valid:raise ValueError('Invalid polygon '+name+'; repair its ring in the exporting app')
        x,y,X,Y=g.bounds
        if not(-180<=x<=X<=180 and -90<=y<=Y<=90):raise ValueError('Area coordinates must be longitude/latitude degrees')
    return items


def convert(path,destination,selection=None):
    items=choices(path)
    if len(items)>1 and selection is None:
        listing='; '.join(f'{i+1}: {name}' for i,(name,g) in enumerate(items))
        raise ValueError('Multiple polygons: '+listing+'. Repeat with --polygon NUMBER or --polygon all (explicit union).')
    if selection=='all':chosen=items
    elif selection is not None:
        try:index=int(selection)-1;assert 0<=index<len(items)
        except (ValueError,AssertionError):raise ValueError('--polygon must be a listed number or all')
        chosen=[items[index]]
    else:chosen=items
    geometry=unary_union([g for name,g in chosen]);dump(Path(destination),dict(type='FeatureCollection',features=[dict(type='Feature',properties=dict(source=str(Path(path).resolve()),source_sha256=digest(path),selected=[name for name,g in chosen]),geometry=mapping(geometry))]))
    return geometry
