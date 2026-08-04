"""Leak prevention and information sanitization test suite."""

import io
import logging
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from bitheim.bootstrap.configuration import ConfigurationError, load_configuration
from bitheim.bootstrap.logging import setup_logging
from bitheim.domain.errors import LifecycleError, RuntimeUnavailableError
from bitheim.infrastructure.compose.adapter import ComposeLifecycleAdapter


def test_collision_inspection_error_leak_prevention() -> None:
    """Verify subnet collision errors do not leak network names or IPs in exception strings."""
    stream = io.StringIO()
    setup_logging(level=logging.DEBUG, stream=stream, force=True)

    adapter = ComposeLifecycleAdapter(compose_subnet="172.28.0.0/16")

    secret_net_name = "super_secret_internal_corp_net_999"
    secret_subnet = "172.28.10.0/24"

    def mock_sub_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        res = MagicMock()
        res.returncode = 0
        if "network" in cmd and "ls" in cmd:
            res.stdout = f"{secret_net_name}\n"
        elif "network" in cmd and "inspect" in cmd:
            res.stdout = f"{secret_subnet} \n"
        elif "info" in cmd:
            res.stdout = "26.0.0\n"
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=mock_sub_run),
    ):
        with pytest.raises(LifecycleError) as exc_info:
            adapter._check_subnet_collision("test-node", deadline=time.monotonic() + 5.0)

        # Exception message must be categorical and not leak secret net name or subnet
        assert secret_net_name not in str(exc_info.value)
        assert secret_subnet not in str(exc_info.value)
        assert "overlaps with an existing Docker network" in str(exc_info.value)


def test_compose_ps_failure_leak_prevention() -> None:
    """Verify that Compose ps failure does not leak raw container stderr or internal details."""
    stream = io.StringIO()
    setup_logging(level=logging.DEBUG, stream=stream, force=True)

    adapter = ComposeLifecycleAdapter()
    sensitive_stderr = "FATAL: /var/lib/docker/overlay2/secret-token-abc/data permission denied"

    def mock_sub_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        res = MagicMock()
        if "info" in cmd:
            res.returncode = 0
            res.stdout = "26.0.0\n"
        elif "ps" in cmd:
            res.returncode = 1
            res.stderr = sensitive_stderr
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=mock_sub_run),
    ):
        with pytest.raises(RuntimeUnavailableError) as exc_info:
            adapter.get_lifecycle_state("test-node")

        # Raw stderr must NOT be in the exception message
        assert sensitive_stderr not in str(exc_info.value)
        assert "secret-token-abc" not in str(exc_info.value)
        assert "Failed to inspect node services via Docker Compose" in str(exc_info.value)


def test_configuration_loading_path_leak_prevention(tmp_path: Path) -> None:
    """Verify configuration parsing errors do not leak full paths in structured error events."""
    stream = io.StringIO()
    setup_logging(level=logging.ERROR, stream=stream, force=True)

    sensitive_path = tmp_path / "sensitive_personal_dir_xyz_123" / "bitheim.toml"
    sensitive_path.parent.mkdir()
    sensitive_path.write_text("invalid = = toml", encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_configuration(config_path=sensitive_path)

    log_output = stream.getvalue()
    assert "sensitive_personal_dir_xyz_123" not in log_output
