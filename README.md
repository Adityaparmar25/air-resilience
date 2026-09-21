# Air Resilience Network — Clean Air & Climate Resilience

An AI-powered early-warning and response network that combines ground, citizen, satellite, fire, and weather signals to detect emerging local pollution events, forecast short-term risk, and route evidence-backed alerts to environmental authorities.

---

## Milestone 1 (Phase 3A) — Status: Completed

Milestone 1 implements the first complete vertical engineering slice:
```text
CPCB data / fixture
  ↓
Canonical normalization (MonitoringObservation)
  ↓
Data-quality pipeline (deduplication, range checks, spike flagging)
  ↓
PM2.5 time-series service (filtering, chronological sorting, gap detection, baseline)
  ↓
Explainable anomaly detector (statistical baseline deviation & documented thresholds)
  ↓
Forecast provider abstraction (24h horizon with empirical confidence intervals)
  ↓
FastAPI endpoints (/health, /api/v1/stations/{id}/series, /api/v1/anomaly, /api/v1/forecast)
```

---

## Repository Structure

```text
air-resilience/
├── apps/
│   ├── api/
│   │   ├── config.py            # Typed Pydantic Settings and environment validation
│   │   ├── demo.py              # CLI Milestone 1 verification demo
│   │   ├── main.py              # FastAPI application factory and lifespan
│   │   └── routes.py            # Endpoints: /health, /api/v1/stations/{id}/series, /api/v1/anomaly, /api/v1/forecast
│   └── web/                     # Frontend Next.js app (scheduled for Milestone 3)
├── services/
│   ├── ingestion/
│   │   ├── cpcb_adapter.py      # CPCB adapter (schema translation, metadata preservation, registry fallback)
│   │   └── quality_pipeline.py  # DataQualityPipeline (deduplication, range checks, spike tagging)
│   ├── anomaly/
│   │   └── detector.py          # ExplainableAnomalyDetector (z-scores, explicit thresholds, status classification)
│   ├── forecasting/
│   │   ├── base.py              # ForecastProvider ABC, ForecastRequest, ForecastResponse, PredictionPoint
│   │   ├── baseline.py          # BaselineTimeSeriesForecastProvider (autoregressive diurnal model)
│   │   ├── bigquery_timesfm.py  # BigQueryTimesFMForecastProvider (GCP TimesFM interface)
│   │   └── time_series_service.py # TimeSeriesService & LocalHistoricalBaselineComputer
│   ├── fusion/                  # Evidence fusion service (scheduled for Milestone 2)
│   └── federation/              # Multi-node federated coordination (scheduled for Milestone 4)
├── schemas/
│   ├── canonical.py             # Canonical MonitoringObservation schema (architecture.md Section 10)
│   ├── quality.py               # QualityFlag and ObservationQualityRecord
│   └── api.py                   # FastAPI request/response models
├── data/
│   └── fixtures/
│       ├── normal_series.json
│       ├── elevated_series.json
│       ├── missing_observations.json
│       ├── duplicate_rows.json
│       ├── suspicious_spike.json
│       ├── forecast_input.json
│       └── anomaly_request_example.json
├── docs/
│   └── milestone_1.md           # Milestone 1 architecture alignment and contracts
└── tests/
    ├── test_schema.py           # Canonical schema validation and coordinate tests
    ├── test_cpcb_adapter.py     # CPCB adapter field translation tests
    ├── test_quality_pipeline.py # Data quality pipeline tests (deduplication, spikes)
    ├── test_time_series_service.py # Time series service and baseline tests
    ├── test_anomaly_detector.py # Explainable anomaly detector tests
    ├── test_forecast_provider.py# Forecast provider abstraction tests
    ├── test_api.py              # FastAPI HTTP endpoints tests
    └── test_m1_acceptance.py    # End-to-end Milestone 1 acceptance test
```

---

## Local Setup & Installation

### 1. Prerequisites
- Python 3.11+ (or Python 3.13)
- pip

### 2. Environment Configuration
Copy the template configuration file:
```bash
cp .env.example .env
```

