"""Local FastAPI application. Optional browser basemap; no arbitrary commands or historical run writes."""

from contextlib import asynccontextmanager
from urllib.parse import urlparse
from fastapi import FastAPI
from fastapi.responses import Response, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .catalog import ROOT
from .jobs import Jobs
from .config import current, configured


def create_app(config=None):
    config = config or current()
    with configured(config):
        from .storage import migrate_records

        migrate_records()
        jobs = Jobs()
        jobs.reconcile()

    @asynccontextmanager
    async def life(app):
        yield
        jobs.shutdown()

    app = FastAPI(lifespan=life)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )
    app.state.jobs = jobs
    app.state.config = config
    from .maintenance import router as maintenance_router

    app.include_router(maintenance_router)

    @app.middleware("http")
    async def local_only(request, call_next):
        if request.method not in ["GET", "HEAD", "OPTIONS"]:
            origin = request.headers.get("origin")
            if request.headers.get("x-huntmaps") != "local" or (
                origin and urlparse(origin).netloc != request.headers.get("host")
            ):
                return JSONResponse(
                    {"detail": "Local app request required"}, status_code=403
                )
        with configured(config):
            return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def invalid_payload(request, error):
        return JSONResponse(
            status_code=400, content={"detail": "Invalid request: " + str(error)}
        )

    @app.exception_handler(OSError)
    async def file_unavailable(request, error):
        return JSONResponse(
            status_code=400,
            content={
                "detail": f"Local file unavailable: {error}. Preserve existing records; restore the named file or a record backup."
            },
        )

    @app.exception_handler(ValueError)
    async def invalid(request, error):
        return JSONResponse(status_code=400, content={"detail": str(error)})

    from .api_routes import api_router

    app.include_router(api_router(jobs))
    from .scouting_api import router as scouting_router

    app.include_router(scouting_router(jobs))

    dist = ROOT / "gui/frontend/dist"
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/")
        def index():
            return FileResponse(dist / "index.html")

    return app
