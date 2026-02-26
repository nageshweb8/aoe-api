"""AOE API — FastAPI application factory."""


import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.middleware.audit import AuditMiddleware
from app.schemas.common import HealthResponse

# Existing (legacy) COI routes — keep untouched
from app.routers.coi import router as coi_router

# v1 routers
from app.routers.v1.vendors import router as vendors_v1_router


def _configure_logging() -> None:
    """Set up structured logging for the application."""
    level = logging.DEBUG if settings.app_env == "development" else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )
    # Quiet noisy libraries
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def create_app() -> FastAPI:
    _configure_logging()

    app = FastAPI(
        title=settings.app_name,
        version="2.0.0",
        docs_url="/docs" if settings.app_env == "development" else None,
        redoc_url="/redoc" if settings.app_env == "development" else None,
    )

    # --- CORS ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # --- Audit middleware ---
    app.add_middleware(AuditMiddleware)

    # --- Global exception handlers ---
    register_exception_handlers(app)

    # --- Existing COI routes (unchanged — /api/coi/*) ---
    app.include_router(coi_router)

    # --- v1 API routes (/api/v1/*) ---
    app.include_router(vendors_v1_router, prefix="/api/v1")

    # --- Health check ---
    @app.get("/health", response_model=HealthResponse, tags=["Health"])
    async def health():
        return HealthResponse(app=settings.app_name, env=settings.app_env)

    return app


app = create_app()
