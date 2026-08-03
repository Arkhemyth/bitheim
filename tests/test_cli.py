"""Unit and functional tests for the Bitheim CLI entrypoint."""

import shutil
import subprocess
import sys

import pytest

from bitheim import __version__
from bitheim.interfaces.cli import build_parser, main


def test_build_parser_configuration() -> None:
    """Verify that build_parser constructs an ArgumentParser with expected metadata."""
    parser = build_parser()
    assert parser.prog == "bitheim"
    assert "Distributed platform" in (parser.description or "")


def test_cli_help_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify that --help exits with code 0 and displays canonical usage text."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "usage: bitheim" in captured.out
    assert "--help" in captured.out
    assert "--version" in captured.out
    assert "Distributed platform" in captured.out


def test_cli_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify that --version exits with code 0 and prints canonical program version."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == f"bitheim {__version__}"


def test_cli_unknown_argument(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify that unknown arguments exit with code 2 and print error message to stderr."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--unrecognized-option-xyz"])
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "unrecognized arguments" in captured.err


def test_cli_default_invocation_returns_zero() -> None:
    """Verify that invocation without arguments succeeds with exit code 0."""
    assert main([]) == 0


def test_cli_module_execution() -> None:
    """Verify that python -m bitheim.interfaces.cli functions correctly as a subprocess."""
    result = subprocess.run(
        [sys.executable, "-m", "bitheim.interfaces.cli", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == f"bitheim {__version__}"


def test_cli_installed_entrypoint() -> None:
    """Verify that the installed bitheim console script executes cleanly if available in PATH."""
    bitheim_bin = shutil.which("bitheim")
    if bitheim_bin is None:
        pytest.skip("bitheim console script is not located in current PATH")

    result = subprocess.run(
        [bitheim_bin, "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == f"bitheim {__version__}"
