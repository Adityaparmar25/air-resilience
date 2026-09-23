"""Structured Observability and Logging Service.

Provides structured JSON logging with correlation IDs, automatic redaction of
sensitive API keys/tokens, and prevents logging of citizen image payloads or secrets.
"""

from datetime import datetime, timezone
import json
import logging
import os
import re
from typing import Any, Dict, Optional
import uuid

# Keys that must be masked in log payloads
SENSITIVE_PATTERNS = re.compile(
    r"(api[-_]?key|secret|password|token|credentials|authorization|bearer)",
    re.IGNORECASE,
)

logger = logging.getLogger("air_resilience")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())


def mask_sensitive_data(obj: Any) -> Any:
    """Recursively mask sensitive keys, credentials, and image payloads."""
    if isinstance(obj, dict):
        sanitized = {}
        for k, v in obj.items():
            if SENSITIVE_PATTERNS.search(str(k)):
                sanitized[k] = "***REDACTED***"
            elif k in ("image", "image_bytes", "image_base64", "sample_image") and isinstance(v, str) and len(v) > 100:
                sanitized[k] = f"<{k} payload: {len(v)} chars omitted>"
            else:
                sanitized[k] = mask_sensitive_data(v)
        return sanitized
    elif isinstance(obj, list):
        return [mask_sensitive_data(item) for item in obj]
    elif isinstance(obj, str):
        # Mask inline api keys or bearer tokens if detected
        if len(obj) > 30 and ("AIza" in obj or "Bearer " in obj):
            return "***REDACTED_SECRET***"
    return obj


def log_event(
    level: str,
    event: str,
    correlation_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    component: str = "core",
) -> None:
    """Emit a structured JSON log entry."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level.upper(),
        "component": component,
        "event": event,
        "correlation_id": correlation_id or "unassigned",
        "data": mask_sensitive_data(details or {}),
    }

    log_line = json.dumps(entry, default=str)
    if level.upper() == "ERROR":
        logger.error(log_line)
    elif level.upper() == "WARNING":
        logger.warning(log_line)
    elif level.upper() == "DEBUG":
        logger.debug(log_line)
    else:
        logger.info(log_line)
