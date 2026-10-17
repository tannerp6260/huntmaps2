"""GUI annual RCMAP acquisition; the frozen CLI planner remains unchanged."""

import math
from pathlib import Path
import shutil
from urllib.parse import parse_qs, urlencode, urlparse
import uuid

from .config import STATE, WORKSPACE
from .storage import locked

POLICY_VERSION = 1
YEAR = 2023
COMPONENTS = {"tree": "tree", "shrub": "shrub", "herb": "herbaceous"}


def filename(key):
    return f"{key}_rcmap_{YEAR}_annual_v{POLICY_VERSION}_padded120.tif"


def plan(config, inputs, original_plan):
    items, errors = original_plan(config, inputs)
    result = []
    for item in items:
        key = item["key"]
        if key not in COMPONENTS:
            result.append(item)
            continue
        params = dict(parse_qs(urlparse(item["url"]).query))
        # Preserve the exact original requested bounds, CRS and interpolation.
        params = {k: v[0] for k, v in params.items() if k != "time"}
        coverage = f"rcmap_{key}:rcmap_{COMPONENTS[key]}_{YEAR}"
        params["coverage"] = coverage
        bounds = list(map(float, params["bbox"].split(",")))
        # Reprojection can enlarge the native-aligned response beyond its bbox.
        # This conservative estimate includes expansion and TIFF metadata; the
        # existing cumulative streaming ceiling remains authoritative.
        columns = math.ceil((bounds[2] - bounds[0]) / 30) + 32
        rows = math.ceil((bounds[3] - bounds[1]) / 30) + 32
        result.append(
            dict(
                item,
                name=filename(key),
                url=f"https://www.mrlc.gov/geoserver/rcmap_{key}/wcs?{urlencode(params)}",
                estimated_bytes=columns * rows * 8 + 65536,
                catalog_source_id=coverage,
                product="RCMAP fractional cover",
                component=COMPONENTS[key],
                observation_year=YEAR,
                source_policy_version=POLICY_VERSION,
                product_release="Unknown; annual layer does not identify a verified release. Year alone does not establish equivalence to prior sources.",
                service_catalog="https://www.mrlc.gov/data-services-page",
                requested_resolution_m=30,
            )
        )
    return result, errors


def refresh_required(record):
    for item in record.get("acquisition", {}).get("items", []):
        if item.get("key") not in COMPONENTS:
            continue
        url = urlparse(item.get("url", ""))
        if url.hostname in ("www.mrlc.gov", "mrlc.gov", "dmsdata.cr.usgs.gov"):
            if url.path.startswith(("/geoserver/rcmap_", "/geoserver/mrlc_")):
                key = item["key"]
                q = parse_qs(url.query)
                if (
                    record.get("source_policy_version") != POLICY_VERSION
                    or url.hostname != "www.mrlc.gov"
                    or url.path != f"/geoserver/rcmap_{key}/wcs"
                    or q.get("coverage")
                    != [f"rcmap_{key}:rcmap_{COMPONENTS[key]}_{YEAR}"]
                    or "time" in q
                ):
                    return True
    return False


def refresh_error(record):
    root = WORKSPACE / "results" / record["name"]
    if (root / "manifest.json").exists():
        return "Completed results are preserved. Use a new run name to change acquisition sources."
    analysis = root / "analysis"
    intake_files = {"intake.json", "manual_import.json", "transfer_owner.json"}
    if record.get("sampling_applied") or (
        analysis.exists()
        and any(p.is_file() and p.name not in intake_files for p in analysis.rglob("*"))
    ):
        return "Existing analysis is preserved. Use a new run name to refresh vegetation sources; numerical checkpoints cannot be reused across changed sources."
    return None


def snapshot(record):
    """Retain the complete pre-migration records before the owner CLI prepares."""
    error = refresh_error(record)
    if error:
        raise ValueError(error)
    root = WORKSPACE / "results" / record["name"]
    with locked(STATE / "source-refresh" / record["id"]):
        folder = STATE / "plans" / "source-history" / record["id"] / uuid.uuid4().hex
        folder.mkdir(parents=True)
        paths = {
            "plan.json": STATE / "plans" / (record["id"] + ".json"),
            "plan-config.json": Path(record["config"]),
        }
        paths.update(
            (name, root / name)
            for name in (
                "scouting.json",
                "download_plan.json",
                "acquisition.json",
                "DATA_REQUIRED.md",
            )
        )
        for name, path in paths.items():
            if path.is_file():
                shutil.copy2(path, folder / name)
        return str(folder)
