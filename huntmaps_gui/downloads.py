"""Transfer ceiling suggestions from metadata, never acquisition authorization."""

import math


def suggested_mb(estimated_bytes, maximum=1900):
    if (
        type(estimated_bytes) not in (int, float)
        or not math.isfinite(estimated_bytes)
        or estimated_bytes < 0
    ):
        raise ValueError("Download estimate must be finite and nonnegative")
    return min(maximum, max(10, math.ceil(estimated_bytes * 1.2 / 10_000_000) * 10))
