"""Bounded corrective validation; preserves all prior controls."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
os.environ.setdefault('GDAL_CACHEMAX','128')
import argparse,csv,json,time,resource,signal
from pathlib import Path
import numpy as np
from . import compare,comparison_models as model,attention
from .acquire import dump,digest


def frozen(c):
    entries=json.loads(Path(c['frozen_control']).read_text())
    bad=[p for p,h in entries.items() if not Path(p).exists() or digest(Path(p))!=h]
    if bad:raise ValueError('Frozen control changed: '+str(bad))
    return len(entries)


def csvwrite(path,rows):
    with open(path,'w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def run_attention(c):
    cc=json.loads(Path(c['comparison_config']).read_text());b,base,ds,a,gt,masks=compare.load(cc)
    layers=compare.read_layers(cc);root=Path(c['work']);root.mkdir(parents=True,exist_ok=True)
    points=json.loads((Path(cc['work'])/'pool.json').read_text());grad=np.gradient(a.astype('float64'),gt[1]);grad[0]*=-1
    rows=[];patch_records={};component_rows=[]
    for p in points:
        v=compare.components(cc,b,base,ds,a,gt,masks,layers,p,grad,stress=False)
        summer=model.habitat(v['summer'],v['shrub'],v['herb'],'summer',cc['habitat_floor'])
        winter=model.habitat(v['winter'],v['shrub'],v['herb'],'winter',cc['habitat_floor'])
        dist=model.distance_response(v['d'],cc)
        light=model.sunlight(v['gx'],v['gy'],v['dx'],v['dy'],v['dz'],cc['light'],cc)
        other=v['search']*dist*v['perspective']*light
        component_rows.append(dict(id=p['id'],x=p['x'],y=p['y'],raw_km2=v['total'],summer_habitat_mean=float(summer.mean()),winter_habitat_mean=float(winter.mean()),searchability_mean=float(v['search'].mean()),distance_mean=float(dist.mean()),perspective_mean=float(v['perspective'].mean()),light_mean=float(light.mean()),unknown_access=True))
        for mix in c['winter_mixtures']:
            reward=((1-mix)*summer+mix*winter)*other
            pats=attention.patches(v['dx'],v['dy'],reward,gt[1]**2/1e6,c['patch_width_deg'],c['band_width_m'],b['baseline_radius_m'])
            full=sum(t['reward'] for t in pats)
            for budget in c['budgets_minutes']:
                opt=attention.select(pats,budget,c['scan_km2_per_minute'],c['patch_overhead_minutes'],c['time_quantum_minutes'])
                for name,val in [('selective',opt['score']),('uniform',attention.uniform_score(full,v['total'],budget,c['scan_km2_per_minute'])),('none',full)]:
                    rows.append(dict(id=p['id'],scenario=f'{name}_winter{mix:g}_minutes{budget}',score=val,raw_km2=v['total'],winter_mix=mix,budget_minutes=budget,strategy=name))
                if mix==.5 and budget==30:patch_records[p['id']]=dict(patches=pats,selection=opt)
            if mix==.5:
                for width,rate,overhead,label in [(w,.02,.5,f'width{w}') for w in [20,45]]+[(30,r,.5,f'rate{r}') for r in [.01,.04]]+[(30,.02,o,f'overhead{o}') for o in [0,1]]:
                    ps=attention.patches(v['dx'],v['dy'],reward,gt[1]**2/1e6,width,c['band_width_m'],b['baseline_radius_m'])
                    opt=attention.select(ps,30,rate,overhead,c['time_quantum_minutes'])
                    rows.append(dict(id=p['id'],scenario=label,score=opt['score'],raw_km2=v['total'],winter_mix=.5,budget_minutes=30,strategy='selective_sensitivity'))
    csvwrite(root/'attention_scores.csv',rows);csvwrite(root/'components.csv',component_rows)
    dump(root/'patches.json',patch_records);dump(root/'paradox.json',attention.paradox())
    scores={}
    for r in rows:scores.setdefault(r['scenario'],{})[r['id']]=r['score']
    nominal=scores['selective_winter0.5_minutes30'];order=lambda d:sorted(d,key=lambda i:(-d[i],i))[:10]
    old=list(csv.DictReader(open(Path(cc['work'])/'component_scores.csv')))
    oldscores={r['id']:float(r['score']) for r in old if r['scenario']=='M3_glass'}
    raw={r['id']:r['raw_km2'] for r in component_rows}
    metrics={k:dict(compare.rank_metrics(nominal,v),top10=order(v)) for k,v in scores.items()}
    # Control reconstruction is checked at exactly the previous summer/30min settings.
    differences=[abs(scores['uniform_winter0_minutes30'][i]-oldscores[i]) for i in oldscores]
    if max(differences)>1e-10:raise ValueError('Uniform control no longer matches frozen scores')
    review=list(dict.fromkeys(['C0064','C0090','C0068','C0025','C0049']+order(nominal)[:2]))
    dump(root/'attention_summary.json',dict(candidate_count=len(points),nominal_top10=order(nominal),review_ids=review,old_M3=compare.rank_metrics(nominal,oldscores),raw=compare.rank_metrics(nominal,raw),control_max_absolute_difference=max(differences),scenarios=metrics,season_interpretation='Undated scenarios, not fall occupancy; summer polygon covers all targets, winter only 21.35%; background retained.'))
    print('Attention:',len(points),'candidates;',len(scores),'scenarios; top:',order(nominal),flush=True)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['acquire','attention','geometry','access','imagery','packet','all','verify']);ap.add_argument('--config',default='configs/correction.json');args=ap.parse_args()
    c=json.loads(Path(args.config).read_text());root=Path(c['work']);root.mkdir(parents=True,exist_ok=True)
    signal.alarm(c['runtime_s']);resource.setrlimit(resource.RLIMIT_AS,(c['memory_mb']*1024**2,resource.RLIM_INFINITY))
    start=time.monotonic();n=frozen(c)
    manifest_path=Path(c['inputs'])/'manifest.json'
    if manifest_path.exists():
        for name,meta in json.loads(manifest_path.read_text()).items():
            if digest(Path(c['inputs'])/name)!=meta['sha256']:raise ValueError('Correction input checksum changed: '+name)
    stages=['attention','geometry','access','packet'] if args.stage=='all' else [args.stage]
    for stage in stages:
        if stage=='acquire':
            from .correction_data import acquire
            acquire(c)
        elif stage=='attention':run_attention(c)
        elif stage=='geometry':
            from .correction_geometry import run
            run(c)
        elif stage=='access':
            from .correction_access import run
            run(c)
        elif stage=='imagery':
            from .correction_data import imagery
            imagery(c)
        elif stage=='packet':
            from .correction_packet import run
            run(c)
    frozen(c)
    identity_files=list(Path('glassing').glob('correction*.py'))+[Path('glassing/correct.py'),Path('glassing/attention.py'),Path(args.config),Path(c['protocol']),Path(c['frozen_control'])]
    if manifest_path.exists():identity_files.append(manifest_path)
    dump(root/'run_identity.json',dict(sha256={str(p):digest(p) for p in identity_files},config=c,python=__import__('sys').version,gdal=compare.gdal.__version__,numpy=np.__version__,frozen_control_count=n))
    size=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    if size>c['disk_bytes']:raise ValueError('Correction disk budget exceeded')
    evidence=dict(stage=args.stage,wall_s=time.monotonic()-start,peak_rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,generated_bytes=size,frozen_files_verified=n,command=' '.join(__import__('sys').argv))
    with open(root/'execution.jsonl','a') as f:f.write(json.dumps(evidence)+'\n')
    print(json.dumps(evidence),flush=True)

if __name__=='__main__':main()
