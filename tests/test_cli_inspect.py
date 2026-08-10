"""Unit and functional tests for the Bitheim CLI inspect subcommand."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bitheim.domain.errors import (
    RpcIncompatibleNodeError,
    RpcUnavailableError,
)
from bitheim.domain.node import NodeLifecycleState, NodeOverview
from bitheim.interfaces.cli import main


def _sample_overview() -> NodeOverview:
    return NodeOverview(
        version=310100,
        subversion="/Satoshi:31.1.0/",
        network_active=True,
        connections=8,
        chain="regtest",
        blocks=200,
        headers=200,
        best_block_hash="0f9188f13cb7b2c71f2a335e3a4fc328bf5beb436012afca590b1a11466e2206",
        median_time=1296688602,
        initial_block_download=False,
        pruned=False,
        chainwork="0000000000000000000000000000000000000000000000000000000000000002",
    )


def test_cli_inspect_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify that 'bitheim inspect --help' displays inspect subcommands."""
    with pytest.raises(SystemExit) as exc_info:
        main(["inspect", "--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "usage: bitheim inspect" in captured.out
    assert "node" in captured.out


def test_cli_inspect_node_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify that 'bitheim inspect node --help' displays node inspection options."""
    with pytest.raises(SystemExit) as exc_info:
        main(["inspect", "node", "--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "usage: bitheim inspect node" in captured.out
    assert "--node-id" in captured.out
    assert "--timeout" in captured.out
    assert "--json" in captured.out


def test_cli_inspect_node_human_output(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify human-readable format of inspect node output."""
    overview = _sample_overview()
    with (
        patch(
            "bitheim.infrastructure.compose.adapter.ComposeLifecycleAdapter.inspect_node",
            return_value=overview,
        ),
        patch("bitheim.interfaces.cli._is_container_execution_context", return_value=False),
    ):
        exit_code = main(["inspect", "node", "--node-id", "regtest-node-1"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Chain:                  regtest" in captured.out
        assert "Version:                310100 (/Satoshi:31.1.0/)" in captured.out
        assert "Blocks:                 200" in captured.out
        assert (
            "Best Block Hash:        "
            "0f9188f13cb7b2c71f2a335e3a4fc328bf5beb436012afca590b1a11466e2206" in captured.out
        )


def test_cli_inspect_node_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify JSON format of inspect node output."""
    overview = _sample_overview()
    with (
        patch(
            "bitheim.infrastructure.compose.adapter.ComposeLifecycleAdapter.inspect_node",
            return_value=overview,
        ),
        patch("bitheim.interfaces.cli._is_container_execution_context", return_value=False),
    ):
        exit_code = main(["inspect", "node", "--json"])
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["version"] == 310100
        assert data["chain"] == "regtest"
        assert data["blocks"] == 200
        assert data["network_active"] is True
        assert data["pruned"] is False


def test_cli_inspect_node_container_context(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Verify inspect node executes via BitcoinRpcClient when run inside container context."""
    overview = _sample_overview()
    cookie = tmp_path / ".cookie"
    cookie.write_text("__cookie__:secret", encoding="utf-8")

    with (
        patch.dict(
            os.environ,
            {
                "BITHEIM_EXECUTION_CONTEXT": "container",
            },
        ),
        patch(
            "bitheim.application.service.NodeObservationService.inspect_node",
            return_value=overview,
        ),
    ):
        exit_code = main(["inspect", "node", "--json"])
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["version"] == 310100


def test_cli_inspect_node_stopped_error(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify inspect node on stopped node fails with exit code 1 and clear error message."""
    with (
        patch(
            "bitheim.infrastructure.compose.adapter.ComposeLifecycleAdapter.inspect_node",
            side_effect=RpcUnavailableError(
                "Managed node 'regtest-node-1' is stopped. Start the node before inspecting."
            ),
        ),
        patch("bitheim.interfaces.cli._is_container_execution_context", return_value=False),
    ):
        exit_code = main(["inspect", "node", "--node-id", "regtest-node-1"])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "bitheim: error: Managed node 'regtest-node-1' is stopped" in captured.err


def test_cli_inspect_node_incompatible_error(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify inspect node on incompatible node reports error without traceback."""
    with (
        patch(
            "bitheim.infrastructure.compose.adapter.ComposeLifecycleAdapter.inspect_node",
            side_effect=RpcIncompatibleNodeError(
                "Incompatible Bitcoin Core version: got 310000, expected 310100"
            ),
        ),
        patch("bitheim.interfaces.cli._is_container_execution_context", return_value=False),
    ):
        exit_code = main(["inspect", "node"])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "bitheim: error: Incompatible Bitcoin Core version" in captured.err
        assert "Traceback" not in captured.err


def test_cli_doctor_rpc_check_running_node(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Verify doctor Check 6 executes RPC probe when node is running."""
    data_dir = tmp_path / "valid_data"
    overview = _sample_overview()
    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run") as mock_sub,
        patch(
            "bitheim.infrastructure.compose.adapter.ComposeLifecycleAdapter.get_lifecycle_state",
            return_value=NodeLifecycleState.HEALTHY,
        ),
        patch(
            "bitheim.infrastructure.compose.adapter.ComposeLifecycleAdapter.inspect_node",
            return_value=overview,
        ),
        patch("bitheim.interfaces.cli._is_container_execution_context", return_value=False),
    ):
        mock_sub.return_value = MagicMock(returncode=0, stdout="26.0.0\n")
        exit_code = main(["doctor", "--data-dir", str(data_dir)])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "[✓] Node RPC: authenticated read-only observation verified" in captured.out
