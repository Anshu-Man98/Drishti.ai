#!/usr/bin/env bash
# ==============================================================================
# Drishti AI / FinShield - Cloud Run Deployment Script
# Idempotent, production-grade deployment script for Cloud Run hackathon demo.
# ==============================================================================
set -euo pipefail

# ------------------------------------------------------------------------------
# Configuration with sane defaults
# ------------------------------------------------------------------------------
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || echo "drishti-demo")}"
REGION="${REGION:-asia-south1}"
SERVICE_NAME="${SERVICE_NAME:-drishti-app}"
REPO_NAME="${REPO_NAME:-drishti}"
SA_NAME="drishti-run"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
COMMIT_SHA="${COMMIT_SHA:-$(git rev-parse --short HEAD 2>/dev/null || echo "latest")}"
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:${COMMIT_SHA}"
IMAGE_LATEST="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:latest"

echo "================================================================================"
echo "Drishti AI - Deploying to Cloud Run"
echo "Project:      ${PROJECT_ID}"
echo "Region:       ${REGION}"
echo "Service:      ${SERVICE_NAME}"
echo "Identity:     ${SA_EMAIL}"
echo "Image:        ${IMAGE_URI}"
echo "Commit SHA:   ${COMMIT_SHA}"
echo "================================================================================"

# ------------------------------------------------------------------------------
# 1. Ensure Artifact Registry repository exists in target region
# ------------------------------------------------------------------------------
echo "Checking Artifact Registry repository '${REPO_NAME}' in ${REGION}..."
if ! gcloud artifacts repositories describe "${REPO_NAME}" --location="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    echo "Creating Artifact Registry repository '${REPO_NAME}' in ${REGION}..."
    gcloud artifacts repositories create "${REPO_NAME}" \
        --repository-format=docker \
        --location="${REGION}" \
        --project="${PROJECT_ID}" \
        --description="Drishti AI container repository"
else
    echo "Artifact Registry repository '${REPO_NAME}' exists."
fi

# ------------------------------------------------------------------------------
# 2. Build and submit container image via Cloud Build
# Passing Google Maps build arguments securely from Secret Manager
# ------------------------------------------------------------------------------
echo "Submitting multi-stage build to Cloud Build..."
gcloud builds submit \
    --project="${PROJECT_ID}" \
    --config=infra/cloudbuild.yaml \
    --substitutions=COMMIT_SHA="${COMMIT_SHA}" \
    .

# ------------------------------------------------------------------------------
# 3. Deploy to Cloud Run
# Flags explained:
#   --region: Deploys close to Indian health-data users and Vertex AI endpoints (asia-south1)
#   --service-account: Dedicated runtime service account with least-privilege IAM
#   --memory 2Gi: Accommodates PDF parsing, image decompression, and BQML feature vectors
#   --cpu 2: Provides 2 vCPUs for responsive concurrent API and agent task handling
#   --concurrency 20: Caps concurrent requests per container to avoid memory thrashing
#   --timeout 300: 5-minute timeout for multi-agent adversarial duels and heavy OCR pipeline
#   --min-instances 1: Keeps 1 instance warm to avoid cold starts for hackathon judges
#   --max-instances 2: Keeps claim-lock/rate-limit state coherent and caps maximum cloud cost
#   --cpu-boost: Allocates extra CPU during container startup
#   --no-cpu-throttling: Essential: allows background tasks (duels, async analysis) to run after HTTP 200
#   --allow-unauthenticated: Exposes public HTTPS URL for hackathon evaluation
#   --port 8080: Standard container listening port
#   --startup-probe: Verifies live GCP connectivity (/api/health) with generous timeout
#   --liveness-probe: Fast health check on SPA root (/)
# ------------------------------------------------------------------------------
echo "Deploying Cloud Run service '${SERVICE_NAME}'..."
gcloud run deploy "${SERVICE_NAME}" \
    --project="${PROJECT_ID}" \
    --image="${IMAGE_URI}" \
    --region="${REGION}" \
    --platform="managed" \
    --allow-unauthenticated \
    --service-account="${SA_EMAIL}" \
    --memory="2Gi" \
    --cpu="2" \
    --concurrency="20" \
    --timeout="300" \
    --min-instances="1" \
    --max-instances="2" \
    --cpu-boost \
    --no-cpu-throttling \
    --port="8080" \
    --set-env-vars="ENVIRONMENT=production,GCP_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GCP_REGION=${REGION},GCS_BUCKET_NAME=finshield-claims-docs-${PROJECT_ID},BIGQUERY_DATASET=finshield,FIRESTORE_DATABASE=(default),DOCUMENTAI_PROCESSOR_ID=projects/848168056257/locations/us/processors/8cb7d125a43425e4,DOCUMENTAI_LOCATION=us,GEMINI_PRO_MODEL=gemini-3.5-flash,GEMINI_FLASH_MODEL=gemini-3.5-flash,REQUIRE_CLOUD_ON_STARTUP=true,RATE_LIMIT_ENABLED=true,ALLOW_DEV_TOKENS=true" \
    --set-secrets="FINSHIELD_PROVENANCE_KEY=finshield-provenance-signing-key:latest" \
    --startup-probe="timeoutSeconds=20,periodSeconds=20,failureThreshold=6,httpGet.path=/api/health,httpGet.port=8080" \
    --liveness-probe="timeoutSeconds=5,periodSeconds=15,failureThreshold=3,httpGet.path=/,httpGet.port=8080"

# ------------------------------------------------------------------------------
# 4. Output service URL and deployment metadata
# ------------------------------------------------------------------------------
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --platform="managed" --region="${REGION}" --project="${PROJECT_ID}" --format="value(status.url)")
REVISION_NAME=$(gcloud run services describe "${SERVICE_NAME}" --platform="managed" --region="${REGION}" --project="${PROJECT_ID}" --format="value(status.latestReadyRevisionName)")

echo "================================================================================"
echo "Deployment Complete!"
echo "Service URL:    ${SERVICE_URL}"
echo "Revision Name:  ${REVISION_NAME}"
echo "================================================================================"
