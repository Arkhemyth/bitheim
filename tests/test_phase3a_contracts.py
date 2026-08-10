"""Protected executable contracts for the Phase 3A observation boundary.

These tests define security and interoperability behavior before the
implementation is accepted. Implementations may add coverage, but must not
weaken, skip, delete, or rewrite these contracts to obtain a green build.
"""

from __future__ import annotations

import ast
import json
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from bitheim.domain.errors import (
    RpcAuthenticationError,
    RpcError,
    RpcIncompatibleNodeError,
    RpcMalformedResponseError,
    RpcProtocolError,
    RpcResponseSizeExceededError,
    RpcTimeoutError,
    RpcUnavailableError,
)
from bitheim.domain.node import NodeLifecycleState
from bitheim.infrastructure.bitcoin.rpc_client import (
    ALLOWED_RPC_HOSTS,
    DEFAULT_COOKIE_PATH,
    DEFAULT_RPC_HOST,
    DEFAULT_RPC_PORT,
    BitcoinRpcClient,
)
from bitheim.infrastructure.compose.adapter import ComposeLifecycleAdapter
from bitheim.interfaces.cli import _map_error_category, main

if TYPE_CHECKING:
    from collections.abc import Callable


class _Response:
    """Small response double with observable bounded reads."""

    def __init__(self, chunks: list[bytes], on_read: Callable[[], None] | None = None) -> None:
        self._chunks = iter(chunks)
        self._on_read = on_read

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, _size: int = -1) -> bytes:
        if self._on_read is not None:
            self._on_read()
        return next(self._chunks, b"")


class _DeadlineAwareResponse(_Response):
    """Response double requiring a remaining timeout before each blocking read."""

    def __init__(self, chunks: list[bytes]) -> None:
        super().__init__(chunks)
        self.applied_timeouts: list[float] = []
        self._timeout_applied = False

    def settimeout(self, timeout: float) -> None:
        assert 0 < timeout <= 1.0
        self.applied_timeouts.append(timeout)
        self._timeout_applied = True

    def read(self, size: int = -1) -> bytes:
        assert self._timeout_applied, "blocking read started without a remaining deadline timeout"
        self._timeout_applied = False
        return super().read(size)


def _rpc_envelope(*, result: object, error: object, request_id: str) -> bytes:
    return json.dumps({"result": result, "error": error, "id": request_id}).encode("utf-8")


def _secure_cookie(path: Path) -> Path:
    path.write_text("__cookie__:contract-secret", encoding="utf-8")
    path.chmod(0o640)
    return path


def _client_with_test_cookie(cookie: Path) -> BitcoinRpcClient:
    """Provide a filesystem seam without relaxing the production constructor."""
    client = BitcoinRpcClient()
    client._cookie_path = cookie
    return client


def test_runtime_rpc_authority_is_one_exact_endpoint() -> None:
    assert DEFAULT_RPC_HOST == "bitcoin-core"
    assert DEFAULT_RPC_PORT == 18443
    assert Path("/data/rpc/.cookie") == DEFAULT_COOKIE_PATH
    assert frozenset({DEFAULT_RPC_HOST}) == ALLOWED_RPC_HOSTS


@pytest.mark.parametrize(
    ("construct", "sentinel"),
    [
        (lambda: BitcoinRpcClient(rpc_host="127.0.0.1"), "127.0.0.1"),
        (lambda: BitcoinRpcClient(rpc_host="localhost"), "localhost"),
        (lambda: BitcoinRpcClient(rpc_port=8332), "8332"),
        (
            lambda: BitcoinRpcClient(cookie_path="/private/user/cookie"),
            "/private/user/cookie",
        ),
    ],
)
def test_alternate_rpc_authority_is_rejected_without_echo(
    construct: Callable[[], BitcoinRpcClient], sentinel: str
) -> None:
    with pytest.raises(RpcError) as caught:
        construct()
    assert sentinel not in str(caught.value)
    assert caught.value.__cause__ is None


def test_disallowed_method_is_rejected_before_credentials_or_network() -> None:
    client = BitcoinRpcClient()
    credential_read = MagicMock()
    network_open = MagicMock()
    client._opener = network_open

    sentinel_method = "sendtoaddress-private-sentinel"
    with (
        patch.object(client, "_read_cookie_header", credential_read),
        pytest.raises(RpcError) as caught,
    ):
        client._send_request(sentinel_method, [], "contract-1", time.monotonic() + 1.0)

    credential_read.assert_not_called()
    network_open.assert_not_called()
    assert sentinel_method not in str(caught.value)


@pytest.mark.parametrize("mode", [0o641, 0o644, 0o650, 0o660, 0o670])
def test_cookie_rejects_permissions_beyond_required_group_read(tmp_path: Path, mode: int) -> None:
    cookie = _secure_cookie(tmp_path / ".cookie")
    cookie.chmod(mode)
    client = _client_with_test_cookie(cookie)
    with pytest.raises(RpcAuthenticationError):
        client._read_cookie_header()


