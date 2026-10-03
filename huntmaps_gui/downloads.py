"""Reviewed transfer estimates and Ubuntu storage safeguards."""

import math
import shutil
import tempfile
from pathlib import Path

RESERVE = 20 * 1024**3


def suggested_mb(estimated_bytes, maximum=None):
    if (
        type(estimated_bytes) not in (int, float)
        or not math.isfinite(estimated_bytes)
        or estimated_bytes < 0
    ):
        raise ValueError("Download estimate must be finite and nonnegative")
    value = max(10, math.ceil(estimated_bytes * 1.2 / 10_000_000) * 10)
    return min(maximum, value) if maximum is not None else value


def existing_path(path):
    path = Path(path)
    while not path.exists():
        path = path.parent
    return path


def check_space(path, next_bytes=0):
    free = shutil.disk_usage(existing_path(path)).free
    if free < RESERVE + next_bytes:
        raise ValueError(
            "Insufficient storage: preserve 20 GiB free; partial files and prior results retained. Free space or reduce the area/source plan, then review again."
        )
    return free


def storage_estimate(paths, new_bytes=0, processing_bytes=0):
    volumes = {}
    for path in paths:
        p = existing_path(path)
        volumes.setdefault(
            p.stat().st_dev, dict(path=str(path), free_bytes=shutil.disk_usage(p).free)
        )
    # Three copies cover downloads, parallel range assembly and temporary source copies.
    required = max(0, new_bytes) * 3 + processing_bytes
    return dict(
        reserve_bytes=RESERVE,
        required_bytes=required,
        processing_estimate_uncertain=True,
        volumes=list(volumes.values()),
        blocked=any(v["free_bytes"] < RESERVE + required for v in volumes.values()),
    )


def time_estimate(new_bytes, providers=None):
    from .progress import recent_rate

    if new_bytes == 0:
        return dict(basis="cached", minimum_s=0, maximum_s=0)
    if new_bytes is None:
        return dict(basis="unknown", minimum_s=None, maximum_s=None)
    if isinstance(providers, dict):
        portions = providers
    else:
        names = providers or [None]
        portions = {p: new_bytes / len(names) for p in names}
    minimum = maximum = 0
    measured = assumed = False
    for provider, size in portions.items():
        rate = recent_rate(provider) if provider else None
        measured |= bool(rate)
        assumed |= not bool(rate)
        minimum += size / (rate * 1.5 if rate else 10_000_000)
        maximum += size / (rate * 0.5 if rate else 1_000_000)
    return dict(
        basis=(
            "mixed"
            if measured and assumed
            else "measured" if measured else "illustrative"
        ),
        minimum_s=minimum,
        maximum_s=maximum,
    )


def provider_estimates(items, size_key):
    from urllib.parse import urlparse

    result = {}
    for item in items:
        if item.get("cached"):
            continue
        provider = urlparse(item.get("url", "")).hostname
        result[provider] = result.get(provider, 0) + item.get(size_key, 0)
    return result or None


def review_info(paths, new_bytes, providers=None, processing_bytes=0):
    return dict(
        storage=storage_estimate(
            [*paths, tempfile.gettempdir()], new_bytes, processing_bytes
        ),
        download_time=time_estimate(new_bytes, providers),
    )


def baseline_review_signature(plan):
    from .approach_service import digest

    return digest(
        dict(
            sources=plan.get("acquisition_hash"), allowance=plan.get("max_download_mb")
        )
    )
