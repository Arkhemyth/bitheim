"""Diagnostic prerequisite checks for Docker Engine and Docker Compose."""

import subprocess
from typing import Final

from bitheim.bootstrap.logging import get_logger

logger = get_logger("infrastructure.compose.diagnostics")

_DIAGNOSTIC_TIMEOUT: Final[float] = 3.0


def _categorize_diagnostic_error(stderr: str) -> str:
    """Map raw stderr into a safe categorical descriptor."""
    lower = stderr.lower()
    if "permission denied" in lower or "access denied" in lower:
        return "permission_denied"
    if "cannot connect to the docker daemon" in lower or "is the docker daemon running" in lower:
        return "daemon_unavailable"
    if "executable file not found" in lower or "no such file or directory" in lower:
        return "binary_not_found"
    return "daemon_unreachable"


def check_docker_engine_available() -> tuple[bool, str]:
    """Check if the Docker CLI and Docker Engine daemon are available and accessible.

    Returns:
        Tuple of (is_available, human_readable_description).
    """
    try:
        proc = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            timeout=_DIAGNOSTIC_TIMEOUT,
            check=False,
        )
        if proc.returncode == 0:
            version = proc.stdout.strip()
            logger.debug(
                "Docker Engine check passed",
                extra={
                    "event": "doctor_docker_passed",
                    "data": {"version": version},
                },
            )
            return True, f"Docker Engine version {version} (daemon active)"

        category = _categorize_diagnostic_error(proc.stderr)
        logger.warning(
            "Docker Engine check failed",
            extra={
                "event": "doctor_docker_failed",
                "data": {"reason": category},
            },
        )
        return False, f"Docker Engine daemon unreachable ({category})"
    except FileNotFoundError:
        logger.warning(
            "Docker CLI not found",
            extra={"event": "doctor_docker_failed", "data": {"reason": "binary_not_found"}},
        )
        return False, "Docker CLI binary not found in system PATH"
    except subprocess.TimeoutExpired:
        logger.warning(
            "Docker Engine check timed out",
            extra={"event": "doctor_docker_failed", "data": {"reason": "timeout"}},
        )
        return False, f"Docker Engine query timed out after {_DIAGNOSTIC_TIMEOUT:.1f}s"
    except Exception as err:
        logger.warning(
            "Docker Engine check encountered error",
            extra={"event": "doctor_docker_failed", "data": {"error_type": type(err).__name__}},
        )
        return False, f"Docker Engine diagnostic error ({type(err).__name__})"


def check_docker_compose_available() -> tuple[bool, str]:
    """Check if Docker Compose v2+ is installed and operational.

    Returns:
        Tuple of (is_available, human_readable_description).
    """
    try:
        proc = subprocess.run(
            ["docker", "compose", "version", "--short"],
            capture_output=True,
            text=True,
            timeout=_DIAGNOSTIC_TIMEOUT,
            check=False,
        )
        if proc.returncode == 0:
            version = proc.stdout.strip()
            logger.debug(
                "Docker Compose check passed",
                extra={
                    "event": "doctor_compose_passed",
                    "data": {"version": version},
                },
            )
            return True, f"Docker Compose v2+ plugin version {version}"

        category = _categorize_diagnostic_error(proc.stderr)
        logger.warning(
            "Docker Compose check failed",
            extra={
                "event": "doctor_compose_failed",
                "data": {"reason": category},
            },
        )
        return False, f"Docker Compose plugin v2+ not available ({category})"
    except FileNotFoundError:
        logger.warning(
            "Docker CLI not found for Compose check",
            extra={"event": "doctor_compose_failed", "data": {"reason": "binary_not_found"}},
        )
        return False, "Docker CLI not found for Compose check"
    except subprocess.TimeoutExpired:
        logger.warning(
            "Docker Compose check timed out",
            extra={"event": "doctor_compose_failed", "data": {"reason": "timeout"}},
        )
        return False, f"Docker Compose query timed out after {_DIAGNOSTIC_TIMEOUT:.1f}s"
    except Exception as err:
        logger.warning(
            "Docker Compose check encountered error",
            extra={"event": "doctor_compose_failed", "data": {"error_type": type(err).__name__}},
        )
        return False, f"Docker Compose diagnostic error ({type(err).__name__})"
