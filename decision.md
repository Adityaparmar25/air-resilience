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
