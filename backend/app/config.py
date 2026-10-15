import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_DATA_DIR = str(Path(__file__).resolve().parent.parent.parent / "data")


class Settings(BaseSettings):
    PROJECT_NAME: str = "FinShield API"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # GCP Configuration
    GCP_PROJECT: Optional[str] = os.getenv("GOOGLE_CLOUD_PROJECT", os.getenv("GCP_PROJECT", "finshield-dev"))
    GCP_REGION: str = os.getenv("GCP_REGION", "asia-south1")
    GCS_BUCKET_NAME: str = os.getenv("GCS_BUCKET_NAME", "finshield-claims-docs")
    FIRESTORE_DATABASE: str = os.getenv("FIRESTORE_DATABASE", "(default)")
    BIGQUERY_DATASET: str = os.getenv("BIGQUERY_DATASET", "finshield")
    
    # Model IDs from environment variables (NEVER hardcoded)
    GEMINI_PRO_MODEL: str = os.getenv("GEMINI_PRO_MODEL", "gemini-2.5-pro")
    GEMINI_FLASH_MODEL: str = os.getenv("GEMINI_FLASH_MODEL", "gemini-2.5-flash")
    
    # API Keys & Credentials
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY", os.getenv("GEMINI_API_KEY"))
    DOCUMENTAI_PROCESSOR_ID: Optional[str] = os.getenv("DOCUMENTAI_PROCESSOR_ID")
    
    # Feature Flags
    SYNTHID_ENABLED: bool = os.getenv("SYNTHID_ENABLED", "false").lower() == "true"
    LOCAL_FALLBACK: bool = os.getenv("LOCAL_FALLBACK", "true").lower() == "true"
    LOCAL_DATA_DIR: str = os.getenv("LOCAL_DATA_DIR", _DEFAULT_DATA_DIR)
    INJECTION_CHECK_ENABLED: bool = os.getenv("INJECTION_CHECK_ENABLED", "true").lower() == "true"
    WATERMARK_ENABLED: bool = os.getenv("WATERMARK_ENABLED", "true").lower() == "true"
    RAG_PATTERNS_ENABLED: bool = os.getenv("RAG_PATTERNS_ENABLED", "true").lower() == "true"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
