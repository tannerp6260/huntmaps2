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

_last_error = None


def run(args):
    global _last_error
    _last_error = None
    with subprocess.Popen(
        [sys.executable, "-u", "-m", "huntmaps_gui.owner_worker", *args],
        cwd=WORKSPACE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    ) as process:
        for line in process.stdout:
            print(line, end="", flush=True)
            if line.startswith(
                ("SCOUT:", "GUI JOB:", "ValueError:", "FileNotFoundError:")
            ):
                _last_error = line.strip()[:4000]
        return process.wait()


def plan_digest(plan):
    return hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()


def approval_inventory(config, acquisition):
    """Source requests, independent of missing-file lists and cache bookkeeping."""

    def source(value):
        if isinstance(value, list):
            return [source(v) for v in value]
        if not isinstance(value, dict):
            return value
        if value.get("reuse_origin") or value.get("raw_source", {}).get("reuse_origin"):
            # Imported bytes and all original provenance belong to this review.
            # Existing remote-request approvals cannot authorize a local crop.
            return {"verified_local_source": value}
        if value.get("url"):
            return {
                k: value[k]
                for k in [
                    "url",
                    "required_bounds",
                    "request_padding_m",
                    "catalog_source_id",
                    "acquisition_date",
                ]
                if k in value
            }
        return {k: value[k] for k in ["path", "sha256"] if k in value}

    net = acquisition.get("network_plan", {})
    sources = {k: source(v) for k, v in config.get("data", {}).items()}
    for item in acquisition.get("items", []):
        if item.get("url") and item.get("key"):
            sources[item["key"]] = source(item)
    return dict(
        version=2,
        sources=sources,
        network={k: net[k] for k in ["bounds", "items", "provider"] if k in net},
    )


