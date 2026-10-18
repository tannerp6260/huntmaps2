"""Disposable viewport context. Never creates analytical networks or transfer ledgers."""

import io
from contextlib import contextmanager
import os
import threading
import urllib.parse
import urllib.request
from PIL import Image
from .config import STATE
from .display_cache import touch, changed, maybe_evict, pin
from .storage import locked

TRANSPORT = (
    "https://carto.nationalmap.gov/arcgis/rest/services/transportation/MapServer/export"
)
WORKERS = threading.BoundedSemaphore(2)


@contextmanager
def capacity():
    # Optional remote context must never queue inside the shared API thread pool.
    if not WORKERS.acquire(blocking=False):
        raise ValueError(
            "Transportation context busy; retry after the current tiles finish"
        )
    try:
        yield
    finally:
        WORKERS.release()


def cached_transportation(z, x, y):
    if not (5 <= z <= 16 and 0 <= x < 2**z and 0 <= y < 2**z):
        raise ValueError("Invalid transportation context tile")
    if os.environ.get("HUNTMAPS_DISABLE_BROWSING") == "1":
        fixture = os.environ.get("HUNTMAPS_BROWSING_FIXTURE")
        if fixture:
            from pathlib import Path

            return Path(fixture).read_bytes()
        raise ValueError("Browsing context provider disabled for offline verification")
    cache = STATE / "cache" / "transportation-v1" / f"{z}-{x}-{y}.png"
    if cache.exists():
        touch(cache)
        return cache.read_bytes()
    return None


def transportation(z, x, y):
    cached = cached_transportation(z, x, y)
    if cached is not None:
        return cached
    cache = STATE / "cache" / "transportation-v1" / f"{z}-{x}-{y}.png"
    half = 20037508.342789244
    span = 2 * half / 2**z
    bounds = [
        -half + x * span,
        half - (y + 1) * span,
        -half + (x + 1) * span,
        half - y * span,
    ]
    params = dict(
        f="image",
        bbox=",".join(map(str, bounds)),
        bboxSR=3857,
        imageSR=3857,
        size="256,256",
        format="png32",
        transparent="true",
        dpi=96,
    )
    with capacity():
        if cache.exists():
            touch(cache)
            return cache.read_bytes()
        with urllib.request.urlopen(
            TRANSPORT + "?" + urllib.parse.urlencode(params), timeout=12
        ) as response:
            data = response.read(1_000_001)
        if len(data) > 1_000_000:
            raise ValueError("Transportation tile exceeds display limit")
        with Image.open(io.BytesIO(data)) as image:
            if image.size != (256, 256) or image.format != "PNG":
                raise ValueError("Invalid transportation context response")
        with locked(STATE / "maintenance"), pin([cache]):
            cache.parent.mkdir(parents=True, exist_ok=True)
            changed()
            temporary = cache.with_suffix(".tmp")
            temporary.write_bytes(data)
            temporary.replace(cache)
            touch(cache)
            maybe_evict()
        return data
