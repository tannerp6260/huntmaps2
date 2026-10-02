"""Read-only GUI environment and launch diagnostics."""

import importlib
import os
from pathlib import Path
import shutil
import socket
import sys
from .config import current


def check(port=8765):
    config = current()
    checks = []

    def result(name, ok, detail, required=True):
        checks.append(dict(name=name, ok=bool(ok), detail=detail, required=required))

    result(
        "interpreter",
        sys.version_info >= (3, 10),
        sys.executable + " " + sys.version.split()[0],
    )
    for name in (
        "fastapi",
        "uvicorn",
        "multipart",
        "numpy",
        "scipy",
        "shapely",
        "matplotlib",
        "osgeo.gdal",
        "pyproj",
        "PIL",
        "laspy",
        "lazrs",
        "skimage.measure",
    ):
        try:
            module = importlib.import_module(name)
            if name == "osgeo.gdal":
                assert (
                    module.GetDriverByName("GTiff")
                    and module.GetDriverByName("GPKG")
                    and hasattr(module, "ViewshedGenerate")
                )
            result(
                name,
                True,
                getattr(module, "__version__", "available"),
                name not in ("laspy", "lazrs", "skimage.measure"),
            )
        except (ImportError, AssertionError) as error:
            result(
                name,
                False,
                str(error),
                name not in ("laspy", "lazrs", "skimage.measure"),
            )
    dist = config.source_dir / "gui/frontend/dist/index.html"
    result("frontend assets", dist.is_file(), str(dist))
    browser = (
        os.environ.get("HUNTMAPS_BROWSER")
        or shutil.which("google-chrome")
        or shutil.which("chromium")
    )
    result(
        "browser",
        browser is not None,
        browser or "No Chrome/Chromium found. Use --no-browser or install a browser.",
        False,
    )
    for name, path in [("state", config.state_dir), ("workspace", config.workspace)]:
        parent = path
        while not parent.exists():
            parent = parent.parent
        result(name, os.access(parent, os.W_OK), str(path))
    free = shutil.disk_usage(
        config.workspace if config.workspace.exists() else config.workspace.parent
    ).free
    result(
        "free disk",
        free >= 1024**3,
        f"{free/1024**3:.2f} GiB; analysis and preparation retain their own budgets",
    )
    try:
        if not 1 <= port <= 65535:
            raise OSError("Port must be 1–65535")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", port))
        result("port", True, f"127.0.0.1:{port}")
    except OSError as error:
        result(
            "port", False, f"127.0.0.1:{port}: {error}. Choose --port with a free port."
        )
    return dict(
        ok=all(item["ok"] for item in checks if item["required"]), checks=checks
    )
