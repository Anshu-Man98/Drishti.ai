# ==============================================================================
# Multi-Stage Build: Drishti AI / FinShield Unified Service
# Stage 1: Build React 19 + Vite Frontend SPA
# Stage 2: Minimal Python 3.11 Runtime serving FastAPI backend & SPA
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Frontend Build
# ------------------------------------------------------------------------------
FROM node:22-slim AS frontend-builder

WORKDIR /app/frontend

# Build arguments for Google Maps (passed by Cloud Build from Secret Manager)
# If omitted, build succeeds with graceful "Map unavailable" fallback
ARG VITE_GOOGLE_MAPS_API_KEY=""
ARG VITE_GOOGLE_MAPS_MAP_ID=""

ENV VITE_GOOGLE_MAPS_API_KEY=$VITE_GOOGLE_MAPS_API_KEY \
    VITE_GOOGLE_MAPS_MAP_ID=$VITE_GOOGLE_MAPS_MAP_ID \
    NODE_ENV=production

# Install dependencies using clean install
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy frontend source and compile bundle
COPY frontend/ ./
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Python 3.11 Runtime
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# System environment configuration
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    WEB_CONCURRENCY=2 \
    FRONTEND_DIST_DIR=/app/frontend/dist

WORKDIR /app

# Install minimal OS runtime libraries:
# libgomp1: required for scikit-learn OpenMP execution
# No build-essential needed (all Python dependencies provide pre-compiled wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install pinned Python dependencies from lockfile
COPY backend/requirements.lock /app/backend/requirements.lock
RUN pip install --no-cache-dir -r /app/backend/requirements.lock

# Create dedicated non-privileged service user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Copy backend application source
COPY backend /app/backend

# Copy ONLY data files required at runtime:
# - data/demo/*.pdf and ground_truth.json (forensic demo document viewing)
# - data/patterns/fraud_patterns.json (base fraud pattern catalog)
# - data/policies/rules.json and clauses_index.json (IRDAI Arogya Sanjeevani & synthetic rules)
COPY data/demo/*.pdf /app/data/demo/
COPY data/demo/ground_truth.json /app/data/demo/ground_truth.json
COPY data/patterns/fraud_patterns.json /app/data/patterns/fraud_patterns.json
COPY data/policies/rules.json /app/data/policies/rules.json
COPY data/policies/clauses_index.json /app/data/policies/clauses_index.json

# Copy compiled frontend SPA bundle from Stage 1
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Secure file ownership to non-root user
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers ${WEB_CONCURRENCY:-2}"]
