import os
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, Depends, APIRouter, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers import claims, provenance, duel
from backend.app.config import settings
from backend.app.dependencies import get_current_user

logger = logging.getLogger("finshield.main")

_CACHED_HEALTH: Dict[str, Any] = {}
_LAST_PROBE_TIME: Optional[datetime] = None


def probe_cloud_dependencies() -> Dict[str, Dict[str, Any]]:
    """
    Probes all 6 core Google Cloud dependencies:
      - firestore: native mode ping / collection list
      - gcs: bucket accessibility check
      - bigquery: lightweight SELECT 1 query
      - documentai: processor lookup
      - gemini: generate_content ping with gemini-3.5-flash
      - provenance_key: presence in env or Secret Manager
    Never exposes API keys, credentials, or secret contents.
    """
    results: Dict[str, Dict[str, Any]] = {}

    # 1. Cloud Firestore
    try:
        from backend.app.services.db import db_service
        fs = db_service.client
        if hasattr(fs, "collections"):
            cols = fs.collections()
            next(iter(cols), None)
        results["firestore"] = {"ok": True, "status": "connected", "database": settings.FIRESTORE_DATABASE}
    except Exception as e:
        results["firestore"] = {"ok": False, "status": "unavailable", "detail": str(e)[:120]}

    # 2. Google Cloud Storage
    try:
        from backend.app.services.storage import storage_service
        gcs = storage_service.client
        bucket = gcs.bucket(settings.GCS_BUCKET_NAME)
        exists = bucket.exists() if hasattr(bucket, "exists") else True
        if exists:
            results["gcs"] = {"ok": True, "status": "connected", "bucket": settings.GCS_BUCKET_NAME}
        else:
            results["gcs"] = {"ok": False, "status": "bucket_not_found", "bucket": settings.GCS_BUCKET_NAME}
    except Exception as e:
        results["gcs"] = {"ok": False, "status": "unavailable", "detail": str(e)[:120]}

    # 3. BigQuery
    try:
        from backend.tools.bq import bq_warehouse
        bq = bq_warehouse.client
        query_job = bq.query("SELECT 1 AS ping")
        rows = list(query_job.result())
        results["bigquery"] = {"ok": True, "status": "connected", "dataset": settings.BIGQUERY_DATASET}
    except Exception as e:
        results["bigquery"] = {"ok": False, "status": "unavailable", "detail": str(e)[:120]}

    # 4. Document AI Processor
    if settings.docai_processor_name:
        try:
            from google.cloud import documentai
            from google.api_core.client_options import ClientOptions
            client = documentai.DocumentProcessorServiceClient(
                client_options=ClientOptions(api_endpoint=settings.docai_endpoint)
            )
            proc_name = settings.docai_processor_name
            proc = client.get_processor(name=proc_name)
            results["documentai"] = {"ok": True, "status": "connected", "type": getattr(proc, "type_", "invoice_processor"), "location": settings.docai_location}
        except Exception as e:
            results["documentai"] = {"ok": False, "status": "unavailable", "detail": str(e)[:120]}
    else:
        results["documentai"] = {"ok": False, "status": "not_configured", "detail": "DOCUMENTAI_PROCESSOR_ID not set"}

    # 5. Gemini API (Live Multimodal / Reasoning via unified service)
    from backend.app.services.gemini_client import probe_gemini_service
    results["gemini"] = probe_gemini_service()

    # 6. Provenance Signing Key
    if settings.FINSHIELD_PROVENANCE_KEY:
        results["provenance_key"] = {"ok": True, "status": "configured", "source": "environment"}
    elif settings.GCP_PROJECT:
        try:
            from google.cloud import secretmanager
            sm = secretmanager.SecretManagerServiceClient()
            sec_name = f"projects/{settings.GCP_PROJECT}/secrets/finshield-provenance-signing-key/versions/latest"
            sm.access_secret_version(request={"name": sec_name})
            results["provenance_key"] = {"ok": True, "status": "configured", "source": "secret_manager"}
        except Exception as e:
            results["provenance_key"] = {"ok": False, "status": "unavailable", "detail": f"Secret Manager error: {str(e)[:80]}"}
    else:
        results["provenance_key"] = {"ok": False, "status": "not_configured", "detail": "Neither FINSHIELD_PROVENANCE_KEY nor GCP_PROJECT set"}

    return results


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager that runs startup probes.
    If REQUIRE_CLOUD_ON_STARTUP is True and any required dependency fails,
    raises RuntimeError with a clear message citing docs/CLOUD_SETUP.md.
    """
    global _CACHED_HEALTH, _LAST_PROBE_TIME
    logger.info("FinShield starting up. Probing Google Cloud dependencies...")
    probe_results = probe_cloud_dependencies()
    _CACHED_HEALTH = probe_results
    _LAST_PROBE_TIME = datetime.utcnow()

    failed = [dep for dep, res in probe_results.items() if not res["ok"]]
    if failed:
        err_msg = (
            f"FinShield Cloud Startup Check FAILED. The following dependencies are unreachable or unconfigured: "
            f"{', '.join(failed)}. Refer to docs/CLOUD_SETUP.md for provisioning instructions."
        )
        if settings.REQUIRE_CLOUD_ON_STARTUP:
            logger.error(err_msg)
            raise RuntimeError(err_msg)
        else:
            logger.warning("%s (Continuing startup because REQUIRE_CLOUD_ON_STARTUP=False)", err_msg)
    else:
        logger.info("FinShield Startup Check: All Google Cloud dependencies connected successfully.")

    yield
    logger.info("FinShield shutting down.")


app = FastAPI(
    title="FinShield API (Drishti.ai)",
    description="Multi-agent claims-fraud copilot backend",
    version=settings.VERSION,
    lifespan=lifespan
)

# CORS configuration: explicit origins instead of wildcard with credentials
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]
frontend_origin = os.getenv("FRONTEND_ORIGIN", os.getenv("FIREBASE_ORIGIN"))
if frontend_origin and frontend_origin not in ALLOWED_ORIGINS:
    ALLOWED_ORIGINS.append(frontend_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

from fastapi import Request
from fastapi.responses import JSONResponse
from backend.app.exceptions import CloudServiceError


@app.exception_handler(CloudServiceError)
async def cloud_service_error_handler(request: Request, exc: CloudServiceError):
    logger.error("Cloud service error on %s: %s (%s)", request.url.path, exc.message, exc.service)
    return JSONResponse(
        status_code=503,
        content=exc.to_dict()
    )


# API Router with /api prefix (matches Firebase Hosting rewrites to Cloud Run)
api_router = APIRouter(prefix="/api")
api_router.include_router(claims.router, dependencies=[Depends(get_current_user)])
api_router.include_router(provenance.router, dependencies=[Depends(get_current_user)])
api_router.include_router(duel.router, dependencies=[Depends(get_current_user)])

# Mount both /api and root prefixed routers for seamless local dev & Cloud Run production
app.include_router(api_router)
app.include_router(claims.router, dependencies=[Depends(get_current_user)])
app.include_router(provenance.router, dependencies=[Depends(get_current_user)])
app.include_router(duel.router, dependencies=[Depends(get_current_user)])


@api_router.get("/health")
@app.get("/health")
def health_check(live: bool = Query(default=False, description="Force real-time probe refresh")):
    """
    Reports the health status of FinShield and its real Google Cloud dependencies.
    Returns HTTP 503 if any required dependency is unreachable or unconfigured.
    Never exposes credentials, API keys, or secret names/values.
    """
    global _CACHED_HEALTH, _LAST_PROBE_TIME
    if live or not _CACHED_HEALTH:
        _CACHED_HEALTH = probe_cloud_dependencies()
        _LAST_PROBE_TIME = datetime.utcnow()

    deps = _CACHED_HEALTH
    all_ok = all(d.get("ok", False) for d in deps.values())
    status_str = "healthy" if all_ok else "unhealthy"

    content = {
        "status": status_str,
        "service": "FinShield API",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "cloud_mode": "google_cloud",
        "all_healthy": all_ok,
        "dependencies": deps,
        "models": {
            "pro": settings.GEMINI_PRO_MODEL,
            "flash": settings.GEMINI_FLASH_MODEL
        },
        "last_probe": _LAST_PROBE_TIME.isoformat() if _LAST_PROBE_TIME else None
    }

    if not all_ok:
        return JSONResponse(status_code=503, content=content)

    return content


@app.get("/")
def root():
    return {
        "message": "Welcome to FinShield (Drishti.ai) API",
        "docs_url": "/docs",
        "health_url": "/health",
        "version": settings.VERSION
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
