# Clean Air & Climate Resilience — Decision Log

## Purpose

This document freezes major product and technical decisions so the three team members do not independently redesign the project.

Every new major decision must be added here before implementation changes the architecture.

---

## D-001 — Product Positioning

### Decision

Build an **AI-powered pollution early-warning and response network**, not an AQI dashboard.

### Reason

The challenge emphasizes hidden local pollution events, forecasting, alerts, interoperability, and rapid response.

### Consequence

Every feature must support:

```text
detect → corroborate → forecast → act → coordinate
```

---

## D-002 — Prototype Geography

### Decision

Primary geography:

- Delhi
- Noida / Greater Noida
- Ghaziabad
- Manesar
- Bawal
- Bhiwadi
- Neemrana

Regional context may include Punjab, Haryana and western Uttar Pradesh for agricultural-burning signals.

### Reason

This gives us a cross-jurisdiction economic-corridor context without claiming national coverage.

---

## D-003 — Primary Prediction Target

### Decision

Forecast **hourly PM2.5**, initially at monitoring-station level.

### Reason

This provides a concrete numerical target and avoids pretending to directly forecast a full continuous spatial pollution field in the first build.

---

## D-004 — Google AI Usage

### Decision

Google AI must perform real product work in at least these areas:

1. Gemini multimodal image analysis
2. Google predictive modeling / TimesFM-based forecasting
3. Gemini evidence explanation / structured incident summary

### Rule

No artificial AI layer should be added only for the pitch.

---

## D-005 — Source Attribution

### Decision

Source attribution remains probabilistic.

Allowed:

> "Likely combustion-related."

Not allowed without independent verification:

> "Factory X caused the event."

---

## D-006 — Evidence Fusion

### Decision

Start with a transparent weighted evidence score.

### Starting weights

- Ground anomaly: 30%
- Satellite: 20%
- Citizen: 15%
- Weather: 15%
- Fire: 20%

### Important

These are prototype parameters and must be evaluated/tuned using replay or historical data.

---

## D-007 — Missing Data

### Decision

Missing data is represented as unavailable/null.

It must not become zero.

Example:

```text
FIRMS unavailable
```

must not be interpreted as:

```text
No fire
```

---

## D-008 — Forecast Validation

### Decision

We will compare the main forecast model with at least one baseline.

The team will report measured error only.

No invented accuracy percentage is allowed in the pitch or README.

---

## D-009 — Replay Mode

### Decision

A deterministic replay mode is mandatory.

### Reason

Live external data is unpredictable during judging.

### Rule

Recorded data must be explicitly labeled as replay/historical.

---

## D-010 — Federated Scope

### Decision

Implement a minimum working multi-node architecture using Delhi, Haryana and Uttar Pradesh logical nodes.

### Requirement

Each node should be able to:

- use local data
- perform local model training/inference
- produce a model update
- send the update to the coordinator
- receive an aggregated model

Do not claim production-grade federated privacy unless implemented and tested.

---

## D-011 — Database Split

### Decision

BigQuery = analytical/historical data.

Firestore = operational application state.

### Reason

This keeps analytical time series separate from live incident documents.

---

## D-012 — Gemini Safety Boundary

### Decision

Gemini may interpret images and summarize validated evidence.

Gemini may not directly execute unrestricted database or administrative actions.

### Flow

```text
Gemini output
    ↓
schema validation
    ↓
backend authorization
    ↓
action
```

---

## D-013 — Feature Freeze

### MVP Must Have

- data ingestion
- PM2.5 anomaly detection
- PM2.5 forecast
- citizen photo analysis
- evidence fusion
- event creation
- authority workflow
- replay mode
- multi-node federation prototype
- deployed working demo

### Explicitly Deprioritized

- social feed
- public chat
- gamification
- complex user profiles
- native mobile app
- full national rollout
- automatic enforcement
- custom hardware

---

## D-014 — Change Control

A team member proposing a major change must answer:

1. Which challenge requirement does it improve?
2. Which existing component does it replace or modify?
3. What new dependency does it add?
4. What demo step does it improve?
5. What work must be removed to keep scope constant?

If these answers are not clear, the change is postponed.

---

## D-015 — Definition of Done

A component is not "done" because it exists.

It is done only when:

- it is tested,
- it has an owner,
- another team member can run it,
- its inputs/outputs match the agreed contract,
- it does not break the end-to-end demo.

---

## D-016 — Architectural Separation of Evidence Status and Operational Lifecycle

### Decision

Separate the classification of scientific/multimodal evidence from the operational authority workflow lifecycle. Do not use a single status field for both meanings.

Every event and incident explicitly distinguishes:

1. **`evidence_status`**:
   - `FALSE_POSITIVE`
   - `POSSIBLE`
   - `CORROBORATED`
   - `HIGH_CONFIDENCE`

