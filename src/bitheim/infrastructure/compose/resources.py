"""Resource resolution and packaged asset discovery for Docker Compose runtime."""

import importlib.resources
from pathlib import Path

from bitheim.domain.errors import RuntimeUnavailableError


def get_compose_template_path() -> Path:
    """Locate the packaged or repository docker compose topology file.

    Priority:
    1. Packaged resource inside bitheim.resources.compose (works for wheel/uv tool installs)
    2. Repository checkout path (docker/compose.yml)

    Returns:
        Absolute Path to compose.yml.

    Raises:
        RuntimeUnavailableError: If compose.yml cannot be located.
    """
    try:
        traversable = importlib.resources.files("bitheim.resources").joinpath(
            "compose", "compose.yml"
        )
        path = Path(str(traversable))
        if path.is_file():
            return path.resolve()
    except Exception:
        pass

    # Fallback to repository checkout relative to this source file
    repo_fallback = Path(__file__).resolve().parents[4] / "docker" / "compose.yml"
    if repo_fallback.is_file():
        return repo_fallback.resolve()

    msg = "Docker Compose template 'compose.yml' not found in package resources or repository."
    raise RuntimeUnavailableError(msg)


def get_bitcoin_core_resource_dir() -> Path:
    """Locate the directory containing the packaged Bitcoin Core Dockerfile and configuration.

    Returns:
        Absolute Path to directory containing Dockerfile and bitcoin.conf.

    Raises:
        RuntimeUnavailableError: If Bitcoin Core resource directory cannot be located.
    """
    try:
        traversable = importlib.resources.files("bitheim.resources").joinpath("bitcoin-core")
        path = Path(str(traversable))
        if path.is_dir() and (path / "Dockerfile").is_file():
            return path.resolve()
    except Exception:
        pass

    repo_fallback = Path(__file__).resolve().parents[4] / "docker" / "bitcoin-core"
    if repo_fallback.is_dir() and (repo_fallback / "Dockerfile").is_file():
        return repo_fallback.resolve()

    msg = "Bitcoin Core runtime resources not found in package resources or repository."
    raise RuntimeUnavailableError(msg)
