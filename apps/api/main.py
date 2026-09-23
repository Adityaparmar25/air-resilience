"""Main FastAPI application entrypoint for Air Resilience Network."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.config import get_settings
from apps.api.routes import router
from services.infrastructure.middleware import (
    CorrelationIdMiddleware,
    register_safe_exception_handlers,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context for startup validation and shutdown."""
    settings = get_settings()
    # Validate production prerequisites when running in production
    settings.validate_production_readiness()
    yield


def create_app() -> FastAPI:
    """Application factory for FastAPI app with production security and observability."""
    settings = get_settings()

    app = FastAPI(
        title="Air Resilience Network API",
        description=(
            "Clean Air & Climate Resilience Platform: CPCB ingestion, multimodal Gemini analysis, "
            "spatial evidence fusion, authority incident dispatch, and federated multi-city learning."
        ),
        version="0.2.0",
        lifespan=lifespan,
    )

    # Correlation ID middleware
    app.add_middleware(CorrelationIdMiddleware)

    # Cross-Origin Resource Sharing middleware
    cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    if "*" in cors_origins or not cors_origins:
        cors_origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Safe production error handlers (no tracebacks leaked)
    register_safe_exception_handlers(app)

    # Cloud Run readiness probe alias
    @app.get("/healthz", tags=["System"])
    def healthz():
        return {"status": "ok", "service": "air-resilience-api"}

    app.include_router(router)
    return app


app = create_app()
