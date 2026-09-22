"""Pollution Event and Evidence Fusion Schemas.

Strictly follows the event contract in architecture.md Section 10,
the evidence weighting in decision.md D-006, and the missing data rule in D-007.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class EventStatus(str, Enum):
    """Lifecycle states of a pollution event."""

    POSSIBLE = "POSSIBLE"
    CORROBORATED = "CORROBORATED"
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    ALERTED = "ALERTED"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    EXPIRED = "EXPIRED"


class EventSeverity(str, Enum):
    """Operational severity of an event."""

    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class LocationCell(BaseModel):
    """Geographic location structure with coarsened cell identifier."""

    lat: float = Field(..., ge=-90.0, le=90.0)
    lng: float = Field(..., ge=-180.0, le=180.0)
    cell_id: str = Field(
        ...,
        description="Coarsened spatial cluster cell identifier (e.g. 'grid_28.65_77.31')",
    )


class EvidenceSignal(BaseModel):
    """Single heterogeneous evidence signal participating in evidence fusion."""

    source: str = Field(
        ...,
        description="Source identifier: ground_sensor | citizen_report | satellite | weather | fire",
    )
    timestamp: datetime
    location: Dict[str, float]
    signal_type: str = Field(
        ...,
        description="Signal type: pm25_anomaly | visible_smoke | thermal_anomaly | wind_alignment",
    )
    score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Normalized signal strength (0.0 to 1.0). Null/None if source is unavailable.",
    )
    weight: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Static evidence weight assigned to this source per Decision D-006",
    )
    availability: bool = Field(
        ...,
        description="True if sensor/satellite observation was successfully evaluated; False if unavailable",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Provenance details (e.g. station_id, z_score, confidence, visual notes)",
    )


class EvidenceBreakdown(BaseModel):
    """Complete evidence bundle used to score and explain an event."""

    signals: Dict[str, EvidenceSignal] = Field(
        description="Mapping of source name (ground, citizen, satellite, weather, fire) to signal",
    )
    fusion_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Normalized weighted fusion score across available evidence sources only",
    )
    available_weight_sum: float = Field(
        description="Sum of weights for sources currently available (denominator in D-006 formula)",
    )
    available_sources_count: int
    corroborating_sources_count: int
    explanation_text: str = Field(
        description="Human-readable transparent narrative answering 'Why was this event created?'",
    )


class PollutionEvent(BaseModel):
    """Canonical Pollution Event model matching architecture.md Section 10."""

    event_id: str = Field(default_factory=lambda: f"ev_{uuid.uuid4().hex[:10]}")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    location: LocationCell
    status: EventStatus = Field(default=EventStatus.POSSIBLE)
    event_type: str = Field(
        default="combustion_event",
        description="Broad event type category (e.g. combustion_event, dust_storm, open_burning)",
    )
    severity: EventSeverity = Field(default=EventSeverity.MODERATE)
    evidence: EvidenceBreakdown
    forecast: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional PM2.5 horizon forecast associated with this event",
    )
    probable_source: Optional[str] = Field(
        default=None,
        description="Probabilistic category (Decision D-005, e.g. 'Likely industrial emissions')",
    )
    human_verification_required: bool = Field(default=True)
    report_ids: List[str] = Field(
        default_factory=list,
        description="List of linked citizen report IDs correlated with this event",
    )
    station_ids: List[str] = Field(
        default_factory=list,
        description="List of linked ground monitoring stations within event radius",
    )
