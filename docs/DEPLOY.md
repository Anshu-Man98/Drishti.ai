# Drishti AI - Google Cloud Run Deployment Guide

## 1. Architecture Overview

Drishti AI is deployed as a single unified service on **Google Cloud Run** (`drishti-app`) in region `asia-south1` (Mumbai), colocated with Vertex AI Gemini and Indian healthcare jurisdiction data.

```
+-------------------------------------------------------------------------+
|                       Google Cloud Run (drishti-app)                    |
|                                                                         |
|  [Browser Request]                                                      |
|         │                                                               |
|         ▼                                                               |
|  [FastAPI Reverse Proxy & Server] ─── (Non-root user: appuser, :8080)   |
|         │                                                               |
|         ├─── GET /assets/* ──────────► CachedStaticFiles (1 yr cache)   |
|         ├─── GET /api/* ─────────────► FastAPI Routers (Strict 404 JSON)|
|         └─── GET /* (Deep Links) ────► index.html (SPA Fallback, no-cache)|
|                                                                         |
|  Connected Cloud Services (via Dedicated Service Account drishti-run):   |
|  ├── Cloud Firestore (Claims, patterns, audit log, duels)               |
|  ├── Cloud Storage gs://finshield-claims-docs-drishti-demo              |
|  ├── BigQuery & BQML finshield dataset (Outliers, audit features)       |
|  ├── Document AI (US-hosted specialized Invoice Parser)                 |
|  ├── Vertex AI Gemini 2.5 / 3.5 Flash (asia-south1)                     |
|  └── Secret Manager (finshield-provenance-signing-key)                  |
+-------------------------------------------------------------------------+
```

- **Same-Origin Deployment**: The React 19 frontend bundle (`frontend/dist`) is baked directly into the multi-stage container and served by FastAPI. Browsers make same-origin requests to `/api/...`, eliminating CORS complexity.
- **Firebase Hosting**: Obsolete and removed. There is no secondary hosting provider or routing proxy.

---

## 2. One-Command Deployment

Run the automated deployment script from the repository root:

```bash
./scripts/deploy_cloud_run.sh
```

### What the script executes:
1. Verifies/creates the Artifact Registry repository `drishti` in `asia-south1`.
2. Triggers Cloud Build with `infra/cloudbuild.yaml` passing Google Maps build arguments from Secret Manager (`drishti-maps-key`, `drishti-maps-map-id`).
3. Compiles the React 19 Vite bundle, packages Python 3.11 with `appuser` non-root security, pushes to Artifact Registry, and rolls out a new Cloud Run revision.
4. Outputs the live service URL and revision name.

---

## 3. Required Google Cloud APIs

Ensure the following APIs are enabled in project `drishti-demo`:

```bash
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    firestore.googleapis.com \
    storage.googleapis.com \
    bigquery.googleapis.com \
    documentai.googleapis.com \
    aiplatform.googleapis.com \
    secretmanager.googleapis.com
```

---

## 4. Identity & Least-Privilege IAM Roles

Cloud Run executes under dedicated runtime identity:
`drishti-run@drishti-demo.iam.gserviceaccount.com`

| Resource / Scope | Role | Purpose |
| :--- | :--- | :--- |
| Project `drishti-demo` | `roles/datastore.user` | Read/write Firestore claims, audit records, duels |
| Project `drishti-demo` | `roles/bigquery.jobUser` | Submit BigQuery SQL queries & BQML inferences |
| Dataset `drishti-demo:finshield` | `roles/bigquery.dataEditor` | Read benchmark tables, write detector features |
| Bucket `gs://finshield-claims-docs-...` | `roles/storage.objectAdmin` | Read/write claim PDFs and signed sanction letters |
| Bucket `gs://finshield-claims-docs-...` | `roles/storage.legacyBucketReader`| Verify bucket existence on startup probe |
| Project `drishti-demo` | `roles/documentai.viewer` | Read processor metadata (`get_processor`) |
| Project `drishti-demo` | `roles/documentai.apiUser` | Execute online document parsing (`processOnline`) |
| Project `drishti-demo` | `roles/aiplatform.user` | Vertex AI Gemini multimodal reasoning |
| Secret `finshield-provenance-signing-key`| `roles/secretmanager.secretAccessor` | Access Ed25519 signing key for digital watermarks |
| Project `drishti-demo` | `roles/logging.logWriter` | Write application logs to Cloud Logging |

Cloud Build build identity (`848168056257-compute@developer.gserviceaccount.com`) has:
- `roles/secretmanager.secretAccessor` on `drishti-maps-key` and `drishti-maps-map-id`
- `roles/run.admin` on project
- `roles/iam.serviceAccountUser` on `drishti-run@drishti-demo.iam.gserviceaccount.com`

