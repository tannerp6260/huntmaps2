"""Owner journeys in a clone without any historical archives or real data."""
import json,os,shutil,subprocess,sys,zipfile
from pathlib import Path
import unittest
import tempfile
from glassing.owner_area import convert

REPO=Path(__file__).resolve().parents[1]

class OwnerTests(unittest.TestCase):
 def test_polygon_selection_preserves_original(self):
    tmp_path=Path(tempfile.mkdtemp(prefix="scout-import-"))
    text='<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'+''.join('<Placemark><name>'+name+'</name><Polygon><outerBoundaryIs><LinearRing><coordinates>-108,38 -107.99,38 -107.99,38.01 -108,38.01 -108,38</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>' for name in ['one','two'])+'</Document></kml>'
    k=tmp_path/'area.kmz'
    with zipfile.ZipFile(k,'w') as z:z.writestr('doc.kml',text)
    original=k.read_bytes()
    with self.assertRaisesRegex(ValueError,'Multiple polygons'):convert(k,tmp_path/'out.json')
    convert(k,tmp_path/'out.json','2');assert k.read_bytes()==original
    assert json.loads((tmp_path/'out.json').read_text())['features'][0]['properties']['selected']==['two / polygon 1']

 def test_owner_journeys_without_archives(self):
    tmp_path=Path(tempfile.mkdtemp(prefix="scout-journey-"))
    shutil.copytree(REPO/'glassing',tmp_path/'glassing',ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(REPO/'configs',tmp_path/'configs')
    shutil.copy2(REPO/'scout',tmp_path/'scout')
    def run(*args,ok=True):
        p=subprocess.run(['./scout',*args],env=dict(os.environ,SCOUT_PYTHON=sys.executable),cwd=tmp_path,text=True,capture_output=True,timeout=180)
        if ok:assert p.returncode==0,p.stdout+'\n'+p.stderr
        else:assert p.returncode!=0
        return p
    subprocess.run([sys.executable,'-c',"from glassing.transfer_fixture import create; create('fixture.json','fixture')"],cwd=tmp_path,check=True)
    assert not (tmp_path/'runs').exists() and not (tmp_path/'docs').exists()
    run('doctor')
    absent=subprocess.run([sys.executable,'-S','-m','glassing.owner','doctor'],cwd=tmp_path,capture_output=True,text=True)
    assert absent.returncode==2 and 'START_HERE.md' in absent.stdout
    run('prepare','--area','fixture/observer.geojson','--source-config','fixture.json','--name','normal')
    run('run','--area','fixture/observer.geojson','--name','normal')
    run('verify','--name','normal')
    run('verify','--name','normal')
    normal=json.loads((tmp_path/'results/normal/analysis/pool.json').read_text())
    assert normal and all(p['group']=='automated' for p in normal)
    assert (tmp_path/'results/normal/overview.png').stat().st_size>1000
    assert 'synthetic_fixture' in (tmp_path/'results/normal/REPORT.md').read_text()
    run('run','--area','fixture/observer.geojson','--manual','fixture/manual.geojson','--source-config','fixture.json','--name','matched')
    matched=json.loads((tmp_path/'results/matched/analysis/pool.json').read_text())
    assert [(p['x'],p['y']) for p in normal]==[(p['x'],p['y']) for p in matched if p['group']=='automated']
    imported=json.loads((tmp_path/'results/matched/analysis/manual_import.json').read_text())
    originals=json.loads((tmp_path/'fixture/manual.geojson').read_text())['features']
    assert [(p['longitude'],p['latitude']) for p in imported]==[tuple(f['geometry']['coordinates']) for f in originals]
    p=run('verify-history',ok=False);assert 'Historical archive unavailable' in p.stderr
    (tmp_path/'results/normal/review.gpx').write_text('corruption')
    assert 'Current run input/output changed' in run('verify','--name','normal',ok=False).stderr
    assert not (tmp_path/'runs').exists()
    print('ISOLATED_RESULTS',tmp_path)

 def test_acquisition_plan_budget_and_corrupt_cache(self):
    from unittest.mock import patch
    from glassing.owner_data import provision,cached
    from glassing.transfer import read
    from glassing.acquire import dump,digest
    from glassing import core
    from glassing.acquire import srs
    import numpy as np
    tmp=Path(tempfile.mkdtemp(prefix='scout-data-'));c=read(REPO/'configs/transfer.template.json')
    c['download_bytes']=1;c['epsg']=32613
    inp={'acquisition_requests':{'terrain':{'bounds':[310000,4275000,310100,4275100]}}}
    catalog={'items':[{'boundingBox':{'minX':-109,'minY':37,'maxX':-102,'maxY':41},'downloadURL':'https://example.invalid/never-download.tif','sizeInBytes':400000000,'publicationDate':'2020'}]}
    import io
    with patch('glassing.owner_data.cached',return_value={}),patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(catalog).encode())),patch('glassing.owner_data.Fetcher') as fetch:
        assert not provision(c,inp,tmp,True)
        fetch.assert_not_called()
        assert 'exceeds' in (tmp/'DATA_REQUIRED.md').read_text()
        assert json.loads((tmp/'acquisition.json').read_text())['new_download_bytes']==0
    cache=tmp/'data'/'cache';cache.mkdir(parents=True)
    core.write_raster(cache/'tree.tif',np.ones((10,10),dtype='float32'),(310000,10,0,4275100,0,-10),srs(32613).ExportToWkt(),-9999)
    dump(cache/'manifest.json',{'tree.tif':{'sha256':digest(cache/'tree.tif'),'provider':'synthetic test','bytes':(cache/'tree.tif').stat().st_size}})
    c['data']['tree']=None
    old=Path.cwd()
    try:
        os.chdir(tmp)
        assert 'tree' in cached(c,inp)
        c['data']['tree']=None
        outside={'acquisition_requests':{'terrain':{'bounds':[320000,4275000,320100,4275100]}}}
        assert not cached(c,outside)
        m=json.loads((cache/'manifest.json').read_text());m['tree.tif']['sha256']='bad';dump(cache/'manifest.json',m)
        with self.assertRaisesRegex(ValueError,'Corrupt cached source'):cached(c,inp)
    finally:os.chdir(old)
