"""Focused regression tests for Phase 3B.2 mempool corrections."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from bitheim.domain.errors import RpcMalformedResponseError, RpcUnavailableError
from bitheim.domain.node import NodeLifecycleState
from bitheim.infrastructure.bitcoin.rpc_client import BitcoinRpcClient
from bitheim.infrastructure.compose.adapter import ComposeLifecycleAdapter


def _rpc_mempool(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "loaded": True,
        "size": 2,
        "bytes": 410,
        "usage": 1024,
        "maxmempool": 300_000_000,
        "total_fee": Decimal("0.00012345"),
    }
    values.update(overrides)
    return values


def test_mempool_extreme_exponent_is_safe_and_typed() -> None:
    client = BitcoinRpcClient()
    # Provide an extreme exponent that would raise OverflowError if evaluated or cast to int.
    # We pass it as string here, wait, the client expects Decimal from JSON parser.
    # The vulnerability was `fee_sats = total_fee * Decimal("100000000")` throwing OverflowError.
    extreme_val = Decimal("1e999999")
    with (
        patch.object(client, "_send_request", return_value=_rpc_mempool(total_fee=extreme_val)),
        pytest.raises(RpcMalformedResponseError) as caught,
    ):
        client.get_mempool(timeout=10.0)

    # 1. Must fail closed as RpcMalformedResponseError
    # 2. Must have no exception cause
    assert caught.value.__cause__ is None
    # 3. Must have no raw value in the message
    assert "999999" not in str(caught.value)
    assert "1e" not in str(caught.value)


def test_mempool_stopped_node_error_omits_node_id() -> None:
    adapter = ComposeLifecycleAdapter()
    sentinel = "private-node-id-sentinel-123"

    with (
        patch.object(adapter, "_check_docker_runtime_available"),
        patch.object(
            adapter,
            "_get_lifecycle_state_deadline",
            return_value=NodeLifecycleState.STOPPED,
        ),
        pytest.raises(RpcUnavailableError) as caught,
    ):
        adapter.inspect_mempool(node_id=sentinel, timeout=10.0)

    assert sentinel not in str(caught.value)


def test_mempool_domain_validation_omits_raw_cause() -> None:
    # Test that when domain validation fails (e.g. ValueError during MempoolSummary instantiation),
    # the RpcMalformedResponseError has a generic message and NO cause.
    client = BitcoinRpcClient()
    sentinel = "private-validation-sentinel"

    # We mock _parse_mempool_summary to avoid having to mock the domain object itself?
    # No, we can just pass a value that triggers ValueError inside MempoolSummary.__post_init__.
    # e.g., size = -1
    with (
        patch(
            "bitheim.infrastructure.bitcoin.rpc_client.MempoolSummary",
            side_effect=ValueError(sentinel),
        ),
        patch.object(client, "_send_request", return_value=_rpc_mempool()),
        pytest.raises(RpcMalformedResponseError) as caught,
    ):
        client.get_mempool(timeout=10.0)

    assert caught.value.__cause__ is None
    assert sentinel not in str(caught.value)  # Just to ensure no raw values
    assert "Invalid domain mempool facts." in str(caught.value)