---

## 5. Environment Variables & Secrets Reference

### Plain Environment Variables

| Variable Name | Production Value | Purpose |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `production` | Enforces production runtime guards |
| `GCP_PROJECT` | `drishti-demo` | Target GCP project identifier |
| `GOOGLE_CLOUD_PROJECT` | `drishti-demo` | Standard GCP SDK project variable |
| `GCP_REGION` | `asia-south1` | Colocated regional endpoint |
| `GCS_BUCKET_NAME` | `finshield-claims-docs-drishti-demo` | Claims document storage bucket |
| `BIGQUERY_DATASET` | `finshield` | Analytics and BQML model dataset |
| `FIRESTORE_DATABASE` | `(default)` | Default Firestore database instance |
| `DOCUMENTAI_PROCESSOR_ID`| Full resource path | Document AI Invoice Parser resource |
| `DOCUMENTAI_LOCATION` | `us` | Multi-region Document AI location |
| `GEMINI_PRO_MODEL` | `gemini-3.5-flash` | Advanced multi-agent reasoning model |
| `GEMINI_FLASH_MODEL` | `gemini-3.5-flash` | High-throughput extraction cross-check model |
| `REQUIRE_CLOUD_ON_STARTUP`| `true` | Fails loud if any dependency is unreachable |
| `RATE_LIMIT_ENABLED` | `true` | In-memory token bucket rate limiting |
| `ALLOW_DEV_TOKENS` | `true` | Hackathon evaluation auth bypass |

### Secret Manager Secrets

| Secret Name | Loaded By | Purpose |
| :--- | :--- | :--- |
| `finshield-provenance-signing-key` | Python Secret Manager SDK | Raw 32-byte Ed25519 private seed |
| `drishti-maps-key` | Cloud Build ARG | Google Maps JavaScript API browser key |
| `drishti-maps-map-id` | Cloud Build ARG | Vector map identifier for dark mode styling |

---

## 6. Operations & Maintenance

### Viewing Real-Time Logs

```bash
# View recent Cloud Run application logs
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="drishti-app"' \
    --limit=50 \
    --format="value(textPayload)"

# Stream live container logs
gcloud alpha run services logs tail drishti-app --region=asia-south1
```

### Rolling Back to a Previous Revision

```bash
# List revisions
gcloud run revisions list --service=drishti-app --region=asia-south1

# Roll back 100% traffic to specific revision
gcloud run services update-traffic drishti-app \
    --region=asia-south1 \
    --to-revisions=drishti-app-00004-7st=100
```

---

## 7. Cost Control & Teardown

### Current Resource Caps
- **Minimum instances**: `1` (ensures sub-second response times for hackathon judges).
- **Maximum instances**: `2` (hard cap prevents runaway scaling or cost overruns).
- **CPU allocation**: `--no-cpu-throttling` (ensures background tasks and duels complete after HTTP 200).
- **Estimated running cost**: ~₹105/day ($1.27/day) while active.

### How to Stop Spending After Hackathon

```bash
# Option A: Pause instances (drops active compute cost to ₹0, instant to resume)
gcloud run services update drishti-app \
    --region=asia-south1 \
    --min-instances=0

# Option B: Complete service deletion
gcloud run services delete drishti-app \
    --region=asia-south1 \
    --quiet
```

### Resources with Ongoing Storage Costs
- **Firestore**: Free tier covers 1 GB storage and 50k reads/day.
- **BigQuery**: Free tier covers 10 GB active storage and 1 TB query scans/month.
- **Cloud Storage (`finshield-claims-docs-drishti-demo`)**: Standard storage costs ~$0.02/GB/month.
- **Artifact Registry (`drishti`)**: Image storage costs ~$0.10/GB/month. Delete older tagged images to recover space:
  ```bash
  gcloud artifacts docker images list asia-south1-docker.pkg.dev/drishti-demo/drishti/drishti-app
  ```

### Cloud Billing Budget Alert
Create or verify your ₹1,000 threshold budget alert via Google Cloud Console:
1. Navigate to **Billing** > **Budgets & alerts**.
2. Click **Create budget**.
3. Target project: `drishti-demo`.
4. Set Target Amount to **₹1,000 INR**.
5. Set alert threshold rules: **50% (₹500)**, **90% (₹900)**, and **100% (₹1,000)**.
6. Check **Email alerts to billing account admins**.

---

## 8. Accepted Demo Risks

- **Authentication**: `ALLOW_DEV_TOKENS=true` is enabled for demo simplicity so judges can evaluate all features without requiring sign-up. Anyone with the URL can interact with the app.
- **In-Memory Rate Limiting**: Token-bucket limits and claim locks are held in-memory per container instance. At `--max-instances=2`, rate limits apply per container.
