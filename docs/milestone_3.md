# Clean Air & Climate Resilience — Milestone 3 (Phase 3C)

## Milestone Objective

Phase 3C bridges corroborated environmental phenomena with government and operational authority workflows:

```text
Pollution Event
  ↓
External Evidence (IMD Weather, NASA FIRMS Thermal, Sentinel-5P / Earth Engine)
  ↓
Forecast Context (+6h, +12h, +24h with 95% uncertainty bounds)
  ↓
AUTHORITY INCIDENT
  ↓
ASSIGN → ACKNOWLEDGE → INVESTIGATE → RESOLVE / DISMISS
  ↓
Server-Side Validated State Machine & Immutable Audit Log
  ↓
Authority Command Center (Next.js Dashboard)
```

---

## Architectural Decisions Implemented

### Decision D-016: Strict Separation of Evidence Status and Operational Lifecycle
Prior iterations risk conflating the scientific confidence of an event with its real-world dispatch lifecycle. In Phase 3C:
- **`event.evidence_status`**: Represents purely scientific corroboration confidence:
  - `FALSE_POSITIVE` (< 0.35)
  - `POSSIBLE` (0.35 - 0.55)
  - `CORROBORATED` (0.55 - 0.75)
  - `HIGH_CONFIDENCE` (>= 0.75)
- **`event.operational_status` & `incident.status`**: Represents operational dispatch and field resolution:
  - `DETECTED` → `ALERTED` → `ASSIGNED` → `ACKNOWLEDGED` → `INVESTIGATING` → `RESOLVED` / `DISMISSED`
- Under no circumstances is a single status field overloaded with both meanings.

### Decision D-017: Minimum Evidence Diversity for Automated Alerting
To eliminate single-source false alarms while preserving rapid notification:
- Automated escalation to `ALERTED` requires $\ge 2$ independent corroborated evidence classes (e.g. Ground Sensor + Satellite, Citizen Report + Thermal Anomaly, or Ground Sensor + Weather Inversion).
- Events with only 1 active signal class remain in `DETECTED` status, requiring manual dispatcher assessment before operational escalation.
- Existing fusion weights (D-006) are strictly maintained.

---

## External Adapters & Scientific Integrity

All external adapters implement strict error isolation, preserve metadata (sensor IDs, instrument names, acquisition timestamps), handle timeouts gracefully by returning `available: false`, and supply deterministic offline fixtures:

1. **IMD Weather Adapter (`services/ingestion/imd_adapter.py`)**:
   - Fetches temperature, relative humidity, wind speed, wind direction, and rainfall.
   - Evaluates inversion risk and boundary layer stagnation indicators.
   - Evaluates downwind plume dispersion vectors.
2. **NASA FIRMS Adapter (`services/ingestion/firms_adapter.py`)**:
   - Detects thermal anomalies, brightness temperature, and Fire Radiative Power (FRP).
   - **Guardrail Enforcement**: Strictly states *"nearby fire/thermal anomaly detected"*. It is **never** permitted to claim *"crop burning confirmed"*.
3. **Sentinel-5P Satellite Adapter (`services/ingestion/sentinel_adapter.py`)**:
   - Retrieves tropospheric NO2 column densities ($mol/m^2$) and absorbing aerosol index (AAI).
   - **Guardrail Enforcement**: Atmospheric column totals are **never** presented as ground-level PM2.5 measurements.

---

## Forecast Context Integration

Phase 3C connects the ML/statistical forecast service directly into the pollution event and authority incident context:
- Supplies +6h, +12h, and +24h projections.
- Provides 95% statistical confidence intervals (`lower_95`, `upper_95`).
- Displays provider identifier (`provider_name`).
- Strictly adheres to Decision D-008: Never fabrics accuracy metrics or invents unverified data.

---

## Incident State Machine & Immutable Audit Log

The incident state machine (`services/operational/store.py`) enforces server-side validation on every status transition:

| Current Status | Permitted Transitions |
|---|---|
| `ALERTED` | `ASSIGNED`, `DISMISSED` |
| `ASSIGNED` | `ACKNOWLEDGED`, `DISMISSED` |
| `ACKNOWLEDGED` | `INVESTIGATING`, `DISMISSED` |
| `INVESTIGATING` | `RESOLVED`, `DISMISSED` |
| `RESOLVED` | *(Terminal)* |
| `DISMISSED` | *(Terminal)* |

Every transition automatically generates an immutable audit record:
```json
{
  "audit_id": "aud_018f921a",
  "incident_id": "INC-447A83",
  "actor": "Inspector Rajesh Kumar",
  "action": "RESOLVE",
  "previous_status": "INVESTIGATING",
  "new_status": "RESOLVED",
  "timestamp": "2026-09-22T14:12:50.039440+00:00",
  "details": {
    "resolution_summary": "Industrial furnace shut down; water-fog cannon deployed."
  }
}
```

---

## Implemented API Surface

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/incidents` | Escalate a corroborated pollution event to an authority incident |
| `GET` | `/api/v1/incidents` | List active authority incidents with optional status filter |
| `GET` | `/api/v1/incidents/{id}` | Retrieve incident details, status, notes, and evidence summary |
| `POST` | `/api/v1/incidents/{id}/assign` | Assign incident to an inspector or response team |
| `POST` | `/api/v1/incidents/{id}/acknowledge` | Mark incident as acknowledged by field response team |
| `POST` | `/api/v1/incidents/{id}/investigate` | Transition incident to active on-site investigation |
| `POST` | `/api/v1/incidents/{id}/resolve` | Resolve incident with mandatory resolution summary |
| `POST` | `/api/v1/incidents/{id}/dismiss` | Dismiss incident with mandatory dismissal rationale |
| `POST` | `/api/v1/incidents/{id}/notes` | Add timestamped inspector/dispatcher field notes |
| `GET` | `/api/v1/incidents/{id}/audit` | Retrieve complete, tamper-evident audit history |

---

## Verification & Test Results

1. **Unit & Integration Suite**:
   ```bash
   py -m pytest -v tests/
   ```
   - **73 of 73 tests passing (100%)** across schema validation, quality pipeline, anomaly detection, forecast abstraction, Gemini vision analysis, spatial correlation, external adapters (IMD, FIRMS, Sentinel-5P), and incident lifecycle state machine.

2. **Deterministic Replay Demo**:
   ```bash
   py apps/api/demo_phase3c.py
   ```
   - Replays end-to-end multi-source correlation $\rightarrow$ 5/5 evidence coverage $\rightarrow$ forecast bounds $\rightarrow$ incident dispatch lifecycle $\rightarrow$ resolution $\rightarrow$ audit trail inspection.

3. **Frontend Production Build**:
   ```bash
   cd apps/web && npm run build
   ```
   - Optimized Next.js production build succeeded with zero TypeScript errors.
