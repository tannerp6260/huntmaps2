"""Single active job worker with inherited desktop resource limits."""

import argparse
import resource
import signal
import sys
import time
from .config import STATE
from .storage import read_json, write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["approach", "network"])
    parser.add_argument("ident")
    parser.add_argument("--remaining-bytes", type=int, default=0)
    a = parser.parse_args()
    started = time.monotonic()
    resource.setrlimit(resource.RLIMIT_AS, (1536 * 1024**2, 1536 * 1024**2))

    def expired(signum, frame):
        raise ValueError(
            "Scouting job exceeded 900 seconds; narrow the travel area/network"
        )

    signal.signal(signal.SIGALRM, expired)
    signal.alarm(900)
    if a.action == "approach":
        from .approach_service import compute

        compute(a.ident)
    else:
        from .scouting_network import acquire

        print("STAGE Acquiring reviewed bounded USFS network", flush=True)
        acquire(a.ident, a.remaining_bytes)
    write(
        STATE / "scouting-metrics" / f"{a.ident}.json",
        dict(
            runtime_s=time.monotonic() - started,
            peak_rss_kb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        ),
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        diagnostic = (
            "Scouting memory limit exceeded; narrow the travel area/network"
            if isinstance(error, MemoryError)
            else str(error)
        )
        print("GUI JOB:", diagnostic, flush=True)
        sys.exit(2)
