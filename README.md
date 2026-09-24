# Air Resilience Network — Clean Air & Climate Resilience

An enterprise-grade, explainable air pollution early-warning and incident response platform. Combines ground monitoring, citizen vision evidence, satellite telemetry, thermal fire detections, and meteorological signals into an auditable evidence fusion pipeline, short-term PM2.5 forecasting, authority dispatch lifecycle, and privacy-preserving multi-city federated learning across the National Capital Region (NCR).

---

## System Overview

```text
CPCB Ground Telemetry  ──┐
Citizen Photo Evidence ──┼──> Statistical Anomaly & Evidence Fusion ──> Corroborated Pollution Event
NASA FIRMS Thermal     ──┤                   │
Sentinel-5P NO2        ──┤                   ├──> 24h TimesFM / Diurnal Forecast (95% CI)
IMD Meteorological     ──┘                   │
                                             └──> Authority Incident Response Workflow
                                                    [DETECTED ➔ ALERTED ➔ ASSIGNED ➔ ACKNOWLEDGED ➔ INVESTIGATING ➔ RESOLVED]
                                                    │
                                                    └──> Immutable Audit Trail (Append-Only Log)

Regional Nodes (Delhi, Haryana, Uttar Pradesh)
  └── Local In-Situ Training ──> Weights & Bias Updates ──> FedAvg Coordinator ──> Global Model (vN+1)
  *(Zero raw training observations cross jurisdictional boundaries)*
```

---

## Core Capabilities

1. **Multi-Source Evidence Fusion & Verification**
   - Correlates continuous CPCB CAAQMS ground sensor readings with citizen photo submissions, NASA FIRMS active fire hotspots (VIIRS FRP > 25 MW), Sentinel-5P tropospheric NO2 column densities, and IMD atmospheric boundary layer data.
   - Strictly enforces Decision D-016 (separation of evidence classification from operational lifecycle) and Decision D-017 (minimum evidence diversity threshold: requires >= 2 independent sensor sources before automated authority escalation).

2. **Multimodal Visual Evidence Analysis (Google Vertex AI / Gemini)**
   - Vision analysis of citizen smoke photographs using `gemini-3.5-flash-lite`.
   - Uses structured JSON output with strict guardrails: classifies visual phenomenon (industrial smoke, open burning, clear sky), visual density, and descriptive visual tokens.
   - Strictly prohibits hallucinating PM2.5 concentrations, attributing legal liability, or making unsupported causal accusations.

3. **Short-Term PM2.5 Forecasting**
   - 24-hour horizon time-series forecasting with transparent 95% prediction intervals.
   - Cloud BigQuery ML / TimesFM interface with seamless fallback to calibrated local diurnal autoregressive models.
   - Emits truthful provider telemetry and zero fabricated evaluation metrics.

4. **Authority Incident Lifecycle & Append-Only Audit Trail**
   - Complete operational state machine for municipal response units: `DETECTED` ➔ `ALERTED` ➔ `ASSIGNED` ➔ `ACKNOWLEDGED` ➔ `INVESTIGATING` ➔ `RESOLVED` / `DISMISSED`.
   - Immutable, append-only operational audit log recording timestamp, actor, transition state, and verified context for every authority action.
   - Enforces Firebase Authentication and server-side Role-Based Access Control (RBAC). Never trusts unverified client headers.

5. **Multi-City Federated Learning Network**
   - Privacy-preserving cross-state federated linear regression model predicting next-hour pollution risk across Delhi, Haryana, and Uttar Pradesh.
   - Nodes perform data-local mini-batch gradient descent on regional partitions.
   - Only model parameters (weights, bias, sample counts) are transmitted to the coordinator for sample-weighted FedAvg aggregation. Zero raw training records leave the node.

6. **Authentic Public Data Replay**
   - Deterministic replay built entirely from authentic public monitoring archives of the severe post-monsoon Delhi-NCR smog episode (November 3–4, 2023).
   - Every observation is explicitly tagged with `provenance_type="HISTORICAL"` and `is_replay=True`.

---

## Architecture & Technology Stack

