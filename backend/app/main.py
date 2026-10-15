import os
from fastapi import FastAPI, Depends, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from backend.app.routers import claims, provenance
from backend.app.config import settings
from backend.app.dependencies import get_current_user

app = FastAPI(
    title="FinShield API (Drishti.ai)",
    description="Multi-agent claims-fraud copilot backend",
    version="1.0.0"
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

# API Router with /api prefix (matches Firebase Hosting rewrites to Cloud Run)
api_router = APIRouter(prefix="/api")
api_router.include_router(claims.router, dependencies=[Depends(get_current_user)])
api_router.include_router(provenance.router, dependencies=[Depends(get_current_user)])

# Mount both /api and root prefixed routers for seamless local dev & Cloud Run production
app.include_router(api_router)
app.include_router(claims.router, dependencies=[Depends(get_current_user)])
app.include_router(provenance.router, dependencies=[Depends(get_current_user)])


@api_router.get("/health")
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "FinShield API",
        "environment": settings.ENVIRONMENT,
        "models": {
            "pro": settings.GEMINI_PRO_MODEL,
            "flash": settings.GEMINI_FLASH_MODEL
        }
    }


@app.get("/")
def root():
    return {
        "message": "Welcome to FinShield (Drishti.ai) API",
        "docs_url": "/docs",
        "health_url": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
