# Clean Air & Climate Resilience — Milestone 1 (Phase 3A)

## Milestone Objective

Milestone 1 implements the first complete engineering vertical slice of the **Air Resilience Network**:

```text
CPCB data / fixture
  ↓
Canonical normalization
  ↓
Data quality pipeline
  ↓
PM2.5 time series
  ↓
Explainable anomaly detection
  ↓
Forecast abstraction
  ↓
FastAPI result
```

This establishes the data, ML, and API foundation for all subsequent milestones.

---

## Architecture Alignment

In accordance with [architecture.md](file:///c:/Users/Aditya%20Singh/Desktop/air-resilience/architecture.md) and [decision.md](file:///c:/Users/Aditya%20Singh/Desktop/air-resilience/decision.md):

1. **Single Canonical Schema**: All ground sensor telemetry is normalized into `MonitoringObservation` ([schemas/canonical.py](file:///c:/Users/Aditya%20Singh/Desktop/air-resilience/schemas/canonical.py)).
2. **Missing Data Policy (Decision D-007)**: Missing pollutant observations are strictly preserved as `None` / `null` and never converted into zero.
3. **Transparent Quality Checks**: Suspicious spikes and duplicates are flagged (`SUSPICIOUS_SPIKE`, `DUPLICATE_TIMESTAMP`) rather than silently dropped or fabricated.
4. **Isolated Historical Baseline**: The baseline statistical engine is isolated in [services/forecasting/time_series_service.py](file:///c:/Users/Aditya%20Singh/Desktop/air-resilience/services/forecasting/time_series_service.py) for easy extension/replacement by BigQuery ML.
5. **Explainable Anomaly Detection**: Uses statistical deviations (z-scores) and documented physical ceilings. Output is never labeled as an "AI confidence score", and thresholds are explicitly configured.
6. **Forecast Abstraction**: Defined via `ForecastProvider` abstract base class. Production target points to BigQuery ML `AI.FORECAST` / TimesFM; local development uses `BaselineTimeSeriesForecastProvider`. Accuracy numbers are never invented (Decision D-008).
7. **Explicit Provenance (Decision D-009)**: All fixtures are explicitly labeled with `data_source: "fixture"` and `is_synthetic: true`.

---

## Implemented API Surface

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | System health check, service name, and version |
| `GET` | `/api/v1/stations/{station_id}/series` | Station time series with quality flags, baseline stats, and missing gaps |
| `POST` | `/api/v1/anomaly` | Statistical anomaly detection comparing observation to baseline |
| `POST` | `/api/v1/forecast` | Horizon PM2.5 forecasting with 95% confidence intervals |

---

## Known Limitations in Milestone 1

1. **Scope Boundaries**: In accordance with the project plan, Milestone 1 excludes Gemini Vision, Earth Engine / Sentinel-5P, NASA FIRMS, Next.js frontend, authority alerting workflows, and federated node aggregation.
2. **External Data Access**: In development and offline environments, the CPCB adapter utilizes labeled development fixtures (`data/fixtures/`) rather than an active CPCB CAAQMS scraper.
3. **Forecast Model**: In local environments without GCP credentials, the forecast provider uses the autoregressive diurnal baseline model. The BigQuery ML TimesFM provider is abstracted and ready for cloud configuration.
