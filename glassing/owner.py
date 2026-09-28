"""Owner-facing scouting entry point; diagnostics need only standard Python."""
import argparse, hashlib, importlib, json, os, shutil, subprocess, sys, time
os.environ.setdefault("MPLCONFIGDIR", "/tmp/glassing-owner-mpl")
from pathlib import Path

def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def versions():
    return dict(python=sys.version.split()[0],**{n:getattr(importlib.import_module(n),'__version__','unknown') for n in ['numpy','scipy','shapely','matplotlib','osgeo.gdal']})
def descriptors(value):
    if isinstance(value,dict):
        if 'path' in value and 'sha256' in value:yield value
        for v in value.values():yield from descriptors(v)
    elif isinstance(value,list):
        for v in value:yield from descriptors(v)
def doctor():
    failures=[]
    print('Python:',sys.version.split()[0],sys.executable,flush=True)
    for name in ['numpy','scipy','shapely','matplotlib','osgeo.gdal']:
        try:
            m=importlib.import_module(name);print(name,getattr(m,'__version__','installed'))
            if name=='osgeo.gdal':assert hasattr(m,'ViewshedGenerate') and m.GetDriverByName('GPKG') and m.GetDriverByName('GTiff')
            if name=='shapely':assert hasattr(m,'make_valid')
        except Exception as e:failures.append(name);print('MISSING/UNSUITABLE:',name,str(e))
    print('Historical archives: optional. Area: supply --area inputs/my-area.geojson (or KML/KMZ).')
    areas=[str(p) for p in Path('inputs').rglob('*') if p.suffix.lower() in ['.geojson','.kml','.kmz']]
    print('Available area exports (selection required):', ', '.join(areas) if areas else 'none found in inputs/')
    print('Free disk GiB:',round(shutil.disk_usage('.').free/2**30,1))
    if failures:print('Setup instructions: START_HERE.md; no system Python changes required.')
    return not failures

def main():
    ap=argparse.ArgumentParser(description='Provisional scouting from your observer-search polygon. Targets extend beyond it.')
    sub=ap.add_subparsers(dest='command')
    sub.add_parser('doctor',help='check environment and input readiness')
    for cmd in ['run','prepare']:
        p=sub.add_parser(cmd,help='analyze area' if cmd=='run' else 'import area and prepare acquisition/configuration')
        p.add_argument('--area',required=True);p.add_argument('--manual',help='optional GPX/GeoJSON/CSV waypoints');p.add_argument('--polygon',help='polygon number, or explicit all')
        p.add_argument('--name',default='my-area');p.add_argument('--source-config',help='existing transfer-compatible configuration; paths relative to project root')
        p.add_argument('--download',action='store_true',help='execute the printed bounded data plan');p.add_argument('--max-download-mb',type=int,default=600)
    p=sub.add_parser('verify');p.add_argument('--name',default='my-area')
    sub.add_parser('verify-history',help='optional archival experiment verification')
    a=ap.parse_args()
    if a.command in [None,'doctor']:
        ok=doctor()
        if a.command is None:ap.print_help()
        return 0 if ok else 2
    if a.command=='verify-history':
        from .transfer_legacy import verify,read
        try:print('Historical files verified:',verify(read('configs/transfer.template.json')))
        except FileNotFoundError as e:raise ValueError('Historical archive unavailable; normal scouting does not need it: '+str(e))
        return 0
    if not a.name.replace('-','').replace('_','').isalnum():raise ValueError('--name must contain letters, digits, hyphens or underscores')
    root=Path('results')/a.name
    if a.command=='verify':
        m=json.loads((root/'manifest.json').read_text())
        for p,h in m.items():
            if not Path(p).is_file() or sha(p)!=h:raise ValueError('Current run input/output changed or missing: '+p)
        if json.loads((root/'environment.json').read_text())!=versions():raise ValueError('Current runtime changed; use a new run name to reproduce with this environment')
        from .transfer import verify,guard_prepared,guard_products,read
        c=read(root/'scouting.json');verify(c);guard_prepared(c);guard_products(Path(c['work']))
        print('Current run verified; historical archives not required.');return 0
    if not doctor():return 2
    from .owner_area import convert,choices
    from .transfer import intake,read
    area=Path(a.area).resolve()
    if not area.is_file():raise ValueError('Supply your observer-search polygon at '+str(area))
    if root.exists():
        if (root/'manifest.json').exists():raise ValueError('Completed results are preserved. Choose a new --name.')
        config=root/'scouting.json'
        if not config.exists():raise ValueError('Unowned/incomplete folder; choose a new --name: '+str(root))
        c=read(config)
        original=root/'originals'/area.name
        if not original.exists() or sha(original)!=sha(area):raise ValueError('Area changed; use a new --name')
        if a.manual and (not c.get('manual_points') or sha(a.manual)!=sha(c['manual_points'])):raise ValueError('Manual inputs changed; use a new --name')
        c['download_bytes']=a.max_download_mb*1000000
    else:
        # Validate selection before reserving the results folder.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            geom=convert(area,Path(tmp)/'observer.geojson',a.polygon)
        root.mkdir(parents=True);(root/'originals').mkdir()
        original=root/'originals'/area.name;shutil.copy2(area,original)
        convert(original,root/'observer.geojson',a.polygon)
        c=read(a.source_config or 'configs/transfer.template.json')
        lon,lat=geom.centroid.coords[0]
        if not a.source_config:c['epsg']=(32600 if lat>=0 else 32700)+min(60,int((lon+180)//6)+1)
        c.update(normal_scouting=True,work=str(root/'analysis'),observer_polygon=str(root/'observer.geojson'),manual_points=None,download_bytes=a.max_download_mb*1000000)
        if a.manual:
            mp=Path(a.manual);dest=root/'originals'/('manual'+mp.suffix);shutil.copy2(mp,dest);c['manual_points']=str(dest)
    c['normal_scouting']=True;c['work']=str(root/'analysis')
    write(root/'scouting.json',c);inp=intake(c)
    from .owner_data import provision
    ready=provision(c,inp,root,a.download);write(root/'scouting.json',c)
    if not ready:print('DATA NOT READY. See',root/'DATA_REQUIRED.md');return 2
    if a.command=='prepare':
        print('Sources ready. Repeat with run instead of prepare; configuration:',root/'scouting.json');return 0
    start=time.monotonic()
    subprocess.run([sys.executable,'-m','glassing.transfer','all','--config',str(root/'scouting.json')],check=True)
    from .owner_results import handoff
    handoff(c,root)
    write(root/'environment.json',versions())
    write(root/'timing.json',dict(owner_analysis_wall_s=time.monotonic()-start,acquisition=read(root/'acquisition.json')))
    paths=[p for p in root.rglob('*') if p.is_file() and p.name!='manifest.json']+list(Path('glassing').glob('*.py'))+[Path(c['model_lock'])]
    from .transfer import source
    for spec in descriptors(c):paths.append(Path(source(spec)))
    paths.extend(p for p in [Path('scout'),Path('environment.scout.yml')] if p.is_file())
    write(root/'manifest.json',{str(p):sha(p) for p in paths})
    print('READY:',root/'REPORT.md','|',root/'overview.png','| GPX/KML and review_packet.pdf in',root)
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,FileNotFoundError,subprocess.CalledProcessError) as e:print('SCOUT:',e,file=sys.stderr);sys.exit(2)
