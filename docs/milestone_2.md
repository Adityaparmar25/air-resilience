# Clean Air & Climate Resilience — Milestone 2 (Phase 3B)

## Milestone Objective

Phase 3B expands the Air Resilience Network to ingest multimodal citizen observations and correlate them with operational ground monitoring stations into corroborated **Pollution Events**:

```text
Citizen Photo
  ↓
Gemini Multimodal Analysis (google-genai SDK, Structured Output)
  ↓
Validated Structured Evidence (Visual cues only, strict guardrails)
  ↓
Spatial & Temporal Correlation (Ground sensor anomaly lookup)
  ↓
Evidence Fusion Engine (D-006 weights, D-007 missing data policy)
  ↓
Pollution Event Creation & State Machine
  ↓
Event APIs (FastAPI)
  ↓
Frontend Event Explanation (Next.js Dashboard)
```

---

## Architecture & Governance Adherence

1. **Official Google GenAI SDK**: Uses `google-genai` with `gemini-2.5-flash` and structured JSON response schemas (`CitizenImageAnalysis`). A deterministic `FixtureGeminiAnalyzer` provides local/offline resilience without API key failures.
2. **Strict Guardrails on AI Vision**:
   - Classifies only visual evidence (`visible_smoke`, `visible_flames`, `event_type`, `smoke_intensity`).
   - Strictly forbidden from hallucinating PM2.5 numerical values.
   - Strictly forbidden from naming specific companies or individuals as responsible.
   - Strictly forbidden from declaring legal violations or making unsupported causal accusations.
   - Explicit uncertainty declaration (`uncertain_fields`, `needs_human_verification`).
3. **Evidence Fusion Engine (Decision D-006 & D-007)**:
   - Starting weights: Ground Anomaly (30%), Satellite (20%), Citizen (15%), Weather (15%), Fire (20%).
   - Missing data policy: Signals without data remain `available: false` and are excluded from the normalization denominator. They are **never** treated as 0.0.
4. **Event State Machine**:
   - `FALSE_POSITIVE` (< 0.35)
   - `POSSIBLE` (0.35 - 0.55)
   - `CORROBORATED` (0.55 - 0.75)
   - `HIGH_CONFIDENCE` (>= 0.75)
5. **Separation of Concerns**:
   - Frontend **never** computes fusion scores or makes event classification judgments; all scores and structured explanations originate from backend APIs.

---

## Implemented API Surface

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/reports` | Submit citizen report (supports multipart file upload & test scenarios) |
| `POST` | `/api/v1/reports/{id}/analyze` | Trigger Gemini multimodal analysis with structured output |
| `POST` | `/api/v1/events/detect` | Run spatial correlation & evidence fusion engine |
| `GET` | `/api/v1/events` | List detected pollution events (supports status & active filters) |
| `GET` | `/api/v1/events/{id}` | Retrieve comprehensive event detail, evidence breakdown, and explanation |

---

## Frontend Application (`apps/web`)

A modern Next.js dashboard built with React 19 and Tailwind CSS:
- **Citizen Vision Studio**:
  - Pre-calibrated Delhi-NCR scenarios (Anand Vihar, Sector 62 Noida, Punjabi Bagh, Manesar) and custom photo upload.
  - Gemini multimodal inspection view showing visual evidence flags, flame/smoke detection, intensity, uncertainty warnings, and guardrail attestation.
  - One-click event corroboration trigger.
- **Pollution Events & Fusion Explorer**:
  - Real-time feed of active events with severity badges and status filters.
  - Radial SVG fusion score gauge.
  - Complete 5-signal evidence breakdown matrix with availability indicators and Decision D-007 missing-data transparency.
  - "Why was this event created?" primary explanation narrative.
