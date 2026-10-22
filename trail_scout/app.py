"""Isolated local API; bounded cancellable background work and immutable saves."""

import argparse
from contextlib import asynccontextmanager
from datetime import date as Date
import json
import os
from pathlib import Path
import threading
import time
import traceback
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
import uvicorn

from .storage import (
    Paths,
    StateLease,
    ROOT,
    atomic,
    read,
    digest,
    now,
    checked,
    seal,
    implementation,
)
from .sources import Pack
from .network import starts
from . import planner, profiles, render, preparation


class Cancelled(Exception):
    pass


class Service:
    def __init__(self, paths):
        self.paths = paths
        self.state_lease = StateLease(paths.state)
        self.worker = None
        self.lock = threading.RLock()
        self.pack = None
        self.active = None
        self.cancel_event = threading.Event()
        for p in (paths.state / "jobs").glob("*.json"):
            record = read(p)
            if record.get("status") in ("running", "pending"):
                record.update(
                    status="interrupted",
                    error="Server stopped before publication. Retry with the same inputs to reuse completed compatible artifacts.",
                    updated_utc=now(),
                )
                atomic(p, record)

    def close(self):
        self.cancel_event.set()
        if (
            self.worker
            and self.worker.is_alive()
            and self.worker is not threading.current_thread()
        ):
            self.worker.join(timeout=30)
        if not self.worker or not self.worker.is_alive():
            self.state_lease.close()

    def data(self):
        with self.lock:
            if self.pack is None:
                self.pack = Pack(self.paths)
            self.pack.recheck()
            return self.pack

    def job(self, ident):
        path = self.paths.artifact("jobs", ident).with_suffix(".json")
        value = read(path)
        if value is None:
            raise ValueError("Job not found")
        return value

    def submit(self, body):
        c = planner.validate(body)
        if not c["start_id"] and not c["custom_start"]:
            c["start_id"] = planner.resolve_start(self.data(), c)["id"]
        token = digest(c)
        with self.lock:
            if self.active:
                current = self.job(self.active)
                if current["input_token"] == token:
                    return current
                raise HTTPException(
                    409,
                    "One analytical job at a time. Cancel the current job before starting changed inputs.",
                )
            ident = uuid.uuid4().hex
            value = dict(
                id=ident,
                status="pending",
                settings=c,
                input_token=token,
                created_utc=now(),
                updated_utc=now(),
                stage="pending",
                progress=0,
                total=1,
                message="Queued in dedicated TrailScout worker",
            )
            atomic(self.paths.artifact("jobs", ident).with_suffix(".json"), value)
            self.active = ident
            self.cancel_event = threading.Event()
            self.worker = threading.Thread(
                target=self.run, args=(ident,), daemon=True, name="trailscout-analysis"
            )
            self.worker.start()
            return value

    def prepare(self, body):
        with self.lock:
            if self.active:
                raise HTTPException(409, "One analytical/preparation job at a time")
            body = dict(body)
            resume = body.pop("resume_id", None)
            prior = self.job(resume) if resume else None
            if prior and (prior.get("kind") != "prepare" or prior["settings"] != body):
                raise HTTPException(
                    409,
                    "Preparation inputs changed; use a new bounded preparation. Prior checkpoint retained.",
                )
            ident = resume or uuid.uuid4().hex
            attempts = (prior or {}).get("attempts", [])
            if prior:
                attempts = attempts + [
                    dict(
                        status=prior["status"],
                        error=prior.get("error"),
                        updated_utc=prior["updated_utc"],
                    )
                ]
            value = dict(
                id=ident,
                kind="prepare",
                status="pending",
                settings=body,
                input_token=digest(body),
                created_utc=(prior or {}).get("created_utc", now()),
                updated_utc=now(),
                stage="pending",
                progress=0,
                total=1,
                message="Preparing bounded official access snapshots",
                attempts=attempts,
            )
            atomic(self.paths.artifact("jobs", ident).with_suffix(".json"), value)
            self.active = ident
            self.cancel_event = threading.Event()
            self.worker = threading.Thread(
                target=self.run, args=(ident,), daemon=True, name="trailscout-prepare"
            )
            self.worker.start()
            return value

    def run(self, ident):
        value = self.job(ident)
        path = self.paths.artifact("jobs", ident).with_suffix(".json")

        def cancel():
            if self.cancel_event.is_set():
                raise Cancelled()

        def progress(stage, n, total, message):
            cancel()
            value.update(
                status="running",
                stage=stage,
                progress=n,
                total=total,
                message=message,
                updated_utc=now(),
            )
            atomic(path, value)

        try:
            if value.get("kind") == "prepare":
                result = preparation.prepare(
                    self.paths,
                    value["settings"],
                    self.paths.artifact("imports", ident),
                    progress,
                    cancel,
                )
                self.pack = None
                value.update(
                    status="completed",
                    message="Bounded source snapshots validated and published; recalculate plans",
                    preparation=result,
                )
                return
            folder = self.paths.artifact("analyses", ident)
            result = planner.calculate(
                self.paths, self.data(), value["settings"], folder, progress, cancel
            )
            cancel()
            seal(folder / "result.json")
            value.update(
                status="completed",
                analysis_id=ident,
                message=result.get(
                    "empty_reason", "Comparison ready; previews are not saved plans"
                ),
            )
        except Cancelled:
            value.update(
                status="cancelled",
                error="Cancelled. Completed sealed source/habitat/mask artifacts retained. Retry the same inputs to reuse them.",
            )
        except Exception as error:
            value.update(
                status="failed", error=str(error), diagnostic=traceback.format_exc()
            )
        finally:
            value["updated_utc"] = now()
            atomic(path, value)
            with self.lock:
                self.active = None

    def result(self, ident):
        folder = self.paths.artifact("analyses", ident)
        return read(checked(folder / "result.json"))

    def saved(self, ident):
        return read(checked(self.paths.artifact("plans", ident).with_suffix(".json")))

    def save(self, body):
        with self.lock:
            r = self.result(body["analysis_id"])
            c = planner.validate(body["settings"])
            if digest(c) != r["input_token"]:
                raise HTTPException(
                    409,
                    "Edited inputs are stale. Recalculate before saving this preview.",
                )
            if r["implementation"] != implementation():
                raise HTTPException(
                    409,
                    "Planner implementation changed. Recalculate; prior saved plans remain available.",
                )
            self.data().recheck()
            if self.data().revision != r["source_revision"]:
                raise HTTPException(
                    409, "Sources changed. Recalculate with current source revision."
                )
            if r.get("practical") or r.get("practical_plan"):
                from practical_glassing.package import CommunityPackage, installed_root

                if (
                    CommunityPackage(installed_root(self.paths)).spec["id"]
                    != (r.get("practical_plan") or r.get("practical"))["package"]
                ):
                    raise HTTPException(
                        409,
                        "Community package changed; recalculate before saving this preview",
                    )
            option = next(
                (o for o in r["options"] if o["id"] == body["option_id"]), None
            )
            if not option:
                raise ValueError("Option not found in analysis")
            mode = body.get("mode", "am")
            if not option["schedules"].get(mode, {}).get("feasible"):
                raise ValueError(
                    "Selected time variant is not feasible. Review its explicit reasons or adjust inputs."
                )
            parent = body.get("parent_id")
            family = parent
            if parent:
                prior = self.saved(parent)
                family = prior["family"]
                head = read(self.paths.state / "heads" / f"{family}.json")
                if head["id"] != parent:
                    raise HTTPException(
                        409,
                        "Another saved version exists. Reopen the latest version before adjusting; no history overwritten.",
                    )
            ident = uuid.uuid4().hex
            family = family or ident
            value = dict(
                version=2 if r.get("practical_plan") else 1,
                id=ident,
                family=family,
                parent_id=parent,
                name=str(body.get("name") or "TrailScout outing")[:120],
                created_utc=now(),
                analysis_id=r["analysis_id"],
                settings=c,
                source_revision=r["source_revision"],
                source=r["source"],
                implementation=r["implementation"],
                start=r["start"],
                mode=mode,
                option=option,
                warnings=r["warnings"],
            )
            if r.get("practical"):
                value["practical"] = r["practical"]
            if r.get("practical_plan"):
                value["practical_plan"] = r["practical_plan"]
            p = self.paths.artifact("plans", ident).with_suffix(".json")
            atomic(p, value)
            seal(p)
            atomic(self.paths.state / "heads" / f"{family}.json", dict(id=ident))
            return value


