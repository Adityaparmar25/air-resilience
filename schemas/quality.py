"""Quality flags and observation quality records."""

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from schemas.canonical import MonitoringObservation


class QualityFlag(str, Enum):
    """Quality and validation flags for air quality observations."""

    VALID = "VALID"
    SUSPICIOUS_SPIKE = "SUSPICIOUS_SPIKE"
    RANGE_OUTLIER = "RANGE_OUTLIER"
    DUPLICATE_TIMESTAMP = "DUPLICATE_TIMESTAMP"
    MISSING_POLLUTANT = "MISSING_POLLUTANT"
    NEGATIVE_VALUE_REJECTED = "NEGATIVE_VALUE_REJECTED"
    STALE_REPEATED_VALUE = "STALE_REPEATED_VALUE"
    UNUSUAL_RATE_OF_CHANGE = "UNUSUAL_RATE_OF_CHANGE"


class ObservationQualityRecord(BaseModel):
    """Encapsulates a normalized observation along with its data-quality assessment."""

    observation: MonitoringObservation
    flags: List[QualityFlag] = Field(default_factory=lambda: [QualityFlag.VALID])
    is_usable: bool = Field(
        default=True,
        description="Whether this observation is acceptable for analytical time-series and ML",
    )
    raw_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Source provenance metadata (e.g. source format, original column names, fetch timestamp)",
    )
    quality_notes: Optional[str] = Field(
        default=None,
        description="Human-readable explanation of any detected quality flags or spike reasons",
    )
