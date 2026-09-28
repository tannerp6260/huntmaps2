"""Bounded, checksum-verified CPW/TNM acquisition. No commercial sources."""
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import urllib.parse
import urllib.request
from osgeo import ogr, osr

CPW = 'https://services5.arcgis.com/ttNGmDvKQA7oeDQ3/ArcGIS/rest/services/CPWAdminData/FeatureServer/6'
TNM = 'https://tnmaccess.nationalmap.gov/api/v1/products'


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def srs(code):
    s = osr.SpatialReference()
    s.ImportFromEPSG(code)
    s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return s


class Fetcher:
    def __init__(self, root, budget):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.budget = budget
        self.used = 0
        self.started = __import__('time').monotonic()
        self.manifest_path = self.root / 'manifest.json'
        self.entries = json.loads(self.manifest_path.read_text()) if self.manifest_path.exists() else {}
        # Total retained source bytes plus new transfer cannot exceed the trial limit.
        self.budget -= sum(v['bytes'] for k,v in self.entries.items() if (self.root/k).exists())

    def get(self, name, url, **metadata):
        path = self.root / name
        if path.exists():
            old = self.entries.get(name)
            if not old or old['url'] != url or old['sha256'] != digest(path):
                raise ValueError(f'Unverified or changed input: {path}; use a new input directory')
            return path
        partial = path.with_suffix(path.suffix + '.partial')
        req = urllib.request.Request(url, headers={'User-Agent': 'glassing-terrain-experiment/0.1'})
        with urllib.request.urlopen(req, timeout=60) as response, open(partial, 'wb') as f:
            length = response.headers.get('Content-Length')
            if length and self.used + int(length) > self.budget:
                raise ValueError('Download budget exceeded before transfer')
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                self.used += len(block)
                if self.used > self.budget:
                    raise ValueError('Download budget exceeded; partial file is not accepted')
                f.write(block)
        partial.replace(path)
        self.entries[name] = dict(url=url, sha256=digest(path), bytes=path.stat().st_size,
                                 elapsed_since_fetcher_start_s=__import__('time').monotonic()-self.started,
                                 retrieved_utc=dt.datetime.now(dt.timezone.utc).isoformat(), **metadata)
        dump(self.manifest_path, self.entries)
        return path

    def json(self, name, url, **metadata):
        value = json.loads(self.get(name, url, **metadata).read_text())
        if 'error' in value:
            raise ValueError(f'Provider returned error: {value["error"]}')
        return value


