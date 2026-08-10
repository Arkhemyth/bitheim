"""Unit and functional tests for Bitheim structured logging foundation."""

import io
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from bitheim.bootstrap.configuration import ConfigurationError, load_configuration
from bitheim.bootstrap.logging import (
    SAFE_FALLBACK_EVENT,
    StructuredFormatter,
    _sanitize_data,
    get_logger,
    parse_log_level,
    setup_logging,
)
from bitheim.domain.node import NodeLifecycleState
from bitheim.interfaces.cli import handle_doctor, main


def _parse_single_json_log(stream: io.StringIO) -> dict[str, Any]:
    """Helper to parse a single JSON Lines record from a string stream."""
    lines = stream.getvalue().strip().splitlines()
    assert len(lines) >= 1, "Expected at least one log line in stream"
    parsed: Any = json.loads(lines[-1])
    assert isinstance(parsed, dict)
    return {str(k): v for k, v in parsed.items()}


def test_structured_formatter_required_fields() -> None:
    """Verify that StructuredFormatter outputs all required schema fields."""
    formatter = StructuredFormatter()
    record = logging.LogRecord(
        name="bitheim.test_module",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Test message content",
        args=(),
        exc_info=None,
    )
    record.event = "test_event"
    parsed = json.loads(formatter.format(record))
    assert "timestamp" in parsed
    assert parsed["level"] == "INFO"
    assert parsed["module"] == "bitheim.test_module"
    assert parsed["event"] == "test_event"
    ts_str = str(parsed["timestamp"])
    assert ts_str.endswith("Z")
    assert datetime.fromisoformat(ts_str.replace("Z", "+00:00")).tzinfo == UTC


