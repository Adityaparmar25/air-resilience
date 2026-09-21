"""Explainable Anomaly Detector for PM2.5 Observations.

Uses an isolated local historical baseline and documented statistical thresholds.
Produces transparent, explainable anomaly scores and classifications without
magic numbers or fake 'AI confidence' metrics.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from schemas.canonical import MonitoringObservation
from services.forecasting.time_series_service import LocalHistoricalBaselineComputer


class AnomalyStatus(str, Enum):
    """Documented anomaly classification states."""

    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"
    STRONG_ANOMALY = "STRONG_ANOMALY"


class AnomalyDetectionConfig(BaseModel):
    """Explicit, documented configuration for anomaly detection thresholds."""

    z_score_elevated_threshold: float = Field(
        default=2.0,
        description="Z-score threshold above historical baseline mean to trigger ELEVATED status",
    )
    z_score_strong_threshold: float = Field(
        default=3.5,
        description="Z-score threshold above historical baseline mean to trigger STRONG_ANOMALY status",
    )
    absolute_elevated_ceiling: float = Field(
        default=150.0,
        description="Absolute PM2.5 level (ug/m3) where readings are classified at least ELEVATED regardless of z-score",
    )
    absolute_strong_ceiling: float = Field(
        default=300.0,
        description="Absolute PM2.5 level (ug/m3) where readings are classified STRONG_ANOMALY regardless of z-score",
    )
    min_baseline_samples: int = Field(
        default=3,
        description="Minimum historical observations required to compute dynamic baseline",
    )
    fallback_expected_pm25: float = Field(
        default=60.0,
        description="Fallback expected PM2.5 concentration (NAAQS 24h standard: 60 ug/m3) when baseline is insufficient",
    )
    fallback_std_pm25: float = Field(
        default=25.0,
        description="Fallback standard deviation when historical variance cannot be computed",
    )


class AnomalyResult(BaseModel):
    """Anomaly detection result adhering strictly to Phase 3A contract."""

    station_id: str
    timestamp: datetime
    pm25: float
    expected_pm25: float
    anomaly_score: float
    status: AnomalyStatus
    explanation: Optional[str] = Field(
        default=None,
        description="Human-readable transparent explanation of how anomaly score and status were determined",
    )
    baseline_std: Optional[float] = Field(
        default=None,
        description="Standard deviation of the baseline used for z-score calculation",
    )
    thresholds_applied: Optional[Dict[str, float]] = Field(
        default=None,
        description="Exact threshold values applied during evaluation",
    )

    def to_contract_dict(self) -> Dict[str, Any]:
        """Produce the exact dictionary required by Phase 3A specification."""
        return {
            "station_id": self.station_id,
            "timestamp": self.timestamp.isoformat(),
            "pm25": self.pm25,
            "expected_pm25": self.expected_pm25,
            "anomaly_score": self.anomaly_score,
            "status": self.status.value,
        }


class ExplainableAnomalyDetector:
    """Explainable anomaly detector using documented statistical baselines and thresholds."""

    def __init__(self, config: Optional[AnomalyDetectionConfig] = None):
        self.config = config or AnomalyDetectionConfig()

    def detect(
        self,
        observation: MonitoringObservation,
        history: List[MonitoringObservation],
    ) -> AnomalyResult:
        """Evaluate observation against historical baseline and return explainable assessment."""
        if observation.pm25 is None:
            raise ValueError(
                f"Cannot evaluate anomaly for station {observation.station_id}: PM2.5 measurement is null"
            )

        pm25_val = float(observation.pm25)

        # Attempt diurnal baseline (same hour of day)
        baseline = LocalHistoricalBaselineComputer.compute(
            history, target_hour=observation.timestamp.hour
        )

        # Fallback to overall history if diurnal sample count is too small
        used_diurnal = True
        if baseline["sample_count"] < self.config.min_baseline_samples:
            baseline = LocalHistoricalBaselineComputer.compute(history, target_hour=None)
            used_diurnal = False

        # If still insufficient history, use documented NAAQS standards
        used_fallback = False
        if baseline["sample_count"] < self.config.min_baseline_samples:
            expected_pm25 = self.config.fallback_expected_pm25
            std_pm25 = self.config.fallback_std_pm25
            used_fallback = True
        else:
            expected_pm25 = float(baseline["mean"])
            std_pm25 = float(baseline["std"])

        # Calculate standard score (z-score)
        z_score = (pm25_val - expected_pm25) / std_pm25
        # Anomaly score: non-negative deviation metric rounded to 2 decimal places
        anomaly_score = max(0.0, round(z_score, 2))

        # Status determination with documented rule logic
        status_reasons: List[str] = []
        if z_score >= self.config.z_score_strong_threshold:
            status = AnomalyStatus.STRONG_ANOMALY
            status_reasons.append(
                f"z-score ({z_score:.2f}) exceeds strong threshold ({self.config.z_score_strong_threshold})"
            )
        elif pm25_val >= self.config.absolute_strong_ceiling:
            status = AnomalyStatus.STRONG_ANOMALY
            status_reasons.append(
                f"PM2.5 ({pm25_val} ug/m3) exceeds absolute strong ceiling ({self.config.absolute_strong_ceiling} ug/m3)"
            )
        elif z_score >= self.config.z_score_elevated_threshold:
            status = AnomalyStatus.ELEVATED
            status_reasons.append(
                f"z-score ({z_score:.2f}) exceeds elevated threshold ({self.config.z_score_elevated_threshold})"
            )
        elif pm25_val >= self.config.absolute_elevated_ceiling:
            status = AnomalyStatus.ELEVATED
            status_reasons.append(
                f"PM2.5 ({pm25_val} ug/m3) exceeds absolute elevated ceiling ({self.config.absolute_elevated_ceiling} ug/m3)"
            )
        else:
            status = AnomalyStatus.NORMAL
            status_reasons.append("Observation is within expected statistical baseline range")

        baseline_desc = (
            "NAAQS default fallback"
            if used_fallback
            else ("diurnal hour baseline" if used_diurnal else "historical window baseline")
        )
        explanation = (
            f"Observed PM2.5 of {pm25_val:.1f} ug/m3 vs expected {expected_pm25:.1f} ug/m3 "
            f"(std: {std_pm25:.1f}, {baseline_desc}, samples: {baseline.get('sample_count', 0)}). "
            f"Classified as {status.value}: {'; '.join(status_reasons)}."
        )

        return AnomalyResult(
            station_id=observation.station_id,
            timestamp=observation.timestamp,
            pm25=round(pm25_val, 2),
            expected_pm25=round(expected_pm25, 2),
            anomaly_score=anomaly_score,
            status=status,
            explanation=explanation,
            baseline_std=round(std_pm25, 2),
            thresholds_applied={
                "z_score_elevated": self.config.z_score_elevated_threshold,
                "z_score_strong": self.config.z_score_strong_threshold,
                "absolute_elevated": self.config.absolute_elevated_ceiling,
                "absolute_strong": self.config.absolute_strong_ceiling,
            },
        )