def test_cookie_accepts_exact_runtime_mode(tmp_path: Path) -> None:
    cookie = _secure_cookie(tmp_path / ".cookie")
    client = _client_with_test_cookie(cookie)
    assert client._read_cookie_header().startswith("Basic ")


def test_cookie_replacement_race_fails_closed(tmp_path: Path) -> None:
    cookie = _secure_cookie(tmp_path / ".cookie")
    client = _client_with_test_cookie(cookie)
    real_fstat = __import__("os").fstat

    def mismatched_fstat(fd: int) -> Any:
        observed = real_fstat(fd)
        values = list(observed)
        values[1] = observed.st_ino + 1
        return __import__("os").stat_result(values)

    with (
        patch("os.fstat", side_effect=mismatched_fstat),
        pytest.raises(RpcAuthenticationError) as caught,
    ):
        client._read_cookie_header()
    assert caught.value.__cause__ is None


def test_response_read_that_exhausts_deadline_is_timeout_not_success() -> None:
    client = BitcoinRpcClient()
    clock = [100.0]

    def monotonic() -> float:
        return clock[0]

    response = _Response(
        [_rpc_envelope(result={}, error=None, request_id="contract-1"), b""],
        on_read=lambda: clock.__setitem__(0, clock[0] + 0.6),
    )
    with (
        patch("bitheim.infrastructure.bitcoin.rpc_client.time.monotonic", side_effect=monotonic),
        pytest.raises(RpcTimeoutError),
    ):
        client._read_and_parse_envelope(response, "contract-1", deadline=101.0)


def test_remaining_timeout_is_applied_before_every_blocking_read() -> None:
    client = BitcoinRpcClient()
    response = _DeadlineAwareResponse(
        [_rpc_envelope(result={}, error=None, request_id="contract-1"), b""]
    )
    client._read_and_parse_envelope(response, "contract-1", time.monotonic() + 1.0)
    assert len(response.applied_timeouts) == 2
    assert response.applied_timeouts[1] <= response.applied_timeouts[0]


def test_second_rpc_receives_only_remaining_deadline_budget(tmp_path: Path) -> None:
    cookie = _secure_cookie(tmp_path / ".cookie")
    client = _client_with_test_cookie(cookie)
    clock = [10.0]
    observed_timeouts: list[float] = []

    network = {
        "version": 310100,
        "subversion": "/Satoshi:31.1.0/",
        "networkactive": True,
        "connections": 0,
    }
    chain = {
        "chain": "regtest",
        "blocks": 0,
        "headers": 0,
        "bestblockhash": "0" * 64,
        "mediantime": 0,
        "initialblockdownload": True,
        "pruned": False,
    }

    def open_request(request: Any, timeout: float) -> _Response:
        observed_timeouts.append(timeout)
        payload = json.loads(request.data.decode("utf-8"))
        result = network if payload["method"] == "getnetworkinfo" else chain
        clock[0] += 2.0
        return _Response([_rpc_envelope(result=result, error=None, request_id=payload["id"]), b""])

    opener = MagicMock()
    opener.open.side_effect = open_request
    client._opener = opener
    with patch(
        "bitheim.infrastructure.bitcoin.rpc_client.time.monotonic", side_effect=lambda: clock[0]
    ):
        client.get_node_overview(timeout=10.0)

    assert observed_timeouts[0] == pytest.approx(10.0)
    assert observed_timeouts[1] == pytest.approx(8.0)


@pytest.mark.parametrize(
    "payload",
    [
        b'{"result": {}, "result": {}, "error": null, "id": "contract-1"}',
        _rpc_envelope(result={}, error={"code": -1}, request_id="contract-1"),
        _rpc_envelope(result=None, error=None, request_id="contract-1"),
        _rpc_envelope(result=None, error={"code": True}, request_id="contract-1"),
        _rpc_envelope(result=None, error={"code": "-28"}, request_id="contract-1"),
        _rpc_envelope(result={}, error=None, request_id="wrong-id"),
    ],
)
def test_success_and_http_error_bodies_share_strict_envelope_validation(payload: bytes) -> None:
    client = BitcoinRpcClient()
    response = _Response([payload, b""])
    with pytest.raises((RpcMalformedResponseError, RpcError)):
        client._read_and_parse_envelope(response, "contract-1", time.monotonic() + 1.0)


