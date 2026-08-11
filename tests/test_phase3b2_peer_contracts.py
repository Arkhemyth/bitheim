"""Protected executable contracts for Phase 3B.2b peer observation.

These tests are defined before implementation. They remain expected failures
only while the complete public peer-observation surface is absent. Once that
surface exists, the same immutable contracts activate automatically.
"""

from __future__ import annotations

import dataclasses
import json
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import bitheim.application.ports as ports_module
import bitheim.application.service as service_module
import bitheim.domain.errors as errors_module
import bitheim.domain.node as node_module
from bitheim.infrastructure.bitcoin.rpc_client import (
    ALLOWED_RPC_METHODS,
    BitcoinRpcClient,
)
from bitheim.infrastructure.compose.adapter import ComposeLifecycleAdapter
from bitheim.interfaces.cli import build_parser, main

ENDPOINT = "10.42.0.7:18444"

PeerSummary: Any = getattr(node_module, "PeerSummary", None)
NodeObservationPort: Any = getattr(ports_module, "NodeObservationPort", None)
NodeObservationService: Any = getattr(service_module, "NodeObservationService", None)

_CAPABILITY_AVAILABLE = all(
    (
        PeerSummary is not None,
        NodeObservationPort is not None
        and callable(getattr(NodeObservationPort, "get_peers", None)),
        NodeObservationService is not None
        and callable(getattr(NodeObservationService, "inspect_peers", None)),
        callable(getattr(BitcoinRpcClient, "get_peers", None)),
        callable(getattr(ComposeLifecycleAdapter, "inspect_peers", None)),
    )
)

pytestmark = pytest.mark.xfail(
    not _CAPABILITY_AVAILABLE,
    reason="Phase 3B.2b peer-observation surface is intentionally not implemented yet",
    strict=True,
)


def _summary(**overrides: object) -> Any:
    values: dict[str, object] = {
        "peer_id": 7,
        "endpoint": ENDPOINT,
        "network": "not_publicly_routable",
        "inbound": False,
        "connection_type": "manual",
        "protocol_version": 70016,
        "subversion": "/Satoshi:31.1.0/",
        "synced_headers": 120,
        "synced_blocks": 119,
        "ping_time_seconds": 0.00125,
    }
    values.update(overrides)
    return PeerSummary(**values)


def _rpc_peer(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "id": 7,
        "addr": ENDPOINT,
        "network": "not_publicly_routable",
        "inbound": False,
        "connection_type": "manual",
        "version": 70016,
        "subver": "/Satoshi:31.1.0/",
        "synced_headers": 120,
        "synced_blocks": 119,
        "pingtime": Decimal("0.00125"),
    }
    values.update(overrides)
    return values


def _get_peers(client: BitcoinRpcClient) -> Any:
    return client.__getattribute__("get_peers")


def _inspect_peers(adapter: ComposeLifecycleAdapter) -> Any:
    return adapter.__getattribute__("inspect_peers")


