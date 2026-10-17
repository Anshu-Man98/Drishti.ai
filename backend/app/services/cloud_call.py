"""
FinShield Shared Cloud-Call Resilience Helper.

Enforces:
1. Strict timeouts per cloud service call (Gemini, Document AI, BigQuery, Firestore).
2. Bounded retries with exponential backoff and randomized jitter.
3. Fail-loud semantics: raises CloudServiceError on exhaustion or non-retryable errors.
4. Structured logging of call latencies, retry attempts, and failures.
"""

import time
import random
import logging
import concurrent.futures
from typing import Callable, TypeVar, Optional, Any, Tuple, Type

from backend.app.config import settings
from backend.app.exceptions import CloudServiceError

logger = logging.getLogger("finshield.services.cloud_call")

T = TypeVar("T")

# Shared worker pool for enforcing strict timeouts on blocking cloud RPCs/SDKs
_CLOUD_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=32,
    thread_name_prefix="cloud-worker"
)

# Common non-retryable error signatures
NON_RETRYABLE_KEYWORDS = (
    "invalid_argument",
    "bad request",
    "not found",
    "404",
    "400",
    "unauthorized",
    "401",
    "forbidden",
    "403",
    "unsupported media type",
    "415",
    "payload too large",
    "413",
    "unprocessable entity",
    "422",
    "corrupt",
    "invalid magic bytes",
    "bytes billed",
    "token budget",
)


def is_retryable_exception(exc: Exception) -> bool:
    """Classifies whether an exception represents a transient cloud service outage."""
    if isinstance(exc, concurrent.futures.TimeoutError) or isinstance(exc, TimeoutError):
        return True

    if isinstance(exc, CloudServiceError):
        return exc.retryable

    exc_str = str(exc).lower()
    exc_type = type(exc).__name__.lower()

    if any(k in exc_str for k in NON_RETRYABLE_KEYWORDS):
        return False

    # Transient / Rate-limit / Service Outage signatures
    if any(k in exc_str or k in exc_type for k in (
        "timeout",
        "deadline",
        "serviceunavailable",
        "503",
        "500",
        "502",
        "504",
        "resourceexhausted",
        "429",
        "rate limit",
        "connection",
        "remotedisconnected",
        "broken pipe",
        "internal error",
    )):
        return True

    return False


def cloud_call(
    func: Callable[..., T],
    *args: Any,
    service: str = "cloud_service",
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None,
    base_backoff: float = 0.5,
    max_backoff: float = 4.0,
    jitter: float = 0.25,
    **kwargs: Any
) -> T:
    """
    Executes a callable with strict timeout, bounded retries, and jittered exponential backoff.
    Raises CloudServiceError with service name and retryable status on terminal failure.
    """
    timeout_sec = timeout if timeout is not None else settings.CLOUD_CALL_TIMEOUT_SEC
    retries = max_retries if max_retries is not None else settings.CLOUD_CALL_MAX_RETRIES

    last_error: Optional[Exception] = None

    for attempt in range(retries + 1):
        t0 = time.perf_counter()
        try:
            future = _CLOUD_EXECUTOR.submit(func, *args, **kwargs)
            result = future.result(timeout=timeout_sec)
            lat_ms = (time.perf_counter() - t0) * 1000
            logger.debug(
                "[%s] Call succeeded on attempt %d in %.2f ms",
                service, attempt + 1, lat_ms,
                extra={"service": service, "attempt": attempt + 1, "latency_ms": round(lat_ms, 2)}
            )
            return result
        except concurrent.futures.TimeoutError as te:
            lat_ms = (time.perf_counter() - t0) * 1000
            last_error = te
            err_msg = f"{service} call timed out after {timeout_sec:.1f}s (attempt {attempt + 1}/{retries + 1})"
            logger.warning(
                "[%s] %s (elapsed: %.2f ms)", service, err_msg, lat_ms,
                extra={"service": service, "attempt": attempt + 1, "latency_ms": round(lat_ms, 2)}
            )
        except Exception as e:
            lat_ms = (time.perf_counter() - t0) * 1000
            last_error = e
            err_msg = f"{service} call error on attempt {attempt + 1}/{retries + 1}: {e}"
            logger.warning(
                "[%s] %s (elapsed: %.2f ms)", service, err_msg, lat_ms,
                extra={"service": service, "attempt": attempt + 1, "latency_ms": round(lat_ms, 2)}
            )

        # Check if we should retry
        if attempt < retries and is_retryable_exception(last_error):
            backoff = min(max_backoff, base_backoff * (2 ** attempt)) + random.uniform(0, jitter)
            logger.info("[%s] Retrying in %.2fs...", service, backoff)
            time.sleep(backoff)
        else:
            break

    # Terminal failure after retries exhausted or non-retryable error
    is_retryable = is_retryable_exception(last_error) if last_error else False
    if isinstance(last_error, concurrent.futures.TimeoutError):
        msg = f"{service} call timed out after {timeout_sec:.1f}s ({retries + 1} attempts exhausted)."
    else:
        msg = f"{service} call failed after {retries + 1} attempts: {last_error}"

    logger.error(
        "[%s] Terminal failure: %s", service, msg,
        extra={"service": service, "retryable": is_retryable}
    )
    raise CloudServiceError(service=service, message=msg, retryable=is_retryable) from last_error
