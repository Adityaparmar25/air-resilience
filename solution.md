# Clean Air & Climate Resilience — Solution Definition

## 1. Product

Working name: **Air Resilience Network**

One-line definition:

> An AI-powered early-warning and response network that combines ground, citizen, satellite, fire, and weather signals to detect emerging local pollution events, forecast short-term risk, and route evidence-backed alerts to the appropriate response team.

---

## 2. Core Product Loop

```text
OBSERVE
  ↓
DETECT
  ↓
CORROBORATE
  ↓
FORECAST
  ↓
EXPLAIN
  ↓
RESPOND
  ↓
COORDINATE
```

---

## 3. End-to-End Flow

```text
CPCB / local sensors
IMD / weather
Sentinel-5P / Earth Engine
NASA FIRMS
Citizen reports
        ↓
Data normalization + quality checks
        ↓
Anomaly detection
        ↓
Spatial + temporal grouping
        ↓
Evidence fusion
        ↓
Pollution event
        ↓
Short-term PM2.5 forecast
        ↓
Gemini explanation / structured incident summary
        ↓
Authority alert
        ↓
Investigation / resolution
        ↓
Cross-city model coordination
```

---

## 4. AI Responsibilities

### Gemini Vision

Purpose: analyze citizen-submitted images.

It may identify:

- visible smoke
- visible flames
- broad event category
- visual evidence
- uncertainty

It must not invent:

- PM2.5 concentration
- exact emission source
- legal violation
- causal attribution

### Predictive model

Purpose: numerical short-term PM2.5 forecasting.

Initial target:

- hourly PM2.5
- selected monitoring stations
- 6h / 12h / 24h views

The team will evaluate TimesFM against a baseline before making performance claims.

### Gemini reasoning layer

Purpose:

- summarize evidence
- explain why an event was created
- generate an operator-readable incident summary

The backend remains responsible for executing database/state changes.

---

## 5. Event Engine

### Stage 1 — Anomaly

Compare current measurements with a local historical baseline.

### Stage 2 — Spatial/temporal grouping

Group nearby signals within a controlled time window.

### Stage 3 — Evidence fusion

Combine available signals:

- ground pollution anomaly
- satellite atmospheric signal
- citizen evidence
- weather alignment
- nearby fire/thermal anomaly

Missing evidence is `null`/unavailable, not zero.

### Stage 4 — Event state

```text
POSSIBLE
  ↓
CORROBORATED
  ↓
HIGH_CONFIDENCE
  ↓
ALERTED
  ↓
INVESTIGATING
  ↓
RESOLVED
```

Additional states:

```text
FALSE_POSITIVE
EXPIRED
```

---

## 6. Evidence Model

The prototype will use an interpretable weighted score as a starting point.

Conceptually:

```text
event_score =
sum(weight_i × evidence_i)
/
sum(available weights)
```

Starting weights are implementation parameters, not scientific constants.

Initial configuration:

- Ground anomaly: 30%
- Satellite signal: 20%
- Citizen evidence: 15%
- Weather alignment: 15%
- Fire/thermal evidence: 20%

These weights must be validated and tuned against replay/historical cases.

---

## 7. Forecasting

Primary prediction target:

> Hourly PM2.5 at selected monitoring stations.

Initial model path:

```text
CPCB history
    ↓
BigQuery
    ↓
TimesFM / AI.FORECAST
    ↓
future PM2.5
```

Model comparison:

```text
Baseline
vs
ARIMA-based model
vs
TimesFM
```

The team will report measured error, not assumed accuracy.

---

## 8. Geospatial Layer

Google Maps will display:

- monitoring stations
- active pollution events
- citizen reports
- nearby fire detections
- relevant satellite evidence
- downwind risk direction

The downwind layer is an operational directional estimate, not a full atmospheric-dispersion simulation.

---

## 9. Citizen Workflow

```text
Citizen
  ↓
Photo + location + optional description
  ↓
Gemini Vision
  ↓
Structured observation
  ↓
Evidence fusion
  ↓
Possible event
```

A citizen report alone cannot automatically create a high-priority enforcement event.

---

## 10. Authority Workflow

```text
Event detected
  ↓
Evidence reviewed
  ↓
Alert created
  ↓
Responsible team assigned
  ↓
Investigation
  ↓
Status update
  ↓
Resolved / false positive
```

Every status change is logged.

---

## 11. Federated Network

Prototype nodes:

```text
Delhi
Haryana
Uttar Pradesh
```

Each logical node has:

- local data
- local training
- local inference

The coordinator receives model updates, aggregates them, and distributes the shared model.

Prototype flow:

```text
Node A ─┐
Node B ─┼→ local training → aggregation → shared model
Node C ─┘
```

Raw local training data does not need to be uploaded to the coordinator.

---

## 12. MVP Screens

1. Command Center
2. Event Detail
3. Citizen Report
4. Authority Incident
5. Network/Federation
6. Data & Model Health

---

## 13. Demo Modes

### Live

Uses available current/recent sources.

### Replay

Replays recorded real observations for a deterministic demo.

### Simulation

Used only for testing edge cases and clearly labeled.

---

## 14. Final Demo Flow

```text
Citizen smoke report
        ↓
Gemini image analysis
        ↓
Ground anomaly
        ↓
Satellite / fire / weather corroboration
        ↓
Pollution event
        ↓
Forecast
        ↓
Evidence explanation
        ↓
Authority alert
        ↓
Investigation
        ↓
Cross-city coordination
```
