# Clean Air & Climate Resilience — Problem Definition

## Status

Phase: Problem definition  
Scope: Hackathon prototype  
Primary geography: NCR / Northern DMIC cluster  
Primary event: Emerging local combustion/industrial pollution event  
Secondary event: Regional agricultural-burning-driven pollution

---

## 1. Problem Statement

Indian cities already collect air-quality observations, but the challenge is not simply the absence of measurements.

The problem we are targeting is:

> Emerging local pollution events can be difficult to detect and act on quickly when ground measurements, citizen observations, satellite signals, fire detections, and meteorological context are fragmented.

The result is a gap between:

```text
A signal exists
    ↓
Someone notices it
    ↓
Evidence is verified
    ↓
Short-term risk is understood
    ↓
The right authority acts
```

Our product is designed to reduce that gap.

---

## 2. What We Are NOT Solving

The prototype will not attempt to:

- replace CPCB, SPCBs, CAQM, or existing government monitoring systems
- build India's complete air-quality infrastructure
- prove the exact legal source of an emission
- make automatic enforcement decisions
- predict pollution everywhere in India
- build or manufacture physical sensors
- provide a generic climate chatbot

These are outside the hackathon MVP.

---

## 3. Core Problem Tree

```text
                    LOCAL POLLUTION EVENT
                              |
          +-------------------+-------------------+
          |                   |                   |
     Detection gap       Prediction gap      Response gap
          |                   |                   |
   fragmented signals   difficult to know     evidence may not
   / limited context    what happens next     reach the right
                                              operational user
          |                   |                   |
          +-------------------+-------------------+
                              |
                    WEAK EVENT COORDINATION
                              |
                       HIGHER EXPOSURE RISK
```

---

## 4. Users

### Primary operational user

Environmental authority / pollution-control response team.

Needs:

- emerging-event detection
- evidence
- forecast
- location
- priority
- incident workflow

### Secondary operational user

Field verification team.

Needs:

- exact incident location
- evidence summary
- likely source category
- investigation status
- response instructions

### Data contributor

Citizen.

Needs:

- simple pollution reporting
- photo upload
- location
- clear submission status

### Network participant

City/state node.

Needs:

- local analytics
- interoperable event format
- local model training
- shared model updates

---

## 5. Core Jobs

The system must perform five jobs:

1. Detect an unusual local pollution signal.
2. Corroborate that signal using independent evidence.
3. Forecast short-term pollution risk.
4. Explain the evidence in human-readable form.
5. Route an alert into an operational response workflow.

---

## 6. Operational Definition

### Hyperlocal pollution event

A geographically concentrated and temporally unusual pollution signal supported by one or more independent observations.

### Hidden hotspot

A location where available heterogeneous signals suggest an emerging or under-recognized local pollution event.

### Source assessment

A probabilistic category such as:

- industrial/combustion
- biomass burning
- open-waste burning
- dust
- unknown

The system must never present a probable source as a legally or scientifically proven source without supporting evidence.

---

## 7. Required Inputs

The challenge requires the system to combine:

```text
Citizen observations
        +
Local air-quality observations
        +
Satellite observations
        +
Meteorological data
```

Additional fire/thermal-anomaly data can support the agricultural-burning scenario.

---

## 8. Success Condition

The prototype succeeds when a reviewer can follow one event from:

```text
Signal
  ↓
Detection
  ↓
Evidence fusion
  ↓
Forecast
  ↓
Alert
  ↓
Investigation
  ↓
Resolution
```

and when another city/state node can participate through the same architecture.

---

## 9. Non-Negotiable Constraints

- Google AI must perform a meaningful task.
- Numerical forecasts must come from a predictive model, not generated prose.
- AI-generated claims must be traceable to supplied evidence.
- Missing data must remain distinguishable from negative evidence.
- Replay/demo data must be labeled as replay.
- Source attribution must remain probabilistic unless independently verified.
