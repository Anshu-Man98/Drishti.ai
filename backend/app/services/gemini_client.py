"""
Unified Gemini Client Service for FinShield / Drishti.ai.

Single canonical entrypoint for all Gemini LLM interactions across:
  - Chat Copilot (backend/agents/chat.py)
  - Dueling AI Adversary (backend/agents/duel.py)
  - Visual Forensics Review (backend/tools/forensics_tools.py)
  - Hidden Prompt Injection Classifier (backend/tools/injection_tools.py)
  - System Health Probes (backend/app/main.py)

Architecture & Client Path:
  Operates on Google Cloud Vertex AI using Application Default Credentials (ADC)
  under project settings.GCP_PROJECT and region settings.GCP_REGION (default: asia-south1).
  If Vertex AI is unavailable and an API key is provided, falls back explicitly to API Key.
  Enforces zero silent failures: raises CloudServiceError on failure.
"""

import logging
from typing import Any, Dict, Optional
from google import genai
from backend.app.config import settings
from backend.app.exceptions import CloudServiceError

logger = logging.getLogger("finshield.gemini")

_CLIENT: Optional[genai.Client] = None
_CLIENT_MODE: Optional[str] = None


def get_gemini_client() -> genai.Client:
    """
    Returns the unified, singleton Google GenAI client.
    Prefers Vertex AI with Application Default Credentials (ADC) on Google Cloud.
    """
    global _CLIENT, _CLIENT_MODE
    if _CLIENT is not None:
        return _CLIENT

    # 1. Primary Path: Vertex AI with ADC
    if settings.GCP_PROJECT:
        try:
            location = settings.GCP_REGION or "asia-south1"
            client = genai.Client(
                vertexai=True,
                project=settings.GCP_PROJECT,
                location=location
            )
            _CLIENT = client
            _CLIENT_MODE = f"vertexai:{location}"
            logger.info("Initialized unified Gemini client on Vertex AI (project=%s, location=%s)", settings.GCP_PROJECT, location)
            return _CLIENT
        except Exception as e:
            logger.warning("Failed to initialize Vertex AI client: %s", e)

    # 2. Secondary Path: Gemini API Key
    if settings.GOOGLE_API_KEY:
        try:
            client = genai.Client(api_key=settings.GOOGLE_API_KEY)
            _CLIENT = client
            _CLIENT_MODE = "api_key"
            logger.info("Initialized unified Gemini client with API Key")
            return _CLIENT
        except Exception as e:
            logger.warning("Failed to initialize Gemini API Key client: %s", e)

    raise CloudServiceError(
        service="gemini",
        message="Gemini client could not be initialized. Neither Vertex AI credentials nor GOOGLE_API_KEY available.",
        retryable=True
    )


def reset_gemini_client():
    """Resets the singleton client (used in testing or reconfiguration)."""
    global _CLIENT, _CLIENT_MODE
    _CLIENT = None
    _CLIENT_MODE = None


def get_model_name(role: str = "flash") -> str:
    """
    Resolves the canonical model name for a given role ('flash' or 'pro').
    Default for both is settings.GEMINI_FLASH_MODEL (gemini-3.5-flash).
    """
    if role == "pro":
        return settings.GEMINI_PRO_MODEL or settings.GEMINI_FLASH_MODEL or "gemini-3.5-flash"
    return settings.GEMINI_FLASH_MODEL or "gemini-3.5-flash"


def probe_gemini_service() -> Dict[str, Any]:
    """
    Probes Gemini service health using the exact same unified client and model
    that the application uses for inference.
    """
    model_name = get_model_name("flash")
    try:
        client = get_gemini_client()
        response = client.models.generate_content(
            model=model_name,
            contents="ping"
        )
        if response and response.text:
            return {
                "ok": True,
                "status": "connected",
                "model": model_name,
                "mode": _CLIENT_MODE or "vertexai"
            }
        return {
            "ok": False,
            "status": "unavailable",
            "model": model_name,
            "detail": "Empty response from Gemini probe"
        }
    except Exception as e:
        return {
            "ok": False,
            "status": "unavailable",
            "model": model_name,
            "detail": str(e)
        }


def track_gemini_tokens(
    response: Any,
    claim_id: Optional[str] = None,
    model: str = "gemini-2.5-flash"
) -> int:
    """
    Extracts usage_metadata from a Gemini response and records tokens via token_budget_tracker.
    Enforces the per-claim hard cap (default: 30,000 tokens) raising TokenBudgetExceededError if exceeded.
    Also records metrics globally into metrics_service.
    """
    if not response:
        return 0

    prompt_tokens = 0
    candidate_tokens = 0
    usage = getattr(response, "usage_metadata", None)
    if usage:
        prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
        candidate_tokens = getattr(usage, "candidates_token_count", 0) or 0
    else:
        text = getattr(response, "text", "") or ""
        candidate_tokens = max(1, len(text) // 4) if text else 10
        prompt_tokens = 50

    call_tokens = prompt_tokens + candidate_tokens

    # Update operational metrics
    try:
        from backend.app.services.metrics import metrics_service
        metrics_service.record_llm_tokens(call_tokens)
    except Exception as e:
        logger.debug("Metrics record llm tokens skipped: %s", e)

    if claim_id:
        from backend.app.services.token_budget import token_budget_tracker
        return token_budget_tracker.record_usage(
            claim_id=claim_id,
            prompt_tokens=prompt_tokens,
            candidate_tokens=candidate_tokens,
            model=model
        )

    return call_tokens

