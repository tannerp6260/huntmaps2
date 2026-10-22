"""Fresh synthetic suggestion workflow, isolated from owner evidence."""

import json
from shapely.ops import transform
from huntmaps_gui.config import current
from huntmaps_gui import connectivity
from huntmaps_gui.scouting_network import save_network
from .connectivity_fixture import owner, shortlist


def main():
    config = current()
    if (
        config.workspace == config.source_dir
        or config.state_dir == config.source_dir / ".gui"
    ):
        raise ValueError("Use an isolated workspace and state")
    r = owner(
        "suggested-fixture", "search-fixture.json", "workflow-fixture/observer.geojson"
    )
    terrain = connectivity.Terrain(r)
    ids = list(r.points)[:2]
    features = []
    for cid in ids:
        p = r.points[cid]
        shortlist(r, cid)
        features.append(
            dict(
                type="Feature",
                properties={},
                geometry=dict(
                    type="LineString",
                    coordinates=[
                        terrain.ll(p["x"] - 10, p["y"] - 20),
                        terrain.ll(p["x"] + 10, p["y"] + 20),
                    ],
                ),
            )
        )
    bounds = list(transform(terrain.ll, terrain.footprint).bounds)
    bounds = [bounds[0] - 0.01, bounds[1] - 0.01, bounds[2] + 0.01, bounds[3] + 0.01]
    for kind in ("roads", "trails"):
        save_network(
            json.dumps(dict(type="FeatureCollection", features=features)).encode(),
            ".geojson",
            kind,
            "Synthetic suggested path fixture",
            coverage=bounds,
        )
    print(json.dumps(dict(run=r.id, ids=ids)))


if __name__ == "__main__":
    main()
