"""Run with .venv/bin/python -m glassing STAGE --config configs/gmu54.json."""
import argparse
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import sys
import time

# Bound native thread pools before importing NumPy/GDAL.
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
os.environ.setdefault('GDAL_CACHEMAX','128')


def size(path):
    return sum(p.stat().st_size for p in Path(path).rglob('*') if p.is_file()) if Path(path).exists() else 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['acquire','prepare','candidates','visibility','inspect','export','all'])
    parser.add_argument('--config',required=True)
    args=parser.parse_args(); c=json.loads(Path(args.config).read_text())
    if not 1<=c['candidate_count']<=200 or not 0<c['resolution_m'] or not c['radii_m'] or min(c['radii_m'])<=0:
        raise ValueError('Invalid count/resolution/radii; trial cap is 200 candidates')
    if c['baseline_radius_m'] not in c['radii_m'] or max(c['radii_m'])>3000:
        raise ValueError('Baseline must be evaluated; distance-band schema supports <=3000 m')
    if c['eye_m']<0 or c['target_m']<0 or not 0<=c['curvature']<=1:
        raise ValueError('Invalid height/curvature')
    root=Path(c['work']);root.mkdir(parents=True,exist_ok=True)
    limit=int(c['memory_mb']*1024**2)
    resource.setrlimit(resource.RLIMIT_AS,(limit,limit))
    def timeout(signum,frame):raise TimeoutError('Configured command runtime budget exceeded')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(c['runtime_s'])
    from . import core
    from .acquire import acquire
    from osgeo import gdal
    import numpy, scipy
    actions={'acquire':acquire,'prepare':core.prepare,'candidates':core.generate,'visibility':core.compute,'inspect':core.inspect,'export':core.export}
    stages=['prepare','candidates','visibility','inspect','export'] if args.stage=='all' else [args.stage]
    for stage in stages:
        usage=size(root)+size(c.get('inputs','data/nonexistent'))
        if usage>c['disk_bytes'] or shutil.disk_usage(root).free<min(c['disk_bytes'],1024**3):
            raise ValueError('Disk budget/free-space guard failed')
        start=time.monotonic(); status='ok'
        try:actions[stage](c)
        except Exception as exc:
            status=f'{type(exc).__name__}: {exc}';raise
        finally:
            record=dict(stage=stage,status=status,wall_s=time.monotonic()-start,
                peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                work_bytes=size(root),input_bytes=size(c.get('inputs','data/nonexistent')),
                versions=dict(python=sys.version.split()[0],gdal=gdal.__version__,numpy=numpy.__version__,scipy=scipy.__version__))
            with open(root/'metrics.jsonl','a') as f:f.write(json.dumps(record)+'\n')
            print(json.dumps(record),flush=True)
        if size(root)+size(c.get('inputs','data/nonexistent'))>c['disk_bytes']:
            raise ValueError('Disk budget exceeded after stage; stop before additional work')


if __name__=='__main__':main()