def test_peer_summary_is_frozen_slotted_and_deterministic() -> None:
    summary = _summary()
    assert dataclasses.is_dataclass(type(summary))
    assert vars(type(summary))["__dataclass_params__"].frozen is True
    assert not hasattr(summary, "__dict__")
    assert summary.to_dict() == {
        "connection_type": "manual",
        "endpoint": ENDPOINT,
        "inbound": False,
        "network": "not_publicly_routable",
        "peer_id": 7,
        "ping_time_seconds": 0.00125,
        "protocol_version": 70016,
        "subversion": "/Satoshi:31.1.0/",
        "synced_blocks": 119,
        "synced_headers": 120,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("peer_id", -1),
        ("peer_id", True),
        ("endpoint", ""),
        ("endpoint", "x" * 513),
        ("endpoint", "private-\nendpoint"),
        ("network", ""),
        ("network", "x" * 513),
        ("network", "private-\nnetwork"),
        ("connection_type", ""),
        ("connection_type", "x" * 513),
        ("connection_type", "private-\nconnection"),
        ("protocol_version", -1),
        ("protocol_version", True),
        ("subversion", ""),
        ("subversion", "x" * 513),
        ("subversion", "private-\nsubversion"),
        ("synced_headers", -1),
        ("synced_headers", True),
        ("synced_blocks", -1),
        ("ping_time_seconds", -0.1),
        ("ping_time_seconds", float("nan")),
        ("ping_time_seconds", float("inf")),
        ("ping_time_seconds", True),
    ],
)
def test_peer_summary_rejects_invalid_or_unbounded_facts(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        _summary(**{field: value})


def test_peer_summary_allows_unknown_sync_and_missing_ping() -> None:
    summary = _summary(synced_headers=None, synced_blocks=None, ping_time_seconds=None)
    assert summary.synced_headers is None
    assert summary.synced_blocks is None
    assert summary.ping_time_seconds is None


def test_rpc_allowlist_adds_only_peer_read_method() -> None:
    assert "getpeerinfo" in ALLOWED_RPC_METHODS
    assert not ({"addnode", "disconnectnode", "setnetworkactive"} & ALLOWED_RPC_METHODS)


def test_rpc_peer_lookup_uses_one_bounded_read_request() -> None:
    client = BitcoinRpcClient()
    send = MagicMock(return_value=[_rpc_peer()])
    with patch.object(client, "_send_request", send):
        peers = _get_peers(client)(timeout=4.0)

    assert peers == (_summary(),)
    assert send.call_count == 1
    assert send.call_args.args[:2] == ("getpeerinfo", [])


def test_rpc_accepts_exact_collection_limit_and_sorts_by_peer_id() -> None:
    client = BitcoinRpcClient()
    raw_peers = [
        _rpc_peer(id=peer_id, addr=f"10.42.0.{peer_id % 250 + 1}:18444")
        for peer_id in reversed(range(256))
    ]
    with patch.object(client, "_send_request", return_value=raw_peers):
        peers = _get_peers(client)()

    assert len(peers) == 256
    assert tuple(peer.peer_id for peer in peers) == tuple(range(256))


def test_rpc_rejects_peer_collection_above_limit() -> None:
    client = BitcoinRpcClient()
    raw_peers = [_rpc_peer(id=peer_id) for peer_id in range(257)]
    with (
        patch.object(client, "_send_request", return_value=raw_peers),
        pytest.raises(errors_module.RpcMalformedResponseError),
    ):
        _get_peers(client)()


def test_rpc_rejects_non_collection_peer_result() -> None:
    client = BitcoinRpcClient()
    with (
        patch.object(client, "_send_request", return_value={"peers": []}),
        pytest.raises(errors_module.RpcMalformedResponseError),
    ):
        _get_peers(client)()


def test_rpc_rejects_duplicate_peer_ids() -> None:
    client = BitcoinRpcClient()
    with (
        patch.object(client, "_send_request", return_value=[_rpc_peer(), _rpc_peer()]),
        pytest.raises(errors_module.RpcMalformedResponseError),
    ):
        _get_peers(client)()


@pytest.mark.parametrize(
    "field",
    [
        "id",
        "addr",
        "network",
        "inbound",
        "connection_type",
        "version",
        "subver",
        "synced_headers",
        "synced_blocks",
    ],
)
def test_rpc_rejects_missing_required_peer_fields(field: str) -> None:
    client = BitcoinRpcClient()
    raw_peer = _rpc_peer()
    del raw_peer[field]
    with (
        patch.object(client, "_send_request", return_value=[raw_peer]),
        pytest.raises(errors_module.RpcMalformedResponseError),
    ):
        _get_peers(client)()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", -1),
        ("id", True),
        ("addr", ""),
        ("addr", "x" * 513),
        ("network", 3),
        ("network", ""),
        ("inbound", 0),
        ("connection_type", ""),
        ("version", -1),
        ("version", True),
        ("subver", "private-\nsubversion"),
        ("synced_headers", -2),
        ("synced_headers", True),
        ("synced_blocks", -2),
        ("pingtime", Decimal("-0.1")),
        ("pingtime", Decimal("NaN")),
        ("pingtime", Decimal("Infinity")),
        ("pingtime", 0.1),
        ("pingtime", True),
    ],
)
def test_rpc_rejects_malformed_peer_fields(field: str, value: object) -> None:
    client = BitcoinRpcClient()
    with (
        patch.object(client, "_send_request", return_value=[_rpc_peer(**{field: value})]),
        pytest.raises(errors_module.RpcMalformedResponseError),
    ):
        _get_peers(client)()


def test_rpc_maps_supported_unknown_sync_sentinels_to_none() -> None:
    client = BitcoinRpcClient()
    with patch.object(
        client,
        "_send_request",
        return_value=[_rpc_peer(synced_headers=-1, synced_blocks=-1)],
    ):
        peer = _get_peers(client)()[0]

    assert peer.synced_headers is None
    assert peer.synced_blocks is None


def test_rpc_allows_missing_optional_ping_and_ignores_deprecated_startingheight() -> None:
    client = BitcoinRpcClient()
    raw_peer = _rpc_peer(startingheight="private-deprecated-sentinel")
    del raw_peer["pingtime"]
    with patch.object(client, "_send_request", return_value=[raw_peer]):
        peer = _get_peers(client)()[0]

    assert peer.ping_time_seconds is None
    assert "starting_height" not in peer.to_dict()


def test_rpc_ignores_unknown_additive_peer_fields() -> None:
    client = BitcoinRpcClient()
    with patch.object(
        client,
        "_send_request",
        return_value=[_rpc_peer(future_additive_field="private-payload-sentinel")],
    ):
        assert _get_peers(client)() == (_summary(),)


