"""Unit tests for Docker Compose adapter lifecycle operations and health inspection."""

import json
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from bitheim.domain.errors import (
    LifecycleError,
    RpcIncompatibleNodeError,
    RpcMalformedResponseError,
    RpcUnavailableError,
    RuntimeUnavailableError,
)
from bitheim.domain.node import NodeLifecycleState
from bitheim.infrastructure.compose.adapter import ComposeLifecycleAdapter


def test_compose_adapter_docker_unavailable() -> None:
    """Verify that adapter fails fast with RuntimeUnavailableError when docker is not installed."""
    adapter = ComposeLifecycleAdapter()
    with (
        patch("shutil.which", return_value=None),
        pytest.raises(RuntimeUnavailableError, match="not found in PATH"),
    ):
        adapter.start("test-node")


def test_compose_adapter_docker_daemon_down() -> None:
    """Verify that adapter fails fast when docker daemon is unreachable."""
    adapter = ComposeLifecycleAdapter()
    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", return_value=MagicMock(returncode=1)),
        pytest.raises(RuntimeUnavailableError, match="not running or accessible"),
    ):
        adapter.start("test-node")


def test_compose_adapter_start_success() -> None:
    """Verify start executes compose up with project name and bitcoin-core target."""
    adapter = ComposeLifecycleAdapter()

    calls: list[list[str]] = []

    def mock_sub_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        calls.append(cmd)
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        if "network" in cmd and "ls" in cmd:
            res.stdout = ""
        elif "image" in cmd and "inspect" in cmd:
            res.stdout = "{}"
        elif "ps" in cmd:
            res.stdout = json.dumps(
                [{"Service": "bitcoin-core", "State": "running", "Health": "healthy"}]
            )
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=mock_sub_run),
    ):
        adapter.start("test-node", timeout=15.0)

    up_call = next(c for c in calls if "up" in c)
    assert "--project-name" in up_call
    assert "test-node" in up_call
    assert "bitcoin-core" in up_call


def test_compose_adapter_start_ensures_both_images() -> None:
    """Verify start checks availability of both Bitcoin Core and Bitheim images."""
    adapter = ComposeLifecycleAdapter()

    inspected_images: list[str] = []

    def mock_sub_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        if "image" in cmd and "inspect" in cmd:
            inspected_images.append(cmd[-1])
        elif ("network" in cmd and "ls" in cmd) or "ps" in cmd:
            res.stdout = ""
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=mock_sub_run),
    ):
        adapter.start("test-node", timeout=15.0)

    # Both images must have been inspected
    assert "bitheim-bitcoin-core:31.1" in inspected_images
    assert "bitheim:local" in inspected_images


def test_compose_adapter_stop_success() -> None:
    """Verify stop executes compose stop with graceful timeout derived from remaining budget."""
    adapter = ComposeLifecycleAdapter()

    calls: list[list[str]] = []

    def mock_sub_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        calls.append(cmd)
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        if "ps" in cmd:
            if any("stop" in c for c in calls):
                res.stdout = ""
            else:
                res.stdout = json.dumps([{"Service": "bitcoin-core", "State": "running"}])
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=mock_sub_run),
    ):
        adapter.stop("test-node", timeout=10.0)

    stop_call = next(c for c in calls if "stop" in c)
    assert "--project-name" in stop_call
    assert "test-node" in stop_call
    assert "-t" in stop_call
    t_idx = stop_call.index("-t")
    grace_str = stop_call[t_idx + 1]
    assert int(grace_str) >= 1


def test_compose_adapter_stop_subprocess_timeout_within_budget() -> None:
    """Verify stop passes subprocess timeout <= remaining budget, never budget + 5."""
    adapter = ComposeLifecycleAdapter()
    recorded_timeouts: list[float] = []

    def mock_sub_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        if "timeout" in kwargs:
            recorded_timeouts.append(kwargs["timeout"])
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        if "ps" in cmd:
            if any(t <= 0 for t in recorded_timeouts):
                res.stdout = ""
            elif len(recorded_timeouts) <= 3:
                res.stdout = json.dumps([{"Service": "bitcoin-core", "State": "running"}])
            else:
                res.stdout = ""
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=mock_sub_run),
    ):
        adapter.stop("test-node", timeout=8.0)

    # Every recorded subprocess timeout must be <= 8.0
    for t in recorded_timeouts:
        assert t <= 8.0, f"subprocess timeout {t} exceeds caller budget of 8.0"