2. **`operational_status`**:
   - `DETECTED`
   - `ALERTED`
   - `ASSIGNED`
   - `ACKNOWLEDGED`
   - `INVESTIGATING`
   - `RESOLVED`
   - `DISMISSED`

### Reason

An event may have `HIGH_CONFIDENCE` evidence while simultaneously being in the operational state of `ASSIGNED` or `INVESTIGATING`. Collapsing these orthogonal dimensions conflated algorithmic confidence with human administrative response.

---

## D-017 — Minimum Evidence Diversity for Operational Alerting

### Decision

Before automatically creating an operational alert or escalating an event/incident to `ALERTED` status, the platform requires at least **two independent evidence classes** to be present and corroborating.

### Examples

- Ground Sensor + Citizen Report = **Eligible for automated alert**
- Ground Sensor + Weather Dispersion Context = **Eligible for automated alert**
- Citizen Photo only = **Requires manual human review** (`DETECTED`)
- Gemini Vision output only = **Requires manual human review** (`DETECTED`)

### Rule

Existing fusion weights from D-006 are strictly preserved. Evidence signals that are unavailable remain `None` and are excluded from the normalization denominator (per D-007).

---

## D-018 — Data-Local Training with Federated Model-Update Aggregation

### Decision

Implement cross-city knowledge sharing as **data-local training with federated model-update aggregation** across regional city nodes (Delhi, Haryana, Uttar Pradesh).

1. **Zero Raw Training Observation Leakage**:
   Raw time-series observations, ground sensor records, and citizen reports remain strictly confined to the local node's data partition during training. Under no circumstances are raw training rows transmitted to the federation coordinator.
2. **Dedicated Federated Pollution-Risk Model**:
   TimesFM remains the managed univariate time-series forecast engine and is not federated. Instead, a lightweight, transparent risk model trained on multidimensional features (`pm25`, `pm10`, `no2`, `temperature`, `humidity`, `wind_speed`, `wind_direction`, `hour`, `day_of_week`) predicts next-hour pollution risk elevation.
3. **Sample-Weighted FedAvg Aggregation**:
   The central coordinator aggregates participating node parameter updates using transparent sample-count weighting:
   $$W_{global} = \sum_{k} \frac{n_k}{N} W_k, \quad b_{global} = \sum_{k} \frac{n_k}{N} b_k$$
   where $n_k$ is the local sample count of node $k$ and $N = \sum_k n_k$.
4. **Prototype Transparency Boundary**:
   The prototype is explicitly characterized as data-local training with federated model-update aggregation. It does NOT claim formal differential privacy, cryptographic secure multiparty aggregation, or production government federation.

---

## D-019 — Canonical City Node Contract & Interoperability

### Decision

City nodes participate in the federated network through a canonical interoperability contract:

```json
{
  "node_id": "delhi",
  "schema_version": "1.0",
  "supported_signals": ["pm25", "pm10", "no2", "weather"],
  "model_version": "v1"
}
```

### Reason

The platform core and event engine must remain city-agnostic and free from hardcoded municipal business logic. New urban centers, industrial clusters, and state pollution control boards can be added via declarative node registration and standard data contracts without altering engine code.

---

## D-020 — Real Historical Replay & Production Provenance Taxonomies

### Decision

All observations, events, incidents, and command center layers must explicitly carry a standardized provenance tag:
- `LIVE`: Authenticated real-time stream from production government or satellite feeds.
- `RECENT`: Recently cached authentic stream within standard sensor polling frequency.
- `HISTORICAL`: Calibrated public historical records from official archives (e.g. CPCB CAAQMS, NASA FIRMS, Copernicus Sentinel-5P, IMD).
- `REPLAY`: Deterministic playback of historical public or incident scenarios.
- `SIMULATION`: Synthetic or stress-test fixture data used for edge testing.

Replay or historical data must NEVER be represented as live data to users, operators, or evaluators.

### Reason

Maintaining credible provenance boundaries prevents misleading operators or evaluators into mistaking historical calibration episodes for live monitoring.

---

## D-021 — BigQuery TimesFM Integration & Provider Health Observability

### Decision

1. **Clean Forecast Provider Selection**:
   The system supports declarative provider selection: `DEVELOPMENT` (local diurnal autoregressive baseline) or `BIGQUERY_TIMESFM` (Google Cloud BigQuery ML / TimesFM). Every forecast and event response must record `provider_name` and measured evaluation metrics (MAE, RMSE, MAPE) on validation benchmarks. Forecast accuracy numbers must never be invented.
2. **Genuine Provider Health**:
   The `/health` and `/api/v1/health` endpoints and UI indicators must report the real connectivity and operating mode (`available`, `unavailable`, `degraded`, `replay`) for CPCB, IMD, FIRMS, Sentinel-5P, Gemini, Forecast, and Federation. Availability must never be fabricated.


