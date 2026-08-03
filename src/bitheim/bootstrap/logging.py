"""Structured JSON Lines logging foundation for Bitheim."""

import json
import logging
import os
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, TextIO

SENSITIVE_KEY_SUBSTRINGS: tuple[str, ...] = (
    "token",
    "password",
    "secret",
    "key",
    "cookie",
    "seed",
    "auth",
    "credential",
    "privkey",
    "private_key",
)

SAFE_FALLBACK_EVENT: str = "unspecified_event"


class _DynamicStderrStream:
    """Dynamic stream proxy that forwards write/flush to current sys.stderr."""

    def write(self, text: str) -> int:
        return sys.stderr.write(text)

    def flush(self) -> None:
        sys.stderr.flush()


def _sanitize_data(data: Any) -> Any:
    """Recursively sanitize dictionary data structures against sensitive keys."""
    if isinstance(data, Mapping):
        sanitized: dict[str, Any] = {}
        for k, v in data.items():
            key_str = str(k)
            key_lower = key_str.lower()
            if any(substring in key_lower for substring in SENSITIVE_KEY_SUBSTRINGS):
                sanitized[key_str] = "[REDACTED]"
            else:
                sanitized[key_str] = _sanitize_data(v)
        return sanitized
    if isinstance(data, (list, tuple, set)):
        return [_sanitize_data(item) for item in data]
    if isinstance(data, (int, float, bool)) or data is None:
        return data
    return str(data)


class StructuredFormatter(logging.Formatter):
    """Formats LogRecord instances as single-line JSON Lines strings."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a single LogRecord into a canonical JSON Lines string.

        Args:
            record: LogRecord instance to format.

        Returns:
            Single-line JSON string representing the structured log record.
        """
        # Timestamp in ISO 8601 UTC with microsecond precision and 'Z' suffix
        record_dt = datetime.fromtimestamp(record.created, tz=UTC)
        timestamp_str = record_dt.isoformat(timespec="microseconds").replace("+00:00", "Z")

        # Determine canonical event identifier (never fallback to free-form message)
        event_attr = getattr(record, "event", None)
        if isinstance(event_attr, str) and event_attr.strip():
            event_str = event_attr.strip()
        else:
            event_str = SAFE_FALLBACK_EVENT

        payload: dict[str, Any] = {
            "timestamp": timestamp_str,
            "level": record.levelname,
            "module": record.name,
            "event": event_str,
        }

        # Optional standard contextual fields
        for field in ("correlation_id", "node_id", "experiment_id"):
            val = getattr(record, field, None)
            if val is not None and isinstance(val, str) and val.strip():
                payload[field] = val.strip()

        # Optional structured event data payload (sanitized)
        data_payload = getattr(record, "data", None)
        if isinstance(data_payload, Mapping) and data_payload:
            payload["data"] = _sanitize_data(data_payload)

        # Exception metadata: strictly categorical type name, never raw un-sanitized message
        if record.exc_info and record.exc_info[0] is not None:
            payload["exception"] = {
                "type": record.exc_info[0].__name__,
            }

        return json.dumps(payload, ensure_ascii=False, default=str)


def parse_log_level(level_name: str | int | None, default: int = logging.WARNING) -> int:
    """Parse log level from string name or integer value.

    Args:
        level_name: Level name ('DEBUG', 'INFO', etc.) or integer.
        default: Fallback level if resolution fails.

    Returns:
        Standard logging level integer.
    """
    if level_name is None:
        return default
    if isinstance(level_name, int):
        return level_name
    if isinstance(level_name, str):
        level_upper = level_name.strip().upper()
        if level_upper in ("DEBUG", "INFO", "WARNING", "WARN", "ERROR", "CRITICAL"):
            resolved = logging.getLevelName(level_upper)
            if isinstance(resolved, int):
                return resolved
    return default


def setup_logging(
    level: str | int | None = None,
    stream: TextIO | None = None,
    environ: Mapping[str, str] | None = None,
    force: bool = False,
) -> logging.Logger:
    """Configure the Bitheim top-level logger with structured JSON formatting.

    Args:
        level: Optional explicit log level.
        stream: Optional output stream (defaults to dynamic sys.stderr).
        environ: Optional environment mapping (defaults to os.environ).
        force: If True, replace existing structured handlers.

    Returns:
        Configured root 'bitheim' Logger instance.
    """
    env = os.environ if environ is None else environ
    env_level = env.get("BITHEIM_LOG_LEVEL")
    resolved_level = parse_log_level(level if level is not None else env_level)

    logger = logging.getLogger("bitheim")
    logger.setLevel(resolved_level)
    logger.propagate = False

    # Check if a structured StreamHandler is already present
    existing_handler: logging.StreamHandler[Any] | None = None
    for h in logger.handlers:
        if isinstance(h, logging.StreamHandler) and isinstance(h.formatter, StructuredFormatter):
            existing_handler = h
            break

    if existing_handler is not None and not force and stream is None:
        existing_handler.setLevel(resolved_level)
        return logger

    # Clear previous stream handlers if reconfiguring or forcing
    for h in list(logger.handlers):
        if isinstance(h, logging.StreamHandler):
            logger.removeHandler(h)

    target_stream: TextIO | _DynamicStderrStream = (
        _DynamicStderrStream() if stream is None else stream
    )
    handler = logging.StreamHandler(target_stream)
    handler.setLevel(resolved_level)
    handler.setFormatter(StructuredFormatter())
    logger.addHandler(handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Obtain a logger within the 'bitheim' hierarchy.

    Args:
        name: Name of the subsystem or module (e.g. 'bootstrap.configuration').

    Returns:
        Logger named 'bitheim.<name>' or 'bitheim'.
    """
    if name == "bitheim" or name.startswith("bitheim."):
        return logging.getLogger(name)
    return logging.getLogger(f"bitheim.{name}")
