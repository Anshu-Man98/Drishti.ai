"""
Structured logging configuration for Drishti / FinShield.
Formats log records as structured JSON entries containing:
- timestamp
- level
- logger name
- message
- claim_id (if provided in extra)
- specialist_id (if provided in extra)
- latency_ms (if provided in extra)
- exception info (if present)
"""

import json
import logging
import sys
from typing import Any, Dict


class StructuredJsonFormatter(logging.Formatter):
    """Formats log records as structured JSON strings."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt or "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Structured context fields if passed via extra={...}
        for attr in ("claim_id", "specialist_id", "latency_ms", "service", "error_code", "agent_name"):
            if hasattr(record, attr):
                log_obj[attr] = getattr(record, attr)

        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            log_obj["exception"] = record.exc_text

        return json.dumps(log_obj)


def configure_logging(level: int = logging.INFO, json_format: bool = False) -> None:
    """Configures handlers on the root logger or finshield loggers."""
    root_logger = logging.getLogger()
    if any(getattr(h, "_finshield_configured", False) for h in root_logger.handlers):
        return

    handler = logging.StreamHandler(sys.stdout)
    handler._finshield_configured = True  # type: ignore[attr-defined]

    if json_format:
        formatter = StructuredJsonFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S"
        )

    handler.setFormatter(formatter)
    root_logger.setLevel(level)
    root_logger.addHandler(handler)
