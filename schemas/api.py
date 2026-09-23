"""API request and response schemas for FastAPI endpoints."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from schemas.canonical import MonitoringObservation
from services.anomaly.detector import AnomalyStatus
from services.forecasting.base import PredictionPoint


class HealthResponse(BaseModel):
    """System health check response with genuine provider status indicators."""

    status: str = Field(default="ok", description="Overall health status: ok | degraded | unhealthy")
    service: str = Field(default="air-resilience-api", description="Service name")
    version: str = Field(default="0.1.0", description="API version")
    environment: str = Field(default="development", description="Runtime environment")
    data_mode: str = Field(default="HISTORICAL_REPLAY", description="Current data mode: HISTORICAL_REPLAY | LIVE")
    timestamp: datetime = Field(description="Server timestamp")
    providers: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Genuine status indicators for CPCB, IMD, FIRMS, Sentinel-5P, Gemini, Forecast, Federation",
    )


class StationSeriesResponse(BaseModel):
    """Response for GET /api/v1/stations/{station_id}/series."""

    station_id: str
    station_name: str
    observation_count: int
    observations: List[MonitoringObservation]
    baseline: Dict[str, Any] = Field(
        description="Local historical baseline summary (mean, median, std, min, max)"
    )
    gaps_detected: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Detected gaps in hourly telemetry",
    )
    quality_flags_summary: Dict[str, int] = Field(
        default_factory=dict,
        description="Aggregated count of quality flags across series",
    )
    data_source: str = Field(
        default="fixture",
        description="Label indicating data provenance (fixture | live)",
    )


class AnomalyRequest(BaseModel):
    """Request model for POST /api/v1/anomaly."""

    observation: MonitoringObservation = Field(
        ...,
        description="Target observation to evaluate for anomalies",
    )
    history: List[MonitoringObservation] = Field(
        default_factory=list,
        description="Historical observations from the same station to compute local baseline",
    )


class AnomalyResponse(BaseModel):
    """Response model for POST /api/v1/anomaly matching Phase 3A contract."""

    station_id: str
    timestamp: datetime
    pm25: float
    expected_pm25: float
    anomaly_score: float
    status: AnomalyStatus
    explanation: Optional[str] = None
    baseline_std: Optional[float] = None
