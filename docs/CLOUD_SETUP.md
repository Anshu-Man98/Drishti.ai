# FinShield (Drishti.ai) — Google Cloud Platform Provisioning & Reproduction Guide

FinShield operates exclusively in **Pure Cloud Mode** on Google Cloud Platform. There is no local mode, sqlite fallback, or offline mock engine. This document provides step-by-step instructions, exact `gcloud` commands, and real project configuration values used in production.

---

## 1. Verified Production Cloud Resources

| Service | Real Resource Identifier / Name | Location / Region | Purpose |
| :--- | :--- | :--- | :--- |
| **GCP Project** | `drishti-demo` (`848168056257`) | Global | Host Google Cloud Project |
| **Cloud Firestore** | `(default)` (Native Mode) | `asia-south1` | Operational database for claims, dossiers, agent status, and chat history |
| **Cloud Storage** | `gs://finshield-claims-docs-drishti-demo` | `asia-south1` | Uploaded PDFs, 150 DPI page preview PNGs, signed sanction notes |
| **BigQuery Dataset** | `finshield` | `asia-south1` | Data warehouse tables (`claims`, `line_items`, `doctor_events`, `ext_provider_fraud`) |
| **BigQuery ML** | `finshield.fraud_model`, `finshield.provider_fraud_model` | `asia-south1` | Gradient-boosted tree classifier with `ML.EXPLAIN_PREDICT` feature attribution |
| **Document AI** | `projects/848168056257/locations/us/processors/8cb7d125a43425e4` | `us` (multi-region) | Specialized `INVOICE_PROCESSOR` extracting line items and bounding boxes |
| **Secret Manager** | `finshield-provenance-signing-key` | Automatic | Hardware-backed Ed25519 digital signature signing key for Feature A2 |
| **Gemini AI** | `gemini-3.5-flash` | Vertex AI / AI Studio | Multimodal reasoning, prompt injection detection, visual forensics, dossier synthesis |

---

## 2. Prerequisites & Identity Authentication

1. **Google Cloud SDK (`gcloud`)**:
   ```bash
   which gcloud && gcloud --version
   ```

2. **User ADC Login & Quota Project**:
   ```bash
   gcloud auth login
   gcloud auth application-default login
   gcloud config set project drishti-demo
   gcloud auth application-default set-quota-project drishti-demo
   ```

3. **Verify Billing**:
   ```bash
   gcloud billing projects describe drishti-demo --format="value(billingEnabled)"
   # Output: true (Billing Account: 01FE9B-05711A-E28CAD)
   ```

---

## 3. Enable Required Google Cloud APIs

```bash
gcloud services enable \
  aiplatform.googleapis.com \
  documentai.googleapis.com \
  firestore.googleapis.com \
  bigquery.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com
```

---

## 4. Provision Cloud Infrastructure

### 4.1. Cloud Firestore (Native Mode)
```bash
gcloud firestore databases create \
  --location=asia-south1 \
  --type=firestore-native
```

### 4.2. Cloud Storage Bucket & CORS Policy
```bash
# Create bucket with uniform access
gcloud storage buckets create "gs://finshield-claims-docs-drishti-demo" \
  --location=asia-south1 \
  --uniform-bucket-level-access

# Configure CORS for local frontend preview (ports 3000, 5173)
cat <<'EOF' > /tmp/gcs-cors.json
[
  {
    "origin": ["http://localhost:5173", "http://localhost:3000"],
    "method": ["GET", "HEAD", "PUT", "POST", "OPTIONS"],
    "responseHeader": ["Content-Type", "Authorization", "x-goog-resumable"],
    "maxAgeSeconds": 3600
  }
]
EOF
gcloud storage buckets update "gs://finshield-claims-docs-drishti-demo" --cors-file=/tmp/gcs-cors.json
rm -f /tmp/gcs-cors.json
```

### 4.3. BigQuery Dataset, Tables & ML Models
```bash
# 1. Create dataset
bq mk --location=asia-south1 --dataset drishti-demo:finshield

# 2. Provision warehouse tables
bq query --use_legacy_sql=false < infra/bigquery.sql

# 3. Train BigQuery ML boosted-tree classifier and provider clustering models
bq query --use_legacy_sql=false < infra/bqml.sql
```

### 4.4. Document AI Invoice Processor
*Note: Specialized processors reside in `us` or `eu` multi-region endpoints.*
```bash
gcloud documentai processors create \
  --location=us \
  --type=INVOICE_PROCESSOR \
  --display-name="finshield-invoice-parser"

# Output Processor ID: projects/848168056257/locations/us/processors/8cb7d125a43425e4
```

### 4.5. Secret Manager (Ed25519 Provenance Signing Key)
```bash
# Generate 32-byte Ed25519 signing seed (never print or commit)
openssl rand -hex 32 | tr -d '\n' | gcloud secrets create finshield-provenance-signing-key \
  --data-file=- \
  --replication-policy="automatic"
```

---

## 5. IAM Permissions (Least Privilege)

Grant the identity running the application (e.g. user ADC or Cloud Run Service Account) the following roles:

