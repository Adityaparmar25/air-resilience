"""Forecast Provider Abstraction.

Defines the abstract interface and canonical contracts for PM2.5 forecasting.
Numerical forecasts must come from predictive models/heuristics, never from LLM prose.
Never invent accuracy numbers (Decision D-008).
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator

from schemas.canonical import MonitoringObservation


class PredictionPoint(BaseModel):
    """Single-point forecast in the future time horizon."""

    timestamp: datetime = Field(..., description="Forecast target timestamp (UTC)")
    pm25_forecast: float = Field(..., ge=0.0, description="Predicted PM2.5 concentration (ug/m3)")
    lower_bound: float = Field(..., ge=0.0, description="Lower prediction bound (e.g. 95% CI)")
    upper_bound: float = Field(..., ge=0.0, description="Upper prediction bound (e.g. 95% CI)")

    @model_validator(mode="after")
    def validate_bounds(self) -> "PredictionPoint":
        if self.lower_bound > self.pm25_forecast:
            raise ValueError(f"lower_bound ({self.lower_bound}) cannot exceed pm25_forecast ({self.pm25_forecast})")
        if self.upper_bound < self.pm25_forecast:
            raise ValueError(f"upper_bound ({self.upper_bound}) cannot be less than pm25_forecast ({self.pm25_forecast})")
        return self


class ForecastRequest(BaseModel):
    """Request model for PM2.5 horizon forecasting."""

    station_id: str = Field(..., min_length=1, description="Target station identifier")
    history: List[MonitoringObservation] = Field(
        ...,
        min_length=1,
        description="Historical observations used to condition the forecast",
    )
    horizon: int = Field(
        default=24,
        ge=1,
        le=72,
        description="Forecast horizon in hours (default 24 hours)",
    )


class ForecastResponse(BaseModel):
    """Forecast response adhering strictly to Phase 3A specification."""

    station_id: str
    horizon: int
    predictions: List[PredictionPoint]
    provider_type: str = Field(
        default="development_baseline",
        description="Identifies provider: 'development_baseline' | 'bigquery_timesfm'",
    )
    measured_metrics: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Measured validation metrics (MAE, RMSE, MAPE) on benchmark data; never invented",
    )

    def to_contract_dict(self) -> Dict[str, Any]:
        """Produce the exact dictionary required by Phase 3A specification."""
        res: Dict[str, Any] = {
            "station_id": self.station_id,
            "horizon": self.horizon,
            "provider_type": self.provider_type,
            "predictions": [
                {
                    "timestamp": p.timestamp.isoformat(),
                    "pm25_forecast": p.pm25_forecast,
                    "lower_bound": p.lower_bound,
                    "upper_bound": p.upper_bound,
                }
                for p in self.predictions
            ],
        }
        if self.measured_metrics:
            res["measured_metrics"] = self.measured_metrics
        return res


class ForecastProvider(ABC):
    """Abstract interface for all PM2.5 forecast providers."""

    @abstractmethod
    def forecast(self, request: ForecastRequest) -> ForecastResponse:
        """Produce horizon forecast from request observations."""
        pass
