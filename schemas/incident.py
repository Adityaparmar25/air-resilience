"""Authority Incident and Audit Log Schemas.

Supports Phase 3C operational authority lifecycle:
DETECTED -> ALERTED -> ASSIGNED -> ACKNOWLEDGED -> INVESTIGATING -> RESOLVED / DISMISSED
with server-side validation and immutable audit history.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field
from schemas.event import EvidenceCoverage, EvidenceStatus, LocationCell


class IncidentPriority(str, Enum):
    """Operational urgency level of an incident."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(str, Enum):
    """Operational lifecycle stages of an authority incident (Decision D-016)."""

    DETECTED = "DETECTED"
    ALERTED = "ALERTED"
    ASSIGNED = "ASSIGNED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class IncidentNote(BaseModel):
    """Operational log entry or field note added by response teams."""

    note_id: str = Field(default_factory=lambda: f"note_{uuid.uuid4().hex[:8]}")
    actor: str = Field(..., description="Identity or role of the author (e.g. 'dispatcher_1', 'field_lead')")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content: str = Field(..., min_length=1, max_length=2000)


class AuditRecord(BaseModel):
    """Immutable audit log entry tracking all state transitions and critical authority actions."""

    audit_id: str = Field(default_factory=lambda: f"aud_{uuid.uuid4().hex[:10]}")
    incident_id: str
    actor: str = Field(..., description="User or automated agent triggering the transition")
    actor_id: str = Field(default="", description="Identifier of the actor")
    action: str = Field(
        ...,
        description="Action keyword: CREATE | ALERT | ASSIGN | ACKNOWLEDGE | INVESTIGATE | RESOLVE | DISMISS | ADD_NOTE",
    )
    previous_status: Optional[IncidentStatus] = None
    new_status: Optional[IncidentStatus] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if not self.actor_id and self.actor:
            self.actor_id = self.actor
        elif not self.actor and self.actor_id:
            self.actor = self.actor_id


class Incident(BaseModel):
    """Canonical Authority Incident matching Phase 3C specifications."""

    incident_id: str = Field(default_factory=lambda: f"INC-{uuid.uuid4().hex[:6].upper()}")
    event_id: str = Field(..., description="Foreign key to originating PollutionEvent")
    priority: IncidentPriority = Field(default=IncidentPriority.HIGH)
    status: IncidentStatus = Field(default=IncidentStatus.DETECTED)
    assigned_to: Optional[str] = Field(default=None, description="Assigned responder or officer")
    assigned_team: Optional[str] = Field(default=None, description="Response unit or municipal team")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged_at: Optional[datetime] = None
    investigating_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    dismissed_at: Optional[datetime] = None
    resolution_summary: Optional[str] = None
    dismissal_reason: Optional[str] = None
    notes: List[IncidentNote] = Field(default_factory=list)

    # Correlated context from originating event
    evidence_status: EvidenceStatus = Field(default=EvidenceStatus.POSSIBLE)
    evidence_coverage: EvidenceCoverage = Field(default_factory=EvidenceCoverage)
    location: LocationCell
    probable_source: Optional[str] = None
    forecast: Dict[str, Any] = Field(default_factory=dict)
    explanation: Optional[str] = None
    provenance_type: str = Field(
        default="REPLAY",
        description="Data provenance: LIVE | RECENT | HISTORICAL | REPLAY | SIMULATION",
    )
    is_replay: bool = Field(
        default=True,
        description="True if based on historical replay or fixture data",
    )


# --- Request DTOs ---

class CreateIncidentRequest(BaseModel):
    event_id: str
    priority: Optional[IncidentPriority] = None
    actor: str = "authority_system"
    initial_notes: Optional[str] = None


class AssignIncidentRequest(BaseModel):
    assigned_to: str = Field(..., min_length=2)
    assigned_team: Optional[str] = "Delhi Pollution Response Cell"
    actor: str = "authority_dispatcher"
    notes: Optional[str] = None


class AcknowledgeIncidentRequest(BaseModel):
    actor: str = Field(..., min_length=2)
    notes: Optional[str] = None


class InvestigateIncidentRequest(BaseModel):
    actor: str = Field(..., min_length=2)
    notes: Optional[str] = None


class ResolveIncidentRequest(BaseModel):
    actor: str = Field(..., min_length=2)
    resolution_summary: str = Field(..., min_length=5)
    notes: Optional[str] = None


class DismissIncidentRequest(BaseModel):
    actor: str = Field(..., min_length=2)
    dismissal_reason: str = Field(..., min_length=5)
    notes: Optional[str] = None


class AddNoteRequest(BaseModel):
    actor: str = Field(..., min_length=2)
    content: str = Field(..., min_length=1)