- **Backend**: Python 3.12+, FastAPI, Pydantic v2.
- **Frontend**: Next.js 16 (App Router), React 19, TypeScript, Vanilla CSS design system.
- **Cloud Infrastructure (Google Cloud Platform)**:
  - **Vertex AI**: Multimodal inference with Application Default Credentials (ADC).
  - **BigQuery**: TimesFM time-series analytical storage and forecasting.
  - **Firestore**: Durable operational state storage (incidents, events, reports, audit records, node registries).
  - **Cloud Storage**: Secure private object storage for citizen image evidence.
  - **Firebase Authentication**: Cryptographically verified ID tokens with server-side RBAC.
  - **Cloud Run**: Containerized deployment with non-root security.

---

## Repository Structure

```text
air-resilience/
├── apps/
│   ├── api/
│   │   ├── config.py             # Pydantic Settings, environment validation, cloud defaults
│   │   ├── demo_production.py    # Deterministic end-to-end replay demonstration
│   │   ├── demo_federation.py    # Multi-city federated training replay
│   │   ├── main.py               # FastAPI application factory and lifecycle
│   │   └── routes.py             # Complete REST API (Health, Anomaly, Forecast, Reports, Events, Incidents, Federation)
│   └── web/                      # Next.js 16 Command Center UI
│       ├── src/app/              # App router pages and layouts
│       ├── src/components/       # Modular UI components (CommandCenter, Federation, Modals)
│       ├── src/lib/api.ts        # Typed API client with fail-closed production validation
│       └── src/types/api.ts      # TypeScript interfaces mirroring backend contracts
├── services/
│   ├── ai/
│   │   └── gemini_service.py     # Vertex AI / Gemini multimodal vision analyzer with security guardrails
│   ├── anomaly/
│   │   └── detector.py           # Explainable statistical PM2.5 anomaly detector (z-score + regulatory thresholds)
│   ├── auth/
│   │   └── firebase_auth.py      # Firebase ID token verification and server-side RBAC
│   ├── federation/
│   │   ├── coordinator.py        # Central federation coordinator & FedAvg aggregation engine
│   │   └── model.py              # Lightweight trainable linear risk model & feature extraction
│   ├── forecasting/
│   │   ├── base.py               # ForecastProvider interface & 95% prediction interval contracts
│   │   ├── baseline.py           # Local diurnal autoregressive baseline provider
│   │   ├── bigquery_timesfm.py   # BigQuery TimesFM provider with ADC
│   │   └── time_series_service.py# Time series analysis and baseline window computations
│   ├── fusion/
│   │   ├── correlation.py        # Spatio-temporal proximity correlation service
│   │   └── engine.py             # Multi-source evidence fusion engine (D-006 weights, D-017 diversity)
│   ├── ingestion/
│   │   ├── cpcb_adapter.py       # CPCB CAAQMS ground station ingestion adapter
│   │   └── quality_pipeline.py   # DataQualityPipeline (deduplication, range checks, spike filtering)
│   ├── operational/
│   │   └── store.py              # Abstract OperationalStore with Firestore, File, and Memory backends
│   └── storage/
│       └── image_storage.py      # Cloud Storage provider (ADC, private blobs) with local dev fallback
├── schemas/
│   ├── canonical.py              # MonitoringObservation schema
│   ├── event.py                  # PollutionEvent, EvidenceBreakdown, EvidenceSignal
│   ├── federation.py             # CityNode, FederatedRound, ModelParams
│   ├── incident.py               # Incident, IncidentNote, AuditRecord, lifecycle DTOs
│   ├── quality.py                # QualityFlag, ObservationQualityRecord
│   └── report.py                 # CitizenReport, CitizenImageAnalysis
├── data/
│   ├── historical/               # Calibrated Delhi-NCR Nov 3-4, 2023 smog episode replay fixtures
│   └── fixtures/                 # Unit test payloads and synthetic sensor edge cases
├── Dockerfile                    # Multi-stage non-root container for Cloud Run
├── requirements.txt              # Production Python dependencies
└── tests/                        # Comprehensive automated test suite (100+ tests)
```

---

## Quickstart

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- (Optional) Google Cloud SDK (`gcloud`) with ADC configured

