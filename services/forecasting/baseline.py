"""Baseline Time-Series Forecast Provider.

Implements a clearly labeled development forecast provider using autoregressive decay,
diurnal cycle alignment, and empirical confidence intervals.
Does not invent accuracy numbers.
"""

from datetime import timedelta
import math
from typing import List
import numpy as np

from services.forecasting.base import (
    ForecastProvider,
    ForecastRequest,
    ForecastResponse,
    PredictionPoint,
)
from services.forecasting.time_series_service import (
    LocalHistoricalBaselineComputer,
    TimeSeriesService,
)


class BaselineTimeSeriesForecastProvider(ForecastProvider):
    """Development baseline forecast provider using local historical trends and diurnal adjustment."""

    def __init__(self, autoregressive_weight: float = 0.85):
        """Configure forecast provider.

        autoregressive_weight: Weight given to recent observation vs diurnal historical mean.
        """
        self.autoregressive_weight = max(0.0, min(1.0, autoregressive_weight))

    def forecast(self, request: ForecastRequest) -> ForecastResponse:
        """Generate PM2.5 forecasts for the requested horizon."""
        station_obs = TimeSeriesService.filter_station(request.history, request.station_id)
        if not station_obs:
            raise ValueError(
                f"No historical observations found matching station_id '{request.station_id}'"
            )

        sorted_obs = TimeSeriesService.sort_chronological(station_obs, ascending=True)

        # Get latest observation with valid PM2.5
        valid_obs = [obs for obs in sorted_obs if obs.pm25 is not None]
        if not valid_obs:
            raise ValueError(
                f"No non-null PM2.5 historical measurements for station '{request.station_id}'"
            )

        latest_obs = valid_obs[-1]
        latest_pm25 = float(latest_obs.pm25)
        start_time = latest_obs.timestamp

        # Compute historical standard deviation for bounds
        history_vals = [float(obs.pm25) for obs in valid_obs]
        if len(history_vals) > 1:
            base_std = max(float(np.std(history_vals, ddof=1)), 5.0)
        else:
            base_std = 15.0

        predictions: List[PredictionPoint] = []
        current_pm25 = latest_pm25

        for step in range(1, request.horizon + 1):
            forecast_time = start_time + timedelta(hours=step)
            target_hour = forecast_time.hour

            # Compute diurnal baseline for this target hour
            diurnal_baseline = LocalHistoricalBaselineComputer.compute(
                valid_obs, target_hour=target_hour
            )

            if diurnal_baseline["sample_count"] > 0:
                expected_diurnal = float(diurnal_baseline["mean"])
            else:
                expected_diurnal = float(np.mean(history_vals))

            # Autoregressive step moving toward diurnal mean
            step_forecast = (
                self.autoregressive_weight * current_pm25
                + (1.0 - self.autoregressive_weight) * expected_diurnal
            )
            step_forecast = max(0.0, step_forecast)

            # Prediction interval expands with horizon step
            uncertainty_scale = math.sqrt(1.0 + 0.08 * step)
            margin = 1.96 * base_std * uncertainty_scale

            lower_bound = max(0.0, round(step_forecast - margin, 2))
            upper_bound = max(round(step_forecast, 2), round(step_forecast + margin, 2))
            point_forecast = round(step_forecast, 2)

            predictions.append(
                PredictionPoint(
                    timestamp=forecast_time,
                    pm25_forecast=point_forecast,
                    lower_bound=lower_bound,
                    upper_bound=upper_bound,
                )
            )

            # Evolve current state
            current_pm25 = step_forecast

        return ForecastResponse(
            station_id=request.station_id,
            horizon=request.horizon,
            predictions=predictions,
            provider_type="development_baseline",
        )
