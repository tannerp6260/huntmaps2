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
            sources_ready=code == 0,
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
