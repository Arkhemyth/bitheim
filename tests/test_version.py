"""Tests for Bitheim package initialization and version exposure."""

import bitheim


def test_bitheim_version_exposure() -> None:
    """Verify that bitheim exposes a valid semver version string."""
    assert hasattr(bitheim, "__version__")
    assert isinstance(bitheim.__version__, str)
    assert bitheim.__version__ == "0.1.0"
