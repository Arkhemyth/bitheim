"""Protected executable contracts for Phase 3B.1 block inspection.

These tests are defined before implementation. They remain expected failures
only while the complete public block-inspection surface is absent. Once that
surface exists, the same immutable contracts activate automatically.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import bitheim.application.ports as ports_module
import bitheim.application.service as service_module
import bitheim.domain.errors as errors_module
import bitheim.domain.node as node_module
import bitheim.interfaces.cli as cli_module
from bitheim.infrastructure.bitcoin.rpc_client import (
    ALLOWED_RPC_METHODS,
    BitcoinRpcClient,
)
from bitheim.infrastructure.compose.adapter import ComposeLifecycleAdapter
from bitheim.interfaces.cli import build_parser, main

BLOCK_HASH = "0" * 63 + "1"
PREVIOUS_BLOCK_HASH = "0" * 64
NEXT_BLOCK_HASH = "f" * 64

BlockSummary: Any = getattr(node_module, "BlockSummary", None)
RpcResourceNotFoundError: Any = getattr(errors_module, "RpcResourceNotFoundError", None)
NodeObservationPort: Any = getattr(ports_module, "NodeObservationPort", None)
NodeObservationService: Any = getattr(service_module, "NodeObservationService", None)

_CAPABILITY_AVAILABLE = all(
    (
        BlockSummary is not None,
        RpcResourceNotFoundError is not None,
        NodeObservationPort is not None
        and callable(getattr(NodeObservationPort, "get_block", None)),
        NodeObservationService is not None
        and callable(getattr(NodeObservationService, "inspect_block", None)),
        callable(getattr(BitcoinRpcClient, "get_block", None)),
        callable(getattr(ComposeLifecycleAdapter, "inspect_block", None)),
    )
)

pytestmark = pytest.mark.xfail(
    not _CAPABILITY_AVAILABLE,
    reason="Phase 3B.1 block-inspection surface is intentionally not implemented yet",
    strict=True,
)


def _summary(**overrides: object) -> Any:
    values: dict[str, object] = {
        "hash": BLOCK_HASH,
        "height": 12,
        "confirmations": 3,
        "timestamp": 1_700_000_000,
        "transaction_count": 2,
        "size": 285,
        "weight": 1_140,
        "previous_block_hash": PREVIOUS_BLOCK_HASH,
        "next_block_hash": NEXT_BLOCK_HASH,
    }
    values.update(overrides)
    return BlockSummary(**values)


def _rpc_block(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "hash": BLOCK_HASH,
        "height": 12,
        "confirmations": 3,
        "time": 1_700_000_000,
        "tx": ["a" * 64, "b" * 64],
        "size": 285,
        "weight": 1_140,
        "previousblockhash": PREVIOUS_BLOCK_HASH,
        "nextblockhash": NEXT_BLOCK_HASH,
    }
    values.update(overrides)
    return values


def _get_block(client: BitcoinRpcClient) -> Any:
    return client.__getattribute__("get_block")


def _inspect_block(adapter: ComposeLifecycleAdapter) -> Any:
    return adapter.__getattribute__("inspect_block")


def test_block_summary_is_frozen_slotted_and_deterministic() -> None:
    summary = _summary()
    assert dataclasses.is_dataclass(type(summary))
    assert vars(type(summary))["__dataclass_params__"].frozen is True
    assert not hasattr(summary, "__dict__")
    assert summary.to_dict() == {
        "confirmations": 3,
        "hash": BLOCK_HASH,
        "height": 12,
        "next_block_hash": NEXT_BLOCK_HASH,
        "previous_block_hash": PREVIOUS_BLOCK_HASH,
        "size": 285,
        "timestamp": 1_700_000_000,
        "transaction_count": 2,
        "weight": 1_140,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("hash", "A" * 64),
        ("hash", "a" * 63),
        ("previous_block_hash", "private-path-sentinel"),
        ("next_block_hash", "g" * 64),
        ("height", -1),
        ("height", True),
        ("confirmations", -1),
        ("timestamp", -1),
        ("transaction_count", -1),
        ("size", -1),
        ("weight", -1),
    ],
)
def test_block_summary_rejects_invalid_or_negative_facts(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        _summary(**{field: value})


def test_block_summary_allows_missing_adjacent_hashes() -> None:
    summary = _summary(previous_block_hash=None, next_block_hash=None)
    assert summary.previous_block_hash is None
    assert summary.next_block_hash is None


def test_rpc_allowlist_adds_only_phase3b1_read_methods() -> None:
    assert "getblockhash" in ALLOWED_RPC_METHODS
    assert "getblock" in ALLOWED_RPC_METHODS
    assert not ({"generate", "generatetoaddress", "submitblock"} & ALLOWED_RPC_METHODS)


def test_rpc_hash_lookup_uses_getblock_verbosity_one() -> None:
    client = BitcoinRpcClient()
    send = MagicMock(return_value=_rpc_block())
    with patch.object(client, "_send_request", send):
        summary = _get_block(client)(block_hash=BLOCK_HASH, timeout=4.0)

    assert summary == _summary()
    assert send.call_count == 1
    assert send.call_args.args[:2] == ("getblock", [BLOCK_HASH, 1])


def test_rpc_height_lookup_shares_one_deadline_across_both_requests() -> None:
    client = BitcoinRpcClient()
    calls: list[tuple[str, list[object], float]] = []

    def send(method: str, params: list[object], req_id: str, deadline: float) -> object:
        del req_id
        calls.append((method, params, deadline))
        return BLOCK_HASH if method == "getblockhash" else _rpc_block()

    with (
        patch.object(client, "_send_request", side_effect=send),
        patch(
            "bitheim.infrastructure.bitcoin.rpc_client.time.monotonic",
            side_effect=[100.0, 101.0, 102.0],
        ),
    ):
        summary = _get_block(client)(height=12, timeout=5.0)

    assert summary == _summary()
    assert [call[:2] for call in calls] == [
        ("getblockhash", [12]),
        ("getblock", [BLOCK_HASH, 1]),
    ]
    assert calls[0][2] == calls[1][2] == 105.0


def test_rpc_envelope_allows_scalar_hash_for_method_level_validation() -> None:
    client = BitcoinRpcClient()
    response = MagicMock()
    response.read.side_effect = [
        json.dumps({"result": BLOCK_HASH, "error": None, "id": "bitheim-block-hash-1"}).encode(
            "utf-8"
        ),
        b"",
    ]
    with patch(
        "bitheim.infrastructure.bitcoin.rpc_client.time.monotonic",
        return_value=100.0,
    ):
        result: Any = client._read_and_parse_envelope(
            response, "bitheim-block-hash-1", deadline=101.0
        )
    assert result == BLOCK_HASH


def test_rpc_height_lookup_validates_resolved_hash_before_second_request() -> None:
    client = BitcoinRpcClient()
    send = MagicMock(return_value="not-a-valid-block-hash")
    with (
        patch.object(client, "_send_request", send),
        pytest.raises(errors_module.RpcMalformedResponseError),
    ):
        _get_block(client)(height=12)
    assert send.call_count == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"block_hash": BLOCK_HASH, "height": 12},
        {"block_hash": "A" * 64},
        {"block_hash": "a" * 63},
        {"height": -1},
        {"height": True},
    ],
)
def test_rpc_lookup_requires_exactly_one_valid_locator(kwargs: dict[str, object]) -> None:
    client = BitcoinRpcClient()
    send = MagicMock()
    with patch.object(client, "_send_request", send), pytest.raises(errors_module.RpcError):
        _get_block(client)(**kwargs)
    send.assert_not_called()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("hash", "A" * 64),
        ("height", True),
        ("confirmations", -1),
        ("time", -1),
        ("tx", ["not-a-transaction-id"]),
        ("tx", [{}]),
        ("size", -1),
        ("weight", -1),
        ("previousblockhash", "g" * 64),
        ("nextblockhash", 3),
    ],
)
def test_rpc_rejects_malformed_block_fields(field: str, value: object) -> None:
    client = BitcoinRpcClient()
    with (
        patch.object(client, "_send_request", return_value=_rpc_block(**{field: value})),
        pytest.raises(errors_module.RpcMalformedResponseError),
    ):
        _get_block(client)(block_hash=BLOCK_HASH)


def test_rpc_ignores_unknown_additive_block_fields() -> None:
    client = BitcoinRpcClient()
    with patch.object(
        client,
        "_send_request",
        return_value=_rpc_block(future_additive_field="private-payload-sentinel"),
    ):
        assert _get_block(client)(block_hash=BLOCK_HASH) == _summary()


def test_unknown_block_maps_to_safe_resource_not_found_without_raw_message() -> None:
    client = BitcoinRpcClient()
    raw_message = "Block not found: private-hash-sentinel"
    response = MagicMock()
    response.read.side_effect = [
        json.dumps(
            {
                "result": None,
                "error": {"code": -5, "message": raw_message},
                "id": "bitheim-block-1",
            }
        ).encode("utf-8"),
        b"",
    ]
    with (
        patch(
            "bitheim.infrastructure.bitcoin.rpc_client.time.monotonic",
            return_value=100.0,
        ),
        pytest.raises(RpcResourceNotFoundError) as caught,
    ):
        client._read_and_parse_envelope(response, "bitheim-block-1", deadline=101.0)
    assert raw_message not in str(caught.value)
    assert caught.value.__cause__ is None


def test_application_service_delegates_one_validated_block_lookup() -> None:
    port = MagicMock()
    port.get_block.return_value = _summary()
    service = NodeObservationService(port)

    result = service.inspect_block(height=12, timeout=7.0)

    assert result == _summary()
    port.get_block.assert_called_once_with(block_hash=None, height=12, timeout=7.0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"block_hash": BLOCK_HASH, "height": 12},
        {"block_hash": "A" * 64},
        {"height": -1},
    ],
)
def test_application_service_rejects_invalid_locator_before_port(
    kwargs: dict[str, object],
) -> None:
    port = MagicMock()
    service = NodeObservationService(port)
    with pytest.raises(errors_module.RpcError):
        service.inspect_block(**kwargs)
    port.get_block.assert_not_called()


def test_resource_not_found_has_stable_delegated_category() -> None:
    error = RpcResourceNotFoundError("Requested block was not found.")
    assert cli_module._map_error_category(error) == "not_found"


def test_cli_block_parser_requires_exactly_one_locator() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["inspect", "block"])
    with pytest.raises(SystemExit):
        parser.parse_args(["inspect", "block", "--hash", BLOCK_HASH, "--height", "12"])

    by_hash = parser.parse_args(["inspect", "block", "--hash", BLOCK_HASH])
    by_height = parser.parse_args(["inspect", "block", "--height", "12"])
    assert by_hash.block_hash == BLOCK_HASH and by_hash.height is None
    assert by_height.height == 12 and by_height.block_hash is None


def test_cli_block_json_output_is_deterministic_and_single_document(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with (
        patch("bitheim.interfaces.cli._is_container_execution_context", return_value=False),
        patch(
            "bitheim.infrastructure.compose.adapter.ComposeLifecycleAdapter.inspect_block",
            return_value=_summary(),
        ) as inspect_block,
    ):
        exit_code = main(["inspect", "block", "--height", "12", "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert json.loads(captured.out) == _summary().to_dict()
    assert captured.out.endswith("\n")
    assert captured.out.count("{") == 1
    inspect_block.assert_called_once()


def test_cli_block_human_output_contains_summary_not_raw_transactions(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with (
        patch("bitheim.interfaces.cli._is_container_execution_context", return_value=False),
        patch(
            "bitheim.infrastructure.compose.adapter.ComposeLifecycleAdapter.inspect_block",
            return_value=_summary(),
        ),
    ):
        exit_code = main(["inspect", "block", "--hash", BLOCK_HASH])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert BLOCK_HASH in captured.out
    assert "Height:" in captured.out
    assert "Transactions:" in captured.out
    assert "raw" not in captured.out.lower()
    assert "private-payload-sentinel" not in captured.out + captured.err


def test_compose_block_delegation_is_no_deps_and_non_mutating() -> None:
    adapter = ComposeLifecycleAdapter()
    completed = MagicMock(returncode=0, stdout=json.dumps(_summary().to_dict()), stderr="")

    with (
        patch.object(adapter, "_check_docker_runtime_available"),
        patch.object(adapter, "_get_lifecycle_state_deadline", return_value="healthy"),
        patch("subprocess.run", return_value=completed) as run,
    ):
        result = _inspect_block(adapter)("test-node", height=12, timeout=10.0)

    command = run.call_args.args[0]
    assert result == _summary()
    assert command[-5:] == ["inspect", "block", "--height", "12", "--json"]
    assert "--no-deps" in command
    assert not ({"up", "start", "restart", "create"} & set(command))


def test_block_observation_does_not_log_hash_or_payload(
    capsys: pytest.CaptureFixture[str],
) -> None:
    sentinel_hash = "d" * 64
    client = BitcoinRpcClient()
    with (
        patch.object(client, "_send_request", return_value=_rpc_block(hash=sentinel_hash)),
        pytest.raises(errors_module.RpcMalformedResponseError),
    ):
        _get_block(client)(block_hash=BLOCK_HASH)

    captured = capsys.readouterr()
    assert sentinel_hash not in captured.out + captured.err
    assert "private-payload-sentinel" not in captured.out + captured.err


def test_ci_runs_real_block_inspection_without_printing_payload() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "Integration test — delegated block inspection" in workflow
    assert "bitheim inspect block --height 0 --json" in workflow
    assert 'echo "${BLOCK_JSON}"' not in workflow
    assert "--no-deps" in workflow
