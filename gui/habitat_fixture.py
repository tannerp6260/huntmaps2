"""Independent synthetic habitat browser input; disposable Ubuntu only."""

import json
from pathlib import Path
import numpy as np
from osgeo import gdal
from glassing.transfer_fixture import create
from glassing.acquire import digest
from huntmaps_gui.config import current
from huntmaps_gui import habitat_service as h, habitat, connectivity, workflow
from huntmaps_gui.storage import write
from .connectivity_fixture import owner, sources
from shapely.geometry import mapping
from shapely.ops import transform


def main():
    config = current()
    if (
        config.workspace == config.source_dir
        or config.state_dir == config.source_dir / ".gui"
    ):
        raise ValueError("Use disposable workspace/state")
    create("habitat-fixture-config.json", "habitat-fixture-source")
    path = Path("habitat-fixture-config.json")
    c = json.loads(path.read_text())
    for key in ("tree", "shrub"):
        source = Path(c["data"][key]["path"])
        d = gdal.Open(str(source), gdal.GA_Update)
        a = d.ReadAsArray()
        rr, cc = np.indices(a.shape)
        a[:] = np.where(
            (cc // 9) % 2 == 0, 55 if key == "tree" else 10, 5 if key == "tree" else 40
        )
        # A broad dense stand beside the mosaic makes the habitat and terrain
        # comparators distinguishable; narrow stripes alone average similarly.
        a[cc < 85] = 85 if key == "tree" else 15
        d.GetRasterBand(1).WriteArray(a)
        d = None
        c["data"][key]["sha256"] = digest(source)
    c.update(
        normal_scouting=True,
        candidate_count=60,
        search=dict(
            version=1,
            ranking_version=2,
            recommendation_count=8,
            recommendation_separation_m=0,
            nearby_radius_m=30,
            tree_threshold_percent=10,
            habitat=habitat.validate(),
        ),
    )
    path.write_text(json.dumps(c))
    r = owner("habitat-fixture", str(path), "habitat-fixture-source/observer.geojson")
    chosen = h.choose(r.id, dict(settings={}, revision=0))
    scored = h.score(r.id, chosen["profile"])
    blocked = [p["id"] for p in scored["candidates"][:3]]
    networks = sources(r, r.candidate(scored["candidates"][4]["id"]))
    terrain = connectivity.Terrain(r)
    drafts = {}
    for cid in blocked:
        area = mapping(transform(terrain.ll, terrain.proposal(r.candidate(cid))))
        drafts[cid] = dict(
            point=workflow.point(r.id, cid),
            travel_area=area,
            exclusions=[area],
            maximum_slope_deg=25,
            network_ids=networks,
            kinds=["roads", "trails"],
        )
    write(
        config.state_dir / "approach-reviews" / f"{r.id}.json",
        dict(
            version=1,
            revision=1,
            queue=[],
            active_point="",
            drafts=drafts,
            defaults=dict(maximum_slope_deg=25),
        ),
    )
    print(
        json.dumps(
            dict(
                run=r.id,
                blocked=blocked,
                profile=chosen["profile"],
                top=scored["recommendation_ids"],
            )
        )
    )


if __name__ == "__main__":
    main()
