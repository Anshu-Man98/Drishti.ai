"""
FinShield Rate Limiting & Denial-of-Service / Cost Protection Service.

Enforces per-minute call limits on write endpoints:
- POST /claims: 10/min (prevents document spamming into GCS)
- POST /claims/{id}/analyze: 20/min (prevents Vertex/Document AI credit burn)
- POST /claims/{id}/chat: 60/min (prevents conversational token flooding)
- POST /duel/start & /duel/round: 30/min (prevents adversarial simulation loops)

Returns HTTP 429 Too Many Requests with a Retry-After header.
"""

import time
import math
import logging
import threading
from typing import Dict, List, Tuple
from fastapi import Request, HTTPException

logger = logging.getLogger("finshield.services.rate_limiter")


class RateLimitManager:
    """Thread-safe sliding-window in-memory rate limiter."""

    def __init__(self):
        self._mutex = threading.Lock()
        self._history: Dict[str, List[float]] = {}

    def check(self, key: str, max_requests: int, window_seconds: float = 60.0) -> Tuple[bool, int]:
        """
        Validates whether `key` is within the rate limit.
        Returns:
            (is_allowed: bool, retry_after_seconds: int)
        """
        now = time.time()
        cutoff = now - window_seconds

        with self._mutex:
            timestamps = self._history.get(key, [])
            # Prune timestamps older than sliding window cutoff
            active = [t for t in timestamps if t > cutoff]

            if len(active) >= max_requests:
                oldest = active[0]
                retry_after = max(1, math.ceil(oldest + window_seconds - now))
                logger.warning(
                    "Rate limit exceeded for key '%s': %d/%d calls in last %.1fs. Retry-After: %ds",
                    key, len(active), max_requests, window_seconds, retry_after
                )
                self._history[key] = active
                return False, retry_after

            active.append(now)
            self._history[key] = active
            return True, 0

    def clear(self) -> None:
        """Clears all rate limit histories (for testing purposes)."""
        with self._mutex:
            self._history.clear()


rate_limit_manager = RateLimitManager()


class RateLimiter:
    """FastAPI route dependency that enforces rate limiting per client IP and authorization token."""

    def __init__(self, requests_per_minute: int, name: str = "default"):
        self.requests_per_minute = requests_per_minute
        self.name = name

    def __call__(self, request: Request) -> None:
        from backend.app.config import settings
        if not getattr(settings, "RATE_LIMIT_ENABLED", True):
            return

        client_ip = request.headers.get("X-Forwarded-For")
        if client_ip:
            client_ip = client_ip.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "127.0.0.1"

        auth = request.headers.get("Authorization", "")
        token_fingerprint = auth[-12:] if len(auth) > 12 else auth

        # Enforce role-specific limit for chat: 10/min for user role, default (60/min) for officers/admins
        effective_limit = self.requests_per_minute
        auth_lower = auth.lower()
        if self.name == "chat" and ("user" in auth_lower or "viewer" in auth_lower):
            effective_limit = min(effective_limit, 10)

        key = f"{self.name}:{client_ip}:{token_fingerprint}"
        allowed, retry_after = rate_limit_manager.check(key, effective_limit, window_seconds=60.0)

        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Too Many Requests: Rate limit for {self.name} exceeded ({effective_limit}/min). Try again in {retry_after}s.",
                headers={"Retry-After": str(retry_after)}
            )
