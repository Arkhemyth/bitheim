"""Protected executable contracts for Phase 3B.2 mempool observation.

These tests are defined before implementation. They remain expected failures
only while the complete public mempool-observation surface is absent. Once that
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

MempoolSummary: Any = getattr(node_module, "MempoolSummary", None)
NodeObservationPort: Any = getattr(ports_module, "NodeObservationPort", None)
NodeObservationService: Any = getattr(service_module, "NodeObservationService", None)

_CAPABILITY_AVAILABLE = all(
    (
        MempoolSummary is not None,
        NodeObservationPort is not None
        and callable(getattr(NodeObservationPort, "get_mempool", None)),
        NodeObservationService is not None
        and callable(getattr(NodeObservationService, "inspect_mempool", None)),
        callable(getattr(BitcoinRpcClient, "get_mempool", None)),
        callable(getattr(ComposeLifecycleAdapter, "inspect_mempool", None)),
    )
)

pytestmark = pytest.mark.xfail(
    not _CAPABILITY_AVAILABLE,
    reason="Phase 3B.2 mempool-observation surface is intentionally not implemented yet",
    strict=True,
)


def _summary(**overrides: object) -> Any:
    values: dict[str, object] = {
        "loaded": True,
        "transaction_count": 2,
        "serialized_bytes": 410,
        "dynamic_memory_usage": 1_024,
        "max_memory": 300_000_000,
        "total_fees_satoshis": 12_345,
    }
    values.update(overrides)
    return MempoolSummary(**values)


def _rpc_mempool(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "loaded": True,
        "size": 2,
        "bytes": 410,
        "usage": 1_024,
        "maxmempool": 300_000_000,
        "total_fee": Decimal("0.00012345"),
    }
    values.update(overrides)
    return values


def _get_mempool(client: BitcoinRpcClient) -> Any:
    return client.__getattribute__("get_mempool")


def _inspect_mempool(adapter: ComposeLifecycleAdapter) -> Any:
    return adapter.__getattribute__("inspect_mempool")


def test_mempool_summary_is_frozen_slotted_and_deterministic() -> None:
    summary = _summary()
    assert dataclasses.is_dataclass(type(summary))
    assert vars(type(summary))["__dataclass_params__"].frozen is True
    assert not hasattr(summary, "__dict__")
    assert summary.to_dict() == {
        "dynamic_memory_usage": 1_024,
        "loaded": True,
        "max_memory": 300_000_000,
        "serialized_bytes": 410,
        "total_fees_satoshis": 12_345,
        "transaction_count": 2,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("loaded", 1),
        ("transaction_count", -1),
        ("transaction_count", True),
        ("serialized_bytes", -1),
        ("serialized_bytes", True),
        ("dynamic_memory_usage", -1),
        ("max_memory", -1),
        ("total_fees_satoshis", -1),
        ("total_fees_satoshis", True),
    ],
)
def test_mempool_summary_rejects_invalid_facts(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        _summary(**{field: value})


def test_rpc_allowlist_adds_only_mempool_read_method() -> None:
    assert "getmempoolinfo" in ALLOWED_RPC_METHODS
    assert not (
        {"sendrawtransaction", "testmempoolaccept", "prioritisetransaction"} & ALLOWED_RPC_METHODS
    )


def test_rpc_mempool_lookup_uses_one_bounded_read_request() -> None:
    client = BitcoinRpcClient()
    send = MagicMock(return_value=_rpc_mempool())
    with patch.object(client, "_send_request", send):
        summary = _get_mempool(client)(timeout=4.0)

    assert summary == _summary()
    assert send.call_count == 1
    assert send.call_args.args[:2] == ("getmempoolinfo", [])


@pytest.mark.parametrize(
    ("amount", "satoshis"),
    [
        (Decimal("0"), 0),
        (Decimal("0.00000001"), 1),
        (Decimal("0.00012345"), 12_345),
        (Decimal("1.00000000"), 100_000_000),
    ],
)
def test_rpc_converts_decimal_bitcoin_fees_exactly_to_satoshis(
    amount: Decimal, satoshis: int
) -> None:
    client = BitcoinRpcClient()
    with patch.object(client, "_send_request", return_value=_rpc_mempool(total_fee=amount)):
        assert _get_mempool(client)().total_fees_satoshis == satoshis


@pytest.mark.parametrize(
    "amount",
    [
        Decimal("-0.00000001"),
        Decimal("0.000000001"),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
        0.00000001,
        True,
        "0.00000001",
    ],
)
def test_rpc_rejects_unsafe_or_inexact_fee_values(amount: object) -> None:
    client = BitcoinRpcClient()
    with (
        patch.object(client, "_send_request", return_value=_rpc_mempool(total_fee=amount)),
        pytest.raises(errors_module.RpcMalformedResponseError),
    ):
        _get_mempool(client)()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("loaded", 1),
        ("size", -1),
        ("size", True),
        ("bytes", -1),
        ("usage", -1),
        ("maxmempool", -1),
    ],
)
def test_rpc_rejects_malformed_mempool_fields(field: str, value: object) -> None:
    client = BitcoinRpcClient()
    with (
        patch.object(client, "_send_request", return_value=_rpc_mempool(**{field: value})),
        pytest.raises(errors_module.RpcMalformedResponseError),
    ):
        _get_mempool(client)()


def test_rpc_ignores_unknown_additive_mempool_fields() -> None:
    client = BitcoinRpcClient()
    with patch.object(
        client,
        "_send_request",
        return_value=_rpc_mempool(future_additive_field="private-payload-sentinel"),
    ):
        assert _get_mempool(client)() == _summary()


def test_rpc_json_decoder_preserves_decimal_fee_precision() -> None:
    client = BitcoinRpcClient()
    response = MagicMock()
    response.read.side_effect = [
        b'{"result":{"total_fee":0.00000001},"error":null,"id":"mempool-1"}',
        b"",
    ]
    with patch("bitheim.infrastructure.bitcoin.rpc_client.time.monotonic", return_value=100.0):
        result: Any = client._read_and_parse_envelope(response, "mempool-1", deadline=101.0)

    assert result["total_fee"] == Decimal("0.00000001")
    assert isinstance(result["total_fee"], Decimal)


def test_application_service_delegates_one_mempool_lookup() -> None:
    port = MagicMock()
    port.get_mempool.return_value = _summary()
    service = NodeObservationService(port)

    result = service.inspect_mempool(timeout=7.0)

    assert result == _summary()
    port.get_mempool.assert_called_once_with(timeout=7.0)


@pytest.mark.parametrize("timeout", [0, -1, True, float("nan"), float("inf"), 61])
def test_application_service_rejects_invalid_timeout_before_port(timeout: object) -> None:
    port = MagicMock()
    service = NodeObservationService(port)
    with pytest.raises(errors_module.RpcError):
        service.inspect_mempool(timeout=timeout)
    port.get_mempool.assert_not_called()


def test_cli_mempool_parser_exposes_json_mode() -> None:
    parsed = build_parser().parse_args(["inspect", "mempool", "--json"])
    assert parsed.inspect_command == "mempool"
    assert parsed.json is True


def test_cli_mempool_json_output_is_deterministic_and_single_document(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with (
        patch("bitheim.interfaces.cli._is_container_execution_context", return_value=False),
        patch(
            "bitheim.infrastructure.compose.adapter.ComposeLifecycleAdapter.inspect_mempool",
            return_value=_summary(),
        ) as inspect_mempool,
    ):
        exit_code = main(["inspect", "mempool", "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert json.loads(captured.out) == _summary().to_dict()
    assert captured.out.endswith("\n")
    assert captured.out.count("{") == 1
    inspect_mempool.assert_called_once()


def test_cli_mempool_human_output_contains_aggregate_summary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with (
        patch("bitheim.interfaces.cli._is_container_execution_context", return_value=False),
        patch(
            "bitheim.infrastructure.compose.adapter.ComposeLifecycleAdapter.inspect_mempool",
            return_value=_summary(),
        ),
    ):
        exit_code = main(["inspect", "mempool"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Transactions:" in captured.out
    assert "Total fees (sats):" in captured.out
    assert "private-payload-sentinel" not in captured.out + captured.err


def test_compose_mempool_delegation_is_no_deps_and_non_mutating() -> None:
    adapter = ComposeLifecycleAdapter()
    completed = MagicMock(returncode=0, stdout=json.dumps(_summary().to_dict()), stderr="")

    with (
        patch.object(adapter, "_check_docker_runtime_available"),
        patch.object(adapter, "_get_lifecycle_state_deadline", return_value="healthy"),
        patch("subprocess.run", return_value=completed) as run,
    ):
        result = _inspect_mempool(adapter)("test-node", timeout=10.0)

    command = run.call_args.args[0]
    assert result == _summary()
    assert command[-3:] == ["inspect", "mempool", "--json"]
    assert "--no-deps" in command
    assert not ({"up", "start", "restart", "create"} & set(command))


def test_mempool_observation_does_not_log_payload(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = BitcoinRpcClient()
    with (
        patch.object(
            client,
            "_send_request",
            return_value=_rpc_mempool(total_fee="private-payload-sentinel"),
        ),
        pytest.raises(errors_module.RpcMalformedResponseError) as caught,
    ):
        _get_mempool(client)()

    captured = capsys.readouterr()
    observable = captured.out + captured.err + str(caught.value)
    assert "private-payload-sentinel" not in observable
    assert caught.value.__cause__ is None


def test_ci_runs_real_mempool_inspection_without_printing_payload() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "Integration test — delegated mempool inspection" in workflow
    assert "bitheim inspect mempool --json" in workflow
    assert 'echo "${MEMPOOL_JSON}"' not in workflow
    assert "--no-deps" in workflow
