"""Additive APIs for review filtering and independent kept-point approaches."""

import sys
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Body, Header
from fastapi.responses import Response
from shapely.geometry import mapping
from glassing.owner_area import choices, LIMIT
from .config import STATE
from .storage import write, read_json, locked
from . import (
    scouting_network as network,
    scouting_filters as filters,
    approach_service as approaches,
)
from .working_waypoints import DisplayRun
from .tiles import tile


def router(jobs):
    r = APIRouter(prefix="/api")

    from . import workflow

    @r.get("/runs/{ident}/workflow")
    def workflow_get(ident):
        return workflow.get(ident, jobs)

    @r.get("/runs/{ident}/workflow-point/{cid}")
    def workflow_point(ident, cid):
        return workflow.point(ident, cid, jobs)

    @r.put("/runs/{ident}/workflow/{cid}")
    def workflow_decide(ident, cid, body: dict = Body(...)):
        return workflow.decide(ident, cid, body, jobs)

    @r.post("/networks/import")
    async def imported(
        kind: str, source_date: str = "unknown", file: UploadFile = File(...)
    ):
        ext = Path(file.filename or "").suffix.lower()
        if ext not in (".geojson", ".json", ".kml", ".kmz", ".gpx"):
            raise ValueError("Import GeoJSON, KML/KMZ or GPX lines")
        return network.save_network(
            await file.read(network.LIMIT + 1), ext, kind, file.filename, source_date
        )

    @r.get("/networks")
    def networks():
        return [
            network.display_network(read_json(p))
            for p in (STATE / "networks").glob("*/network.json")
        ]

    @r.post("/network-plans")
    def network_plan(body: dict = Body(...)):
        from .downloads import review_info

        p = network.network_plan(body["bounds"], body["max_download_mb"])
        return dict(
            p, **review_info([STATE], p["estimated_bytes"], ["apps.fs.usda.gov"])
        )

    @r.get("/network-plans/{ident}")
    def network_result(ident):
        network.checked_id(ident)
        return dict(
            plan=read_json(STATE / "network-plans" / f"{ident}.json"),
            result=read_json(STATE / "network-plans" / f"{ident}-result.json"),
        )

    @r.post("/network-plans/{ident}/start")
    def network_start(ident, body: dict = Body(...)):
        if body.get("download") is not True:
            raise ValueError("Explicitly approve the reviewed network download plan")
        p = read_json(STATE / "network-plans" / f"{network.checked_id(ident)}.json")
        if not p:
            raise ValueError("Review network plan first")
        from .downloads import check_space

        check_space(STATE, 3 * p["estimated_bytes"])
        # The caller may link an analysis plan; its reviewed estimate consumes budget.
        remaining = p["max_download_mb"] * 1000000
        if body.get("analysis_plan"):
            base = read_json(
                STATE / "plans" / f"{network.checked_id(body['analysis_plan'])}.json"
            )
            if not base or not base.get("prepared"):
                raise ValueError("Prepare analysis plan first")
            remaining = min(
                remaining,
                base["max_download_mb"] * 1000000
                - base["acquisition"]["estimated_bytes"],
            )
        if remaining < p["estimated_bytes"]:
            raise ValueError(
                "Combined plan exceeds shared cap; narrow area or change cap"
            )
        return jobs.start(
            [
                sys.executable,
                "-u",
                "-m",
                "huntmaps_gui.scouting_worker",
                "network",
                ident,
                "--remaining-bytes",
                str(remaining),
            ],
            "network-acquisition",
            plan=ident,
        )

    @r.post("/runs/{ident}/network-point")
    def network_point(ident, body: dict = Body(...)):
        from shapely.geometry import Point
        from glassing.transfer import project

        run = DisplayRun(ident, jobs)
        p = approaches.geometry(
            dict(type="Point", coordinates=body["coordinates"]), False
        )
        xy = project(4326, run.config["epsg"])
        ll = project(run.config["epsg"], 4326)
        query = Point(xy(p.x, p.y))
        lines, _ = network.load_networks(
            body["network_ids"],
            run.config["epsg"],
            body.get("kinds", ["roads", "trails"]),
        )
        if not lines:
            raise ValueError("Select loaded mapped roads/trails first")
        nearest = min(
            (line.interpolate(line.project(query)) for line in lines),
            key=lambda p: (p.distance(query), p.x, p.y),
        )
        if query.distance(nearest) > 100:
            raise ValueError("Click within 100 m of the selected mapped network")
        return dict(
            coordinates=ll(nearest.x, nearest.y),
            projection_distance_m=query.distance(nearest),
        )

    @r.post("/runs/{ident}/filters")
    def save_filter(ident, body: dict = Body(...)):
        return filters.save(ident, body)

    @r.get("/runs/{ident}/filters/{profile}")
    def filtered(ident, profile):
        run = DisplayRun(ident, jobs)
        return filters.FilteredRun(run, filters.load(profile, ident)).results(
            list(run.points)
        )

    @r.get("/runs/{ident}/filtered-tiles/{profile}/{layer}/{cid}/{z}/{x}/{y}.png")
    def filtered_tile(
        ident,
        profile,
        layer,
        cid,
        z: int,
        x: int,
        y: int,
        color: int = 0,
        x_huntmaps_prefetch: bool = Header(False),
    ):
        return Response(
            tile(
                filters.FilteredRun(
                    DisplayRun(ident, jobs), filters.load(profile, ident)
                ),
                layer,
                cid,
                z,
                x,
                y,
                color,
                background=x_huntmaps_prefetch,
            ),
            media_type="image/png",
            headers={"Cache-Control": "private, max-age=3600"},
        )

    @r.get("/runs/{ident}/filtered-overlap/{profile}")
    def overlap(ident, profile, ids: str):
        run = filters.FilteredRun(DisplayRun(ident, jobs), filters.load(profile, ident))
        selected = ids.split(",")
        if not 1 <= len(selected) <= 3 or len(set(selected)) != len(selected):
            raise ValueError("Compare one to three distinct setups")
        masks = {i: run.mask(i)[0] for i in selected}
        area = abs(run.dem.GetGeoTransform()[1] * run.dem.GetGeoTransform()[5]) / 1e6
        return [
            dict(a=a, b=b, shared_km2=float((masks[a] & masks[b]).sum() * area))
            for n, a in enumerate(selected)
            for b in selected[n + 1 :]
        ]

    @r.get("/runs/{ident}/kept-points")
    def kept(ident):
        return list(approaches.point_snapshot(ident, jobs)[1].values())

    @r.post("/travel/import")
    async def travel(file: UploadFile = File(...)):
        data = await file.read(LIMIT + 1)
        if len(data) > LIMIT:
            raise ValueError("Travel polygon import exceeds 10 MB")
        ext = Path(file.filename or "").suffix.lower()
        if ext not in (".json", ".geojson", ".kml", ".kmz"):
            raise ValueError("Import GeoJSON or KML/KMZ polygons")
        folder = STATE / "travel-imports" / uuid.uuid4().hex
        folder.mkdir(parents=True)
        path = folder / ("original" + ext)
        path.write_bytes(data)
        return [dict(name=name, geometry=mapping(g)) for name, g in choices(path)]

    @r.post("/runs/{ident}/approaches")
    def submit(ident, body: dict = Body(...)):
        with locked(STATE / "maintenance"):
            if any(j["status"] in ("running", "cancelling") for j in jobs.list(False)):
                raise ValueError("Another job is running; wait or cancel it first")
            scenario = approaches.create(ident, body, jobs)
            job = jobs.start(
                [
                    sys.executable,
                    "-u",
                    "-m",
                    "huntmaps_gui.scouting_worker",
                    "approach",
                    scenario["id"],
                ],
                "approach",
                name=ident,
                plan=scenario["id"],
            )
            return dict(scenario=scenario, job=job)

    @r.get("/runs/{ident}/approaches")
    def scenarios(ident):
        return [
            approaches.status(p.parent.name, jobs)
            for p in (STATE / "approaches").glob("*/scenario.json")
            if read_json(p)["run_id"] == ident
        ]

    @r.get("/approaches/{ident}")
    def scenario(ident):
        return approaches.status(ident, jobs)

    @r.get("/approaches/{ident}/export/{fmt}")
    def export(
        ident, fmt, point: int = 0, alternative: int = 0, waypoint: str | None = None
    ):
        if waypoint is not None:
            saved = approaches.status(ident, jobs)
            matches = [
                i
                for i, r in enumerate((saved.get("results") or {}).get("results", []))
                if r["point"]["id"] == waypoint
            ]
            if not matches:
                raise ValueError("Choose a waypoint in this completed scenario")
            point = matches[0]
        if point < 0 or alternative < 0:
            raise ValueError("Choose a result alternative")
        try:
            data = approaches.export(ident, point, alternative, fmt, jobs)
        except IndexError:
            raise ValueError("Choose a result alternative")
        return Response(
            data,
            media_type=(
                "application/geo+json" if fmt == "geojson" else "application/gpx+xml"
            ),
            headers={
                "Content-Disposition": f'attachment; filename="provisional-approach-{ident}.{fmt}"'
            },
        )

    return r