def test_compose_adapter_probe_health_healthy() -> None:
    """Verify probe_health delegates through bitheim service and returns HEALTHY."""
    adapter = ComposeLifecycleAdapter()

    healthy_response = json.dumps(
        {
            "node_id": "test-node",
            "state": "healthy",
            "health": {
                "state": "healthy",
                "chain": "regtest",
                "version": 310100,
                "blocks": 0,
                "headers": 0,
                "details": "ready",
            },
        }
    )

    def mock_sub_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        if "ps" in cmd:
            res.stdout = json.dumps([{"Service": "bitcoin-core", "State": "running"}])
        elif "run" in cmd and "bitheim" in cmd:
            res.stdout = healthy_response
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=mock_sub_run),
    ):
        health = adapter.probe_health("test-node")

    assert health.state == NodeLifecycleState.HEALTHY
    assert health.chain == "regtest"
    assert health.version == 310100


def test_compose_adapter_probe_health_incompatible_version() -> None:
    """Verify probe_health returns INCOMPATIBLE when delegated probe reports wrong version."""
    adapter = ComposeLifecycleAdapter()

    incompatible_response = json.dumps(
        {
            "node_id": "test-node",
            "state": "incompatible",
            "health": {
                "state": "incompatible",
                "chain": "regtest",
                "version": 280100,
                "blocks": 0,
                "headers": 0,
                "details": "incompatible_version",
            },
        }
    )

    def mock_sub_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        if "ps" in cmd:
            res.stdout = json.dumps([{"Service": "bitcoin-core", "State": "running"}])
        elif "run" in cmd and "bitheim" in cmd:
            res.stdout = incompatible_response
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=mock_sub_run),
    ):
        health = adapter.probe_health("test-node")

    assert health.state == NodeLifecycleState.INCOMPATIBLE
    assert health.details == "incompatible_version"


def test_compose_adapter_probe_delegates_through_bitheim_service() -> None:
    """Verify probe_health uses 'compose run --no-deps bitheim' boundary, not 'compose exec'."""
    adapter = ComposeLifecycleAdapter()
    calls: list[list[str]] = []

    def mock_sub_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        calls.append(cmd)
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        if "ps" in cmd:
            res.stdout = json.dumps([{"Service": "bitcoin-core", "State": "running"}])
        elif "run" in cmd:
            res.stdout = json.dumps(
                {
                    "node_id": "test-node",
                    "state": "healthy",
                    "health": {
                        "state": "healthy",
                        "chain": "regtest",
                        "version": 310100,
                        "details": "ready",
                    },
                }
            )
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=mock_sub_run),
    ):
        adapter.probe_health("test-node")

    run_calls = [c for c in calls if "run" in c]
    assert len(run_calls) == 1
    run_cmd = run_calls[0]
    assert "--no-deps" in run_cmd
    assert "--rm" in run_cmd
    assert "bitheim" in run_cmd
    assert "status" in run_cmd
    assert "--json" in run_cmd
    assert "exec" not in run_cmd
    assert "bitcoin-cli" not in run_cmd


def test_compose_adapter_get_lifecycle_state_unknown_for_unexpected_state() -> None:
    """Verify get_lifecycle_state returns UNKNOWN for unrecognized container states."""
    adapter = ComposeLifecycleAdapter()

    def mock_sub_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        if "ps" in cmd:
            res.stdout = json.dumps([{"Service": "bitcoin-core", "State": "restarting"}])
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=mock_sub_run),
    ):
        state = adapter.get_lifecycle_state("test-node")

    assert state == NodeLifecycleState.UNKNOWN


def test_compose_adapter_get_lifecycle_state_unknown_when_bitcoin_core_absent() -> None:
    """F3: Non-empty output with only unexpected services must be UNKNOWN, not STOPPED."""
    adapter = ComposeLifecycleAdapter()

    def mock_sub_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        if "ps" in cmd:
            # Containers exist but bitcoin-core is not among them
            res.stdout = json.dumps([{"Service": "bitheim", "State": "exited"}])
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=mock_sub_run),
    ):
        state = adapter.get_lifecycle_state("test-node")

    assert state == NodeLifecycleState.UNKNOWN


