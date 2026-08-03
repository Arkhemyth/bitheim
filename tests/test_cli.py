"""Unit and functional tests for the Bitheim CLI entrypoint and diagnostic commands."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from bitheim import __version__
from bitheim.interfaces.cli import build_parser, main


def test_build_parser_configuration() -> None:
    """Verify that build_parser constructs an ArgumentParser with expected metadata."""
    parser = build_parser()
    assert parser.prog == "bitheim"
    assert "Distributed platform" in (parser.description or "")


def test_cli_help_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify that --help exits with code 0 and displays canonical usage and subcommands."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "usage: bitheim" in captured.out
    assert "--help" in captured.out
    assert "--version" in captured.out
    assert "doctor" in captured.out


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


def test_cli_doctor_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify that 'bitheim doctor --help' exits with code 0 and displays doctor options."""
    with pytest.raises(SystemExit) as exc_info:
        main(["doctor", "--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "usage: bitheim doctor" in captured.out
    assert "--config" in captured.out
    assert "--data-dir" in captured.out


def test_cli_doctor_success(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """Verify that 'bitheim doctor' executes all diagnostic checks successfully and exits 0."""
    data_dir = tmp_path / "valid_data"
    exit_code = main(["doctor", "--data-dir", str(data_dir)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "[✓] Python runtime:" in captured.out
    assert "[✓] Configuration: loaded successfully" in captured.out
    assert "[✓] Effective data directory:" in captured.out
    assert "[✓] Data directory access:" in captured.out
    assert not data_dir.exists()  # Diagnostics do not create the directory


def test_cli_doctor_existing_directory_success(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Verify that 'bitheim doctor' succeeds when data_dir already exists and is writable."""
    data_dir = tmp_path / "existing_data"
    data_dir.mkdir()
    exit_code = main(["doctor", "--data-dir", str(data_dir)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "[✓] Data directory access: directory exists and is writable" in captured.out


def test_cli_doctor_data_dir_is_not_directory(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Verify that 'bitheim doctor' fails when data_dir points to a regular file."""
    fake_file = tmp_path / "not_a_dir.txt"
    fake_file.write_text("dummy", encoding="utf-8")

    exit_code = main(["doctor", "--data-dir", str(fake_file)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "exists but is not a directory" in captured.err


def test_cli_doctor_invalid_configuration_file(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify doctor reports configuration error to stderr and exits 1 without traceback."""
    exit_code = main(["doctor", "--config", "non_existent_file.toml"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "[✗] Configuration:" in captured.err
    assert "Traceback" not in captured.err


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
    """Verify that the installed bitheim console script is located in PATH and executes doctor."""
    bitheim_bin = shutil.which("bitheim")
    assert bitheim_bin is not None, "bitheim console script executable was not found in PATH"

    clean_env = os.environ.copy()
    clean_env.pop("BITHEIM_DATA_DIR", None)

    result = subprocess.run(
        [bitheim_bin, "doctor"],
        capture_output=True,
        text=True,
        check=False,
        env=clean_env,
    )
    assert result.returncode == 0
    assert "[✓] Python runtime:" in result.stdout
