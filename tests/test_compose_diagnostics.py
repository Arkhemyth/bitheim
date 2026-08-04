"""Tests for Docker Engine and Compose diagnostics."""

import subprocess
from unittest.mock import patch

from bitheim.infrastructure.compose.diagnostics import (
    check_docker_compose_available,
    check_docker_engine_available,
)


def test_check_docker_engine_success() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="27.0.3\n", stderr=""
        )
        ok, desc = check_docker_engine_available()
        assert ok is True
        assert "27.0.3" in desc


def test_check_docker_engine_not_running() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Cannot connect to the Docker daemon"
        )
        ok, desc = check_docker_engine_available()
        assert ok is False
        assert "unreachable" in desc


def test_check_docker_engine_missing_binary() -> None:
    with patch("subprocess.run", side_effect=FileNotFoundError):
        ok, desc = check_docker_engine_available()
        assert ok is False
        assert "not found" in desc


def test_check_docker_compose_success() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="v2.29.1\n", stderr=""
        )
        ok, desc = check_docker_compose_available()
        assert ok is True
        assert "v2.29.1" in desc


def test_check_docker_compose_failure() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="compose is not a docker command"
        )
        ok, desc = check_docker_compose_available()
        assert ok is False
        assert "not available" in desc
