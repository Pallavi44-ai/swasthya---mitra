from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import account, auth, profile, security
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import init_db

log = logging.getLogger("swasthya")

DISCLAIMER = (
    "Swasthya Mitra is a support tool. It does not replace a doctor, give a diagnosis, prescribe "
    "medicines or change doses. In an emergency call 108."
)


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cache-Control"] = "no-store"  # API responses contain personal health data
        return resp


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    init_db()
    from app.services import rag

    rag.ensure_knowledge_base()
    log.info("Swasthya Mitra API started (env=%s)", get_settings().app_env)
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="Swasthya Mitra API",
        version="1.0.0",
        description=DISCLAIMER,
        lifespan=lifespan,
        docs_url=None if s.is_production else "/docs",
        redoc_url=None,
    )
    app.add_middleware(SecurityHeaders)
    app.add_middleware(
        CORSMiddleware, allow_origins=s.cors_origin_list, allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Content-Type", "Authorization"],
    )

    api = APIRouter(prefix="/api")
    api.include_router(auth.router)
    api.include_router(account.router)
    api.include_router(profile.router)
    api.include_router(security.router)
    # Feature routers are registered in _register_features to keep imports lazy for fast tests
    _register_features(api)
    app.include_router(api)

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error: %s", type(exc).__name__)  # no request bodies in logs
        return JSONResponse({"detail": "Something went wrong. Please try again."}, status_code=500)

    return app


def _register_features(api: APIRouter) -> None:
    import importlib

    for name in ("chat", "voice", "prescriptions", "reminders", "emergency", "system"):
        try:
            mod = importlib.import_module(f"app.api.routes.{name}")
        except ModuleNotFoundError as exc:
            if exc.name == f"app.api.routes.{name}":
                continue  # module not built yet
            raise
        api.include_router(mod.router)


app = create_app()