def acquire(c):
    root = Path(c['inputs'])
    f = Fetcher(root, c['download_bytes'])
    f.json('cpw_layer.json', CPW + '?f=pjson', provider='Colorado Parks and Wildlife')
    f.json('cpw_item.json', 'https://www.arcgis.com/sharing/rest/content/items/168fccb0583f42f1afe57de6c9ce846d?f=json', provider='CPW', purpose='license and description')
    url = CPW + '/query?' + urllib.parse.urlencode(dict(where='GMUID=54', outFields='*', outSR=4326, f='geojson'))
    raw = f.json('gmu54.geojson', url, provider='CPW', acquisition_date='unknown; feature edit dates retained',
                 license='see cpw_item.json licenseInfo; CPW public distribution', crs='EPSG:4326', resolution='1:24000 source mapping', vertical_reference='not applicable')
    if digest(root / 'gmu54.geojson') != c['boundary_sha256']:
        raise ValueError('Live GMU boundary differs from frozen trial; retain archived input or explicitly define new trial')
    if raw.get('exceededTransferLimit') or not raw.get('features'):
        raise ValueError('Incomplete boundary response')
    combined = None
    for feature in raw['features']:
        geom = ogr.CreateGeometryFromJson(json.dumps(feature['geometry']))
        geom.Transform(osr.CoordinateTransformation(srs(4326), srs(c['epsg'])))
        combined = geom if combined is None else combined.Union(geom)
    if not combined.IsValid():
        raise ValueError('Invalid authoritative boundary; manual repair required')
    center = combined.Centroid()
    # Deterministic centroid-centred 8 km square, clipped to the authoritative unit.
    x, y = round(center.GetX() / 10) * 10, round(center.GetY() / 10) * 10
    ring = ogr.Geometry(ogr.wkbLinearRing)
    for xx, yy in [(x-4000,y-4000),(x+4000,y-4000),(x+4000,y+4000),(x-4000,y+4000),(x-4000,y-4000)]:
        ring.AddPoint_2D(xx, yy)
    square = ogr.Geometry(ogr.wkbPolygon); square.AddGeometry(ring)
    pilot = combined.Intersection(square)
    if not 50e6 <= pilot.GetArea() <= 100e6:
        raise ValueError(f'Centroid pilot area {pilot.GetArea()/1e6:.3f} km² outside 50–100; selection needs review')
    dump(root / 'pilot.json', dict(epsg=c['epsg'], geometry=json.loads(pilot.ExportToJson()),
        area_m2=pilot.GetArea(), selection='GMU 54 dissolved projected centroid rounded to 10 m; 8 km square intersected with unit',
        boundary_sha256=digest(root / 'gmu54.geojson')))
    xmin, xmax, ymin, ymax = pilot.GetEnvelope()
    halo = max(c['radii_m']) + 2*c['resolution_m']
    bounds = [math.floor((xmin-halo)/10)*10, math.floor((ymin-halo)/10)*10,
              math.ceil((xmax+halo)/10)*10, math.ceil((ymax+halo)/10)*10]
    transform = osr.CoordinateTransformation(srs(c['epsg']), srs(4326))
    corners = [transform.TransformPoint(xx, yy) for xx in (bounds[0],bounds[2]) for yy in (bounds[1],bounds[3])]
    bbox = [min(p[0] for p in corners),min(p[1] for p in corners),max(p[0] for p in corners),max(p[1] for p in corners)]
    query = TNM + '?' + urllib.parse.urlencode(dict(datasets='National Elevation Dataset (NED) 1/3 arc-second', bbox=','.join(map(str,bbox)), prodFormats='GeoTIFF', max=20))
    catalog = f.json('tnm_products.json', query, provider='USGS TNM')
    items = catalog.get('items', [])
    if not items or catalog.get('total',len(items)) > len(items):
        raise ValueError(f'TNM catalog incomplete or empty: {catalog.get("total")}')
    # Freeze one chosen product before transferring bytes. TNM includes historical
    # revisions of the same spatial tile; never download every returned revision.
    selected = [i for i in items if Path(urllib.parse.urlparse(i.get('downloadURL','')).path).name == c['dem_product']]
    if len(selected) != 1:
        raise ValueError('Pinned DEM product missing or ambiguous in catalog')
    paths = []
    for item in selected:
        url = item.get('downloadURL', '')
        if not url.lower().endswith('.tif'):
            raise ValueError(f'Expected GeoTIFF product, got {url}')
        name = Path(urllib.parse.urlparse(url).path).name
        if not (root/name).exists() and item.get('sizeInBytes',0) and int(item['sizeInBytes']) > f.budget - f.used:
            raise ValueError('Catalog product exceeds remaining download budget')
        p = f.get(name, url, provider='USGS 3DEP', title=item.get('title'),
                  acquisition_date='unknown; publication date is not acquisition', publication_date=item.get('publicationDate'),
                  resolution='1/3 arc-second (~10 m)', crs='inspect source GeoTIFF', vertical_units='metres per USGS product specification',
                  vertical_datum='NAVD88 per CONUS product specification; tile metadata may be incomplete',
                  license='USGS public domain', catalog_source_id=item.get('sourceId'), metadata_url=item.get('metaUrl'))
        if digest(p) != c['dem_sha256']:
            raise ValueError('Pinned DEM checksum differs; do not silently change experiment terrain')
        paths.append(str(p))
    dump(root / 'inputs.json', dict(dem=paths, bounds=bounds, pilot=str(root/'pilot.json'), new_download_bytes=f.used))
    print(json.dumps(dict(pilot_km2=pilot.GetArea()/1e6, products=paths, new_download_bytes=f.used)))
