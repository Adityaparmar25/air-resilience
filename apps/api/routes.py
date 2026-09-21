"""FastAPI route definitions for Milestone 1 endpoints."""

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from apps.api.config import get_settings
from schemas.api import (
    AnomalyRequest,
    AnomalyResponse,
    HealthResponse,
    StationSeriesResponse,
)
from schemas.canonical import MonitoringObservation
from services.anomaly.detector import (
    AnomalyDetectionConfig,
    ExplainableAnomalyDetector,
)
from services.forecasting.base import (
    ForecastRequest,
    ForecastResponse,
)
from services.forecasting.baseline import BaselineTimeSeriesForecastProvider
from services.forecasting.time_series_service import TimeSeriesService
from services.ingestion.cpcb_adapter import CPCBAdapter
from services.ingestion.quality_pipeline import DataQualityPipeline

router = APIRouter()

# Fixture directory for development and testing
FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "fixtures"


@router.get("/health", response_model=HealthResponse, tags=["System"])
def health_check() -> HealthResponse:
    """System health check endpoint."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service="air-resilience-api",
        version="0.1.0",
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
    )


@router.get(
    "/api/v1/stations/{station_id}/series",
    response_model=StationSeriesResponse,
    tags=["Monitoring"],
    responses={
        404: {"description": "Station not found in monitoring network or fixtures"},
    },
)
def get_station_series(
    station_id: str,
    limit: int = Query(default=48, ge=1, le=168, description="Maximum observations to return"),
    scenario: Optional[str] = Query(
        default=None,
        description="Optional fixture scenario: 'normal' | 'elevated' | 'missing' | 'spike'",
    ),
) -> StationSeriesResponse:
    """Retrieve chronologically ordered time series and quality checks for a monitoring station."""
    # Determine fixture source based on scenario or default normal series
    scenario_files = {
        "normal": "normal_series.json",
        "elevated": "elevated_series.json",
        "missing": "missing_observations.json",
        "spike": "suspicious_spike.json",
    }
    fixture_file = scenario_files.get(scenario or "normal", "normal_series.json")
    fixture_path = FIXTURE_DIR / fixture_file

    if not fixture_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Development fixture file missing: {fixture_path}",
        )

    adapter = CPCBAdapter(default_fixture_path=str(fixture_path))
    pipeline = DataQualityPipeline(adapter=adapter)

    # Fetch raw observations for station
    raw_records = adapter.fetch(station_id=station_id, is_fixture=True)
    if not raw_records:
        # Check if station exists in station registry
        if station_id.upper() in CPCBAdapter.STATION_REGISTRY:
            # If in registry but no observations in this specific scenario file
            raw_records = adapter.fetch(is_fixture=True)
            # Filter if station matches
            raw_records = [
                r for r in raw_records
                if str(adapter._extract_first_match(r, adapter.STATION_ID_KEYS) or "").upper()
                == station_id.upper()
            ]

    if not raw_records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Station '{station_id}' not found in active observations or fixtures",
        )

    # Process batch through data quality pipeline
    quality_records = pipeline.process_batch(raw_records, is_fixture=True)
    observations = [qr.observation for qr in quality_records]

    # Chronological sort and limit
    sorted_obs = TimeSeriesService.sort_chronological(observations, ascending=True)
    recent_obs = sorted_obs[-limit:] if len(sorted_obs) > limit else sorted_obs

    # Baseline and gaps calculation
    baseline = TimeSeriesService.compute_local_baseline(recent_obs)
    gaps = TimeSeriesService.detect_missing_timestamps(recent_obs)

    # Quality flags aggregation
    all_flags: List[str] = []
    for qr in quality_records:
        all_flags.extend([f.value for f in qr.flags])
    flag_counts = dict(Counter(all_flags))

    station_name = recent_obs[0].station_name if recent_obs else station_id

    return StationSeriesResponse(
        station_id=station_id,
        station_name=station_name,
        observation_count=len(recent_obs),
        observations=recent_obs,
        baseline=baseline,
        gaps_detected=gaps,
        quality_flags_summary=flag_counts,
        data_source="fixture",
    )


@router.post(
    "/api/v1/anomaly",
    response_model=AnomalyResponse,
    tags=["ML & Analytics"],
    responses={
        422: {"description": "Validation error: PM2.5 measurement is null"},
    },
)
def detect_anomaly(request: AnomalyRequest) -> AnomalyResponse:
    """Evaluate target observation against historical baseline for explainable anomaly detection."""
    if request.observation.pm25 is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot detect anomaly: observation pm25 measurement is null/unavailable",
        )

    detector = ExplainableAnomalyDetector()
    try:
        result = detector.detect(
            observation=request.observation,
            history=request.history,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    return AnomalyResponse(
        station_id=result.station_id,
        timestamp=result.timestamp,
        pm25=result.pm25,
        expected_pm25=result.expected_pm25,
        anomaly_score=result.anomaly_score,
        status=result.status,
        explanation=result.explanation,
        baseline_std=result.baseline_std,
    )


@router.post(
    "/api/v1/forecast",
    response_model=ForecastResponse,
    tags=["ML & Analytics"],
    responses={
        400: {"description": "History does not contain observations for specified station"},
        422: {"description": "Invalid horizon or empty history"},
    },
)
def generate_forecast(request: ForecastRequest) -> ForecastResponse:
    """Produce PM2.5 horizon forecast using the forecast provider abstraction."""
    provider = BaselineTimeSeriesForecastProvider()
    try:
        response = provider.forecast(request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return response
