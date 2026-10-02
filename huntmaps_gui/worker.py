"""Out-of-handler subprocess adapter for the unchanged owner CLI."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from .catalog import ROOT, STATE, read
from .jobs import write
from .config import WORKSPACE


def run(args):
    return subprocess.run(
        [sys.executable, "-u", "-m", "glassing.owner", *args], cwd=WORKSPACE
    ).returncode


def plan_digest(plan):
    return hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["prepare", "run"])
    ap.add_argument("plan")
    ap.add_argument("--download", action="store_true")
    a = ap.parse_args()
    path = STATE / "plans" / (a.plan + ".json")
    p = read(path)
    args = [
        "--area",
        p["area"],
        "--name",
        p["name"],
        "--polygon",
        p["polygon"],
        "--max-download-mb",
        str(p["max_download_mb"]),
    ]
    root = WORKSPACE / "results" / p["name"]
    if (root / "manifest.json").exists():
        raise ValueError("Completed run preserved; choose a new run name")
    print("STAGE Checking area and validated sources", flush=True)
    code = run(["prepare", *args, "--source-config", p["config"]])
    acquisition = read(root / "download_plan.json")
    original_acquisition = acquisition
    if acquisition is not None and p.get("include_network"):
        from .scouting_network import network_plan

        if not p.get("network_plan"):
            from shapely.geometry import shape

            boundary = read(root / "observer.geojson")
            if boundary["type"] == "FeatureCollection":
                from shapely.ops import unary_union

                area = unary_union([shape(f["geometry"]) for f in boundary["features"]])
            else:
                area = shape(boundary.get("geometry", boundary))
            p["network_plan"] = network_plan(list(area.bounds), p["max_download_mb"])[
                "id"
            ]
        net = read(STATE / "network-plans" / (p["network_plan"] + ".json"))
        if a.action == "prepare" and not net.get("cached_network_ids"):
            from .scouting_network import covering_networks

            if covering_networks(net["bounds"]):
                p["network_plan"] = network_plan(net["bounds"], p["max_download_mb"])[
                    "id"
                ]
                net = read(STATE / "network-plans" / (p["network_plan"] + ".json"))
        cached = read(STATE / "network-plans" / (p["network_plan"] + "-result.json"))
        if cached is None and net.get("cached_network_ids"):
            from .scouting_network import acquire

            acquire(p["network_plan"], 0)
            cached = read(
                STATE / "network-plans" / (p["network_plan"] + "-result.json")
            )
        reservation = net["estimated_bytes"]
        acquisition = dict(
            acquisition,
            estimated_bytes=acquisition["estimated_bytes"] + reservation,
            items=acquisition.get("items", [])
            + [dict(key="USFS roads/trails", estimated_bytes=reservation)],
            network_plan=net,
        )
    if acquisition is None:
        return code or 2
    if a.action == "prepare":
        p.update(
            acquisition=acquisition,
            acquisition_hash=plan_digest(acquisition),
            prepared=True,
            required_data=(
                (root / "DATA_REQUIRED.md").read_text()
                if (root / "DATA_REQUIRED.md").exists()
                else ""
            ),
            sources_ready=code == 0
            and (not p.get("include_network") or cached is not None),
        )
        write(path, p)
        print(
            "STAGE Acquisition plan ready for review; no bulk downloads performed",
            flush=True,
        )
        return 0
    if not p.get("prepared"):
        raise ValueError("Prepare and review the acquisition plan first")
    if plan_digest(acquisition) != p["acquisition_hash"]:
        raise ValueError(
            "Acquisition plan changed. Prepare again and review the new estimate before starting."
        )
    if acquisition["estimated_bytes"] > p["max_download_mb"] * 1000000:
        raise ValueError(
            "Combined reviewed acquisition exceeds the shared download cap"
        )
    if p.get("include_network") and cached is None:
        if not a.download:
            raise ValueError("Explicitly allow this plan’s network bulk downloads")
        from .scouting_network import acquire

        acquire(
            p["network_plan"],
            p["max_download_mb"] * 1000000 - original_acquisition["estimated_bytes"],
        )
        cached = read(STATE / "network-plans" / (p["network_plan"] + "-result.json"))
    if p.get("include_network"):
        args[args.index("--max-download-mb") + 1] = str(
            max(
                1,
                int(
                    (p["max_download_mb"] * 1000000 - cached["downloaded_bytes"])
                    // 1000000
                ),
            )
        )
    if p.get("access_sampling"):
        from .scouting_network import sampling_networks

        sampling, sampling_sources = sampling_networks(
            p["access_sampling"], cached if p.get("include_network") else None
        )
        if code != 0:
            if not a.download:
                raise ValueError("Sampling eligibility requires approved DEM sources")
            if run(["prepare", *args, "--download"]) != 0:
                raise ValueError("Could not prepare approved DEM for observer sampling")
        from .scouting_filters import sampling_exclusion

        c = read(root / "scouting.json")
        if not p.get("sampling_applied"):
            import resource, signal

            previous_memory = resource.getrlimit(resource.RLIMIT_AS)
            previous_handler = signal.getsignal(signal.SIGALRM)

            def timed_out(signum, frame):
                raise ValueError(
                    "Observer eligibility exceeded 900 seconds; narrow the area/network"
                )

            try:
                resource.setrlimit(
                    resource.RLIMIT_AS,
                    (
                        (
                            min(1536 * 1024**2, previous_memory[0])
                            if previous_memory[0] > 0
                            else 1536 * 1024**2
                        ),
                        previous_memory[1],
                    ),
                )
                signal.signal(signal.SIGALRM, timed_out)
                signal.alarm(900)
                excluded = sampling_exclusion(
                    c,
                    sampling,
                    STATE / "plans" / (a.plan + "-observer-exclusion.geojson"),
                )
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, previous_handler)
                resource.setrlimit(resource.RLIMIT_AS, previous_memory)
            if excluded:
                c["observer_exclusions"] = c.get("observer_exclusions", []) + [excluded]
            write(root / "scouting.json", c)
            write(
                root / "observer_sampling.json",
                dict(
                    settings=sampling,
                    sources=sampling_sources,
                    notice="Observer eligibility only; original polygon, targets and obstruction terrain preserved",
                ),
            )
            p["sampling_applied"] = True
            write(path, p)
    if not a.download and code != 0:
        raise ValueError(
            "Sources missing. Review the plan and explicitly enable downloads, or provide supported checked sources."
        )
    print(
        "STAGE "
        + (
            "Downloading and validating approved sources, then baseline analysis"
            if a.download
            else "Baseline analysis with validated cached sources"
        ),
        flush=True,
    )
    code = run(["run", *args] + (["--download"] if a.download else []))
    if code == 0:
        print("STAGE Baseline report and GIS exports complete", flush=True)
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print("GUI JOB:", e, flush=True)
        sys.exit(2)
