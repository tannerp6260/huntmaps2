"""Scene storage estimates and free-space guards; saved history is never a quota."""

import tempfile
from pathlib import Path
from . import downloads, first_person as fp

# Conservative working estimates, not limits on accumulated scene history.
SCENE_BYTES = 60_000_000
METADATA_BYTES = 64_000


def estimate(plan, allow=True):
    from .lidar_batch import MAX_SPOOL_BYTES

    sources = plan.get("sources", []) + plan.get("imagery_sources", [])
    count = len(plan.get("candidates", []))
    available = [s for s in sources if allow or s.get("cached")]
    output = count * SCENE_BYTES
    spool = MAX_SPOOL_BYTES if available and count > 1 else 0
    assembly = max(
        (s["bytes"] for s in sources if allow and not s.get("cached")), default=0
    )
    return dict(
        scene_count=count,
        estimated_output_bytes=output,
        processing_bytes=output + spool + assembly,
    )


def usage():
    def size(area):
        total = 0
        for path in (fp.HOME / area).rglob("*"):
            try:
                if path.is_file():
                    total += path.stat().st_size
            except FileNotFoundError:
                # Publishing atomically moves a partial folder into bundles.
                # Inventory is informational and can straddle that move.
                continue
        return total

    return dict(saved_bytes=size("bundles"), partial_bytes=size("partial"))


def review(plan):
    work = estimate(plan)
    info = downloads.review_info(
        [fp.HOME],
        plan.get("estimated_new_bytes", 0),
        downloads.provider_estimates(plan.get("sources", []), "remaining_bytes"),
        work["processing_bytes"],
    )
    info["storage"]["scene_assets"] = dict(**usage(), **work)
    if not plan.get("prepared"):
        # Missing source sizes are unknown, not a zero-byte cached preparation.
        info.pop("download_time", None)
    return info


def check_plan(plan, allow):
    work = estimate(plan, allow)
    required = (
        3 * (plan.get("estimated_new_bytes", 0) if allow else 0)
        + work["processing_bytes"]
    )
    # Scene assets and anonymous lidar spools can live on different filesystems.
    for path in (fp.HOME, tempfile.gettempdir()):
        downloads.check_space(path, required)


def write_array(array, path):
    location = (
        Path(path).parent if isinstance(path, (str, Path)) else tempfile.gettempdir()
    )
    downloads.check_space(location, array.nbytes)
    array.tofile(path)
