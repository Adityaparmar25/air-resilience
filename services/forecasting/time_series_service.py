"""PM2.5 Time-Series Service.

Provides station filtering, chronological ordering, missing-timestamp detection,
recent observation retrieval, and local historical baseline computation.
Baseline calculation is kept isolated so it can later be replaced or complemented
by BigQuery ML.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import numpy as np

from schemas.canonical import MonitoringObservation


class LocalHistoricalBaselineComputer:
    """Computes transparent local historical baselines from time series observations.

    Kept isolated from model providers so it can be swapped for BigQuery ML.
    """

    DEFAULT_MIN_STD = 5.0  # Minimum standard deviation floor to avoid division by zero

    @classmethod
    def compute(
        cls,
        observations: List[MonitoringObservation],
        target_hour: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Compute statistical baseline for PM2.5 observations.

        If target_hour is provided (0-23), calculates the diurnal baseline for that
        specific hour of the day across historical observations.
        """
        valid_pm25 = [
            obs.pm25 for obs in observations
            if obs.pm25 is not None
            and (target_hour is None or obs.timestamp.hour == target_hour)
        ]

        if not valid_pm25:
            return {
                "sample_count": 0,
                "mean": 0.0,
                "median": 0.0,
                "std": cls.DEFAULT_MIN_STD,
                "min": 0.0,
                "max": 0.0,
                "p25": 0.0,
                "p75": 0.0,
                "target_hour": target_hour,
            }

        arr = np.array(valid_pm25, dtype=float)
        mean_val = float(np.mean(arr))
        median_val = float(np.median(arr))
        raw_std = float(np.std(arr, ddof=1)) if len(arr) > 1 else cls.DEFAULT_MIN_STD
        std_val = max(raw_std, cls.DEFAULT_MIN_STD)

        return {
            "sample_count": len(valid_pm25),
            "mean": round(mean_val, 2),
            "median": round(median_val, 2),
            "std": round(std_val, 2),
            "min": round(float(np.min(arr)), 2),
            "max": round(float(np.max(arr)), 2),
            "p25": round(float(np.percentile(arr, 25)), 2),
            "p75": round(float(np.percentile(arr, 75)), 2),
            "target_hour": target_hour,
        }


class TimeSeriesService:
    """Service for managing, aligning, and querying station PM2.5 time series."""

    @staticmethod
    def filter_station(
        observations: List[MonitoringObservation],
        station_id: str,
    ) -> List[MonitoringObservation]:
        """Filter observations by station ID (case-insensitive)."""
        target = station_id.strip().lower()
        return [obs for obs in observations if obs.station_id.strip().lower() == target]

    @staticmethod
    def sort_chronological(
        observations: List[MonitoringObservation],
        ascending: bool = True,
    ) -> List[MonitoringObservation]:
        """Sort observations strictly by timestamp."""
        return sorted(observations, key=lambda obs: obs.timestamp, reverse=not ascending)

    @classmethod
    def get_recent_observations(
        cls,
        observations: List[MonitoringObservation],
        limit: int = 24,
    ) -> List[MonitoringObservation]:
        """Retrieve the latest N observations in ascending chronological order."""
        sorted_obs = cls.sort_chronological(observations, ascending=True)
        return sorted_obs[-limit:] if len(sorted_obs) > limit else sorted_obs

    @classmethod
    def detect_missing_timestamps(
        cls,
        observations: List[MonitoringObservation],
        expected_interval_minutes: int = 60,
        tolerance_minutes: int = 15,
    ) -> List[Dict[str, Any]]:
        """Identify missing timestamps / observation gaps in a time series.

        Returns a list of detected gap intervals with estimated missing observation counts.
        """
        if len(observations) < 2:
            return []

        sorted_obs = cls.sort_chronological(observations, ascending=True)
        gaps: List[Dict[str, Any]] = []

        expected_delta = timedelta(minutes=expected_interval_minutes)
        max_allowed_delta = timedelta(minutes=expected_interval_minutes + tolerance_minutes)

        for i in range(1, len(sorted_obs)):
            prev_obs = sorted_obs[i - 1]
            curr_obs = sorted_obs[i]

            diff = curr_obs.timestamp - prev_obs.timestamp
            if diff > max_allowed_delta:
                diff_seconds = diff.total_seconds()
                interval_seconds = expected_interval_minutes * 60
                missing_count = int(round(diff_seconds / interval_seconds)) - 1

                gaps.append({
                    "station_id": curr_obs.station_id,
                    "gap_start": prev_obs.timestamp.isoformat(),
                    "gap_end": curr_obs.timestamp.isoformat(),
                    "gap_duration_hours": round(diff_seconds / 3600.0, 2),
                    "missing_observations_count": max(1, missing_count),
                })

        return gaps

    @staticmethod
    def compute_local_baseline(
        observations: List[MonitoringObservation],
        target_hour: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Compute local historical baseline using the isolated baseline computer."""
        return LocalHistoricalBaselineComputer.compute(observations, target_hour=target_hour)
