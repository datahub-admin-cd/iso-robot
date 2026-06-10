from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import aiosqlite
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from iso_robot.config import get_settings
from iso_robot.errors import APIError
from iso_robot.handlers import auth
from iso_robot.handlers.health import health
from iso_robot.domain.repair_storage_paths import repair_storage_paths
from iso_robot.repositories.schema import ensure_schema
from iso_robot.middleware import SessionValidationMiddleware
from iso_robot.routers.v1 import router as v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(level=level)
    db_path = settings.resolved_database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(db_path)) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys = ON")
        await ensure_schema(conn)
        try:
            await repair_storage_paths(conn, settings)
        except Exception:
            logging.getLogger(__name__).exception(
                "Storage path repair failed; continuing startup"
            )
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="ISO Robot API", lifespan=lifespan)
    app.add_middleware(SessionValidationMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Refresh-Token"],
    )

    @app.exception_handler(APIError)
    async def api_error_handler(_request: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict):
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": str(exc.detail), "code": "http_error"},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Request validation failed",
                "code": "validation_error",
            },
        )

    @app.get("/", tags=["health"])
    async def root() -> dict[str, str]:
        return {
            "status": "ok",
            "health": "/health",
            "api": "/api/v1",
            "docs": "/docs",
        }

    app.add_api_route("/health", health, methods=["GET"], tags=["health"])
    app.include_router(v1_router, prefix="/api/v1")
    # Convenience aliases (same handlers as /api/v1/auth/*) for clients that omit the prefix.
    app.add_api_route("/auth/login", auth.login, methods=["POST"], tags=["auth"])
    app.add_api_route("/auth/register", auth.register_user, methods=["POST"], tags=["auth"])
    return app


app = create_app()