def test_compose_adapter_subnet_collision_inspect_failure_fails_closed() -> None:
    """Verify subnet collision check fails closed when network inspect returns error."""
    adapter = ComposeLifecycleAdapter()

    def mock_sub_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        res = MagicMock()
        res.stderr = ""
        if "info" in cmd:
            res.returncode = 0
            res.stdout = "26.0.0"
        elif "network" in cmd and "ls" in cmd:
            res.returncode = 0
            res.stdout = "bridge\nhost\n"
        elif "network" in cmd and "inspect" in cmd:
            res.returncode = 1
            res.stderr = "Error: No such network"
        elif "image" in cmd and "inspect" in cmd:
            res.returncode = 0
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=mock_sub_run),
        pytest.raises(RuntimeUnavailableError, match="Failed to inspect Docker network"),
    ):
        adapter.start("test-node", timeout=15.0)


def test_compose_adapter_subnet_collision_malformed_subnet_fails_closed() -> None:
    """Verify subnet collision check fails closed on malformed existing subnet."""
    adapter = ComposeLifecycleAdapter()

    def mock_sub_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        res = MagicMock()
        res.stderr = ""
        if "info" in cmd:
            res.returncode = 0
            res.stdout = "26.0.0"
        elif "network" in cmd and "ls" in cmd:
            res.returncode = 0
            res.stdout = "external-net\n"
        elif "network" in cmd and "inspect" in cmd:
            res.returncode = 0
            res.stdout = "not-a-valid-cidr"
        elif "image" in cmd and "inspect" in cmd:
            res.returncode = 0
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=mock_sub_run),
        pytest.raises(LifecycleError, match="Malformed subnet"),
    ):
        adapter.start("test-node", timeout=15.0)


def test_compose_adapter_get_status_preserves_unknown() -> None:
    """Verify get_status preserves UNKNOWN from runtime state, not collapsing it."""
    adapter = ComposeLifecycleAdapter()

    def mock_sub_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        if "ps" in cmd:
            res.stdout = json.dumps([{"Service": "bitcoin-core", "State": "paused"}])
        elif "run" in cmd:
            res.stdout = json.dumps(
                {
                    "health": {
                        "state": "healthy",
                        "chain": "regtest",
                        "version": 310100,
                        "details": "ready",
                    }
                }
            )
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=mock_sub_run),
    ):
        status = adapter.get_status("test-node")

    assert status.state == NodeLifecycleState.UNKNOWN


def test_compose_adapter_image_inspect_daemon_failure_fails_closed() -> None:
    """F4: image inspect non-not-found error must fail closed, not fall through to build."""
    adapter = ComposeLifecycleAdapter()

    def mock_sub_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        res = MagicMock()
        if "info" in cmd:
            res.returncode = 0
            res.stdout = "26.0.0"
        elif "network" in cmd and "ls" in cmd:
            res.returncode = 0
            res.stdout = ""
        elif "image" in cmd and "inspect" in cmd:
            # Permission/daemon failure — NOT a clean "no such image"
            res.returncode = 1
            res.stderr = "Error response from daemon: permission denied"
        else:
            res.returncode = 0
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=mock_sub_run),
        pytest.raises(RuntimeUnavailableError, match="unexpected error"),
    ):
        adapter.start("test-node", timeout=15.0)


def test_compose_adapter_probe_health_forged_healthy_wrong_chain_rejected() -> None:
    """F7: Forged delegated JSON claiming HEALTHY but wrong chain must be INCOMPATIBLE."""
    adapter = ComposeLifecycleAdapter()

    forged_response = json.dumps(
        {
            "health": {
                "state": "healthy",
                "chain": "mainnet",
                "version": 310100,
                "details": "ready",
            }
        }
    )

    def mock_sub_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        if "ps" in cmd:
            res.stdout = json.dumps([{"Service": "bitcoin-core", "State": "running"}])
        elif "run" in cmd:
            res.stdout = forged_response
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=mock_sub_run),
    ):
        health = adapter.probe_health("test-node")

    assert health.state == NodeLifecycleState.INCOMPATIBLE


