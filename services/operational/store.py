"""Operational data store for citizen reports, active pollution events, authority incidents, and audit logs.

Provides:
- Abstract OperationalStore base class (Decision D-016 & D-017)
- InMemoryOperationalStore (thread-safe, memory-only for tests)
- FileOperationalStore (JSON-persisted store for local development)
- FirestoreOperationalStore (production GCP Firestore client with ADC)

Enforces:
- Server-side incident state transition validation
- Minimum evidence diversity rules for automated alerting
- Append-only audit logging for state transitions and operational actions
- User role mappings for server-side RBAC
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from apps.api.config import get_settings
from schemas.event import EventStatus, EvidenceStatus, OperationalStatus, PollutionEvent
from schemas.federation import CityNode, FederatedRound
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

logger = logging.getLogger(__name__)

# Strict valid state transitions (Decision D-016)
VALID_TRANSITIONS: Dict[IncidentStatus, List[IncidentStatus]] = {
    IncidentStatus.DETECTED: [IncidentStatus.ALERTED, IncidentStatus.DISMISSED],
    IncidentStatus.ALERTED: [IncidentStatus.ASSIGNED, IncidentStatus.DISMISSED],
    IncidentStatus.ASSIGNED: [IncidentStatus.ASSIGNED, IncidentStatus.ACKNOWLEDGED, IncidentStatus.DISMISSED],
    IncidentStatus.ACKNOWLEDGED: [IncidentStatus.INVESTIGATING, IncidentStatus.DISMISSED],
    IncidentStatus.INVESTIGATING: [IncidentStatus.RESOLVED, IncidentStatus.DISMISSED],
    IncidentStatus.RESOLVED: [],  # terminal
    IncidentStatus.DISMISSED: [],  # terminal
}


class OperationalStore(ABC):
    """Abstract base repository for operational data entities."""

    def _validate_transition(self, current: IncidentStatus, target: IncidentStatus) -> None:
        """Validate state transition against allowed lifecycle rules."""
        allowed = VALID_TRANSITIONS.get(current, [])
        if target not in allowed:
            raise ValueError(
                f"Invalid status transition from '{current.value}' to '{target.value}'. Allowed transitions: {[s.value for s in allowed]}"
            )

    @abstractmethod
    def save_report(self, report: CitizenReport) -> CitizenReport:
        pass

    @abstractmethod
    def get_report(self, report_id: str) -> Optional[CitizenReport]:
        pass

    @abstractmethod
    def list_reports(self, limit: int = 50) -> List[CitizenReport]:
        pass

    @abstractmethod
    def save_event(self, event: PollutionEvent) -> PollutionEvent:
        pass

    @abstractmethod
    def get_event(self, event_id: str) -> Optional[PollutionEvent]:
        pass

    @abstractmethod
    def list_events(
        self,
        status: Optional[EventStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[PollutionEvent]:
        pass

    @abstractmethod
    def create_incident(self, request: CreateIncidentRequest, event: PollutionEvent) -> Incident:
        pass

    @abstractmethod
    def assign_incident(self, incident_id: str, request: AssignIncidentRequest) -> Incident:
        pass

    @abstractmethod
    def acknowledge_incident(self, incident_id: str, request: AcknowledgeIncidentRequest) -> Incident:
        pass

    @abstractmethod
    def investigate_incident(self, incident_id: str, request: InvestigateIncidentRequest) -> Incident:
        pass

    @abstractmethod
    def resolve_incident(self, incident_id: str, request: ResolveIncidentRequest) -> Incident:
        pass

    @abstractmethod
    def dismiss_incident(self, incident_id: str, request: DismissIncidentRequest) -> Incident:
        pass

    @abstractmethod
    def add_note(self, incident_id: str, request: AddNoteRequest) -> IncidentNote:
        pass

    @abstractmethod
    def get_incident(self, incident_id: str) -> Optional[Incident]:
        pass

    @abstractmethod
    def list_incidents(
        self,
        status: Optional[IncidentStatus] = None,
        priority: Optional[IncidentPriority] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Incident]:
        pass

    @abstractmethod
    def list_audit_records(self, incident_id: Optional[str] = None, limit: int = 100) -> List[AuditRecord]:
        pass

    def get_audit_records(self, incident_id: Optional[str] = None, limit: int = 100) -> List[AuditRecord]:
        """Convenience alias for list_audit_records."""
        return self.list_audit_records(incident_id=incident_id, limit=limit)

    @abstractmethod
    def save_node(self, node: CityNode) -> CityNode:
        pass

    @abstractmethod
    def get_node(self, node_id: str) -> Optional[CityNode]:
        pass

    @abstractmethod
    def list_nodes(self) -> List[CityNode]:
        pass

    @abstractmethod
    def save_federation_round(self, round_record: FederatedRound) -> FederatedRound:
        pass

    @abstractmethod
    def get_federation_round(self, round_id: str) -> Optional[FederatedRound]:
        pass

    @abstractmethod
    def list_federation_rounds(self) -> List[FederatedRound]:
        pass

    @abstractmethod
    def save_user_role(self, uid: str, role: str, email: Optional[str] = None) -> None:
        pass

    @abstractmethod
    def get_user_role(self, uid: str, email: Optional[str] = None) -> Optional[str]:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass


class InMemoryOperationalStore(OperationalStore):
    """In-memory operational store with thread-safety for testing and local operation."""

    def __init__(self):
        self._lock = Lock()
        self._reports: Dict[str, CitizenReport] = {}
        self._events: Dict[str, PollutionEvent] = {}
        self._incidents: Dict[str, Incident] = {}
        self._audit_records: List[AuditRecord] = []
        self._nodes: Dict[str, CityNode] = {}
        self._federation_rounds: Dict[str, FederatedRound] = {}
        self._user_roles: Dict[str, Dict[str, str]] = {}

    def save_report(self, report: CitizenReport) -> CitizenReport:
        with self._lock:
            self._reports[report.report_id] = report
            return report

    def get_report(self, report_id: str) -> Optional[CitizenReport]:
        with self._lock:
            return self._reports.get(report_id)

    def list_reports(self, limit: int = 50) -> List[CitizenReport]:
        with self._lock:
            sorted_reports = sorted(
                self._reports.values(), key=lambda r: r.timestamp, reverse=True
            )
            return sorted_reports[:limit]

    def save_event(self, event: PollutionEvent) -> PollutionEvent:
        with self._lock:
            self._events[event.event_id] = event
            return event

    def get_event(self, event_id: str) -> Optional[PollutionEvent]:
        with self._lock:
            return self._events.get(event_id)

    def list_events(
        self,
        status: Optional[EventStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[PollutionEvent]:
        with self._lock:
            events = list(self._events.values())
            if status:
                events = [e for e in events if e.evidence_status == status or e.status == status]
            events.sort(key=lambda e: e.timestamp, reverse=True)
            return events[offset : offset + limit]

    def create_incident(
        self,
        request: CreateIncidentRequest,
        event: PollutionEvent,
    ) -> Incident:
        with self._lock:
            for inc in self._incidents.values():
                if inc.event_id == event.event_id and inc.status not in (IncidentStatus.RESOLVED, IncidentStatus.DISMISSED):
                    return inc

            priority = request.priority
            if not priority:
                if event.severity.value in ("CRITICAL", "HIGH"):
                    priority = IncidentPriority.CRITICAL if event.severity.value == "CRITICAL" else IncidentPriority.HIGH
                elif event.severity.value == "MODERATE":
                    priority = IncidentPriority.MEDIUM
                else:
                    priority = IncidentPriority.LOW

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
            return incident

    def assign_incident(self, incident_id: str, request: AssignIncidentRequest) -> Incident:
        with self._lock:
            incident = self._incidents.get(incident_id)
            if not incident:
                raise KeyError(f"Incident '{incident_id}' not found")

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
            return incident

    def acknowledge_incident(self, incident_id: str, request: AcknowledgeIncidentRequest) -> Incident:
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
                details={"acknowledged_by": request.actor},
            )
            self._audit_records.append(audit)
            return incident

    def investigate_incident(self, incident_id: str, request: InvestigateIncidentRequest) -> Incident:
        with self._lock:
            incident = self._incidents.get(incident_id)
            if not incident:
                raise KeyError(f"Incident '{incident_id}' not found")

            self._validate_transition(incident.status, IncidentStatus.INVESTIGATING)
            prev_status = incident.status
            incident.status = IncidentStatus.INVESTIGATING

            now = datetime.now(timezone.utc)
            incident.investigating_at = now
            obs_notes = getattr(request, "notes", None) or getattr(request, "field_observations", None)
            if obs_notes:
                incident.notes.append(
                    IncidentNote(
                        actor=request.actor,
                        timestamp=now,
                        content=f"[Investigation] {obs_notes}",
                    )
                )

            audit = AuditRecord(
                incident_id=incident_id,
                actor=request.actor,
                action="INVESTIGATE",
                previous_status=prev_status,
                new_status=IncidentStatus.INVESTIGATING,
                timestamp=now,
                details={"notes": obs_notes},
            )
            self._audit_records.append(audit)
            return incident

    def resolve_incident(self, incident_id: str, request: ResolveIncidentRequest) -> Incident:
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

            res_notes = getattr(request, "notes", None) or getattr(request, "final_notes", None)
            if res_notes:
                incident.notes.append(
                    IncidentNote(
                        actor=request.actor,
                        timestamp=now,
                        content=f"[Resolution] {res_notes}",
                    )
                )

            audit = AuditRecord(
                incident_id=incident_id,
                actor=request.actor,
                action="RESOLVE",
                previous_status=prev_status,
                new_status=IncidentStatus.RESOLVED,
                timestamp=now,
                details={
                    "resolution_summary": request.resolution_summary,
                },
            )
            self._audit_records.append(audit)
            return incident

    def dismiss_incident(self, incident_id: str, request: DismissIncidentRequest) -> Incident:
        with self._lock:
            incident = self._incidents.get(incident_id)
            if not incident:
                raise KeyError(f"Incident '{incident_id}' not found")

            self._validate_transition(incident.status, IncidentStatus.DISMISSED)
            prev_status = incident.status
            now = datetime.now(timezone.utc)
            incident.status = IncidentStatus.DISMISSED
            incident.dismissed_at = now
            reason = getattr(request, "dismissal_reason", None) or getattr(request, "reason", "")
            incident.dismissal_reason = reason
            incident.resolution_summary = f"[Dismissed] {reason}"

            audit = AuditRecord(
                incident_id=incident_id,
                actor=request.actor,
                action="DISMISS",
                previous_status=prev_status,
                new_status=IncidentStatus.DISMISSED,
                timestamp=now,
                details={"reason": reason},
            )
            self._audit_records.append(audit)
            return incident

    def add_note(self, incident_id: str, request: AddNoteRequest) -> IncidentNote:
        with self._lock:
            incident = self._incidents.get(incident_id)
            if not incident:
                raise KeyError(f"Incident '{incident_id}' not found")

            now = datetime.now(timezone.utc)
            note = IncidentNote(actor=request.actor, timestamp=now, content=request.content)
            incident.notes.append(note)

            audit = AuditRecord(
                incident_id=incident_id,
                actor=request.actor,
                action="ADD_NOTE",
                previous_status=incident.status,
                new_status=incident.status,
                timestamp=now,
                details={"note_snippet": request.content[:50]},
            )
            self._audit_records.append(audit)
            return note

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        with self._lock:
            return self._incidents.get(incident_id)

    def list_incidents(
        self,
        status: Optional[IncidentStatus] = None,
        priority: Optional[IncidentPriority] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Incident]:
        with self._lock:
            incidents = list(self._incidents.values())
            if status:
                incidents = [i for i in incidents if i.status == status]
            if priority:
                incidents = [i for i in incidents if i.priority == priority]
            incidents.sort(key=lambda i: i.created_at, reverse=True)
            return incidents[offset : offset + limit]

    def list_audit_records(self, incident_id: Optional[str] = None, limit: int = 100) -> List[AuditRecord]:
        with self._lock:
            records = self._audit_records
            if incident_id:
                records = [r for r in records if r.incident_id == incident_id]
            sorted_records = sorted(records, key=lambda r: r.timestamp, reverse=True)
            return sorted_records[:limit]

    def save_node(self, node: CityNode) -> CityNode:
        with self._lock:
            self._nodes[node.node_id] = node
            return node

    def get_node(self, node_id: str) -> Optional[CityNode]:
        with self._lock:
            return self._nodes.get(node_id)

    def list_nodes(self) -> List[CityNode]:
        with self._lock:
            return list(self._nodes.values())

    def save_federation_round(self, round_record: FederatedRound) -> FederatedRound:
        with self._lock:
            self._federation_rounds[round_record.round_id] = round_record
            return round_record

    def get_federation_round(self, round_id: str) -> Optional[FederatedRound]:
        with self._lock:
            return self._federation_rounds.get(round_id)

    def list_federation_rounds(self) -> List[FederatedRound]:
        with self._lock:
            return sorted(self._federation_rounds.values(), key=lambda r: r.created_at, reverse=True)

    def save_user_role(self, uid: str, role: str, email: Optional[str] = None) -> None:
        with self._lock:
            self._user_roles[uid] = {"role": role.upper(), "email": email or ""}

    def get_user_role(self, uid: str, email: Optional[str] = None) -> Optional[str]:
        with self._lock:
            if uid in self._user_roles:
                return self._user_roles[uid]["role"]
            if email:
                for entry in self._user_roles.values():
                    if entry.get("email") == email:
                        return entry["role"]
            return None

    def clear(self) -> None:
        with self._lock:
            self._reports.clear()
            self._events.clear()
            self._incidents.clear()
            self._audit_records.clear()
            self._nodes.clear()
            self._federation_rounds.clear()
            self._user_roles.clear()


class FileOperationalStore(InMemoryOperationalStore):
    """File-persisted operational store for local development."""

    def __init__(self, storage_dir: Optional[Path] = None):
        super().__init__()
        self.storage_dir = storage_dir or (Path(__file__).resolve().parent.parent.parent / "data" / "operational")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.reports_file = self.storage_dir / "reports.json"
        self.events_file = self.storage_dir / "events.json"
        self.incidents_file = self.storage_dir / "incidents.json"
        self.audit_file = self.storage_dir / "audit.json"
        self._load()

    def save_report(self, report: CitizenReport) -> CitizenReport:
        res = super().save_report(report)
        self._persist_reports()
        return res

    def save_event(self, event: PollutionEvent) -> PollutionEvent:
        res = super().save_event(event)
        self._persist_events()
        return res

    def create_incident(self, request: CreateIncidentRequest, event: PollutionEvent) -> Incident:
        res = super().create_incident(request, event)
        self._persist_incidents()
        self._persist_audit()
        return res

    def assign_incident(self, incident_id: str, request: AssignIncidentRequest) -> Incident:
        res = super().assign_incident(incident_id, request)
        self._persist_incidents()
        self._persist_audit()
        return res

    def acknowledge_incident(self, incident_id: str, request: AcknowledgeIncidentRequest) -> Incident:
        res = super().acknowledge_incident(incident_id, request)
        self._persist_incidents()
        self._persist_audit()
        return res

    def investigate_incident(self, incident_id: str, request: InvestigateIncidentRequest) -> Incident:
        res = super().investigate_incident(incident_id, request)
        self._persist_incidents()
        self._persist_audit()
        return res

    def resolve_incident(self, incident_id: str, request: ResolveIncidentRequest) -> Incident:
        res = super().resolve_incident(incident_id, request)
        self._persist_incidents()
        self._persist_audit()
        return res

    def dismiss_incident(self, incident_id: str, request: DismissIncidentRequest) -> Incident:
        res = super().dismiss_incident(incident_id, request)
        self._persist_incidents()
        self._persist_audit()
        return res

    def add_note(self, incident_id: str, request: AddNoteRequest) -> IncidentNote:
        res = super().add_note(incident_id, request)
        self._persist_incidents()
        self._persist_audit()
        return res

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
        if self.reports_file.exists():
            try:
                with open(self.reports_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    self._reports = {k: CitizenReport.model_validate(v) for k, v in raw.items()}
            except Exception:
                self._reports = {}

        if self.events_file.exists():
            try:
                with open(self.events_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    self._events = {k: PollutionEvent.model_validate(v) for k, v in raw.items()}
            except Exception:
                self._events = {}

        if self.incidents_file.exists():
            try:
                with open(self.incidents_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    self._incidents = {k: Incident.model_validate(v) for k, v in raw.items()}
            except Exception:
                self._incidents = {}

        if self.audit_file.exists():
            try:
                with open(self.audit_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    self._audit_records = [AuditRecord.model_validate(r) for r in raw]
            except Exception:
                self._audit_records = []


class FirestoreOperationalStore(OperationalStore):
    """Production GCP Firestore repository for durable multi-instance state."""

    def __init__(self, project: Optional[str] = None, database: Optional[str] = None):
        from google.cloud import firestore

        settings = get_settings()
        self.project = project or settings.GOOGLE_CLOUD_PROJECT
        self.database = database or settings.FIRESTORE_DATABASE or "(default)"
        self.client = firestore.Client(project=self.project, database=self.database)
        logger.info(f"Initialized FirestoreOperationalStore on project={self.project}, db={self.database}")

    def save_report(self, report: CitizenReport) -> CitizenReport:
        self.client.collection("reports").document(report.report_id).set(report.model_dump(mode="json"))
        return report

    def get_report(self, report_id: str) -> Optional[CitizenReport]:
        doc = self.client.collection("reports").document(report_id).get()
        if not doc.exists:
            return None
        return CitizenReport.model_validate(doc.to_dict())

    def list_reports(self, limit: int = 50) -> List[CitizenReport]:
        from google.cloud import firestore

        query = self.client.collection("reports").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit)
        return [CitizenReport.model_validate(d.to_dict()) for d in query.stream()]

    def save_event(self, event: PollutionEvent) -> PollutionEvent:
        self.client.collection("events").document(event.event_id).set(event.model_dump(mode="json"))
        return event

    def get_event(self, event_id: str) -> Optional[PollutionEvent]:
        doc = self.client.collection("events").document(event_id).get()
        if not doc.exists:
            return None
        return PollutionEvent.model_validate(doc.to_dict())

    def list_events(
        self,
        status: Optional[EventStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[PollutionEvent]:
        from google.cloud import firestore

        query = self.client.collection("events")
        if status:
            query = query.where("evidence_status", "==", status.value)
        query = query.order_by("timestamp", direction=firestore.Query.DESCENDING).offset(offset).limit(limit)
        return [PollutionEvent.model_validate(d.to_dict()) for d in query.stream()]

    def create_incident(self, request: CreateIncidentRequest, event: PollutionEvent) -> Incident:
        # Check active incident
        existing = (
            self.client.collection("incidents")
            .where("event_id", "==", event.event_id)
            .where("status", "not-in", ["RESOLVED", "DISMISSED"])
            .limit(1)
            .stream()
        )
        for doc in existing:
            return Incident.model_validate(doc.to_dict())

        priority = request.priority
        if not priority:
            if event.severity.value in ("CRITICAL", "HIGH"):
                priority = IncidentPriority.CRITICAL if event.severity.value == "CRITICAL" else IncidentPriority.HIGH
            elif event.severity.value == "MODERATE":
                priority = IncidentPriority.MEDIUM
            else:
                priority = IncidentPriority.LOW

        initial_status = IncidentStatus.DETECTED
        if event.evidence_coverage and event.evidence_coverage.diversity_eligible_for_alert:
            if event.evidence.fusion_score >= 0.55:
                initial_status = IncidentStatus.ALERTED

        now = datetime.now(timezone.utc)
        notes_list: List[IncidentNote] = []
        if request.initial_notes:
            notes_list.append(IncidentNote(actor=request.actor, timestamp=now, content=request.initial_notes))

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

        self.client.collection("incidents").document(incident.incident_id).set(incident.model_dump(mode="json"))

        # Append-only audit logging
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
            },
        )
        self.client.collection("audit_records").add(audit.model_dump(mode="json"))
        return incident

    def assign_incident(self, incident_id: str, request: AssignIncidentRequest) -> Incident:
        doc_ref = self.client.collection("incidents").document(incident_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise KeyError(f"Incident '{incident_id}' not found")
        incident = Incident.model_validate(doc.to_dict())

        self._validate_transition(incident.status, IncidentStatus.ASSIGNED)
        prev_status = incident.status
        incident.status = IncidentStatus.ASSIGNED
        incident.assigned_to = request.assigned_to
        incident.assigned_team = request.assigned_team or incident.assigned_team

        now = datetime.now(timezone.utc)
        if request.notes:
            incident.notes.append(IncidentNote(actor=request.actor, timestamp=now, content=request.notes))

        doc_ref.set(incident.model_dump(mode="json"))

        audit = AuditRecord(
            incident_id=incident_id,
            actor=request.actor,
            action="ASSIGN",
            previous_status=prev_status,
            new_status=IncidentStatus.ASSIGNED,
            timestamp=now,
            details={"assigned_to": request.assigned_to, "assigned_team": request.assigned_team},
        )
        self.client.collection("audit_records").add(audit.model_dump(mode="json"))
        return incident

    def acknowledge_incident(self, incident_id: str, request: AcknowledgeIncidentRequest) -> Incident:
        doc_ref = self.client.collection("incidents").document(incident_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise KeyError(f"Incident '{incident_id}' not found")
        incident = Incident.model_validate(doc.to_dict())

        self._validate_transition(incident.status, IncidentStatus.ACKNOWLEDGED)
        prev_status = incident.status
        now = datetime.now(timezone.utc)
        incident.status = IncidentStatus.ACKNOWLEDGED
        incident.acknowledged_at = now
        if request.notes:
            incident.notes.append(IncidentNote(actor=request.actor, timestamp=now, content=request.notes))

        doc_ref.set(incident.model_dump(mode="json"))

        audit = AuditRecord(
            incident_id=incident_id,
            actor=request.actor,
            action="ACKNOWLEDGE",
            previous_status=prev_status,
            new_status=IncidentStatus.ACKNOWLEDGED,
            timestamp=now,
            details={"acknowledged_by": request.actor},
        )
        self.client.collection("audit_records").add(audit.model_dump(mode="json"))
        return incident

    def investigate_incident(self, incident_id: str, request: InvestigateIncidentRequest) -> Incident:
        doc_ref = self.client.collection("incidents").document(incident_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise KeyError(f"Incident '{incident_id}' not found")
        incident = Incident.model_validate(doc.to_dict())

        self._validate_transition(incident.status, IncidentStatus.INVESTIGATING)
        prev_status = incident.status
        incident.status = IncidentStatus.INVESTIGATING

        now = datetime.now(timezone.utc)
        if request.field_observations:
            incident.notes.append(
                IncidentNote(actor=request.actor, timestamp=now, content=f"[Investigation] {request.field_observations}")
            )

        doc_ref.set(incident.model_dump(mode="json"))

        audit = AuditRecord(
            incident_id=incident_id,
            actor=request.actor,
            action="INVESTIGATE",
            previous_status=prev_status,
            new_status=IncidentStatus.INVESTIGATING,
            timestamp=now,
            details={"findings": request.field_observations},
        )
        self.client.collection("audit_records").add(audit.model_dump(mode="json"))
        return incident

    def resolve_incident(self, incident_id: str, request: ResolveIncidentRequest) -> Incident:
        doc_ref = self.client.collection("incidents").document(incident_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise KeyError(f"Incident '{incident_id}' not found")
        incident = Incident.model_validate(doc.to_dict())

        self._validate_transition(incident.status, IncidentStatus.RESOLVED)
        prev_status = incident.status
        now = datetime.now(timezone.utc)
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = now
        incident.resolution_summary = request.resolution_summary

        if request.final_notes:
            incident.notes.append(
                IncidentNote(actor=request.actor, timestamp=now, content=f"[Resolution] {request.final_notes}")
            )

        doc_ref.set(incident.model_dump(mode="json"))

        audit = AuditRecord(
            incident_id=incident_id,
            actor=request.actor,
            action="RESOLVE",
            previous_status=prev_status,
            new_status=IncidentStatus.RESOLVED,
            timestamp=now,
            details={"resolution_summary": request.resolution_summary},
        )
        self.client.collection("audit_records").add(audit.model_dump(mode="json"))
        return incident

    def dismiss_incident(self, incident_id: str, request: DismissIncidentRequest) -> Incident:
        doc_ref = self.client.collection("incidents").document(incident_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise KeyError(f"Incident '{incident_id}' not found")
        incident = Incident.model_validate(doc.to_dict())

        self._validate_transition(incident.status, IncidentStatus.DISMISSED)
        prev_status = incident.status
        now = datetime.now(timezone.utc)
        incident.status = IncidentStatus.DISMISSED
        incident.dismissed_at = now
        reason = getattr(request, "dismissal_reason", None) or getattr(request, "reason", "")
        incident.dismissal_reason = reason
        incident.resolution_summary = f"[Dismissed] {reason}"

        doc_ref.set(incident.model_dump(mode="json"))

        audit = AuditRecord(
            incident_id=incident_id,
            actor=request.actor,
            action="DISMISS",
            previous_status=prev_status,
            new_status=IncidentStatus.DISMISSED,
            timestamp=now,
            details={"reason": reason},
        )
        self.client.collection("audit_records").add(audit.model_dump(mode="json"))
        return incident

    def add_note(self, incident_id: str, request: AddNoteRequest) -> IncidentNote:
        doc_ref = self.client.collection("incidents").document(incident_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise KeyError(f"Incident '{incident_id}' not found")
        incident = Incident.model_validate(doc.to_dict())

        now = datetime.now(timezone.utc)
        note = IncidentNote(actor=request.actor, timestamp=now, content=request.content)
        incident.notes.append(note)
        doc_ref.set(incident.model_dump(mode="json"))

        audit = AuditRecord(
            incident_id=incident_id,
            actor=request.actor,
            action="ADD_NOTE",
            previous_status=incident.status,
            new_status=incident.status,
            timestamp=now,
            details={"note_snippet": request.content[:50]},
        )
        self.client.collection("audit_records").add(audit.model_dump(mode="json"))
        return note

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        doc = self.client.collection("incidents").document(incident_id).get()
        if not doc.exists:
            return None
        return Incident.model_validate(doc.to_dict())

    def list_incidents(
        self,
        status: Optional[IncidentStatus] = None,
        priority: Optional[IncidentPriority] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Incident]:
        from google.cloud import firestore

        query = self.client.collection("incidents")
        if status:
            query = query.where("status", "==", status.value)
        if priority:
            query = query.where("priority", "==", priority.value)
        query = query.order_by("created_at", direction=firestore.Query.DESCENDING).offset(offset).limit(limit)
        return [Incident.model_validate(d.to_dict()) for d in query.stream()]

    def list_audit_records(self, incident_id: Optional[str] = None, limit: int = 100) -> List[AuditRecord]:
        from google.cloud import firestore

        query = self.client.collection("audit_records")
        if incident_id:
            query = query.where("incident_id", "==", incident_id)
        query = query.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit)
        return [AuditRecord.model_validate(d.to_dict()) for d in query.stream()]

    def save_node(self, node: CityNode) -> CityNode:
        self.client.collection("nodes").document(node.node_id).set(node.model_dump(mode="json"))
        return node

    def get_node(self, node_id: str) -> Optional[CityNode]:
        doc = self.client.collection("nodes").document(node_id).get()
        if not doc.exists:
            return None
        return CityNode.model_validate(doc.to_dict())

    def list_nodes(self) -> List[CityNode]:
        return [CityNode.model_validate(d.to_dict()) for d in self.client.collection("nodes").stream()]

    def save_federation_round(self, round_record: FederatedRound) -> FederatedRound:
        self.client.collection("federation_rounds").document(round_record.round_id).set(round_record.model_dump(mode="json"))
        return round_record

    def get_federation_round(self, round_id: str) -> Optional[FederatedRound]:
        doc = self.client.collection("federation_rounds").document(round_id).get()
        if not doc.exists:
            return None
        return FederatedRound.model_validate(doc.to_dict())

    def list_federation_rounds(self) -> List[FederatedRound]:
        from google.cloud import firestore

        query = self.client.collection("federation_rounds").order_by("created_at", direction=firestore.Query.DESCENDING)
        return [FederatedRound.model_validate(d.to_dict()) for d in query.stream()]

    def save_user_role(self, uid: str, role: str, email: Optional[str] = None) -> None:
        self.client.collection("users").document(uid).set({"role": role.upper(), "email": email or ""})

    def get_user_role(self, uid: str, email: Optional[str] = None) -> Optional[str]:
        doc = self.client.collection("users").document(uid).get()
        if doc.exists:
            return doc.to_dict().get("role")
        if email:
            query = self.client.collection("users").where("email", "==", email).limit(1).stream()
            for d in query:
                return d.to_dict().get("role")
        return None

    def clear(self) -> None:
        """Clear all collections (intended for integration testing)."""
        for col in ["reports", "events", "incidents", "audit_records", "nodes", "federation_rounds", "users"]:
            docs = self.client.collection(col).stream()
            for doc in docs:
                doc.reference.delete()


_store_instance: Optional[OperationalStore] = None


def get_operational_store() -> OperationalStore:
    """Singleton factory for obtaining operational repository based on environment."""
    global _store_instance
    if _store_instance is None:
        settings = get_settings()
        if settings.ENVIRONMENT == "production":
            try:
                _store_instance = FirestoreOperationalStore()
            except Exception as e:
                logger.warning(f"Failed to initialize Firestore store: {e}; falling back to file store.")
                _store_instance = FileOperationalStore()
        elif settings.ENVIRONMENT == "test":
            _store_instance = InMemoryOperationalStore()
        else:
            _store_instance = FileOperationalStore()
    return _store_instance
