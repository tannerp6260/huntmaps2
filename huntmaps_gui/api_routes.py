"""Local FastAPI application. Optional browser basemap; no arbitrary commands or historical run writes."""

import re
import sys
import threading
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Body
from fastapi.responses import Response, FileResponse
from shapely.geometry import mapping
from .catalog import ROOT, STATE, Run, runs, read, collection, feature
from .jobs import Jobs, write
from .config import WORKSPACE
from .storage import transaction
from .requests import (
    Annotation,
    Observer,
    Waypoint,
    Review,
    Profile,
    Preparation,
    Start,
)
from .tiles import tile
from .terrain import metadata, elevation_tile
from glassing.owner_area import choices, convert, LIMIT

STORE_LOCK = threading.RLock()


def valid_name(name):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name or ""):
        raise ValueError(
            "Use a run name of 1–64 letters, digits, hyphens or underscores"
        )
    return name


def api_router(jobs: Jobs):
    router = APIRouter()
    from . import first_person as fp

    @router.post("/api/first-person/plans")
    def fp_plan(body: dict = Body(default={})):
        ident = fp.new_plan(
            body.get("run_id", fp.RUN),
            body.get("ids"),
            body.get("fidelity", "lidar"),
            body.get("acquisition"),
        )
        return jobs.start(
            [
                sys.executable,
                "-u",
                "-m",
                "huntmaps_gui.first_person_worker",
                "plan",
                ident,
            ],
            "first-person-plan",
            plan=ident,
        )

    @router.get("/api/first-person/plans/{ident}")
    def fp_get_plan(ident):
        p = fp.plan(ident)
        from .downloads import review_info, provider_estimates

        return dict(
            p,
            review_required=bool(p.get("prepared") and not p.get("review_signature")),
            errors=[e for e in p.get("errors", []) if "500 MB pilot budget" not in e],
            **review_info(
                [fp.HOME],
                p.get("estimated_new_bytes", 0),
                provider_estimates(p.get("sources", []), "remaining_bytes"),
                800_000_000
                + max(
                    (s["bytes"] for s in p.get("sources", []) if not s.get("cached")),
                    default=0,
                ),
            ),
        )

    @router.put("/api/first-person/plans/{ident}/allowance")
    def fp_allowance(ident, body: dict = Body(...)):
        from .storage import locked

        with locked(STATE / "maintenance"):
            if any(j["status"] in ("running", "cancelling") for j in jobs.list(False)):
                raise ValueError(
                    "Wait for the active job before changing the allowance"
                )
            p = fp.plan(ident)
            cap = body.get("max_download_mb")
            if type(cap) is not int or not cap >= 10:
                raise ValueError(
                    "Choose an integer scene transfer allowance of at least 10 MB"
                )
            p["download_cap_bytes"] = cap * 1_000_000
            from .approach_service import digest

            p["review_signature"] = digest(
                {
                    k: p.get(k)
                    for k in (
                        "sources",
                        "snapshots",
                        "acquisition",
                        "fidelity",
                        "download_cap_bytes",
                    )
                }
            )
            write(fp.HOME / "plans" / (ident + ".json"), p)
            return p

    @router.post("/api/first-person/plans/{ident}/start")
    def fp_start(ident, body: Start):
        body = body.model_dump(exclude_unset=True)
        p = fp.plan(ident)
        if not p.get("prepared"):
            raise ValueError("Review the source plan first")
        from .downloads import check_space

        check_space(
            fp.HOME,
            3 * (p.get("estimated_new_bytes", 0) if body.get("download") else 0)
            + (
                max(
                    (s["bytes"] for s in p.get("sources", []) if not s.get("cached")),
                    default=0,
                )
                if body.get("download")
                else 0
            )
            + 800_000_000,
        )
        if body.get("download") and (
            not p.get("review_signature")
            or body.get("review_signature") != p["review_signature"]
        ):
            raise ValueError(
                "Source plan changed or consent is outdated; refresh and approve the current scene plan"
            )
        return jobs.start(
            [
                sys.executable,
                "-u",
                "-m",
                "huntmaps_gui.first_person_worker",
                "prepare",
                ident,
            ]
            + (
                ["--download", "--review-signature", body["review_signature"]]
                if body.get("download") is True
                else []
            ),
            "first-person-prepare",
            plan=ident,
        )

    @router.get("/api/runs/{ident}/first-person/{cid}")
    def fp_scene(ident, cid):
        return fp.scene(ident, cid)

    @router.get("/api/runs/{ident}/first-person/{cid}/assets/{name}")
    def fp_asset(ident, cid, name):
        fp.candidate(ident, cid)
        folder, meta = fp.bundle(cid, ident)
        if name not in meta["hashes"] or name.endswith(".npz"):
            raise ValueError("Unknown scene asset")
        return FileResponse(
            fp.asset_path(folder, meta, name),
            headers={"Cache-Control": "private, max-age=3600"},
        )

    @router.post("/api/runs/{ident}/first-person/{cid}/profile")
    def fp_profile(ident, cid, body: Profile):
        body = body.model_dump(exclude_unset=True)
        return fp.profile(ident, cid, body)

    @router.post("/api/runs/{ident}/first-person/{cid}/observer")
    def fp_observer(ident, cid, body: Observer):
        body = body.model_dump(exclude_unset=True)
        return fp.observer(ident, cid, body)

    from . import manual_observers as manual

    @router.get("/api/runs/{ident}/manual-observers")
    def manual_list(ident):
        return list(manual.records(ident).values())

    @router.post("/api/runs/{ident}/manual-observers")
    def manual_create(ident, body: Waypoint):
        body = body.model_dump(exclude_unset=True)
        with STORE_LOCK:
            return manual.create(ident, body)

    @router.put("/api/runs/{ident}/manual-observers/{key}")
    def manual_update(ident, key, body: Review):
        body = body.model_dump(exclude_unset=True)
        with STORE_LOCK:
            return manual.update(ident, key, body)

    @router.delete("/api/runs/{ident}/manual-observers/{key}")
    def manual_delete(ident, key):
        with STORE_LOCK:
            working.restore(ident, key, jobs)
            return manual.delete(ident, key)

    from . import working_waypoints as working

    @router.get("/api/runs/{ident}/working-waypoints")
    def working_list(ident):
        return working.snapshot(ident, jobs)

    @router.post("/api/runs/{ident}/working-waypoints/{key}")
    def working_update(ident, key, body: Waypoint):
        body = body.model_dump(exclude_unset=True)
        return working.start(ident, key, body, jobs)

    @router.delete("/api/runs/{ident}/working-waypoints/{key}")
    def working_restore(ident, key):
        return working.restore(ident, key, jobs)

    @router.put("/api/runs/{ident}/working-waypoints/{key}/review")
    def working_review(ident, key, body: Review):
        body = body.model_dump(exclude_unset=True)
        return working.review(ident, key, body, jobs)

    @router.get("/api/runs/{ident}/working-candidates/{key}")
    def working_candidate(ident, key):
        return working.DisplayRun(ident, jobs).candidate(key, True)

    @router.get("/api/runs/{ident}/working-tiles/{layer}/{key}/{z}/{x}/{y}.png")
    def working_tile(ident, layer, key, z: int, x: int, y: int, color: int = 0):
        return Response(
            tile(working.DisplayRun(ident, jobs), layer, key, z, x, y, color),
            media_type="image/png",
            headers={"Cache-Control": "private, max-age=3600"},
        )

    @router.get("/api/runs/{ident}/working-overlap")
    def working_overlap(ident, ids: str):
        r = working.DisplayRun(ident, jobs)
        selected = ids.split(",")
        if not 1 <= len(selected) <= 3 or len(set(selected)) != len(selected):
            raise ValueError("Compare one to three distinct setups")
        masks = {i: r.mask(i)[0] for i in selected}
        area = abs(r.dem.GetGeoTransform()[1] * r.dem.GetGeoTransform()[5]) / 1e6
        return [
            dict(a=a, b=b, shared_km2=float((masks[a] & masks[b]).sum() * area))
            for n, a in enumerate(selected)
            for b in selected[n + 1 :]
        ]

    @router.get("/api/runs")
    def get_runs():
        return runs()

    @router.get("/api/runs/{ident}")
    def get_run(ident):
        return Run(ident).summary()

    @router.get("/api/runs/{ident}/candidates/{candidate}")
    def get_candidate(ident, candidate):
        return Run(ident).candidate(candidate, True)

    @router.get("/api/runs/{ident}/sectors/{candidate}")
    def get_sectors(ident, candidate):
        return Run(ident).sectors(candidate)

    @router.get("/api/runs/{ident}/tiles/{layer}/{candidate}/{z}/{x}/{y}.png")
    def get_tile(ident, layer, candidate, z: int, x: int, y: int, color: int = 0):
        return Response(
            tile(Run(ident), layer, candidate, z, x, y, color),
            media_type="image/png",
            headers={"Cache-Control": "private, max-age=3600"},
        )

    @router.get("/api/runs/{ident}/terrain")
    def terrain_info(ident):
        return metadata(Run(ident))

    @router.get("/api/runs/{ident}/terrain/{z}/{x}/{y}.png")
    def terrain_tile(ident, z: int, x: int, y: int):
        return Response(
            elevation_tile(Run(ident), z, x, y),
            media_type="image/png",
            headers={"Cache-Control": "private, max-age=3600"},
        )

    @router.get("/api/runs/{ident}/overlap")
    def overlap(ident, ids: str):
        r = Run(ident)
        selected = ids.split(",")
        if not 1 <= len(selected) <= 3 or len(set(selected)) != len(selected):
            raise ValueError("Compare one to three distinct setups")
        masks = {i: r.mask(i)[0] for i in selected}
        area = abs(r.dem.GetGeoTransform()[1] * r.dem.GetGeoTransform()[5]) / 1e6
        return [
            dict(a=a, b=b, shared_km2=float((masks[a] & masks[b]).sum() * area))
            for n, a in enumerate(selected)
            for b in selected[n + 1 :]
        ]

    @router.get("/api/runs/{ident}/annotations")
    def annotations(ident):
        Run(ident)
        return read(STATE / "annotations" / (ident + ".json"), {})

    @router.put("/api/runs/{ident}/annotations/{candidate}")
    def annotate(ident, candidate, body: Annotation):
        body = body.model_dump(exclude_unset=True)
        r = Run(ident)
        if candidate not in r.points:
            raise ValueError("Unknown candidate")
        if body.get("status") not in ["unmarked", "keep", "reject", "needs inspection"]:
            raise ValueError("Choose keep, reject or needs inspection")
        if len(body.get("notes", "")) > 10000:
            raise ValueError("Notes are limited to 10,000 characters")
        path = STATE / "annotations" / (ident + ".json")
        with STORE_LOCK, transaction(path, {}) as data:
            data[candidate] = dict(status=body["status"], notes=body.get("notes", ""))
        return data[candidate]

    @router.get("/api/runs/{ident}/export/{fmt}")
    def export(ident, fmt, ids: str):
        if fmt not in ["gpx", "kml"]:
            raise ValueError("Choose GPX or KML")
        r = Run(ident)
        selected = ids.split(",")
        if not selected or len(selected) > 250 or len(set(selected)) != len(selected):
            raise ValueError("Select distinct observer waypoints")
        notes = read(STATE / "annotations" / (ident + ".json"), {})
        if fmt == "gpx":
            root = ET.Element(
                "gpx",
                version="1.1",
                creator="HuntMaps2 local GUI",
                xmlns="http://www.topografix.com/GPX/1/1",
            )
            doc = root
        else:
            root = ET.Element("kml", xmlns="http://www.opengis.net/kml/2.2")
            doc = ET.SubElement(root, "Document")
        working_points = working.snapshot(ident, jobs)["overrides"]
        manual_points = manual.records(ident)
        for i in selected:
            if i in working_points:
                p = working_points[i]
                name = p["name"]
                desc = (
                    f"Updated working observer {i}; calculated terrain-only view; access and field sightlines unverified. "
                    + p["notes"]
                )
            elif i.startswith("manual-"):
                if i not in manual_points:
                    raise ValueError("Unknown provisional waypoint.")
                p = manual_points[i]
                name = p["name"]
                desc = (
                    f"Provisional manual observer near {p['anchor']}; no full-area analysis calculated; access and sightlines unverified. "
                    + p["notes"]
                )
            else:
                p = r.candidate(i)
                name = f'{p["neighborhood"]+" / " if p["neighborhood"] else ""}{i}' + (
                    f' (alternative to {p["parent"]})' if p["parent"] else ""
                )
                desc = "Provisional observer setup; legal access and sightlines unresolved. " + notes.get(
                    i, {}
                ).get(
                    "notes", ""
                )
            if fmt == "gpx":
                w = ET.SubElement(
                    doc, "wpt", lat=str(p["latitude"]), lon=str(p["longitude"])
                )
                ET.SubElement(w, "name").text = name
                ET.SubElement(w, "desc").text = desc
            else:
                w = ET.SubElement(doc, "Placemark")
                ET.SubElement(w, "name").text = name
                ET.SubElement(w, "description").text = desc
                ET.SubElement(ET.SubElement(w, "Point"), "coordinates").text = (
                    f'{p["longitude"]},{p["latitude"]},0'
                )
        return Response(
            ET.tostring(root, encoding="utf-8", xml_declaration=True),
            media_type="application/xml",
            headers={
                "Content-Disposition": f'attachment; filename="{ident}-observers.{fmt}"'
            },
        )

    @router.post("/api/imports")
    async def import_area(file: UploadFile = File(...), practice: bool = False):
        ext = Path(file.filename or "").suffix.lower()
        if ext not in [".geojson", ".json", ".kml", ".kmz"]:
            raise ValueError("Import GeoJSON, KML or KMZ")
        data = await file.read(LIMIT + 1)
        if len(data) > LIMIT:
            raise ValueError("Area file exceeds 10 MB")
        ident = uuid.uuid4().hex
        folder = STATE / ("practice-areas" if practice else "imports") / ident
        folder.mkdir(parents=True)
        path = folder / ("area" + ext)
        path.write_bytes(data)
        items = choices(path)
        result = dict(
            id=ident,
            path=str(path),
            choices=[
                dict(number=str(n + 1), name=name, geometry=mapping(g))
                for n, (name, g) in enumerate(items)
            ],
        )
        write(folder / "import.json", result)
        return result

    @router.post("/api/plans")
    def prepare(body: Preparation):
        body = body.model_dump(exclude_unset=True)
        name = valid_name(body.get("name"))
        from .scouting_filters import validate as validate_filters

        sampling = (
            validate_filters(body["access_sampling"])
            if body.get("access_sampling") is not None
            else None
        )
        if sampling and not sampling["network_ids"] and not body.get("include_network"):
            raise ValueError(
                "Select road/trail source datasets or include the reviewed USFS network acquisition"
            )
        imp = body.get("import_id", "")
        if not re.fullmatch("[a-f0-9]{32}", imp):
            raise ValueError("Import your observer polygon first")
        imported = read(STATE / "imports" / imp / "import.json")
        if not imported:
            raise ValueError("Import not found; import the area again")
        selection = str(body.get("polygon", ""))
        if selection not in [v["number"] for v in imported["choices"]] + ["all"]:
            raise ValueError("Explicitly select a polygon number or all")
        radius = int(body.get("radius_m", 2000))
        minutes = int(body.get("observation_minutes", 30))
        budget = int(body.get("max_download_mb", 600))
        count = int(body.get("candidate_count", 150))
        if (
            radius not in [500, 1000, 1500, 2000, 2500, 3000]
            or not 5 <= minutes <= 120
            or not budget >= 1
            or not 12 <= count <= 5000
        ):
            raise ValueError(
                "Use a supported radius, 5–120 minutes, 12–5000 candidates and positive MB transfer allowance"
            )
        if body.get("recommendation_count", min(20, count)) > count:
            raise ValueError("Recommendations cannot exceed the search budget")
        ident = uuid.uuid4().hex
        folder = STATE / "plans"
        folder.mkdir(parents=True, exist_ok=True)
        root = WORKSPACE / "results" / name
        if root.exists():
            raise ValueError(
                "This run name already exists. Resume its GUI job or use a new name."
            )
        c = read(ROOT / "configs/transfer.template.json")
        geometry = convert(
            imported["path"], folder / (ident + "-observer.geojson"), selection
        )
        lon, lat = geometry.centroid.coords[0]
        c.update(
            epsg=(32600 if lat >= 0 else 32700) + min(60, int((lon + 180) // 6) + 1),
            radius_m=radius,
            observation_minutes=minutes,
            candidate_count=count,
            search=dict(
                version=1,
                recommendation_count=min(count, body.get("recommendation_count", 20)),
                nearby_radius_m=body.get("nearby_radius_m", 30),
                tree_threshold_percent=body.get("tree_threshold_percent", 10),
            ),
            normal_scouting=True,
            manual_points=None,
            download_bytes=budget * 1000000,
        )
        config = folder / (ident + "-config.json")
        write(config, c)
        p = dict(
            id=ident,
            name=name,
            area=imported["path"],
            polygon=selection,
            config=str(config),
            max_download_mb=budget,
            prepared=False,
            access_sampling=sampling,
            include_network=body.get("include_network", False),
            estimate_first=True,
        )
        write(folder / (ident + ".json"), p)
        return jobs.start(
            [sys.executable, "-u", "-m", "huntmaps_gui.worker", "prepare", ident],
            "prepare",
            name,
            ident,
        )

    @router.put("/api/plans/{ident}/allowance")
    def allowance(ident, body: dict = Body(...)):
        from .storage import locked

        with locked(STATE / "maintenance"):
            if any(j["status"] in ("running", "cancelling") for j in jobs.list(False)):
                raise ValueError(
                    "Wait for the active job before changing the allowance"
                )
            p = (
                read(STATE / "plans" / (ident + ".json"))
                if re.fullmatch(r"[a-f0-9]{32}", ident)
                else None
            )
            cap = body.get("max_download_mb")
            if not p or type(cap) is not int or not cap >= 10:
                raise ValueError(
                    "Choose a prepared plan and an integer transfer allowance of at least 10 MB"
                )
            if (WORKSPACE / "results" / p["name"] / "manifest.json").exists():
                raise ValueError("Completed run preserved")
            p.update(max_download_mb=cap, prepared=False, allowance_reviewed=True)
            write(STATE / "plans" / (ident + ".json"), p)
            return jobs.start(
                [sys.executable, "-u", "-m", "huntmaps_gui.worker", "prepare", ident],
                "prepare",
                p["name"],
                ident,
            )

    @router.get("/api/plans/{ident}")
    def plan(ident):
        if not re.fullmatch("[a-f0-9]{32}", ident):
            raise ValueError("Unknown plan")
        p = read(STATE / "plans" / (ident + ".json"))
        if not p:
            raise ValueError("Unknown plan")
        from .downloads import (
            review_info,
            provider_estimates,
            baseline_review_signature,
        )

        return dict(
            p,
            review_signature=baseline_review_signature(p),
            **review_info(
                [WORKSPACE, STATE],
                p.get("acquisition", {}).get("estimated_bytes", 0),
                provider_estimates(
                    p.get("acquisition", {}).get("items", []), "estimated_bytes"
                ),
                processing_bytes=2 * 1024**3,
            ),
            boundary=read(WORKSPACE / "results" / p["name"] / "observer.geojson"),
            settings={
                k: v
                for k, v in read(p["config"]).items()
                if k in ["radius_m", "observation_minutes", "candidate_count", "search"]
            },
        )

    @router.post("/api/plans/{ident}/start")
    def start(ident, body: Start):
        body = body.model_dump(exclude_unset=True)
        p = plan(ident)
        if not p.get("prepared"):
            raise ValueError("Prepare and review the acquisition plan first")
        from .downloads import check_space

        check_space(
            WORKSPACE,
            3 * p.get("acquisition", {}).get("estimated_bytes", 0) + 2 * 1024**3,
        )
        if body.get("download") and body.get("review_signature") != p.get(
            "review_signature"
        ):
            raise ValueError(
                "Source plan changed; review and approve the current acquisition plan"
            )
        if p.get("acquisition", {}).get("errors"):
            raise ValueError("Fix acquisition plan errors before starting")
        if (
            p.get("acquisition", {}).get("estimated_bytes", 0)
            > p["max_download_mb"] * 1000000
        ):
            raise ValueError("Reviewed estimate exceeds the shared download cap")
        if not p.get("sources_ready") and not body.get("download"):
            raise ValueError(
                "Review and explicitly allow this plan’s bulk downloads first"
            )
        return jobs.start(
            [sys.executable, "-u", "-m", "huntmaps_gui.worker", "run", ident]
            + (
                ["--download", "--review-signature", body["review_signature"]]
                if body.get("download") is True
                else []
            ),
            "baseline",
            p["name"],
            ident,
        )

    @router.post("/api/plans/{ident}/prepare")
    def reprepare(ident):
        p = plan(ident)
        p["prepared"] = False
        write(
            STATE / "plans" / (ident + ".json"),
            {k: v for k, v in p.items() if k not in ("boundary", "settings")},
        )
        return jobs.start(
            [sys.executable, "-u", "-m", "huntmaps_gui.worker", "prepare", ident],
            "prepare",
            p["name"],
            ident,
        )

    @router.get("/api/jobs")
    def get_jobs(offset: int = 0, limit: int = 50):
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError("Use a nonnegative offset and limit 1–100")
        return jobs.list(include_logs=False)[offset : offset + limit]

    @router.get("/api/jobs/{ident}/logs")
    def job_logs(ident, limit: int = 64000):
        if not 0 <= limit <= 64000:
            raise ValueError("Log limit must be 0–64000 bytes")
        return dict(logs=jobs.logs(ident, limit))

    @router.post("/api/jobs/{ident}/cancel")
    def cancel(ident):
        if not re.fullmatch("[a-f0-9]{32}", ident):
            raise ValueError("Unknown job")
        return jobs.cancel(ident)

    return router
