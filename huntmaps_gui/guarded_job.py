"""Monitor storage during GUI workers, including native processing and subprocesses."""

import os
import signal
import subprocess
import sys
import time
import tempfile
from .config import current
from .downloads import check_space


def main():
    if os.getpgrp() != os.getpid():
        raise ValueError("Storage monitor must run in its own job process group")
    paths = [current().workspace, current().state_dir, tempfile.gettempdir()]
    for p in paths:
        check_space(p)
    proc = subprocess.Popen(sys.argv[1:])
    while proc.poll() is None:
        try:
            for p in paths:
                check_space(p, 64 * 1024**2)
        except ValueError as e:
            print("GUI JOB: " + str(e), flush=True)
            os.killpg(os.getpgrp(), signal.SIGTERM)
            return 2
        time.sleep(0.25)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