def create_app(paths):
    service = Service(paths)

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            service.close()

    app = FastAPI(title="TrailScout local planner", lifespan=lifespan)
    app.state.service = service

    @app.middleware("http")
    async def local_mutations(request: Request, call_next):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if origin and origin != str(request.base_url).rstrip("/"):
                return Response("Local same-origin requests only", status_code=403)
            if int(request.headers.get("content-length", "0")) > 2_000_000:
                return Response("Request exceeds 2 MB", status_code=413)
        return await call_next(request)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return Response(
            json.dumps({"detail": str(exc)}),
            status_code=422,
            media_type="application/json",
        )

    @app.exception_handler(FileNotFoundError)
    async def missing(request, exc):
        return Response(
            json.dumps(
                {
                    "detail": f"Missing source/artifact: {exc}. Restore/import data or retry; saved work is retained."
                }
            ),
            status_code=404,
            media_type="application/json",
        )

    @app.post("/api/sources/import")
    def import_source(body: dict):
        with service.lock:
            if service.active:
                raise HTTPException(
                    409, "Finish or cancel current work before changing sources"
                )
            result = preparation.import_snapshot(paths, body)
            service.pack = None
            return result

    @app.post("/api/sources/prepare")
    def prepare_sources(body: dict):
        return service.prepare(body)

    @app.get("/api/health")
    def health():
        return dict(
            status="ok",
            app="TrailScout",
            state=str(paths.state),
            source=str(paths.source),
            active=service.active,
            implementation=implementation(),
            source_revision=service.pack.revision if service.pack else None,
        )

    @app.get("/api/context")
    def context(
        date: str = "2026-10-31", vehicle: str = "truck", width: float | None = None
    ):
        from osgeo import gdal
        from .sources import Terrain, feature, collection, access

        pack = service.data()
        folder = paths.state / "overview" / pack.revision
        folder.mkdir(parents=True, exist_ok=True)
        metadata = read(folder / "map.json")
        if metadata is None:
            terrain = Terrain(
                gdal.Warp(
                    "",
                    str(pack.asset(pack.spec["data"]["dem"]["path"])),
                    format="MEM",
                    xRes=100,
                    yRes=100,
                    resampleAlg="bilinear",
                )
            )
            corners = render.relief(terrain, folder / "relief.png")
            metadata = dict(corners=corners)
            atomic(folder / "map.json", metadata)
        day = Date.fromisoformat(date)
        lines = [
            feature(
                r["geometry"].simplify(5),
                id=r["id"],
                name=r["properties"].get("trail_name", r["properties"].get("name")),
                kind="closed-road" if r["motor_closed"] else r["kind"],
                access=access(r, day, vehicle, width_inches=width),
            )
            for r in pack.network
        ]
        return dict(
            map=dict(
                corners=metadata["corners"],
                relief_url="/api/overview/" + pack.revision,
                network=collection(lines),
                target_boundary=feature(pack.boundary),
                spurs=collection([]),
            ),
            candidates=[],
        )

    @app.get("/api/overview/{revision}")
    def overview(revision: str):
        path = paths.artifact("overview", revision) / "relief.png"
        return FileResponse(
            path,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    @app.get("/api/areas")
    def areas():
        summary = service.data().summary()
        from practical_glassing.package import CommunityPackage, installed_root

        try:
            spec = CommunityPackage(installed_root(paths)).spec
            summary["practical"] = dict(
                status="ready", release=spec["release"], id=spec["id"]
            )
        except (ValueError, FileNotFoundError, KeyError) as error:
            summary["practical"] = dict(status="unavailable", reason=str(error))
        return [summary]

    @app.post("/api/start-preview")
    def start_preview(body: dict):
        from shapely.geometry import Point
        from .sources import project, geographic

        pack = service.data()
        row = next((r for r in pack.network if r["id"] == body.get("segment")), None)
        if row is None:
            raise ValueError("Select an intended mapped segment")
        point = project(Point(body["longitude"], body["latitude"]))
        offset = point.distance(row["geometry"])
        if offset > 100:
            raise ValueError(
                "Click closer to the intended mapped segment (within 100 m); no arbitrary nearest-line connector is used"
            )
        exact = row["geometry"].interpolate(row["geometry"].project(point))
        lon, lat = geographic(exact).coords[0]
        return dict(
            longitude=lon,
            latitude=lat,
            segment=row["id"],
            label="Owner selected "
            + str(row["properties"].get("trail_name", row["properties"].get("name"))),
            click_offset_m=offset,
        )

    @app.post("/api/starts")
    def edited_entries(body: dict):
        c = planner.validate(body)
        return starts(
            service.data(),
            Date.fromisoformat(c["date"]),
            c["vehicle"],
            c["restrictions"],
            c.get("vehicle_width_inches"),
        )

    @app.get("/api/starts")
    def entry(
        date: str = "2026-10-31", vehicle: str = "truck", width: float | None = None
    ):
        return starts(
            service.data(), Date.fromisoformat(date), vehicle, width_inches=width
        )

    @app.get("/api/profiles")
    def preset():
        return profiles.PROFILES

    @app.get("/api/draft")
    def draft():
        return read(paths.state / "draft.json", {})

    @app.put("/api/draft")
    def draft_save(body: dict):
        # Drafts are separate from immutable analyses and saves; exact owner edits
        # remain available after cancellation/reload, including infeasible settings.
        atomic(
            paths.state / "draft.json",
            dict(settings=planner.validate(body["settings"]), updated_utc=now()),
        )
        return dict(saved=True)

    @app.post("/api/jobs")
    def submit(body: dict):
        return service.submit(body)

    @app.get("/api/jobs")
    def jobs():
        return sorted(
            [read(p) for p in (paths.state / "jobs").glob("*.json")],
            key=lambda r: r["created_utc"],
            reverse=True,
        )[:30]

    @app.get("/api/jobs/{ident}")
    def status(ident: str):
        return service.job(ident)

    @app.post("/api/jobs/{ident}/cancel")
    def cancel(ident: str):
        with service.lock:
            value = service.job(ident)
            if service.active == ident:
                service.cancel_event.set()
                return dict(status="cancelling", id=ident)
            return value

    @app.get("/api/analyses/{ident}")
    def result(ident: str):
        return service.result(ident)

    @app.get("/api/plans")
    def plans():
        out = []
        for p in (paths.state / "plans").glob("*.json"):
            if ".seal." in p.name:
                continue
            try:
                v = read(checked(p))
                out.append(
                    {
                        k: v[k]
                        for k in (
                            "id",
                            "family",
                            "parent_id",
                            "name",
                            "created_utc",
                            "mode",
                            "analysis_id",
                        )
                    }
                )
            except (OSError, ValueError) as error:
                out.append(
                    dict(id=p.stem, error=str(error), name="Unavailable saved version")
                )
        return sorted(out, key=lambda v: v.get("created_utc", ""), reverse=True)

    @app.post("/api/plans")
    def save(body: dict):
        return service.save(body)

    @app.get("/api/plans/{ident}")
    def plan(ident: str):
        return service.saved(ident)

    @app.get("/api/plans/{ident}/export/{kind}")
    def export(ident: str, kind: str):
        v = service.saved(ident)
        if kind == "json":
            data = json.dumps(v, indent=2).encode()
            mime = "application/json"
        elif kind == "geojson":
            data = json.dumps(render.geojson(v), indent=2).encode()
            mime = "application/geo+json"
        elif kind == "gpx":
            data = render.gpx(v)
            mime = "application/gpx+xml"
        elif kind == "md":
            data = render.field_summary(v).encode()
            mime = "text/markdown"
        else:
            raise ValueError("Choose json, geojson, gpx or md")
        return Response(
            data,
            media_type=mime,
            headers={
                "Content-Disposition": f'attachment; filename="trailscout-{ident[:8]}.{kind}"'
            },
        )

    @app.get("/artifacts/{ident}/{name}")
    def artifact(ident: str, name: str):
        if not (
            name == "relief.png"
            or (
                name.startswith("coverage-")
                and name.endswith(".png")
                and len(name) == 45
            )
        ):
            raise ValueError("Invalid map artifact")
        return FileResponse(
            paths.artifact("analyses", ident) / name,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    @app.get("/practical/{ident}/{name}")
    def practical_artifact(ident: str, name: str):
        import re

        if name not in (
            "review.html",
            "comparison.json",
            "points.csv",
            "community-context.tif",
            "shortlist.gpx",
            "community.png",
            "habitat.png",
            "unknown.png",
        ) and not re.fullmatch(
            r"(?:view-[a-f0-9]{16}|union-(?:terrain|fall_mixed_v1|community_fixed_observation|observation_fixed_habitat|combined))\.png",
            name,
        ):
            raise ValueError("Invalid practical report artifact")
        folder = paths.artifact("analyses", ident) / "practical"
        from practical_glassing.packet import artifact

        return FileResponse(artifact(folder, name))

    static = ROOT / "trail_scout/web/dist"
    if static.is_dir():
        app.mount("/", StaticFiles(directory=static, html=True), name="browser")
    else:

        @app.get("/")
        def no_build():
            return Response(
                "TrailScout browser assets missing. Run ./trailscout build, then restart.",
                status_code=503,
            )

    return app


def main():
    parser = argparse.ArgumentParser(
        description="Isolated TrailScout local application"
    )
    parser.add_argument(
        "command", choices=("serve", "plan", "inventory"), nargs="?", default="serve"
    )
    parser.add_argument(
        "--source-root",
        default=os.environ.get(
            "TRAILSCOUT_SOURCE_ROOT", "/home/tanner/Desktop/huntmaps2"
        ),
    )
    parser.add_argument(
        "--state", default=os.environ.get("TRAILSCOUT_STATE", str(ROOT / ".trailscout"))
    )
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--inputs")
    parser.add_argument("--out")
    args = parser.parse_args()
    paths = Paths(Path(args.source_root), Path(args.state))
    if args.command == "serve":
        uvicorn.run(
            create_app(paths), host="127.0.0.1", port=args.port, access_log=False
        )
    elif args.command == "inventory":
        print(json.dumps(Pack(paths).summary(), indent=2))
    else:
        with StateLease(paths.state):
            body = read(args.inputs, {}) if args.inputs else {}
            ident = uuid.uuid4().hex
            result = planner.calculate(
                paths,
                Pack(paths),
                body,
                paths.artifact("analyses", ident),
                lambda stage, n, total, message: print(
                    f"{stage} {n}/{total}: {message}", flush=True
                ),
            )
            seal(paths.artifact("analyses", ident) / "result.json")
            if args.out:
                atomic(args.out, result)
            print(
                json.dumps(
                    dict(
                        analysis_id=ident,
                        options=len(result["options"]),
                        recommended=result["recommended"],
                        performance=result["performance"],
                    )
                )
            )


if __name__ == "__main__":
    main()
