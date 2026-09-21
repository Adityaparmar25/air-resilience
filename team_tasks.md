# Clean Air & Climate Resilience — 3-Member Team Work Plan

## Team Rule

The three members are building **one system**.

No member owns an isolated "mini-project."

Every task must connect to the shared event pipeline:

```text
DATA
 ↓
DETECT
 ↓
CORROBORATE
 ↓
FORECAST
 ↓
EXPLAIN
 ↓
ALERT
 ↓
COORDINATE
```

---

# Member 1 — AI + Data / Model Owner

## Primary ownership

Own the evidence and model layer.

### Tasks

1. CPCB ingestion and normalization
2. Data-quality pipeline
3. Station/time-series preparation
4. PM2.5 anomaly detection
5. Forecast model
6. Forecast evaluation
7. Gemini Vision schema and prompts
8. Evidence features for fusion

### Deliverables

```text
services/ingestion/
services/anomaly/
services/forecasting/
schemas/citizen_image_analysis.json
notebooks/
docs/model-evaluation.md
```

### Must expose

```text
GET /internal/stations/{id}/series
POST /internal/anomaly
POST /internal/forecast
POST /internal/image-analysis
```

### Must NOT own independently

- frontend design
- authority workflow rules
- database authorization
- changing product scope
- inventing new user features

### Track constraint

Every model output must be usable by the Event Engine.

---

# Member 2 — Backend + Federation + Security Owner

## Primary ownership

Own the operational system and system integrity.

### Tasks

1. FastAPI service
2. Firestore schema
3. Pollution-event state machine
4. Evidence-fusion API
5. Alert/assignment workflow
6. Federation coordinator and node simulation
7. Authentication/authorization
8. audit logging
9. replay backend
10. deployment infrastructure

### Deliverables

```text
apps/api/
services/fusion/
services/federation/
infra/
docs/api-contract.md
```

### Must expose

```text
POST /api/v1/reports
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
```

### Must NOT own independently

- changing ML methodology without Member 1
- adding unrelated product features
- creating a second event schema
- bypassing security controls for demo convenience

### Track constraint

Backend must enforce the contracts defined in `architecture.md` and `security.md`.

---

# Member 3 — Frontend + Product + Demo Owner

## Primary ownership

Own how the working system is understood and demonstrated.

### Tasks

1. Command Center
2. Map
3. Event detail page
4. Citizen report flow
5. Authority incident flow
6. Network/Federation view
7. Data/model health view
8. Replay controls
9. demo script
10. pitch visuals and screenshots

### Deliverables

```text
apps/web/
docs/demo-flow.md
docs/ui-state-map.md
```

### Must consume

Only the backend APIs.

The frontend must not:

- calculate event scores
- invent forecasts
- call Gemini directly with secret keys
- make authorization decisions

### Track constraint

The UI must follow the actual event lifecycle:

```text
POSSIBLE
→ CORROBORATED
→ ALERTED
→ INVESTIGATING
→ RESOLVED
```

Do not design screens for features that do not exist in the backend.

---

# Shared Responsibility

All three members must:

- review pull requests
- run the end-to-end demo
- test failure cases
- keep docs updated
- avoid unapproved scope changes

---

# Ownership Matrix

| Area | Member 1 | Member 2 | Member 3 |
|---|---:|---:|---:|
| CPCB data | OWNER | Support | Informed |
| Anomaly model | OWNER | Support | Informed |
| Forecast | OWNER | Support | Informed |
| Gemini Vision | OWNER | Support | Informed |
| Evidence fusion | Support | OWNER | Informed |
| Event API | Support | OWNER | Informed |
| Firestore | Informed | OWNER | Informed |
| Security | Support | OWNER | Support |
| Federation | Support | OWNER | Display |
| Frontend | Informed | Support | OWNER |
| Map | Informed | Support | OWNER |
| Replay UI | Informed | Support | OWNER |
| Demo | Support | Support | OWNER |
| Final integration | Shared | Shared | Shared |

---

# Anti-Diversion Rules

## Rule 1 — One backlog

No private feature lists.

All tasks live in one issue board.

## Rule 2 — No unapproved feature

A new feature must answer:

1. Which challenge requirement does it satisfy?
2. Which stage of the event pipeline does it improve?
3. What existing work will be removed to make room?

If there is no good answer, do not build it.

## Rule 3 — No duplicate schemas

Only the canonical schemas in `architecture.md` are valid.

## Rule 4 — No frontend invention

A UI state must correspond to a real backend state.

## Rule 5 — No model invention

A numerical claim must come from the model/data layer.

## Rule 6 — No AI decoration

Do not add a chatbot, AI summary, AI score, or AI button unless it improves the core event workflow.

## Rule 7 — Interface before implementation

Each owner documents:

```text
input
output
error cases
```

before another member integrates the component.

---

# Daily 15-Minute Sync

Each member answers:

1. What did I finish?
2. What exact contract did I expose/change?
3. What is blocking me?
4. Is anything pulling the project away from the agreed scope?

The fourth question is mandatory.

---

# Integration Checkpoints

## Checkpoint 1

Member 1:

```text
CPCB → anomaly → forecast
```

Member 2:

```text
event schema + API skeleton
```

Member 3:

```text
static event view using the exact schema
```

Then integrate.

## Checkpoint 2

```text
Gemini → structured evidence
       ↓
Event Engine
       ↓
Frontend event detail
```

## Checkpoint 3

```text
event
 ↓
alert
 ↓
investigation
 ↓
resolved
```

## Checkpoint 4

```text
Delhi
Haryana
UP
 ↓
local training
 ↓
aggregation
 ↓
shared model
```

## Checkpoint 5

Full replay:

```text
citizen report
→ AI analysis
→ multi-source evidence
→ event
→ forecast
→ alert
→ response
→ federation
```

---

# Definition of Team Success

The team is on track when every member can explain:

```text
What is the problem?
What is our solution?
What data enters the system?
Where does Google AI run?
How is an event created?
How is a forecast produced?
Who receives the alert?
How do three jurisdictions participate?
```

If any member cannot answer these, stop feature work and synchronize before adding more code.
