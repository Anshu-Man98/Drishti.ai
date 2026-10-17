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
# 3. Cloud Build executes Build -> Push -> Cloud Run Deploy atomically
# ------------------------------------------------------------------------------
echo "Cloud Build pipeline completed successfully."

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