def refresh_source_display(plan, root):
    """Publish verified reuse after acquisition even if subsequent analysis fails."""
    from glassing.transfer import source

    config = read(root / "scouting.json", {})
    cached, size = [], 0
    for key, descriptor in config.get("data", {}).items():
        if key not in [
            "dem",
            "tree",
            "shrub",
            "herb",
            "summer",
            "winter",
        ] or not isinstance(descriptor, dict):
            continue
        try:
            checked = dict(descriptor)
            if checked.get("path") and not Path(checked["path"]).is_absolute():
                checked["path"] = str(WORKSPACE / checked["path"])
            path = Path(source(checked))
        except (ValueError, OSError, TypeError):
            continue
        cached.append(key)
        size += path.stat().st_size
        approved = plan.get("approval_inventory", {}).get("sources", {}).get(key)
        actual = approval_inventory({"data": {key: descriptor}}, {})["sources"][key]
        if approved == actual:
            plan.setdefault("approved_checksums", {}).setdefault(
                key, descriptor["sha256"]
            )
    display = dict(plan.get("acquisition", {}))
    items = []
    for item in display.get("items", []):
        descriptor = config.get("data", {}).get(item.get("key"))
        if item.get("key") in cached and descriptor.get("url") == item.get("url"):
            continue
        items.append(item)
    display.update(
        items=items,
        estimated_bytes=sum(i.get("estimated_bytes", 0) for i in items),
        already_cached_bytes=size,
        cached_keys=cached,
    )
    plan["acquisition"] = display
    network_ready = (
        not plan.get("include_network")
        or read(STATE / "network-plans" / (plan["network_plan"] + "-result.json"))
        is not None
    )
    plan["sources_ready"] = (
        all(
            key in cached
            for key in ["dem", "tree", "shrub", "herb", "summer", "winter"]
        )
        and network_ready
    )
    return plan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["prepare", "run"])
    ap.add_argument("plan")
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--review-signature")
    a = ap.parse_args()
    path = STATE / "plans" / (a.plan + ".json")
    p = read(path)
    if a.review_signature:
        from .downloads import baseline_review_signature

        if not p.get("prepared") or baseline_review_signature(p) != a.review_signature:
            raise ValueError(
                "Source plan or allowance changed; review and approve again"
            )
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
    current_config = read(root / "scouting.json", {})
    cached_keys = [
        key
        for key in ["dem", "tree", "shrub", "herb", "summer", "winter"]
        if isinstance(current_config.get("data", {}).get(key), dict)
        and current_config["data"][key].get("path")
    ]
    cached_bytes = 0
    for key in cached_keys:
        descriptor = current_config.get("data", {}).get(key)
        if isinstance(descriptor, dict) and descriptor.get("path"):
            source = Path(descriptor["path"])
            if not source.is_absolute():
                source = WORKSPACE / source
            if source.is_file():
                cached_bytes += source.stat().st_size
    acquisition = dict(
        acquisition,
        already_cached_bytes=cached_bytes,
        cached_keys=cached_keys,
        reused_sources=[
            dict(
                key=key,
                provider=v.get("provider"),
                acquisition_date=v.get("acquisition_date"),
                retrieved_utc=v.get("retrieved_utc"),
                url=v.get("url"),
                sha256=v.get("sha256"),
            )
            for key, v in current_config.get("data", {}).items()
            if isinstance(v, dict)
            and (v.get("reuse_origin") or v.get("raw_source", {}).get("reuse_origin"))
        ],
    )
    inventory = approval_inventory(current_config, acquisition)
    checksums = {
        k: v["sha256"]
        for k, v in current_config.get("data", {}).items()
        if isinstance(v, dict) and v.get("sha256")
    }
    if (
        a.action == "prepare"
        and p.get("estimate_first")
        and not p.get("allowance_reviewed")
    ):
        from .downloads import suggested_mb

        p.update(
            max_download_mb=suggested_mb(acquisition["estimated_bytes"]),
            allowance_reviewed=True,
        )
        write(path, p)
        return subprocess.run(
            [sys.executable, "-u", "-m", "huntmaps_gui.worker", "prepare", a.plan],
            cwd=WORKSPACE,
        ).returncode
    if a.action == "prepare":
        if p.get("acquisition_hash") and p.get("approval_version") != 2:
            p["approval_migrated"] = True
            p["recovery_notice"] = (
                "Legacy approval refreshed. Verified downloads are retained; interrupted transfer bytes from older jobs may be unknown."
            )
        p.update(
            acquisition=acquisition,
            acquisition_hash=plan_digest(acquisition),
            approval_inventory=inventory,
            approval_version=2,
            approved_checksums=checksums,
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
    if p.get("approval_version") != 2:
        raise ValueError(
            "Legacy approval requires one refresh and review; downloaded files are retained"
        )
    if inventory != p.get("approval_inventory") or any(
        checksums.get(k) != v for k, v in p.get("approved_checksums", {}).items()
    ):
        raise ValueError(
            "Acquisition plan changed. Prepare again and review the new estimate before starting."
        )
    # Refresh display accounting without changing approval of identical requests.
    p.update(acquisition=acquisition)
    write(path, p)
    if acquisition["estimated_bytes"] > p["max_download_mb"] * 1000000:
        raise ValueError(
            "Combined reviewed acquisition exceeds the shared download cap"
        )
    ledger = STATE / "plans" / (a.plan + "-transfer.json")
    accounting = read(ledger)
    if accounting is None:
        # Legacy completed source transfers have manifests; unknown interrupted
        # bytes cannot be reconstructed and are disclosed during migration.
        entries = read(root / "downloads" / "manifest.json", {})
        accounting = dict(
            received_bytes=sum(v.get("bytes", 0) for v in entries.values()),
            legacy_partial_bytes_unknown=p.get("approval_migrated", False),
        )
        if p.get("include_network") and cached:
            accounting["received_bytes"] += cached.get("downloaded_bytes", 0)
    accounting["ceiling_bytes"] = p["max_download_mb"] * 1000000
    write(ledger, accounting)
    if (
        accounting["received_bytes"] >= accounting["ceiling_bytes"]
        and acquisition["estimated_bytes"]
    ):
        raise ValueError(
            "Cumulative download allowance exhausted; review a larger allowance before retrying"
        )
    os.environ["HUNTMAPS_TRANSFER_LEDGER"] = str(ledger)
    from .downloads import check_space
    from .progress import start_download, emit

    check_space(WORKSPACE, 3 * acquisition["estimated_bytes"] + 2 * 1024**3)
    start_download(acquisition["estimated_bytes"])
    if p.get("include_network") and cached is None:
        if not a.download:
            raise ValueError("Explicitly allow this plan’s network bulk downloads")
        from .scouting_network import acquire

        acquire(
            p["network_plan"],
            max(
                0,
                accounting["ceiling_bytes"]
                - accounting["received_bytes"]
                - original_acquisition["estimated_bytes"],
            ),
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
            print(
                "STAGE Downloading and validating approved sources for observer sampling",
                flush=True,
            )
            if run(["prepare", *args, "--download"]) != 0:
                write(path, refresh_source_display(p, root))
                raise ValueError(
                    (_last_error.removeprefix("SCOUT: ") if _last_error else None)
                    or "Source preparation failed; inspect the current job log"
                )
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
    write(path, refresh_source_display(p, root))
    if code == 0:
        print("STAGE Baseline report and GIS exports complete", flush=True)
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print("GUI JOB:", e, flush=True)
        sys.exit(2)
