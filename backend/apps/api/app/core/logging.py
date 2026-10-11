"""Structured JSON logging with request ID tracking and secret redaction."""
import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

# Sensitive keys and patterns to automatically redact from logs per Rule 4 and Rule 8
SENSITIVE_PATTERNS = [
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"authorization", re.IGNORECASE),
    re.compile(r"cookie", re.IGNORECASE),
]


def redact_sensitive_data(data: Any) -> Any:
    """Recursively redact sensitive fields from dictionaries and lists."""
    if isinstance(data, dict):
        redacted = {}
        for k, v in data.items():
            if any(pattern.search(str(k)) for pattern in SENSITIVE_PATTERNS):
                redacted[k] = "[REDACTED]"
            elif isinstance(v, (dict, list)):
                redacted[k] = redact_sensitive_data(v)
            else:
                redacted[k] = v
        return redacted
    elif isinstance(data, list):
        return [redact_sensitive_data(item) for item in data]
    return data


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs log records as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include request_id if attached
        if hasattr(record, "request_id"):
            log_obj["request_id"] = record.request_id

        # Include extra attributes if present
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_obj["extra"] = redact_sensitive_data(record.extra)

        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            log_obj["exception"] = record.exc_text

        return json.dumps(log_obj)


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure root and application loggers."""
    logger = logging.getLogger("enterprise_rag")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Avoid duplicate handlers
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)

    return logger


logger = setup_logging()
