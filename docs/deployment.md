# Google Cloud Run Deployment Guide

This document describes the production deployment procedure for the **Air Resilience Network** FastAPI backend to Google Cloud Run and the Next.js frontend to Vercel or Cloud Run.

---

## 1. Prerequisites

- Google Cloud Project with Billing Enabled
- Google Cloud SDK (`gcloud` CLI) installed and authenticated:
  ```bash
  gcloud auth login
  gcloud config set project YOUR_PROJECT_ID
  ```
- Required Google Cloud APIs enabled:
  ```bash
  gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com \
    bigquery.googleapis.com
  ```

---

## 2. Secrets Management (Google Secret Manager)

Store sensitive API keys in Google Secret Manager rather than baking them into images:

```bash
# 1. Gemini API Key
echo -n "YOUR_GEMINI_API_KEY" | gcloud secrets create gemini-api-key \
    --data-file=- \
    --replication-policy="automatic"

# 2. Grant Cloud Run Service Account access
PROJECT_NUMBER=$(gcloud projects describe YOUR_PROJECT_ID --format="value(projectNumber)")
gcloud secrets add-iam-policy-binding gemini-api-key \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

---

## 3. Build & Containerize (Google Artifact Registry)

Create an Artifact Registry repository and build the container:

```bash
# 1. Create Docker repository in region (e.g. asia-south1 Mumbai)
gcloud artifacts repositories create air-resilience-repo \
    --repository-format=docker \
    --location=asia-south1 \
    --description="Air Resilience Network Docker Repository"

# 2. Build and submit container image via Cloud Build
gcloud builds submit --tag asia-south1-docker.pkg.dev/YOUR_PROJECT_ID/air-resilience-repo/api:latest .
```

---

## 4. Deploy to Google Cloud Run

Deploy the containerized FastAPI service with appropriate resources, environment variables, and secret references:

```bash
gcloud run deploy air-resilience-api \
    --image=asia-south1-docker.pkg.dev/YOUR_PROJECT_ID/air-resilience-repo/api:latest \
    --region=asia-south1 \
    --platform=managed \
    --allow-unauthenticated \
    --port=8000 \
    --memory=1Gi \
    --cpu=1 \
    --min-instances=1 \
    --max-instances=10 \
    --set-env-vars="ENVIRONMENT=production,GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID,BIGQUERY_DATASET=air_resilience,FORECAST_PROVIDER=BIGQUERY_TIMESFM,DATA_MODE=HISTORICAL_REPLAY,CORS_ORIGINS=*" \
    --set-secrets="GEMINI_API_KEY=gemini-api-key:latest"
```

---

## 5. Verify Deployment & Health Checks

Once deployment completes, retrieve the public service URL:

```bash
SERVICE_URL=$(gcloud run services describe air-resilience-api --region=asia-south1 --format="value(status.url)")
echo "Service URL: ${SERVICE_URL}"

# 1. Probe readiness endpoint
curl -s "${SERVICE_URL}/healthz"

# 2. Check full system health and provider indicators
curl -s "${SERVICE_URL}/api/v1/health" | jq .

# 3. Retrieve historical severe episode
curl -s "${SERVICE_URL}/api/v1/historical/delhi-smog-2023" | jq .metadata
```

---

## 6. Frontend Configuration

When deploying the Next.js frontend (`apps/web`) to Vercel or Cloud Run:

Set the environment variable pointing to the Cloud Run backend:
```env
NEXT_PUBLIC_API_URL=https://air-resilience-api-xyz-as.a.run.app
NEXT_PUBLIC_GOOGLE_MAPS_API_KEY=YOUR_GOOGLE_MAPS_API_KEY
```

Build command:
```bash
cd apps/web
npm run build
npm run start
```
