"""Bounded driver around the unchanged transfer implementation for normal GUI runs."""

import argparse
import resource
import signal
import time
from pathlib import Path
from glassing import transfer
from . import search


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    c = transfer.read(args.config)
    root = transfer.work(c)
    if not c.get("normal_scouting") or not c.get("search"):
        raise ValueError("Expanded search requires a normal GUI run")
    search.validate(c)
    search.guard_checkpoint(root)
    transfer.verify(c)
    resource.setrlimit(
        resource.RLIMIT_AS, (c["memory_mb"] * 1024**2, resource.RLIM_INFINITY)
    )

    def expired(*args):
        raise ValueError(
            "Search batch exceeded processing time limit; checkpoint retained for recovery"
        )

    signal.signal(signal.SIGALRM, expired)
    started = time.monotonic()
    for stage in ["prepare", "candidates", "score", "access", "packet"]:
        signal.alarm(c["runtime_s"])
        print("STAGE " + stage, flush=True)
        if stage == "prepare":
            search.prepare(c)
        else:
            transfer.guard_prepared(c)
            transfer.guard_products(root)
            if stage == "candidates":
                search.candidates(c)
            elif stage == "score":
                search.score(c)
            elif stage == "access":
                from glassing.transfer_access import run

                run(c)
            else:
                if any(
                    p["group"] == "automated"
                    for p in transfer.read(root / "scores.json")
                ):
                    from glassing.transfer_packet import run
                else:
                    from .manual_packet import run

                run(c)
        signal.alarm(0)
        names = {
            "prepare": [
                "manual_import.json",
                "prepared.json",
                "core_config.json",
                "input_identity.json",
            ]
            + [
                k + ".tif"
                for k in [
                    "dem",
                    "target",
                    "observer",
                    "tree",
                    "shrub",
                    "herb",
                    "summer",
                    "winter",
                    "vegetation_unknown",
                    "actionability",
                ]
            ],
            "candidates": ["pool.json", "sampling_summary.json"],
            "access": ["approaches.json"],
            "score": [
                "scores.json",
                "patches.json",
                "refinement.json",
                "leading.json",
                "overlap.json",
                "recommendations.json",
            ],
        }.get(stage, [])
        products = {} if stage == "prepare" else transfer.read(root / "products.json")
        for name in names:
            products[name] = transfer.digest(root / name)
        transfer.dump(root / "products.json", products)
    size = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
    if size > c["disk_bytes"]:
        raise ValueError("Output disk budget exceeded; results retained")
    metrics = dict(
        wall_s=time.monotonic() - started,
        peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        output_bytes=size,
    )
    transfer.dump(root / "search-metrics.json", metrics)
    import json

    with (root / "execution.jsonl").open("a") as handle:
        handle.write(
            json.dumps(dict(metrics, stage="all", search_version=search.VERSION)) + "\n"
        )
    transfer.dump(
        root / "implementation.json",
        {
            str(p): transfer.digest(p)
            for p in [
                Path(args.config),
                Path(c["model_lock"]),
                Path(__file__),
                Path(search.__file__),
                Path(search.target_filters.__file__),
                Path(__file__).with_name("manual_packet.py"),
            ]
            + list(Path("glassing").glob("transfer*.py"))
        },
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, MemoryError) as error:
        import sys

        print(
            "GUI JOB:",
            (
                str(error)
                if not isinstance(error, MemoryError)
                else "Search memory limit reached; checkpoint retained for recovery"
            ),
            flush=True,
        )
        sys.exit(2)