def test_compose_adapter_probe_health_forged_healthy_wrong_version_rejected() -> None:
    """F7: Forged delegated JSON claiming HEALTHY but wrong version must be INCOMPATIBLE."""
    adapter = ComposeLifecycleAdapter()

    forged_response = json.dumps(
        {
            "health": {
                "state": "healthy",
                "chain": "regtest",
                "version": 999999,
                "details": "ready",
            }
        }
    )

    def mock_sub_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        if "ps" in cmd:
            res.stdout = json.dumps([{"Service": "bitcoin-core", "State": "running"}])
        elif "run" in cmd:
            res.stdout = forged_response
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=mock_sub_run),
    ):
        health = adapter.probe_health("test-node")

    assert health.state == NodeLifecycleState.INCOMPATIBLE
    assert health.details == "delegated_contract_mismatch"


def test_compose_adapter_probe_health_forged_healthy_missing_chain_rejected() -> None:
    """F7: Forged HEALTHY with missing chain (None) must not be accepted as healthy."""
    adapter = ComposeLifecycleAdapter()

    forged_response = json.dumps(
        {
            "health": {
                "state": "healthy",
                "version": 310100,
                "details": "ready",
            }
        }
    )

    def mock_sub_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        if "ps" in cmd:
            res.stdout = json.dumps([{"Service": "bitcoin-core", "State": "running"}])
        elif "run" in cmd:
            res.stdout = forged_response
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=mock_sub_run),
    ):
        health = adapter.probe_health("test-node")

    assert health.state != NodeLifecycleState.HEALTHY


def test_compose_adapter_probe_health_does_not_raise_startup_timeout() -> None:
    """F8: probe_health is read-only and must return UNKNOWN, not raise StartupTimeoutError."""
    adapter = ComposeLifecycleAdapter()

    def mock_sub_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        if "ps" in cmd:
            res.stdout = json.dumps([{"Service": "bitcoin-core", "State": "running"}])
        elif "run" in cmd:
            raise TimeoutError("deliberate timeout")
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=mock_sub_run),
    ):
        # Must not raise — returns UNKNOWN instead
        health = adapter.probe_health("test-node", timeout=0.1)

    assert health.state in (NodeLifecycleState.UNKNOWN, NodeLifecycleState.STOPPED)


def test_compose_adapter_deadline_cumulative_budget() -> None:
    """F2: Prove cumulative calls cannot exceed the original budget.

    Records wall-clock timestamps of every subprocess call and verifies all
    stay within the caller's original timeout window.
    """
    adapter = ComposeLifecycleAdapter()
    start_time = time.monotonic()
    budget = 5.0

    def mock_sub_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        elapsed = time.monotonic() - start_time
        assert elapsed <= budget + 0.5, (
            f"subprocess call at {elapsed:.2f}s exceeds budget {budget}s"
        )
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        if "network" in cmd and "ls" in cmd:
            res.stdout = "net1\nnet2\nnet3\n"
        elif "network" in cmd and "inspect" in cmd:
            res.stdout = "192.168.0.0/24"
        elif "image" in cmd and "inspect" in cmd:
            res.stdout = "{}"
        elif "ps" in cmd:
            res.stdout = ""
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=mock_sub_run),
    ):
        adapter.start("test-node", timeout=budget)


def test_compose_adapter_inspect_node_success() -> None:
    """Verify delegated inspect_node invokes one-shot bitheim inspect node."""
    adapter = ComposeLifecycleAdapter()
    calls: list[list[str]] = []

    def mock_sub_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        calls.append(cmd)
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        if "info" in cmd:
            res.stdout = "26.0.0\n"
        elif "ps" in cmd:
            res.stdout = json.dumps([{"Service": "bitcoin-core", "State": "running"}])
        elif "run" in cmd:
            payload = {
                "version": 310100,
                "subversion": "/Satoshi:31.1.0/",
                "protocol_version": 70016,
                "network_active": True,
                "connections": 8,
                "chain": "regtest",
                "blocks": 100,
                "headers": 100,
                "best_block_hash": (
                    "0f9188f13cb7b2c71f2a335e3a4fc328bf5beb436012afca590b1a11466e2206"
                ),
                "median_time": 1296688602,
                "initial_block_download": False,
                "pruned": False,
                "chainwork": "0000000000000000000000000000000000000000000000000000000000000002",
            }
            res.stdout = json.dumps(payload)
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=mock_sub_run),
    ):
        overview = adapter.inspect_node("test-node", timeout=10.0)

    assert overview.version == 310100
    assert overview.chain == "regtest"
    assert overview.blocks == 100

    run_call = next(c for c in calls if "run" in c)
    assert "--rm" in run_call
    assert "--no-deps" in run_call
    assert "-T" in run_call
    assert "bitheim" in run_call
    assert "inspect" in run_call
    assert "node" in run_call
    assert "--json" in run_call


