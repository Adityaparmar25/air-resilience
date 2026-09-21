"""Main FastAPI application entrypoint for Air Resilience Network."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.config import get_settings
from apps.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context for startup validation and shutdown."""
    settings = get_settings()
    # Validate production prerequisites when running in production
    settings.validate_production_readiness()
    yield


def create_app() -> FastAPI:
    """Application factory for FastAPI app."""
    settings = get_settings()

    app = FastAPI(
        title="Air Resilience Network API",
        description=(
            "Phase 3A Milestone 1 API: CPCB data ingestion, canonical normalization, "
            "data-quality pipeline, explainable anomaly detection, and forecast abstraction."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    # Cross-Origin Resource Sharing middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    return app


app = create_app()
