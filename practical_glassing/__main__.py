"""Explicit bounded preparation or offline comparison, never automatic downloads."""

import argparse
from pathlib import Path
import json
import resource
import time

from trail_scout.storage import Paths
from trail_scout.sources import Pack

from .package import CommunityPackage, prepare
from .adapters import saved_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "status", "compare"))
    parser.add_argument("--source", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument(
        "--state", default=str(Path(__file__).resolve().parents[1] / ".trailscout")
    )
    parser.add_argument("--run", default="2")
    parser.add_argument("--out")
    parser.add_argument(
        "--policy", help="JSON planning assumptions; defaults frozen in protocol"
    )
    args = parser.parse_args()
    paths = Paths(Path(args.source), Path(args.state))
    started = time.perf_counter()
    progress = lambda *a: print(*a, flush=True)
    if args.command == "prepare":
        paths.space(100 * 1024**2)
        value = prepare(Pack(paths), paths.state / "community", progress)
        print(
            json.dumps(
                {k: value[k] for k in ("id", "source_received_bytes", "status")},
                indent=2,
            )
        )
    elif args.command == "status":
        value = CommunityPackage(paths.state / "community").spec
        print(json.dumps(value, indent=2))
    else:
        paths.space(350 * 1024**2)
        folder = (
            Path(args.out)
            if args.out
            else paths.state / "reviews" / (args.run + "-" + str(time.time_ns()))
        )
        if folder.exists() and any(folder.iterdir()):
            raise ValueError(
                "Choose a new comparison output folder; prior evidence is immutable"
            )
        if not folder.resolve().is_relative_to(paths.state):
            raise ValueError(
                "Comparison output must stay in its separate application state"
            )
        value = saved_run(
            paths,
            args.run,
            folder,
            json.loads(args.policy) if args.policy else None,
            progress,
        )
        print(
            json.dumps(
                dict(
                    report=str(folder / "review.html"),
                    points=len(value["rows"]),
                    v1_max_error=value["v1_reproduction_max_abs_m2"],
                )
            )
        )
    print(
        json.dumps(
            dict(
                seconds=time.perf_counter() - started,
                peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            )
        )
    )


if __name__ == "__main__":
    main()