def test_host_cli_error_does_not_emit_internal_child_envelope(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["status", "--config", "/missing/private-contract.toml"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert '"schema":"bitheim.delegated-error"' not in captured.err
    assert "bitheim: error:" in captured.err


def test_container_child_error_uses_versioned_categorical_envelope(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with patch.dict("os.environ", {"BITHEIM_EXECUTION_CONTEXT": "container"}):
        exit_code = main(["status", "--config", "/missing/private-contract.toml"])
    captured = capsys.readouterr()
    assert exit_code == 1
    first_line = captured.err.splitlines()[0]
    envelope = json.loads(first_line)
    assert envelope == {
        "schema": "bitheim.delegated-error",
        "version": 1,
        "category": "configuration",
    }


@pytest.mark.parametrize(
    "stderr",
    [
        '{"error_type":"RpcAuthenticationError"}\n',
        '{"error_type":"RpcAuthenticationError","extra":"forged"}\n',
        '{"error_type":"RpcAuthenticationError"}\n{"error_type":"RpcTimeoutError"}\n',
        'prefix {"error_type":"RpcAuthenticationError"}\n',
        "bitheim: error: Incompatible Bitcoin Core version: private-sentinel\n",
        "x" * 16385,
    ],
)
def test_delegated_error_parser_rejects_forged_or_ambiguous_envelopes(stderr: str) -> None:
    adapter = ComposeLifecycleAdapter()

    def run(command: list[str], **_kwargs: object) -> MagicMock:
        result = MagicMock(returncode=0, stdout="", stderr="")
        if "info" in command:
            result.stdout = "26.0.0\n"
        elif "ps" in command:
            result.stdout = json.dumps([{"Service": "bitcoin-core", "State": "running"}])
        elif "run" in command:
            result.returncode = 1
            result.stderr = stderr
        return result

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", side_effect=run),
        pytest.raises(RpcUnavailableError),
    ):
        adapter.inspect_node("contract-node")


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (RpcAuthenticationError("sentinel"), "authentication"),
        (RpcIncompatibleNodeError("sentinel"), "incompatible"),
        (RpcTimeoutError("sentinel"), "timeout"),
        (RpcUnavailableError("sentinel"), "unavailable"),
        (RpcMalformedResponseError("sentinel"), "malformed_response"),
        (RpcProtocolError("sentinel"), "malformed_response"),
        (RpcResponseSizeExceededError("sentinel"), "malformed_response"),
        (RuntimeError("private-class-sentinel"), "unexpected"),
    ],
)
def test_delegated_error_categories_are_closed_and_do_not_expose_class_names(
    error: Exception, category: str
) -> None:
    assert _map_error_category(error) == category


def test_doctor_unknown_state_is_failure_not_stopped(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="26.0.0\n")),
        patch(
            "bitheim.interfaces.cli.ComposeLifecycleAdapter.get_lifecycle_state",
            return_value=NodeLifecycleState.UNKNOWN,
        ),
    ):
        exit_code = main(["doctor", "--data-dir", str(tmp_path / "data")])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "state is unknown" in captured.err
    assert "stopped" not in captured.err


def test_doctor_runtime_failure_is_not_reported_as_stopped(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="26.0.0\n")),
        patch(
            "bitheim.interfaces.cli.ComposeLifecycleAdapter.get_lifecycle_state",
            side_effect=RpcUnavailableError("private-runtime-sentinel"),
        ),
    ):
        exit_code = main(["doctor", "--data-dir", str(tmp_path / "data")])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "failed to determine node state" in captured.err
    assert "stopped" not in captured.err
    assert "private-runtime-sentinel" not in captured.err


def test_ci_contract_does_not_print_observation_payload_and_checks_stopped_behavior() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert 'echo "${INSPECT_JSON}" | jq .' not in workflow
    assert "inspect-stopped" in workflow
    assert "--no-deps" in workflow
    assert "must not start bitcoin-core" in workflow
    assert "POST_INSPECT_STATE=" in workflow
    assert 'test -z "${POST_INSPECT_STATE}"' in workflow


def test_release_plan_records_phase_3a_and_phase_3b_boundary() -> None:
    plan = Path("docs/releases/v0.2.0-plan.md").read_text(encoding="utf-8")
    assert "Phase 3A" in plan
    assert "Phase 3B" in plan
    assert "block, mempool, and peer" in plan
    phase_3a = plan.split("### Phase 3A", 1)[1].split("### Phase 3B", 1)[0]
    phase_3b = plan.split("### Phase 3B", 1)[1].split("### Phase 4", 1)[0]
    assert "node and chain overview" in phase_3a
    assert "validate JSON-RPC response" in phase_3a
    assert "human-readable and deterministic JSON" in phase_3a
    assert "block, mempool, and peer" in phase_3b


def test_project_status_keeps_phase_number_and_names_active_subincrement() -> None:
    status = Path("docs/PROJECT_STATUS.md").read_text(encoding="utf-8")
    assert "Phase 3 of 6 — Secure RPC and Read-Only Observation" in status
    assert "Phase 3A" in status.split("## Active Increment", 1)[1]
    assert "Phase 3A of 6" not in status


def test_historical_test_inventory_is_not_reduced() -> None:
    protected = {
        "tests/test_cli.py",
        "tests/test_compose_adapter.py",
        "tests/test_leak_prevention.py",
        "tests/test_logging.py",
    }
    for path in protected:
        baseline = subprocess.run(
            ["git", "show", f"main:{path}"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        current = Path(path).read_text(encoding="utf-8")
        baseline_tests = {
            node.name
            for node in ast.walk(ast.parse(baseline))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        }
        current_tests = {
            node.name
            for node in ast.walk(ast.parse(current))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        }
        assert baseline_tests <= current_tests, f"historical tests removed from {path}"