Review `.env.example` settings:
```env
# Google Cloud Platform (Optional for local development baseline)
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account-key.json

# Google AI / Gemini API (Used in Milestone 2)
GEMINI_API_KEY=your-gemini-api-key

# Operational & Analytical Database Settings
FIRESTORE_DATABASE=(default)
BIGQUERY_DATASET=air_resilience

# Application Environment & Server Settings
ENVIRONMENT=development
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## Running the Verification Demo

Run the end-to-end Milestone 1 demonstration script:
```bash
py apps/api/demo.py
```
*(On Linux/macOS, replace `py` with `python` or `python3`)*

This script executes the entire data and ML pipeline:
1. Ingests CPCB data from fixture
2. Normalizes into canonical schema
3. Executes data-quality pipeline checks
4. Assembles station time series and detects gaps
5. Computes explainable anomaly scores
6. Produces 24-hour horizon PM2.5 forecast
7. Verifies FastAPI HTTP endpoints

---

## Running the Test Suite

Run the full pytest suite:
```bash
py -m pytest -v tests/
```

Run only the Milestone 1 acceptance test:
```bash
py -m pytest -v tests/test_m1_acceptance.py
```

---

## Starting the FastAPI Server

Launch the development server via Uvicorn:
```bash
py -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload
```

Interactive API documentation will be available at:
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## Example API Queries

### 1. Health Check
```bash
curl http://127.0.0.1:8000/health
```
Response:
```json
{
  "status": "ok",
  "service": "air-resilience-api",
  "version": "0.1.0",
  "environment": "development",
  "timestamp": "2026-09-21T13:20:00Z"
}
```

### 2. Station Time Series
```bash
curl "http://127.0.0.1:8000/api/v1/stations/DL001/series?limit=12"
```

### 3. Explainable Anomaly Detection
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/anomaly" \
  -H "Content-Type: application/json" \
  -d @data/fixtures/anomaly_request_example.json
```
Response:
```json
{
  "station_id": "DL001",
  "timestamp": "2026-01-20T12:00:00Z",
  "pm25": 195.0,
  "expected_pm25": 61.2,
  "anomaly_score": 5.35,
  "status": "STRONG_ANOMALY",
  "explanation": "Observed PM2.5 of 195.0 ug/m3 vs expected 61.2 ug/m3 (std: 25.0, historical window baseline, samples: 4). Classified as STRONG_ANOMALY: z-score (5.35) exceeds strong threshold (3.5).",
  "baseline_std": 25.0
}
```

### 4. PM2.5 Horizon Forecasting
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/forecast" \
  -H "Content-Type: application/json" \
  -d @data/fixtures/forecast_input.json
```
Response:
```json
{
  "station_id": "DL001",
  "horizon": 24,
  "predictions": [
    {
      "timestamp": "2026-01-20T12:00:00Z",
      "pm25_forecast": 82.54,
      "lower_bound": 52.88,
      "upper_bound": 112.2
    }
  ],
  "provider_type": "development_baseline"
}
```

---

## Known Limitations in Milestone 1

1. **Scope Freeze**: Per project contract ([decision.md](decision.md) D-013), Milestone 1 focuses solely on ground station telemetry, quality checks, local anomaly detection, forecast abstraction, and the core FastAPI interface. Multimodal Gemini Vision, satellite ingestion, NASA FIRMS, and authority consoles are deferred to Milestone 2+.
2. **Offline / Development Data**: External live CPCB servers are accessed through fixtures or local mocks in development to ensure deterministic testing without external service degradation during judging.
3. **Forecasting**: BigQuery ML / TimesFM is abstracted behind `ForecastProvider`. When running locally without active GCP credentials, the system automatically uses the baseline model and clearly labels responses as `development_baseline`.

---

## Next Milestone (Milestone 2)

**Checkpoint 2 / Milestone 2**:
```text
Gemini Vision
  ↓
Structured citizen evidence extraction
  ↓
Evidence fusion (ground anomaly + citizen observation + weather + satellite)
  ↓
Pollution event creation & lifecycle state machine
```
*Note: Do NOT start Milestone 2 automatically until team review of Milestone 1 is completed.*