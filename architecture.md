# Clean Air & Climate Resilience — Architecture

## 1. Architecture Principle

The system is a pipeline, not a dashboard.

```text
DATA
 ↓
QUALITY
 ↓
DETECTION
 ↓
EVIDENCE FUSION
 ↓
FORECAST
 ↓
EXPLANATION
 ↓
ACTION
 ↓
FEDERATION
```

---

## 2. High-Level Architecture

```text
                         DATA SOURCES
 ┌──────────┬──────────┬────────────┬──────────────┐
 │  CPCB    │   IMD    │ Sentinel-5P│ NASA FIRMS  │
 └────┬─────┴────┬─────┴──────┬─────┴──────┬──────┘
      │          │            │             │
      └──────────┴────────────┴─────────────┘
                         ↓
                INGESTION / ADAPTERS
                         ↓
                VALIDATION / QUALITY
                         ↓
              ┌──────────┴───────────┐
              │                      │
           BigQuery              Firestore
      analytical history      operational state
              │                      │
              └──────────┬───────────┘
                         ↓
               EVENT / ML SERVICES
            ┌────────────┼────────────┐
            ↓            ↓            ↓
       anomaly       forecasting   evidence
       detection       model        fusion
            │            │            │
            └────────────┼────────────┘
                         ↓
                    POLLUTION EVENT
                         ↑
                         │
                  Gemini Vision
                  / Gemini summary
                         │
                    citizen image
                         │
                         ↓
                 AUTHORITY WORKFLOW
                         ↓
                  alert / assign /
                  investigate /
                     resolve
                         ↓
                  FEDERATED LAYER
             Delhi / Haryana / UP nodes
                         ↓
                    shared model
```

---

## 3. Frontend

Recommended:

- React / Next.js
- Tailwind CSS
- Google Maps Platform

Responsibilities:

- map rendering
- event visualization
- citizen report UI
- authority incident workflow
- model/network status
- replay controls

The frontend does not perform sensitive AI/model logic.

---

## 4. Backend

Recommended:

- Python
- FastAPI
- Cloud Run

Responsibilities:

- authentication/authorization boundary
- API orchestration
- event creation
- evidence fusion
- workflow state changes
- validation of AI outputs
- audit logging
- integration with external services

---

## 5. Analytical Data Layer

Recommended:

### BigQuery

Stores:

- historical CPCB observations
- historical weather
- satellite-derived features
- fire detections
- model features
- forecast/evaluation results

BigQuery is the analytical source for model pipelines.

---

## 6. Operational Data Layer

Recommended:

### Firestore

Stores:

- users/roles
- citizen reports
- active events
- alerts
- assignments
- investigation status
- city configuration
- federation rounds
- audit/event metadata

Do not use Firestore as the primary historical time-series warehouse.

---

## 7. AI Layer

### Gemini Vision

```text
image
 ↓
structured visual evidence
```

### Gemini reasoning

```text
validated event evidence
 ↓
operator-readable explanation
```

### Forecasting

```text
time series
 ↓
TimesFM / AI.FORECAST
 ↓
numerical forecast
```

### Anomaly detection

Initial:

- local historical baseline
- z-score / deviation

Then:

- BigQuery ML anomaly detection

---

## 8. Event Engine Architecture

```text
Raw signal
   ↓
Signal validation
   ↓
Local anomaly
   ↓
Spatial/temporal lookup
   ↓
Supporting evidence retrieval
   ↓
Evidence normalization
   ↓
Evidence fusion
   ↓
Event classification
   ↓
Forecast
   ↓
Event state machine
```

---

## 9. API Surface

```text
POST /api/v1/reports
POST /api/v1/reports/{id}/analyze

GET  /api/v1/events
GET  /api/v1/events/{id}
POST /api/v1/events/detect
POST /api/v1/events/{id}/forecast
POST /api/v1/events/{id}/alert
PATCH /api/v1/events/{id}/status

POST /api/v1/replay/start/{scenario_id}

POST /api/v1/federation/register-node
POST /api/v1/federation/train
POST /api/v1/federation/update
POST /api/v1/federation/aggregate
GET  /api/v1/federation/rounds/{id}
```

---

## 10. Canonical Data Contract

### Monitoring observation

```json
{
  "station_id": "string",
  "station_name": "string",
  "timestamp": "datetime",
  "lat": "float",
  "lon": "float",
  "city": "string",
  "state": "string",
  "pm25": "float|null",
  "pm10": "float|null",
  "no2": "float|null",
  "so2": "float|null",
  "co": "float|null",
  "o3": "float|null"
}
```

### Event

```json
{
  "event_id": "string",
  "timestamp": "datetime",
  "location": {
    "lat": "float",
    "lng": "float",
    "cell_id": "string"
  },
  "status": "string",
  "event_type": "string",
  "severity": "string",
  "evidence": {},
  "forecast": {},
  "probable_source": "string|null",
  "human_verification_required": "boolean"
}
```

---

## 11. Service Boundaries

### Ingestion service

Owns:

- source adapters
- normalization
- quality flags

### ML service

Owns:

- anomaly detection
- forecasting
- evaluation

### AI service

Owns:

- Gemini requests
- schemas
- prompt versions
- response validation

### Fusion service

Owns:

- evidence matching
- event scoring
- event state transitions

### Federation service

Owns:

- node registration
- local training requests
- model update handling
- aggregation

### API service

Owns:

- external application API
- authorization
- workflow execution

---

## 12. Failure Handling

If one source fails:

```text
Source unavailable
    ↓
mark unavailable
    ↓
continue with available evidence
    ↓
reduce evidence coverage
    ↓
do not silently treat as negative evidence
```

Examples:

- satellite unavailable ≠ no satellite anomaly
- FIRMS unavailable ≠ no fire
- Gemini unavailable ≠ no smoke
- weather unavailable ≠ no wind

---

## 13. Replay Architecture

A replay scenario contains timestamped observations.

```text
scenario
  ├── ground observations
  ├── citizen reports
  ├── satellite signals
  ├── weather
  └── fire detections
```

Replay engine controls the event clock.

This guarantees a reproducible judging demo without falsely presenting recorded data as live.

---

## 14. Federated Architecture

```text
                    COORDINATOR
                         │
                  global model vN
                         │
          ┌──────────────┼──────────────┐
          ↓              ↓              ↓
       Delhi          Haryana            UP
       node             node            node
          │              │              │
      local data      local data      local data
          │              │              │
       local train    local train     local train
          │              │              │
       update         update          update
          └──────────────┼──────────────┘
                         ↓
                   aggregation
                         ↓
                  global model vN+1
```

Raw training rows should remain within each node in the prototype design.

---

## 15. Deployment

Recommended:

```text
Next.js
    ↓
Cloud Run
    ↓
FastAPI
    ↓
Firestore + BigQuery
    ↓
Gemini / Earth Engine / external source adapters
```

Separate ingestion jobs from request/response APIs.

---

## 16. Build Order

```text
1. CPCB ingestion
2. canonical schema
3. quality pipeline
4. baseline anomaly
5. PM2.5 forecast
6. Gemini Vision
7. evidence fusion
8. pollution event API
9. minimal command center
10. authority workflow
11. satellite/FIRMS/IMD expansion
12. federation
13. replay
14. deployment
15. demo hardening
```

---

## 17. Architecture Boundary

The team must preserve this boundary:

```text
Gemini = interpretation / multimodal reasoning

ML = numerical prediction

Backend = validation / state change

Data sources = observations

Human authority = final operational decision
```

No component should silently take another component's responsibility.
