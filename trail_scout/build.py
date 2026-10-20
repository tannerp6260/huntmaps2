"""Use installed frontend packages without installing or modifying owner env."""

import os
from pathlib import Path
import subprocess
from .storage import ROOT


def main():
    web = ROOT / "trail_scout/web"
    installed = Path(
        os.environ.get(
            "TRAILSCOUT_NODE_MODULES",
            os.environ.get("TRAILSCOUT_SOURCE_ROOT", "/home/tanner/Desktop/huntmaps2")
            + "/gui/frontend/node_modules",
        )
    ).resolve()
    if not (installed / "vite/bin/vite.js").is_file():
        raise SystemExit(
            "Installed frontend packages unavailable. Supply TRAILSCOUT_NODE_MODULES or npm ci in trail_scout/web (isolated); do not upgrade the owner environment."
        )
    link = web / "node_modules"
    if not link.exists():
        link.symlink_to(installed, target_is_directory=True)
    subprocess.run(
        ["node", str(installed / "typescript/bin/tsc"), "--noEmit"], cwd=web, check=True
    )
    subprocess.run(
        ["node", str(installed / "vite/bin/vite.js"), "build"], cwd=web, check=True
    )


if __name__ == "__main__":
    main()