def test_application_service_delegates_one_peer_lookup() -> None:
    port = MagicMock()
    port.get_peers.return_value = (_summary(),)
    service = NodeObservationService(port)

    result = service.inspect_peers(timeout=7.0)

    assert result == (_summary(),)
    port.get_peers.assert_called_once_with(timeout=7.0)


@pytest.mark.parametrize("timeout", [0, -1, True, float("nan"), float("inf"), 61])
def test_application_service_rejects_invalid_timeout_before_port(timeout: object) -> None:
    port = MagicMock()
    service = NodeObservationService(port)
    with pytest.raises(errors_module.RpcError):
        service.inspect_peers(timeout=timeout)
    port.get_peers.assert_not_called()


def test_cli_peers_parser_exposes_json_mode() -> None:
    parsed = build_parser().parse_args(["inspect", "peers", "--json"])
    assert parsed.inspect_command == "peers"
    assert parsed.json is True


def test_cli_peers_json_output_is_deterministic_object(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with (
        patch("bitheim.interfaces.cli._is_container_execution_context", return_value=False),
        patch(
            "bitheim.infrastructure.compose.adapter.ComposeLifecycleAdapter.inspect_peers",
            return_value=(_summary(),),
        ) as inspect_peers,
    ):
        exit_code = main(["inspect", "peers", "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert json.loads(captured.out) == {"peers": [_summary().to_dict()]}
    assert captured.out.endswith("\n")
    inspect_peers.assert_called_once()


def test_cli_peers_human_output_explicitly_contains_endpoint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with (
        patch("bitheim.interfaces.cli._is_container_execution_context", return_value=False),
        patch(
            "bitheim.infrastructure.compose.adapter.ComposeLifecycleAdapter.inspect_peers",
            return_value=(_summary(),),
        ),
    ):
        exit_code = main(["inspect", "peers"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Peer 7" in captured.out
    assert ENDPOINT in captured.out
    assert captured.err == ""


def test_cli_peers_empty_output_is_deterministic(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with (
        patch("bitheim.interfaces.cli._is_container_execution_context", return_value=False),
        patch(
            "bitheim.infrastructure.compose.adapter.ComposeLifecycleAdapter.inspect_peers",
            return_value=(),
        ),
    ):
        exit_code = main(["inspect", "peers", "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == {"peers": []}


def test_compose_peer_delegation_is_no_deps_and_non_mutating() -> None:
    adapter = ComposeLifecycleAdapter()
    completed = MagicMock(
        returncode=0,
        stdout=json.dumps({"peers": [_summary().to_dict()]}),
        stderr="",
    )

    with (
        patch.object(adapter, "_check_docker_runtime_available"),
        patch.object(adapter, "_get_lifecycle_state_deadline", return_value="healthy"),
        patch("subprocess.run", return_value=completed) as run,
    ):
        result = _inspect_peers(adapter)("test-node", timeout=10.0)

    command = run.call_args.args[0]
    assert result == (_summary(),)
    assert command[-3:] == ["inspect", "peers", "--json"]
    assert "--no-deps" in command
    assert not ({"up", "start", "restart", "create"} & set(command))


def test_compose_stopped_node_error_omits_node_id() -> None:
    adapter = ComposeLifecycleAdapter()
    sentinel = "private-peer-node-id-sentinel"
    with (
        patch.object(adapter, "_check_docker_runtime_available"),
        patch.object(adapter, "_get_lifecycle_state_deadline", return_value="stopped"),
        pytest.raises(errors_module.RpcUnavailableError) as caught,
    ):
        _inspect_peers(adapter)(sentinel, timeout=10.0)

    assert sentinel not in str(caught.value)


def test_peer_endpoint_never_enters_application_logs() -> None:
    port = MagicMock()
    port.get_peers.return_value = (_summary(),)
    service = NodeObservationService(port)
    with patch.object(service_module, "logger") as logger:
        assert service.inspect_peers() == (_summary(),)

    assert ENDPOINT not in repr(logger.method_calls)


def test_peer_endpoint_never_enters_errors_or_logs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    sentinel = "private-peer-endpoint-sentinel\n"
    client = BitcoinRpcClient()
    with (
        patch.object(client, "_send_request", return_value=[_rpc_peer(addr=sentinel)]),
        pytest.raises(errors_module.RpcMalformedResponseError) as caught,
    ):
        _get_peers(client)()

    captured = capsys.readouterr()
    observable = captured.out + captured.err + str(caught.value)
    assert "private-peer-endpoint-sentinel" not in observable
    assert caught.value.__cause__ is None


def test_ci_runs_real_peer_inspection_without_printing_payload() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "Integration test — delegated peer inspection" in workflow
    assert "bitheim inspect peers --json" in workflow
    assert 'echo "${PEERS_JSON}"' not in workflow
    assert "--no-deps" in workflow