def test_compose_adapter_inspect_node_stopped_raises_error() -> None:
    """Verify inspect_node on stopped node raises RpcUnavailableError."""
    adapter = ComposeLifecycleAdapter()

    def mock_sub_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        if "info" in cmd:
            res.stdout = "26.0.0\n"
        elif "ps" in cmd:
            res.stdout = ""  # No running containers -> STOPPED
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=mock_sub_run),
    ):
        with pytest.raises(RpcUnavailableError) as exc_info:
            adapter.inspect_node("test-node", timeout=10.0)
        assert "stopped" in str(exc_info.value)


def test_compose_adapter_inspect_node_incompatible_error() -> None:
    """Verify delegated inspection with incompatible stderr raises RpcIncompatibleNodeError."""
    adapter = ComposeLifecycleAdapter()

    def mock_sub_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        res = MagicMock()
        if "info" in cmd:
            res.returncode = 0
            res.stdout = "26.0.0\n"
        elif "ps" in cmd:
            res.returncode = 0
            res.stdout = json.dumps([{"Service": "bitcoin-core", "State": "running"}])
        elif "run" in cmd:
            res.returncode = 1
            res.stderr = (
                json.dumps(
                    {
                        "schema": "bitheim.delegated-error",
                        "version": 1,
                        "category": "incompatible",
                    }
                )
                + "\nbitheim: error: Incompatible Bitcoin Core version: "
                + "got 310000, expected 310100\n"
            )
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=mock_sub_run),
        pytest.raises(RpcIncompatibleNodeError),
    ):
        adapter.inspect_node("test-node")


def test_compose_adapter_inspect_node_adversarial_malformed_type() -> None:
    """Verify that type coercion is rejected (string for int, bool for int, etc)."""
    adapter = ComposeLifecycleAdapter()

    def mock_sub_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        if "info" in cmd:
            res.stdout = "26.0.0\n"
        elif "ps" in cmd:
            res.stdout = json.dumps([{"Service": "bitcoin-core", "State": "running"}])
        elif "run" in cmd:
            payload = {
                "version": "310100",  # String instead of int
                "subversion": "/Satoshi:31.1.0/",
                "network_active": True,
                "connections": 8,
                "chain": "regtest",
                "blocks": 100,
                "headers": 100,
                "best_block_hash": (
                    "0f9188f13cb7b2c71f2a335e3a4fc328bf5beb436012afca590b1a11466e2206"
                ),
                "median_time": 1296688602,
                "initial_block_download": False,
                "pruned": False,
                "chainwork": "0000000000000000000000000000000000000000000000000000000000000002",
            }
            res.stdout = json.dumps(payload)
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=mock_sub_run),
        pytest.raises(RpcMalformedResponseError),
    ):
        adapter.inspect_node("test-node")


def test_compose_adapter_inspect_node_adversarial_duplicate_keys() -> None:
    """Verify duplicate JSON keys in delegated output are rejected."""
    adapter = ComposeLifecycleAdapter()

    def mock_sub_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        if "info" in cmd:
            res.stdout = "26.0.0\n"
        elif "ps" in cmd:
            res.stdout = json.dumps([{"Service": "bitcoin-core", "State": "running"}])
        elif "run" in cmd:
            res.stdout = (
                '{"version": 310100, "version": 310100, "subversion": "/Satoshi:31.1.0/", '
                '"network_active": true, "connections": 8, "chain": "regtest", "blocks": 100, '
                '"headers": 100, '
                '"best_block_hash": '
                '"0f9188f13cb7b2c71f2a335e3a4fc328bf5beb436012afca590b1a11466e2206", '
                '"median_time": 1296688602, "initial_block_download": false, "pruned": false, '
                '"chainwork": "0000000000000000000000000000000000000000000000000000000000000002"}'
            )
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=mock_sub_run),
        pytest.raises(RpcMalformedResponseError),
    ):
        adapter.inspect_node("test-node")