```bash
USER_IDENTITY=$(gcloud auth list --filter=status:ACTIVE --format="value(account)")

for ROLE in \
  roles/datastore.user \
  roles/storage.objectAdmin \
  roles/bigquery.user \
  roles/bigquery.dataEditor \
  roles/documentai.viewer \
  roles/aiplatform.user \
  roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding drishti-demo \
    --member="user:${USER_IDENTITY}" \
    --role="$ROLE"
done
```

---

## 6. Local Configuration (`.env`)

Create your local `.env` (gitignored):

```env
# Google Cloud Platform Identifiers
GOOGLE_CLOUD_PROJECT=drishti-demo
GCP_PROJECT=drishti-demo
GCP_REGION=asia-south1

# Cloud Storage & Database
GCS_BUCKET_NAME=finshield-claims-docs-drishti-demo
FIRESTORE_DATABASE=(default)
BIGQUERY_DATASET=finshield

# Document AI (Processor in US location)
DOCUMENTAI_PROCESSOR_ID=projects/848168056257/locations/us/processors/8cb7d125a43425e4
DOCUMENTAI_LOCATION=us

# Provenance Cryptographic Secret (Loaded from Secret Manager)
# FINSHIELD_PROVENANCE_KEY=

# Gemini Models & API Keys
GOOGLE_API_KEY=YOUR_GEMINI_API_KEY
GEMINI_PRO_MODEL=gemini-3.5-flash
GEMINI_FLASH_MODEL=gemini-3.5-flash

# Operational Enforcement
REQUIRE_CLOUD_ON_STARTUP=true
ALLOW_DEV_TOKENS=true
INJECTION_CHECK_ENABLED=true
WATERMARK_ENABLED=true
RAG_PATTERNS_ENABLED=true
SYNTHID_ENABLED=false
```

---

## 7. Cloud Seeding & Data Population

Run the idempotent cloud seeding script to upload golden PDFs, pre-render page previews, seed Firestore documents, and verify BigQuery tables:

```bash
# 1. Dry run verification:
.venv/bin/python scripts/seed_cloud.py --dry-run

# 2. Live cloud application:
.venv/bin/python scripts/seed_cloud.py --apply
```

---

## 8. GCP Cost Analysis & Budget Alerts

### 8.1. Billable Services & Estimated Cost per Claim Analysis

| Cloud Service | Billable Metric | Rate | Cost per Claim Analysis |
| :--- | :--- | :--- | :--- |
| **Document AI** | Invoice Parser page processing | ~$10.00 / 1,000 pages (~$0.01/page) | **~$0.01 – $0.05** (only when uploading raw PDFs) |
| **Gemini AI** | Vertex AI tokens (Gemini 2.5 Flash) | $0.075 / 1M input, $0.30 / 1M output | **~$0.0005** (fraction of a cent) |
| **BigQuery ML** | `ML.EXPLAIN_PREDICT` computation | $6.25 / TB on-demand (1 TB/mo free) | **$0.00** (queries scan < 2 MB, within free tier) |
| **Cloud Firestore** | Document reads & writes | $0.06 / 100K reads, $0.18 / 100K writes | **$0.00** (~20 ops per claim, within 50K/day free tier) |
| **Cloud Storage** | Standard storage & network ops | $0.020 / GB-month | **$0.00** (< 10 MB total demo storage) |
| **Secret Manager** | Secret version access operations | $0.03 / 10,000 operations | **$0.00** (cached at backend startup) |

**Estimated Total Cost per Claim Scrutiny:**
- **Pre-seeded Golden Claim (G1–G9):** **< $0.001** (~₹0.08).
- **New PDF Upload (Document AI OCR + Table Parsing):** **~$0.02 to $0.05** (~₹1.70 – ₹4.20).

### 8.2. Setting a Budget Alert in Google Cloud

To prevent unexpected billing overruns, you can create a monthly budget alert (e.g. ₹500 or $10.00) with email thresholds at 50%, 80%, and 100%:

#### Option A: Via Google Cloud Console (Recommended)
1. Navigate to: [Google Cloud Console Billing Budgets & Alerts](https://console.cloud.google.com/billing/01FE9B-05711A-E28CAD/budgets?project=drishti-demo)
2. Click **Create Budget**.
3. Set **Scope** to Project `drishti-demo`.
4. Set **Amount** to Target Monthly Budget (e.g. ₹500 or $10.00).
5. Set **Threshold Rules** to trigger alert emails at 50%, 80%, and 100% of budget.

#### Option B: Via `gcloud` CLI
```bash
# Enable billing budgets API on project:
gcloud services enable billingbudgets.googleapis.com --project=drishti-demo

# Create monthly budget alert:
gcloud billing budgets create \
  --billing-account="01FE9B-05711A-E28CAD" \
  --display-name="FinShield-Monthly-Safety-Cap" \
  --budget-amount="10.00USD" \
  --threshold-rule="percent=0.5" \
  --threshold-rule="percent=0.8" \
  --threshold-rule="percent=1.0" \
  --filter-projects="projects/drishti-demo"
```
