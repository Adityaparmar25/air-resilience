"""Operational data store for citizen reports, active pollution events, authority incidents, and audit logs.

Provides thread-safe in-memory caching with JSON persistence for operational state.
Enforces:
- Server-side incident state transition validation (Decision D-016)
- Minimum evidence diversity rules for automated alerting (Decision D-017)
- Immutable audit trail recording every state change and critical action
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from schemas.event import EventStatus, EvidenceStatus, OperationalStatus, PollutionEvent
from schemas.incident import (
    AcknowledgeIncidentRequest,
    AddNoteRequest,
    AssignIncidentRequest,
    AuditRecord,
    CreateIncidentRequest,
    DismissIncidentRequest,
    Incident,
    IncidentNote,
    IncidentPriority,
    IncidentStatus,
    InvestigateIncidentRequest,
    ResolveIncidentRequest,
)
from schemas.report import CitizenReport


# Strict valid state transitions
VALID_TRANSITIONS: Dict[IncidentStatus, List[IncidentStatus]] = {
    IncidentStatus.DETECTED: [IncidentStatus.ALERTED, IncidentStatus.DISMISSED],
    IncidentStatus.ALERTED: [IncidentStatus.ASSIGNED, IncidentStatus.DISMISSED],
    IncidentStatus.ASSIGNED: [IncidentStatus.ASSIGNED, IncidentStatus.ACKNOWLEDGED, IncidentStatus.DISMISSED],
    IncidentStatus.ACKNOWLEDGED: [IncidentStatus.INVESTIGATING, IncidentStatus.DISMISSED],
    IncidentStatus.INVESTIGATING: [IncidentStatus.RESOLVED, IncidentStatus.DISMISSED],
    IncidentStatus.RESOLVED: [],  # terminal
    IncidentStatus.DISMISSED: [],  # terminal
}


class OperationalStore:
    """In-memory operational store with optional file-based state persistence."""

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or (Path(__file__).resolve().parent.parent.parent / "data" / "operational")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.reports_file = self.storage_dir / "reports.json"
        self.events_file = self.storage_dir / "events.json"
        self.incidents_file = self.storage_dir / "incidents.json"
        self.audit_file = self.storage_dir / "audit.json"

        self._lock = Lock()
        self._reports: Dict[str, CitizenReport] = {}
        self._events: Dict[str, PollutionEvent] = {}
        self._incidents: Dict[str, Incident] = {}
        self._audit_records: List[AuditRecord] = []

        self._load()

    # --- Reports ---

    def save_report(self, report: CitizenReport) -> CitizenReport:
        """Store or update a citizen report."""
        with self._lock:
            self._reports[report.report_id] = report
            self._persist_reports()
            return report

    def get_report(self, report_id: str) -> Optional[CitizenReport]:
        """Retrieve citizen report by ID."""
        with self._lock:
            return self._reports.get(report_id)

    def list_reports(self, limit: int = 50) -> List[CitizenReport]:
        """List citizen reports sorted by timestamp descending."""
        with self._lock:
            sorted_reports = sorted(
                self._reports.values(), key=lambda r: r.timestamp, reverse=True
            )
            return sorted_reports[:limit]

    # --- Events ---

    def save_event(self, event: PollutionEvent) -> PollutionEvent:
        """Store or update a pollution event."""
        with self._lock:
            self._events[event.event_id] = event
            self._persist_events()
            return event

    def get_event(self, event_id: str) -> Optional[PollutionEvent]:
        """Retrieve event by ID."""
        with self._lock:
            return self._events.get(event_id)

    def list_events(
        self,
        status: Optional[EventStatus] = None,
        limit: int = 50,
    ) -> List[PollutionEvent]:
        """List events sorted by timestamp descending, optionally filtered by status."""
        with self._lock:
            events = list(self._events.values())
            if status:
                events = [e for e in events if e.evidence_status == status or e.status == status]
            events.sort(key=lambda e: e.timestamp, reverse=True)
            return events[:limit]

    # --- Incidents & Lifecycle Transitions ---

    def create_incident(
        self,
        request: CreateIncidentRequest,
        event: PollutionEvent,
    ) -> Incident:
        """Create authority incident from a verified pollution event.

        Enforces D-017 minimum evidence diversity:
        Events with >= 2 independent evidence sources and high confidence escalate to ALERTED.
        Single-source events default to DETECTED (requiring manual review).
        """
        with self._lock:
            # Check for existing active incident for this event
            for inc in self._incidents.values():
                if inc.event_id == event.event_id and inc.status not in (IncidentStatus.RESOLVED, IncidentStatus.DISMISSED):
                    return inc

            # Priority mapping
            priority = request.priority
            if not priority:
                if event.severity.value in ("CRITICAL", "HIGH"):
                    priority = IncidentPriority.CRITICAL if event.severity.value == "CRITICAL" else IncidentPriority.HIGH
                elif event.severity.value == "MODERATE":
                    priority = IncidentPriority.MEDIUM
                else:
                    priority = IncidentPriority.LOW

            # Initial status adhering to D-017
            initial_status = IncidentStatus.DETECTED
            if event.evidence_coverage and event.evidence_coverage.diversity_eligible_for_alert:
                if event.evidence.fusion_score >= 0.55:
                    initial_status = IncidentStatus.ALERTED

            now = datetime.now(timezone.utc)
            notes_list: List[IncidentNote] = []
            if request.initial_notes:
                notes_list.append(
                    IncidentNote(
                        actor=request.actor,
                        timestamp=now,
                        content=request.initial_notes,
                    )
                )

            incident = Incident(
                event_id=event.event_id,
                priority=priority,
                status=initial_status,
                created_at=now,
                notes=notes_list,
                evidence_status=event.evidence_status,
                evidence_coverage=event.evidence_coverage,
                location=event.location,
                probable_source=event.probable_source,
                forecast=event.forecast,
                explanation=event.evidence.explanation_text if event.evidence else None,
            )

            self._incidents[incident.incident_id] = incident

            # Record immutable audit log
            audit = AuditRecord(
                incident_id=incident.incident_id,
                actor=request.actor,
                action="CREATE",
                previous_status=None,
                new_status=initial_status,
                timestamp=now,
                details={
                    "event_id": event.event_id,
                    "fusion_score": event.evidence.fusion_score if event.evidence else None,
                    "coverage_ratio": event.evidence_coverage.coverage_ratio if event.evidence_coverage else None,
                    "diversity_eligible": event.evidence_coverage.diversity_eligible_for_alert if event.evidence_coverage else False,
                },
            )
            self._audit_records.append(audit)

            self._persist_incidents()
            self._persist_audit()
            return incident

    def _validate_transition(self, current: IncidentStatus, target: IncidentStatus) -> None:
        allowed = VALID_TRANSITIONS.get(current, [])
        if target not in allowed:
            raise ValueError(
                f"Invalid status transition from '{current.value}' to '{target.value}'. Allowed transitions: {[s.value for s in allowed]}"
            )

    def assign_incident(
        self,
        incident_id: str,
        request: AssignIncidentRequest,
    ) -> Incident:
        """Assign incident to a designated officer and response team."""
        with self._lock:
            incident = self._incidents.get(incident_id)
            if not incident:
                raise KeyError(f"Incident '{incident_id}' not found")

            # Validate transition (can assign from ALERTED, or re-assign from ASSIGNED)
            self._validate_transition(incident.status, IncidentStatus.ASSIGNED)

            prev_status = incident.status
            incident.status = IncidentStatus.ASSIGNED
            incident.assigned_to = request.assigned_to
            incident.assigned_team = request.assigned_team or incident.assigned_team

            now = datetime.now(timezone.utc)
            if request.notes:
                incident.notes.append(
                    IncidentNote(actor=request.actor, timestamp=now, content=request.notes)
                )

            audit = AuditRecord(
                incident_id=incident_id,
                actor=request.actor,
                action="ASSIGN",
                previous_status=prev_status,
                new_status=IncidentStatus.ASSIGNED,
                timestamp=now,
                details={"assigned_to": request.assigned_to, "assigned_team": request.assigned_team},
            )
            self._audit_records.append(audit)

            self._persist_incidents()
            self._persist_audit()
            return incident

    def acknowledge_incident(
        self,
        incident_id: str,
        request: AcknowledgeIncidentRequest,
    ) -> Incident:
        """Acknowledge incident by assigned field team."""
        with self._lock:
            incident = self._incidents.get(incident_id)
            if not incident:
                raise KeyError(f"Incident '{incident_id}' not found")

            self._validate_transition(incident.status, IncidentStatus.ACKNOWLEDGED)

            prev_status = incident.status
            now = datetime.now(timezone.utc)
            incident.status = IncidentStatus.ACKNOWLEDGED
            incident.acknowledged_at = now

            if request.notes:
                incident.notes.append(
                    IncidentNote(actor=request.actor, timestamp=now, content=request.notes)
                )

            audit = AuditRecord(
                incident_id=incident_id,
                actor=request.actor,
                action="ACKNOWLEDGE",
                previous_status=prev_status,
                new_status=IncidentStatus.ACKNOWLEDGED,
                timestamp=now,
                details={},
            )
            self._audit_records.append(audit)

            self._persist_incidents()
            self._persist_audit()
            return incident

    def investigate_incident(
        self,
        incident_id: str,
        request: InvestigateIncidentRequest,
    ) -> Incident:
        """Mark incident as actively under field investigation."""
        with self._lock:
            incident = self._incidents.get(incident_id)
            if not incident:
                raise KeyError(f"Incident '{incident_id}' not found")

            self._validate_transition(incident.status, IncidentStatus.INVESTIGATING)

            prev_status = incident.status
            now = datetime.now(timezone.utc)
            incident.status = IncidentStatus.INVESTIGATING
            incident.investigating_at = now

            if request.notes:
                incident.notes.append(
                    IncidentNote(actor=request.actor, timestamp=now, content=request.notes)
                )

            audit = AuditRecord(
                incident_id=incident_id,
                actor=request.actor,
                action="INVESTIGATE",
                previous_status=prev_status,
                new_status=IncidentStatus.INVESTIGATING,
                timestamp=now,
                details={},
            )
            self._audit_records.append(audit)

            self._persist_incidents()
            self._persist_audit()
            return incident

    def resolve_incident(
        self,
        incident_id: str,
        request: ResolveIncidentRequest,
    ) -> Incident:
        """Resolve incident following field inspection or mitigation."""
        with self._lock:
            incident = self._incidents.get(incident_id)
            if not incident:
                raise KeyError(f"Incident '{incident_id}' not found")

            self._validate_transition(incident.status, IncidentStatus.RESOLVED)

            prev_status = incident.status
            now = datetime.now(timezone.utc)
            incident.status = IncidentStatus.RESOLVED
            incident.resolved_at = now
            incident.resolution_summary = request.resolution_summary

            if request.notes:
                incident.notes.append(
                    IncidentNote(actor=request.actor, timestamp=now, content=request.notes)
                )

            audit = AuditRecord(
                incident_id=incident_id,
                actor=request.actor,
                action="RESOLVE",
                previous_status=prev_status,
                new_status=IncidentStatus.RESOLVED,
                timestamp=now,
                details={"resolution_summary": request.resolution_summary},
            )
            self._audit_records.append(audit)

            self._persist_incidents()
            self._persist_audit()
            return incident

    def dismiss_incident(
        self,
        incident_id: str,
        request: DismissIncidentRequest,
    ) -> Incident:
        """Dismiss incident as non-actionable or false alarm."""
        with self._lock:
            incident = self._incidents.get(incident_id)
            if not incident:
                raise KeyError(f"Incident '{incident_id}' not found")

            self._validate_transition(incident.status, IncidentStatus.DISMISSED)

            prev_status = incident.status
            now = datetime.now(timezone.utc)
            incident.status = IncidentStatus.DISMISSED
            incident.dismissed_at = now
            incident.dismissal_reason = request.dismissal_reason

            if request.notes:
                incident.notes.append(
                    IncidentNote(actor=request.actor, timestamp=now, content=request.notes)
                )

            audit = AuditRecord(
                incident_id=incident_id,
                actor=request.actor,
                action="DISMISS",
                previous_status=prev_status,
                new_status=IncidentStatus.DISMISSED,
                timestamp=now,
                details={"dismissal_reason": request.dismissal_reason},
            )
            self._audit_records.append(audit)

            self._persist_incidents()
            self._persist_audit()
            return incident

    def add_note(self, incident_id: str, request: AddNoteRequest) -> IncidentNote:
        """Add timestamped field observation note to incident."""
        with self._lock:
            incident = self._incidents.get(incident_id)
            if not incident:
                raise KeyError(f"Incident '{incident_id}' not found")

            now = datetime.now(timezone.utc)
            note = IncidentNote(
                actor=request.actor,
                timestamp=now,
                content=request.content,
            )
            incident.notes.append(note)

            audit = AuditRecord(
                incident_id=incident_id,
                actor=request.actor,
                action="ADD_NOTE",
                previous_status=incident.status,
                new_status=incident.status,
                timestamp=now,
                details={"note_id": note.note_id, "snippet": note.content[:50]},
            )
            self._audit_records.append(audit)

            self._persist_incidents()
            self._persist_audit()
            return note

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Retrieve incident by ID."""
        with self._lock:
            return self._incidents.get(incident_id)

    def list_incidents(
        self,
        status: Optional[IncidentStatus] = None,
        priority: Optional[IncidentPriority] = None,
        limit: int = 50,
    ) -> List[Incident]:
        """List incidents sorted by creation time descending."""
        with self._lock:
            incidents = list(self._incidents.values())
            if status:
                incidents = [i for i in incidents if i.status == status]
            if priority:
                incidents = [i for i in incidents if i.priority == priority]
            incidents.sort(key=lambda i: i.created_at, reverse=True)
            return incidents[:limit]

    def get_audit_records(self, incident_id: Optional[str] = None) -> List[AuditRecord]:
        """Retrieve immutable audit records."""
        with self._lock:
            records = list(self._audit_records)
            if incident_id:
                records = [r for r in records if r.incident_id == incident_id]
            records.sort(key=lambda r: r.timestamp, reverse=True)
            return records

    # --- Persistence ---

    def clear(self) -> None:
        """Clear all stored operational data (useful for clean test runs)."""
        with self._lock:
            self._reports.clear()
            self._events.clear()
            self._incidents.clear()
            self._audit_records.clear()
            for f in (self.reports_file, self.events_file, self.incidents_file, self.audit_file):
                if f.exists():
                    f.unlink()

    def _persist_reports(self) -> None:
        try:
            data = {k: v.model_dump(mode="json") for k, v in self._reports.items()}
            with open(self.reports_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _persist_events(self) -> None:
        try:
            data = {k: v.model_dump(mode="json") for k, v in self._events.items()}
            with open(self.events_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _persist_incidents(self) -> None:
        try:
            data = {k: v.model_dump(mode="json") for k, v in self._incidents.items()}
            with open(self.incidents_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _persist_audit(self) -> None:
        try:
            data = [r.model_dump(mode="json") for r in self._audit_records]
            with open(self.audit_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _load(self) -> None:
        # Load reports
        if self.reports_file.exists():
            try:
                with open(self.reports_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    self._reports = {k: CitizenReport.model_validate(v) for k, v in raw.items()}
            except Exception:
                self._reports = {}

        # Load events
        if self.events_file.exists():
            try:
                with open(self.events_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    self._events = {k: PollutionEvent.model_validate(v) for k, v in raw.items()}
            except Exception:
                self._events = {}

        # Load incidents
        if self.incidents_file.exists():
            try:
                with open(self.incidents_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    self._incidents = {k: Incident.model_validate(v) for k, v in raw.items()}
            except Exception:
                self._incidents = {}

        # Load audit records
        if self.audit_file.exists():
            try:
                with open(self.audit_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    self._audit_records = [AuditRecord.model_validate(r) for r in raw]
            except Exception:
                self._audit_records = []


_GLOBAL_STORE: Optional[OperationalStore] = None


def get_operational_store() -> OperationalStore:
    """Singleton getter for operational data store."""
    global _GLOBAL_STORE
    if _GLOBAL_STORE is None:
        _GLOBAL_STORE = OperationalStore()
    return _GLOBAL_STORE
