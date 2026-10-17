import os
import threading
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

PDFIUM_LOCK = threading.Lock()


class Settings(BaseSettings):
    PROJECT_NAME: str = "FinShield API"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # GCP Configuration
    GCP_PROJECT: Optional[str] = os.getenv("GOOGLE_CLOUD_PROJECT", os.getenv("GCP_PROJECT"))
    GCP_REGION: str = os.getenv("GCP_REGION", "asia-south1")
    GCS_BUCKET_NAME: str = os.getenv("GCS_BUCKET_NAME", "finshield-claims-docs-drishti-demo")
    FIRESTORE_DATABASE: str = os.getenv("FIRESTORE_DATABASE", "(default)")
    BIGQUERY_DATASET: str = os.getenv("BIGQUERY_DATASET", "finshield")
    
    # Model IDs from environment variables (NEVER hardcoded)
    GEMINI_PRO_MODEL: str = os.getenv("GEMINI_PRO_MODEL", "gemini-3.5-flash")
    GEMINI_FLASH_MODEL: str = os.getenv("GEMINI_FLASH_MODEL", "gemini-3.5-flash")
    
    VERSION: str = "1.0.0"

    # Upload & Payload Limits
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "15"))
    MAX_TOTAL_UPLOAD_MB: int = int(os.getenv("MAX_TOTAL_UPLOAD_MB", "50"))
    MAX_UPLOAD_FILES: int = int(os.getenv("MAX_UPLOAD_FILES", "10"))

    # API Keys & Credentials
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY", os.getenv("GEMINI_API_KEY"))
    DOCUMENTAI_PROCESSOR_ID: Optional[str] = os.getenv("DOCUMENTAI_PROCESSOR_ID")
    DOCUMENTAI_LOCATION: Optional[str] = os.getenv("DOCUMENTAI_LOCATION", "us")
    FINSHIELD_PROVENANCE_KEY: Optional[str] = os.getenv("FINSHIELD_PROVENANCE_KEY")

    @property
    def docai_processor_name(self) -> Optional[str]:
        if not self.DOCUMENTAI_PROCESSOR_ID:
            return None
        if self.DOCUMENTAI_PROCESSOR_ID.startswith("projects/"):
            return self.DOCUMENTAI_PROCESSOR_ID
        loc = self.docai_location
        proj = self.GCP_PROJECT
        if not proj:
            return None
        return f"projects/{proj}/locations/{loc}/processors/{self.DOCUMENTAI_PROCESSOR_ID}"

    @property
    def docai_location(self) -> str:
        if self.DOCUMENTAI_PROCESSOR_ID and "locations/" in self.DOCUMENTAI_PROCESSOR_ID:
            import re
            m = re.search(r"locations/([^/]+)", self.DOCUMENTAI_PROCESSOR_ID)
            if m:
                return m.group(1)
        return self.DOCUMENTAI_LOCATION or "us"

    @property
    def docai_endpoint(self) -> str:
        loc = self.docai_location
        return f"{loc}-documentai.googleapis.com"

    # Cloud Startup & Security Enforcement
    REQUIRE_CLOUD_ON_STARTUP: bool = os.getenv("REQUIRE_CLOUD_ON_STARTUP", "true").lower() == "true"
    ALLOW_DEV_TOKENS: bool = os.getenv("ALLOW_DEV_TOKENS", "true" if os.getenv("ENVIRONMENT", "development") != "production" else "false").lower() == "true"

    # Feature Flags
    SYNTHID_ENABLED: bool = os.getenv("SYNTHID_ENABLED", "false").lower() == "true"
    INJECTION_CHECK_ENABLED: bool = os.getenv("INJECTION_CHECK_ENABLED", "true").lower() == "true"
    WATERMARK_ENABLED: bool = os.getenv("WATERMARK_ENABLED", "true").lower() == "true"
    RAG_PATTERNS_ENABLED: bool = os.getenv("RAG_PATTERNS_ENABLED", "true").lower() == "true"
    
    # Latency & Resilience Budgets
    ANALYSIS_BUDGET_SECONDS: float = float(os.getenv("ANALYSIS_BUDGET_SECONDS", "90.0"))
    CLOUD_CALL_TIMEOUT_SEC: float = float(os.getenv("CLOUD_CALL_TIMEOUT_SEC", "30.0"))
    CLOUD_CALL_MAX_RETRIES: int = int(os.getenv("CLOUD_CALL_MAX_RETRIES", "2"))

    # Cost Protection & Quota Guards (Fix 7)
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("true", "1", "yes")
    MAX_CLAIM_LLM_TOKENS: int = int(os.getenv("MAX_CLAIM_LLM_TOKENS", "30000"))
    BQ_MAX_BYTES_BILLED: int = int(os.getenv("BQ_MAX_BYTES_BILLED", str(50 * 1024 * 1024)))  # 50 MB
    RATE_LIMIT_CLAIMS_PER_MIN: int = int(os.getenv("RATE_LIMIT_CLAIMS_PER_MIN", "10"))
    RATE_LIMIT_ANALYSES_PER_MIN: int = int(os.getenv("RATE_LIMIT_ANALYSES_PER_MIN", "20"))
    RATE_LIMIT_CHATS_PER_MIN: int = int(os.getenv("RATE_LIMIT_CHATS_PER_MIN", "60"))
    RATE_LIMIT_DUEL_PER_MIN: int = int(os.getenv("RATE_LIMIT_DUEL_PER_MIN", "30"))
    CACHE_MAX_AGE_DOSSIER: int = int(os.getenv("CACHE_MAX_AGE_DOSSIER", "60"))
    CACHE_MAX_AGE_STATIC: int = int(os.getenv("CACHE_MAX_AGE_STATIC", "300"))
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
