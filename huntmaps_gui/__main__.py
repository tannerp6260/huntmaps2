"""Launch one localhost server and open the locally served frontend."""
import argparse
import fcntl
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from .catalog import ROOT,STATE

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=8765);ap.add_argument('--no-browser',action='store_true');a=ap.parse_args()
    os.chdir(ROOT);STATE.mkdir(exist_ok=True)
    lock=(STATE/'server.lock').open('w')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise SystemExit('HuntMaps GUI is already running. Open http://127.0.0.1:8765 or stop the existing server.')
    if not (ROOT/'gui/frontend/dist/index.html').exists():raise SystemExit('Build local assets first: npm ci --prefix gui/frontend && npm run build --prefix gui/frontend')
    import uvicorn
    url=f'http://127.0.0.1:{a.port}'
    print('HuntMaps2:',url,'— Ctrl+C stops the app and its active job.',flush=True)
    if not a.no_browser:
        def browser():
            for _ in range(100):
                try:
                    with socket.create_connection(('127.0.0.1',a.port),timeout=.2):break
                except OSError:time.sleep(.1)
            subprocess.run(['xdg-open',url],check=False)
        threading.Thread(target=browser,daemon=True).start()
    uvicorn.run('huntmaps_gui.server:create_app',factory=True,host='127.0.0.1',port=a.port,log_level='warning')
if __name__=='__main__':main()
