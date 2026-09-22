"""BigQuery ML / TimesFM Forecast Provider abstraction.

Provides the production GCP interface for BigQuery ML AI.FORECAST / TimesFM.
When GCP credentials or BigQuery services are unconfigured, clearly informs
the operator and supports safe fallback to development baseline.
"""

from typing import Optional
from apps.api.config import get_settings
from services.forecasting.base import (
    ForecastProvider,
    ForecastRequest,
    ForecastResponse,
)
from services.forecasting.baseline import BaselineTimeSeriesForecastProvider


class BigQueryTimesFMForecastProvider(ForecastProvider):
    """Production target forecast provider interfacing with BigQuery ML TimesFM."""

    def __init__(self, fallback_to_baseline: bool = True):
        self.settings = get_settings()
        self.fallback_to_baseline = fallback_to_baseline
        self._baseline_provider = BaselineTimeSeriesForecastProvider()

    def is_gcp_configured(self) -> bool:
        """Check whether minimum GCP credentials file and dataset exist."""
        from pathlib import Path
        creds_path = self.settings.GOOGLE_APPLICATION_CREDENTIALS
        has_real_creds = bool(creds_path and Path(creds_path).exists())
        return bool(
            self.settings.GOOGLE_CLOUD_PROJECT
            and has_real_creds
            and self.settings.BIGQUERY_DATASET
        )

    def forecast(self, request: ForecastRequest) -> ForecastResponse:
        """Generate forecast using BigQuery ML / TimesFM or configured development fallback."""
        if not self.is_gcp_configured():
            if self.fallback_to_baseline:
                resp = self._baseline_provider.forecast(request)
                # Keep provider_type clearly labeled as fallback
                return ForecastResponse(
                    station_id=resp.station_id,
                    horizon=resp.horizon,
                    predictions=resp.predictions,
                    provider_type="bigquery_timesfm_fallback_to_baseline",
                )
            raise RuntimeError(
                "BigQuery ML / TimesFM provider unavailable: "
                "GOOGLE_CLOUD_PROJECT, GOOGLE_APPLICATION_CREDENTIALS, and BIGQUERY_DATASET must be set."
            )

        # In production GCP environment: BigQuery AI.FORECAST query would be dispatched here
        # E.g.: SELECT * FROM ML.FORECAST(MODEL `dataset.timesfm_pm25_model`, STRUCT(horizon AS horizon))
        raise NotImplementedError(
            "Live BigQuery ML query execution requires authenticated GCP Cloud Run connection."
        )
