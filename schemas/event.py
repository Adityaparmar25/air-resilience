"""Pollution Event and Evidence Fusion Schemas.

Strictly follows the event contract in architecture.md Section 10,
the evidence weighting in decision.md D-006, the missing data rule in D-007,
the separation of evidence classification from operational lifecycle in D-016,
and the minimum evidence diversity rule in D-017.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field, model_validator


class EvidenceStatus(str, Enum):
    """Classification of scientific/multimodal evidence (Decision D-016)."""

    FALSE_POSITIVE = "FALSE_POSITIVE"
    POSSIBLE = "POSSIBLE"
    CORROBORATED = "CORROBORATED"
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"


class OperationalStatus(str, Enum):
    """Operational workflow lifecycle of an event or incident (Decision D-016)."""

    DETECTED = "DETECTED"
    ALERTED = "ALERTED"
    ASSIGNED = "ASSIGNED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


# Backward-compatible alias
EventStatus = EvidenceStatus


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
        description="Mapping of source name (ground_sensor, citizen_report, satellite, weather, fire) to signal",
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


class EvidenceCoverage(BaseModel):
    """Explicit accounting of available vs unavailable evidence classes (D-007, D-016).

    Distinguishes evidence coverage (availability) from evidence strength (score).
    Unavailable signals remain False/null and are never penalized as zero.
    """

    ground_sensor: bool = False
    citizen_report: bool = False
    satellite: bool = False
    weather: bool = False
    fire: bool = False
    available_count: int = 0
    total_sources: int = 5
    coverage_ratio: float = 0.0
    diversity_eligible_for_alert: bool = Field(
        default=False,
        description="True if >= 2 independent evidence classes are available and corroborating (D-017)",
    )


class PollutionEvent(BaseModel):
    """Canonical Pollution Event model matching architecture.md Section 10 and Decision D-016."""

    event_id: str = Field(default_factory=lambda: f"ev_{uuid.uuid4().hex[:10]}")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    location: LocationCell
    evidence_status: EvidenceStatus = Field(default=EvidenceStatus.POSSIBLE)
    operational_status: OperationalStatus = Field(default=OperationalStatus.DETECTED)
    status: EvidenceStatus = Field(
        default=EvidenceStatus.POSSIBLE,
        description="Backward-compatible alias for evidence_status",
    )
    event_type: str = Field(
        default="combustion_event",
        description="Broad event type category (e.g. combustion_event, dust_storm, open_burning)",
    )
    severity: EventSeverity = Field(default=EventSeverity.MODERATE)
    evidence: EvidenceBreakdown
    evidence_coverage: EvidenceCoverage = Field(default_factory=EvidenceCoverage)
    forecast: Dict[str, Any] = Field(
        default_factory=dict,
        description="PM2.5 horizon forecast (+6h, +12h, +24h) and model metadata associated with this event",
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

    @model_validator(mode="after")
    def sync_status_and_coverage(self) -> "PollutionEvent":
        # Keep status and evidence_status aligned
        if self.evidence_status:
            self.status = self.evidence_status
        elif self.status:
            self.evidence_status = self.status

        # Compute evidence_coverage if default
        if self.evidence and self.evidence.signals:
            signals = self.evidence.signals
            ground_avail = bool(signals.get("ground_sensor") and signals["ground_sensor"].availability)
            cit_avail = bool(signals.get("citizen_report") and signals["citizen_report"].availability)
            sat_avail = bool(signals.get("satellite") and signals["satellite"].availability)
            wx_avail = bool(signals.get("weather") and signals["weather"].availability)
            fire_avail = bool(signals.get("fire") and signals["fire"].availability)

            avail_count = sum([ground_avail, cit_avail, sat_avail, wx_avail, fire_avail])
            corrob_count = self.evidence.corroborating_sources_count

            # D-017: >= 2 independent evidence classes available
            diversity_eligible = avail_count >= 2 and corrob_count >= 2

            self.evidence_coverage = EvidenceCoverage(
                ground_sensor=ground_avail,
                citizen_report=cit_avail,
                satellite=sat_avail,
                weather=wx_avail,
                fire=fire_avail,
                available_count=avail_count,
                total_sources=5,
                coverage_ratio=round(avail_count / 5.0, 2),
                diversity_eligible_for_alert=diversity_eligible,
            )

        return self
