"""One process group at a time; durable job records, bounded logs and safe cancellation."""
import json
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from .catalog import ROOT,STATE,read

ACTIVE={'running','cancelling'}
BOOT_ID=__import__('pathlib').Path('/proc/sys/kernel/random/boot_id').read_text().strip()

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2));tmp.replace(path)

def start_ticks(pid):
    try:return (__import__('pathlib').Path(f'/proc/{pid}/stat').read_text()).rsplit(')',1)[1].split()[19]
    except OSError:return None

class Jobs:
    def __init__(self,state=STATE):
        self.folder=state/'jobs';self.folder.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.process=None;self.kill_threads=[]
        for p in self.folder.glob('*.json'):
            j=read(p)
            if j['status'] in ACTIVE:
                # A stale child may survive a server crash. Kill only its recorded process identity.
                if j.get('boot_id')==BOOT_ID and j.get('pid') and j.get('ticks') and start_ticks(j['pid'])==j['ticks']:
                    try:os.killpg(j['pid'],signal.SIGKILL)
                    except ProcessLookupError:pass
                j.update(status='interrupted',stage='Interrupted after app restart',finished=time.time(),error='The app stopped during this job. Partial files were retained; review the plan before resuming.');write(p,j)

    def list(self):
        result=[]
        for p in self.folder.glob('*.json'):
            j=read(p);j['elapsed_s']=round((j.get('finished') or time.time())-j['started'],1)
            log=self.folder/(j['id']+'.log')
            if log.exists():
                with log.open('rb') as f:f.seek(max(0,log.stat().st_size-64000));j['logs']=f.read().decode(errors='replace')
            else:j['logs']=''
            # Stage records are emitted by the actual wrapper or existing engine, never a percentage.
            stages=[line[6:] for line in j['logs'].splitlines() if line.startswith('STAGE ')]
            if stages and j['status']=='running':j['stage']=stages[-1]
            if j.get('name') and j['status']=='running' and j['kind']=='baseline':
                analysis=ROOT/'results'/j['name']/'analysis'
                def fresh(filename):
                    p=analysis/filename
                    return p.exists() and p.stat().st_mtime>=j['started']
                if fresh('dem.tif'):j['stage']='Prepared terrain and eligibility masks'
                if fresh('pool.json'):j['stage']='Candidate pool saved; evaluating visibility and inspection scores'
                masks=[p for p in (analysis/'additional_visibility').glob('*.tif') if p.stat().st_mtime>=j['started']]
                if masks:j['stage']=f'Evaluating visibility and inspection scores · {len(masks)} masks saved this job'
                if fresh('scores.json'):j['stage']='Scores saved; preparing access evidence and review exports'
                if fresh('approaches.json'):j['stage']='Access status saved; building review packet'
                if fresh('review_packet.pdf'):j['stage']='Analysis packet saved; creating owner handoff'
            if j.get('name') and j['status']=='running':
                ex=ROOT/'results'/j['name']/'analysis/execution.jsonl'
                if ex.exists():
                    lines=ex.read_text().splitlines()
                    if lines:
                        try:
                            event=json.loads(lines[-1]);j['engine_event']=event
                        except ValueError:pass
            result.append(j)
        return sorted(result,key=lambda j:j['started'],reverse=True)

    def start(self,command,kind,name=None,plan=None,cwd=ROOT):
        with self.lock:
            if any(j['status'] in ACTIVE for j in self.list()):raise ValueError('Another job is running. Wait or cancel it first.')
            ident=uuid.uuid4().hex
            j=dict(id=ident,kind=kind,name=name,plan=plan,status='running',stage='Starting subprocess',started=time.time(),command=command)
            log=(self.folder/(ident+'.log')).open('wb')
            env=dict(os.environ,PYTHONUNBUFFERED='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLCONFIGDIR='/tmp/huntmaps-gui-mpl')
            self.process=subprocess.Popen(command,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            proc=self.process;j.update(pid=proc.pid,ticks=start_ticks(proc.pid),boot_id=BOOT_ID);write(self.folder/(ident+'.json'),j)
            threading.Thread(target=self._wait,args=(ident,proc,log),daemon=True).start()
            return j

    def _wait(self,ident,proc,log):
        code=proc.wait();log.close()
        with self.lock:
            path=self.folder/(ident+'.json');j=read(path)
            if j['status']=='cancelling':
                try:os.killpg(j['pid'],signal.SIGKILL)
                except ProcessLookupError:pass
            status='cancelled' if j['status']=='cancelling' else ('complete' if code==0 else 'failed')
            j.update(status=status,exit_code=code,finished=time.time(),stage={'complete':'Finished','cancelled':'Cancelled; partial files retained','failed':'Failed; see details and log'}[status])
            if status=='failed':
                lines=(self.folder/(ident+'.log')).read_text(errors='replace').splitlines()
                diagnostics=[line for line in lines if line.startswith(('SCOUT:','GUI JOB:','ValueError:','FileNotFoundError:'))]
                j['error']=(diagnostics[-1]+' ' if diagnostics else 'Job failed. ')+'Review the acquisition plan and log below. Fix the named source, area or budget, then refresh the plan or use a new run name. Partial files were retained.'
            if status=='failed' and j['kind'].startswith('first-person'):
                j['error']=(diagnostics[-1]+' ' if diagnostics else 'First-person preparation failed. ')+'Review the source plan and preparation log in the first-person viewer. Valid bundles and partial source files were retained.'
            write(path,j)

    def cancel(self,ident):
        with self.lock:
            path=self.folder/(ident+'.json');j=read(path)
            if not j or j['status'] not in ACTIVE:raise ValueError('Job is not running')
            j['status']='cancelling';write(path,j)
            if start_ticks(j['pid'])==j['ticks']:
                try:os.killpg(j['pid'],signal.SIGTERM)
                except ProcessLookupError:pass
                thread=threading.Thread(target=self._kill,args=(j,),daemon=True);self.kill_threads.append(thread);thread.start()
            return j

    def _kill(self,j):
        time.sleep(2)
        with self.lock:
            current=read(self.folder/(j['id']+'.json'))
            if current['status'] not in ACTIVE:return
            try:os.killpg(j['pid'],signal.SIGKILL)
            except ProcessLookupError:pass

    def shutdown(self):
        for j in self.list():
            if j['status']=='running':self.cancel(j['id'])
        for thread in self.kill_threads:thread.join(timeout=3)