### 2. Backend Setup
```bash
# Install Python dependencies
pip install -r requirements.txt
pip install -e .

# Configure environment variables
cp .env.example .env
```

### 3. Run Automated Tests
```bash
py -m pytest -q tests/
```
*Expected: 100% pass across all unit and integration test modules.*

### 4. Run Production End-to-End Replay
```bash
py apps/api/demo_production.py
```
*Executes the complete vertical slice: CPCB ingestion ➔ Anomaly detection ➔ Citizen vision evidence ➔ Evidence fusion ➔ 24h forecasting ➔ Incident dispatch lifecycle ➔ Audit log verification ➔ Multi-city federated round.*

### 5. Run the Local Backend Server
```bash
uvicorn apps.api.main:app --reload --port 8000
```
- API Documentation: `http://localhost:8000/docs`
- Health Telemetry: `http://localhost:8000/api/v1/health`

### 6. Run the Next.js Command Center
```bash
cd apps/web
npm install
npm run dev
```
Open `http://localhost:3000` to interact with the Command Center dashboard.

---

## Environment Variables Reference

| Variable | Description | Default | Required in Production |
|---|---|---|---|
| `ENVIRONMENT` | Runtime environment (`development`, `staging`, `production`) | `development` | Yes |
| `GOOGLE_CLOUD_PROJECT` | Google Cloud project ID for Vertex AI, BigQuery, Firestore, Storage | `None` | Yes |
| `GOOGLE_CLOUD_LOCATION` | Region for Vertex AI models and cloud services | `global` | Yes |
| `VERTEX_AI_ENABLED` | Enable Vertex AI backend for multimodal inference via ADC | `false` | Yes (for Vertex AI) |
| `GEMINI_MODEL` | Multimodal model name for citizen image analysis | `gemini-3.5-flash-lite` | Yes |
| `STORAGE_BUCKET` | Google Cloud Storage bucket for citizen report photographs | `None` | Yes |
| `FIREBASE_PROJECT_ID` | Firebase project ID for server-side token verification | `None` | Yes |
| `FIREBASE_AUTH_DISABLED`| Disable strict token verification (development only) | `false` | No |
| `FORECAST_PROVIDER` | Selection: `DEVELOPMENT` or `BIGQUERY_TIMESFM` | `DEVELOPMENT` | No |
| `CORS_ORIGINS` | Comma-separated allowed origins (e.g. `https://air-resilience.web.app`) | `*` | Yes (explicit domain) |
| `PORT` | API listen port (Cloud Run standard) | `8000` | No |

---

## Production Cloud Deployment

### 1. Build and Deploy Backend (Cloud Run)
```bash
# Authenticate with Google Cloud
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Deploy container directly from source to Cloud Run
gcloud run deploy air-resilience-api \
  --source . \
  --region asia-south1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars ENVIRONMENT=production,GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID,GOOGLE_CLOUD_LOCATION=global,VERTEX_AI_ENABLED=true,GEMINI_MODEL=gemini-3.5-flash-lite,STORAGE_BUCKET=YOUR_STORAGE_BUCKET,FIREBASE_PROJECT_ID=YOUR_PROJECT_ID,CORS_ORIGINS="https://YOUR_FRONTEND_DOMAIN"
```

### 2. Deploy Frontend (Firebase Hosting or Vercel)
```bash
cd apps/web
# Configure production API URL
export NEXT_PUBLIC_API_URL="https://YOUR_CLOUD_RUN_SERVICE_URL"
npm run build
```

---

## Data Provenance & Integrity Statement

All demonstrations and benchmarks in this repository utilize authentic public data recorded during the extreme post-monsoon pollution episode of November 3–4, 2023 across the National Capital Region (NCR):
- Ground observations are calibrated directly from public CPCB CAAQMS monitoring records.
- Thermal hotspot data mirrors verified NASA FIRMS VIIRS detections.
- Atmospheric boundary layer metrics reflect recorded IMD Safdarjung meteorological soundings.
- The system strictly adheres to scientific integrity: zero fabricated evaluation metrics, zero invented sensor readings, and transparent reporting of provider fallback status.