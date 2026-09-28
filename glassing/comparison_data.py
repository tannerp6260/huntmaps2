"""Small public CPW range and USGS RCMAP WCS subsets; acquisition only."""
import json
from pathlib import Path
import urllib.parse
from osgeo import gdal,osr
from .acquire import Fetcher,dump,srs,digest

CPW='https://services5.arcgis.com/ttNGmDvKQA7oeDQ3/arcgis/rest/services/CPWSpeciesData/FeatureServer'


def acquire(c):
    b=json.loads(Path(c['baseline_config']).read_text());base=Path(b['work'])
    ds=gdal.Open(str(base/'dem.tif'));gt=ds.GetGeoTransform()
    bounds=[gt[0],gt[3]+ds.RasterYSize*gt[5],gt[0]+ds.RasterXSize*gt[1],gt[3]]
    f=Fetcher(c['inputs'],c['download_bytes'])
    server=f.json('cpw_service.json',CPW+'?f=json',provider='CPW')
    f.json('cpw_item.json','https://www.arcgis.com/sharing/rest/content/items/'+server['serviceItemId']+'?f=json',provider='CPW',purpose='source description/license')
    for name,layer in [('summer',99),('winter',105)]:
        meta=f.json(name+'_metadata.json',f'{CPW}/{layer}?f=json',provider='CPW')
        q=dict(f='geojson',where='1=1',geometry=','.join(map(str,bounds)),geometryType='esriGeometryEnvelope',inSR=b['epsg'],spatialRel='esriSpatialRelIntersects',outFields='*',outSR=4326)
        data=f.json(name+'.geojson',f'{CPW}/{layer}/query?'+urllib.parse.urlencode(q),provider='CPW',crs='EPSG:4326',acquisition_date='unknown; source feature attributes retained',license='CPW as-is terms in cpw_item.json',resolution='agency range polygons, not cell-scale occupancy')
        if data.get('exceededTransferLimit'):raise ValueError('CPW query truncated')
    # Native source about 30 m; fixed year, nearest sampling, no cartographic RGB.
    for component in ['tree','shrub','herb']:
        stem=f'mrlc_{component}_westernconus_year_data'
        url=f'https://dmsdata.cr.usgs.gov/geoserver/{stem}/wcs'
        common=dict(service='WCS',version='1.0.0')
        f.get(component+'_capabilities.xml',url+'?'+urllib.parse.urlencode(dict(common,request='GetCapabilities')),provider='USGS EROS')
        coverage=f'{stem}:{component}_westernconus_year_data'
        f.get(component+'_description.xml',url+'?'+urllib.parse.urlencode(dict(common,request='DescribeCoverage',coverage=coverage)),provider='USGS EROS')
        q=dict(common,request='GetCoverage',coverage=coverage,crs='EPSG:32613',response_crs='EPSG:32613',bbox=','.join(map(str,bounds)),resx=30,resy=30,format='GeoTIFF',time=f'{c["vegetation_year"]}-01-01T00:00:00Z',interpolation='nearest neighbor')
        p=f.get(component+'.tif',url+'?'+urllib.parse.urlencode(q),provider='USGS EROS RCMAP',year=c['vegetation_year'],acquisition_date='annual Landsat composite; exact acquisition dates mixed/unknown',resolution_m=30,units='percent areal cover, not optical transmission',vertical_reference='not applicable',license='USGS public-domain; WCS access constraints NONE',crs='EPSG:32613 requested; source EPSG:5070')
        raster=gdal.Open(str(p))
        if raster is None or raster.RasterCount!=1:raise ValueError('WCS did not return single-band science raster')
    # Query fine terrain availability, but do not download unselected lidar tiles.
    transform=osr.CoordinateTransformation(srs(b['epsg']),srs(4326))
    ll=[transform.TransformPoint(x,y) for x in [bounds[0],bounds[2]] for y in [bounds[1],bounds[3]]]
    bbox=[min(p[0] for p in ll),min(p[1] for p in ll),max(p[0] for p in ll),max(p[1] for p in ll)]
    q=dict(datasets='Digital Elevation Model (DEM) 1 meter',bbox=','.join(map(str,bbox)),max=100)
    f.json('fine_dem_catalog.json','https://tnmaccess.nationalmap.gov/api/v1/products?'+urllib.parse.urlencode(q),provider='USGS TNM',purpose='availability inventory only; not all products selected')
    if c.get('fine_dem'):
        p=f.get('fine_dem.tif',c['fine_dem']['url'],provider='USGS 3DEP',resolution_m=1,acquisition_date='2019 project; exact days unknown',license='USGS public domain',purpose='two 400m exploratory viewsheds')
        if digest(p)!=c['fine_dem']['sha256']:raise ValueError('Fine DEM checksum differs from pinned experiment')
    if c.get('source_lock'):
        for name,checksum in json.loads(Path(c['source_lock']).read_text()).items():
            if digest(Path(c['inputs'])/name)!=checksum:raise ValueError('Live source changed from locked comparison; use retained inputs or register a new experiment')
    dump(Path(c['inputs'])/'acquisition.json',dict(new_bytes=f.used,bounds=bounds,year=c['vegetation_year']))
