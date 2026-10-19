"""Independent source-selection browser fixture; no owner state or source changes."""

import json
from huntmaps_gui.config import current
from .connectivity_fixture import owner


def main():
    c = current()
    if c.workspace == c.source_dir or c.state_dir == c.source_dir / ".gui":
        raise ValueError("Use disposable workspace/state")
    r = owner(
        "scouting-controls-fixture",
        "workflow-fixture.json",
        "workflow-fixture/observer.geojson",
    )
    cid = next(p["id"] for p in r.points.values() if p.get("group") == "automated")
    print(json.dumps(dict(run=r.id, cid=cid)))


if __name__ == "__main__":
    main()
