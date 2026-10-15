from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.routers import claims, provenance
from backend.app.config import settings

app = FastAPI(
    title="FinShield API (Drishti.ai)",
    description="Multi-agent claims-fraud copilot backend",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(claims.router)
app.include_router(provenance.router)


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
