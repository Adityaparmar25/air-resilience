"""Operational data store for citizen reports and active pollution events.

Provides thread-safe in-memory caching with JSON persistence for operational state.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional

from schemas.event import EventStatus, PollutionEvent
from schemas.report import CitizenReport


class OperationalStore:
    """In-memory operational store with optional file-based state persistence."""

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or (Path(__file__).resolve().parent.parent.parent / "data" / "operational")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.reports_file = self.storage_dir / "reports.json"
        self.events_file = self.storage_dir / "events.json"

        self._lock = Lock()
        self._reports: Dict[str, CitizenReport] = {}
        self._events: Dict[str, PollutionEvent] = {}

        self._load()

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
                events = [e for e in events if e.status == status]
            events.sort(key=lambda e: e.timestamp, reverse=True)
            return events[:limit]

    def clear(self) -> None:
        """Clear all stored reports and events (useful for clean test runs)."""
        with self._lock:
            self._reports.clear()
            self._events.clear()
            if self.reports_file.exists():
                self.reports_file.unlink()
            if self.events_file.exists():
                self.events_file.unlink()

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

    def _load(self) -> None:
        if self.reports_file.exists():
            try:
                with open(self.reports_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for k, v in data.items():
                    self._reports[k] = CitizenReport.model_validate(v)
            except Exception:
                pass

        if self.events_file.exists():
            try:
                with open(self.events_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for k, v in data.items():
                    self._events[k] = PollutionEvent.model_validate(v)
            except Exception:
                pass


_store: Optional[OperationalStore] = None


def get_operational_store() -> OperationalStore:
    """Singleton getter for operational store."""
    global _store
    if _store is None:
        _store = OperationalStore()
    return _store