def test_structured_formatter_fallback_event_does_not_leak_message() -> None:
    """Verify that StructuredFormatter uses safe constant fallback and never leaks free message."""
    formatter = StructuredFormatter()
    secret_sentinel = "SECRET_TOKEN_IN_MESSAGE_12345"
    record = logging.LogRecord(
        name="bitheim.fallback",
        level=logging.WARNING,
        pathname="test.py",
        lineno=10,
        msg=f"Message with sensitive data {secret_sentinel}",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    assert json.loads(output)["event"] == SAFE_FALLBACK_EVENT
    assert secret_sentinel not in output


def test_structured_formatter_optional_context_fields() -> None:
    """Verify that correlation_id, node_id, and experiment_id are serialized when present."""
    formatter = StructuredFormatter()
    record = logging.LogRecord(
        name="bitheim.experiment",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Experiment step",
        args=(),
        exc_info=None,
    )
    record.event = "step_executed"
    record.correlation_id = "corr-12345"
    record.node_id = "node-alpha"
    record.experiment_id = "exp-mining-01"
    record.data = {"iteration": 1, "active": True}
    parsed = json.loads(formatter.format(record))
    assert parsed["correlation_id"] == "corr-12345"
    assert parsed["node_id"] == "node-alpha"
    assert parsed["experiment_id"] == "exp-mining-01"
    assert parsed["data"] == {"iteration": 1, "active": True}


def test_structured_formatter_exception_serialization_type_only() -> None:
    """Verify that exceptions serialize only the type name without leaking message details."""
    formatter = StructuredFormatter()
    secret_path_sentinel = "/home/private_user/.secret_keys/wallet.dat"
    try:
        raise ValueError(f"Failed to open {secret_path_sentinel}")
    except ValueError:
        exc_info = sys.exc_info()
    record = logging.LogRecord(
        name="bitheim.error",
        level=logging.ERROR,
        pathname="test.py",
        lineno=20,
        msg="Error encountered",
        args=(),
        exc_info=exc_info,
    )
    record.event = "error_occurred"
    output = formatter.format(record)
    assert json.loads(output)["exception"] == {"type": "ValueError"}
    assert secret_path_sentinel not in output


def test_structured_formatter_defense_in_depth_sanitization() -> None:
    """Verify that sensitive keys are redacted from structured data payloads."""
    formatter = StructuredFormatter()
    record = logging.LogRecord(
        name="bitheim.security",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Payload check",
        args=(),
        exc_info=None,
    )
    record.event = "auth_attempt"
    record.data = {
        "user": "alice",
        "api_key": "secret-key-123",
        "rpc_password": "super-secret-password",
        "auth_token": "token-xyz",
        "cookie_data": "cookie-val",
        "seed_phrase": "word1 word2",
        "nested": {"private_key": "hex-key", "safe_field": 42},
        "list_items": [{"secret_key": "val"}, {"safe": True}],
    }
    data = json.loads(formatter.format(record))["data"]
    assert data["user"] == "alice"
    assert data["api_key"] == "[REDACTED]"
    assert data["rpc_password"] == "[REDACTED]"
    assert data["auth_token"] == "[REDACTED]"
    assert data["cookie_data"] == "[REDACTED]"
    assert data["seed_phrase"] == "[REDACTED]"
    assert data["nested"]["private_key"] == "[REDACTED]"
    assert data["nested"]["safe_field"] == 42
    assert data["list_items"][0]["secret_key"] == "[REDACTED]"
    assert data["list_items"][1]["safe"] is True


def test_sanitize_data_primitive_and_edge_types() -> None:
    """Verify _sanitize_data preserves primitives and handles edge structures."""
    assert _sanitize_data(42) == 42
    assert _sanitize_data(3.14) == 3.14
    assert _sanitize_data(None) is None
    assert _sanitize_data(True) is True
    assert _sanitize_data([1, "two", False]) == [1, "two", False]


def test_parse_log_level() -> None:
    """Verify parsing of log levels from strings, ints, and defaults."""
    assert parse_log_level("DEBUG") == logging.DEBUG
    assert parse_log_level("info") == logging.INFO
    assert parse_log_level("WARNING") == logging.WARNING
    assert parse_log_level("ERROR") == logging.ERROR
    assert parse_log_level("critical") == logging.CRITICAL
    assert parse_log_level(logging.DEBUG) == logging.DEBUG
    assert parse_log_level("UNKNOWN_LEVEL", default=logging.INFO) == logging.INFO
    assert parse_log_level(None, default=logging.WARNING) == logging.WARNING


def test_setup_logging_from_environ() -> None:
    """Verify setup_logging extracts log level from environment mapping."""
    logger = setup_logging(environ={"BITHEIM_LOG_LEVEL": "DEBUG"}, force=True)
    assert logger.level == logging.DEBUG

    logger = setup_logging(environ={"BITHEIM_LOG_LEVEL": "ERROR"}, force=True)
    assert logger.level == logging.ERROR


def test_setup_logging_stream_and_hierarchy() -> None:
    """Verify setup_logging configures stream and child logger inheritance."""
    stream = io.StringIO()
    setup_logging(level=logging.DEBUG, stream=stream, force=True)

    child_logger = get_logger("bootstrap.test")
    child_logger.info("Test message", extra={"event": "test_emitted", "data": {"param": "val"}})

    log_obj = _parse_single_json_log(stream)
    assert log_obj["level"] == "INFO"
    assert log_obj["module"] == "bitheim.bootstrap.test"
    assert log_obj["event"] == "test_emitted"
    assert log_obj["data"] == {"param": "val"}


def test_configuration_loading_structured_logging(tmp_path: Path) -> None:
    """Verify that configuration loading emits structured events with categorical data only."""
    stream = io.StringIO()
    setup_logging(level=logging.DEBUG, stream=stream, force=True)

    # 1. Success case
    config = load_configuration(data_dir=tmp_path / "custom")
    assert config.runtime.data_dir == tmp_path / "custom"
    success_log = _parse_single_json_log(stream)
    assert success_log["level"] == "DEBUG"
    assert success_log["module"] == "bitheim.bootstrap.configuration"
    assert success_log["event"] == "configuration_loaded"
    assert success_log["data"] == {"source": "cli", "has_custom_config": False}
    # Ensure personal paths are NOT in the structured log
    assert str(tmp_path) not in stream.getvalue()

    # 2. Failure case
    secret_sentinel = "SECRET_SENTINEL_CONFIG_PATH_999"
    invalid_file = tmp_path / f"bad_{secret_sentinel}.toml"
    invalid_file.write_text("invalid = = toml", encoding="utf-8")

    stream.truncate(0)
    stream.seek(0)
    with pytest.raises(ConfigurationError):
        load_configuration(config_path=invalid_file)

    error_log = _parse_single_json_log(stream)
    assert error_log["level"] == "ERROR"
    assert error_log["module"] == "bitheim.bootstrap.configuration"
    assert error_log["event"] == "configuration_load_failed"
    assert error_log["data"] == {"error_type": "toml_decode_error"}
    # Ensure personal path / sentinel is not leaked in structured log output
    assert secret_sentinel not in stream.getvalue()


def test_handle_doctor_structured_logging(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify doctor emits JSONL on stderr with categorical data and checkmarks on stdout."""
    stream = io.StringIO()
    setup_logging(level=logging.DEBUG, stream=stream, force=True)

    class Args:
        config = None
        data_dir = str(tmp_path / "data")

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run") as mock_sub,
        patch("bitheim.interfaces.cli.ComposeLifecycleAdapter.get_lifecycle_state") as mock_state,
    ):
        mock_state.return_value = NodeLifecycleState.STOPPED
        mock_sub.return_value = MagicMock(returncode=0, stdout="26.0.0\n")
        exit_code = handle_doctor(Args())  # type: ignore[arg-type]
    assert exit_code == 0

    # Functional stdout output check
    captured = capsys.readouterr()
    assert "[✓] Python runtime:" in captured.out
    assert "[✓] Configuration: loaded successfully" in captured.out

    # Structured stderr logs check
    lines = stream.getvalue().strip().splitlines()
    assert len(lines) >= 4
    events = [json.loads(line)["event"] for line in lines]
    assert "doctor_started" in events
    assert "doctor_check_passed" in events
    assert "doctor_completed" in events

    # Ensure personal paths are NOT in stderr logs
    assert str(tmp_path) not in stream.getvalue()


def test_handle_doctor_failure_modes_logging(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify that doctor diagnostic failure emits structured error events."""
    stream = io.StringIO()
    setup_logging(level=logging.ERROR, stream=stream, force=True)

    # 1. Data dir is a file
    fake_file = tmp_path / "not_a_dir"
    fake_file.write_text("dummy", encoding="utf-8")

    class Args:
        config = None
        data_dir = str(fake_file)

    exit_code = handle_doctor(Args())  # type: ignore[arg-type]
    assert exit_code == 1

    lines = stream.getvalue().strip().splitlines()
    assert len(lines) >= 1
    err_event = json.loads(lines[-1])
    assert err_event["level"] == "ERROR"
    assert err_event["event"] == "doctor_check_failed"
    assert err_event["data"] == {"check": "data_dir_access", "reason": "not_a_directory"}
    # Ensure personal path is NOT in the JSONL payload
    assert str(fake_file) not in stream.getvalue()


def test_handle_doctor_incompatible_python_logging(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify that doctor logs error event when Python version is incompatible."""
    stream = io.StringIO()
    setup_logging(level=logging.ERROR, stream=stream, force=True)

    class Args:
        config = None
        data_dir = None

    with (
        patch("sys.version_info", (3, 12, 0)),
        patch("sys.version", "3.12.0 (mocked)"),
    ):
        exit_code = handle_doctor(Args())  # type: ignore[arg-type]

    assert exit_code == 1
    lines = stream.getvalue().strip().splitlines()
    assert len(lines) >= 1
    err_event = json.loads(lines[0])
    assert err_event["level"] == "ERROR"
    assert err_event["event"] == "doctor_check_failed"
    assert err_event["data"] == {"check": "python_runtime", "version": "3.12.0"}


def test_cli_main_configuration_error_logging(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify that CLI execution failure logs structured error event with categorical error_type."""
    stream = io.StringIO()
    setup_logging(level=logging.ERROR, stream=stream, force=True)

    exit_code = main(["doctor", "--config", "non_existent_config.toml"])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "[✗] Configuration:" in captured.err

    lines = stream.getvalue().strip().splitlines()
    assert len(lines) >= 1
    err_event = json.loads(lines[-1])
    assert err_event["level"] == "ERROR"
    assert err_event["event"] in ("configuration_load_failed", "doctor_check_failed")
