import json
import math
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from bitheim.application.service import NodeObservationService
from bitheim.domain.errors import (
    RpcError,
    RpcMalformedResponseError,
    RpcResourceNotFoundError,
)
from bitheim.infrastructure.bitcoin.rpc_client import BitcoinRpcClient
from bitheim.infrastructure.compose.adapter import ComposeLifecycleAdapter


def test_f2_json_parsing_hides_raw_payload() -> None:
    """F2: JSON parsing raises an RpcMalformedResponseError, hiding raw exception."""
    adapter = ComposeLifecycleAdapter(None)

    with patch("subprocess.run") as run:
        res = MagicMock()
        res.returncode = 0
        res.stdout = "invalid json payload that might expose secrets"
        run.return_value = res

        with (
            patch.object(adapter, "_check_docker_runtime_available"),
            patch.object(
                adapter, "_get_lifecycle_state_deadline", return_value=MagicMock(value="running")
            ),
        ):
            with pytest.raises(RpcMalformedResponseError) as exc_info:
                adapter.inspect_block("node-id", height=10)

            err_msg = str(exc_info.value)
            assert "invalid json payload" not in err_msg
            assert err_msg == "Failed to parse delegated inspection response."
            assert exc_info.value.__cause__ is None


def test_f2_oserror_hides_raw_exception() -> None:
    """F2: OSError raises RpcError with fixed string, hiding raw exception."""
    adapter = ComposeLifecycleAdapter(None)

    with (
        patch("subprocess.run", side_effect=OSError("private path /home/user exposed")),
        patch.object(adapter, "_check_docker_runtime_available"),
        patch.object(
            adapter, "_get_lifecycle_state_deadline", return_value=MagicMock(value="running")
        ),
    ):
        with pytest.raises(RpcError) as exc_info:
            adapter.inspect_block("node-id", height=10)

        err_msg = str(exc_info.value)
        assert "private path" not in err_msg
        assert err_msg == "Failed to execute delegated block inspection."
        assert exc_info.value.__cause__ is None


def test_f3_missing_or_wrong_fields() -> None:
    """F3: Missing or wrong fields are translated to RpcMalformedResponseError from None."""
    adapter = ComposeLifecycleAdapter(None)

    with patch("subprocess.run") as run:
        res = MagicMock()
        res.returncode = 0
        # Valid JSON but invalid block fields (e.g. missing required fields)
        res.stdout = json.dumps({"hash": 1234})
        run.return_value = res

        with (
            patch.object(adapter, "_check_docker_runtime_available"),
            patch.object(
                adapter, "_get_lifecycle_state_deadline", return_value=MagicMock(value="running")
            ),
        ):
            with pytest.raises(RpcMalformedResponseError) as exc_info:
                adapter.inspect_block("node-id", height=10)

            assert str(exc_info.value) == "Invalid domain block facts."
            assert exc_info.value.__cause__ is None


def test_f4_timeout_validation() -> None:
    """F4: Timeout validation fails early before side effects."""
    adapter = ComposeLifecycleAdapter(None)

    invalid_timeouts: list[Any] = [True, False, math.nan, math.inf, -1.0, 0.0, 61.0, "10"]

    with patch.object(adapter, "_check_docker_runtime_available") as check_runtime:
        for t in invalid_timeouts:
            with pytest.raises(RpcError):
                adapter.inspect_block("node-id", height=10, timeout=t)

        check_runtime.assert_not_called()

    port = MagicMock()
    service = NodeObservationService(port)
    for t in invalid_timeouts:
        with pytest.raises(RpcError):
            service.inspect_block(height=10, timeout=t)
    port.get_block.assert_not_called()


def test_f4_locator_validation() -> None:
    """F4: Locator validation fails early before side effects."""
    port = MagicMock()
    service = NodeObservationService(port)

    with pytest.raises(RpcError):
        service.inspect_block(block_hash="invalid_hash_not_hex")

    with pytest.raises(RpcError):
        service.inspect_block(height=-1)

    with pytest.raises(RpcError):
        service.inspect_block(height=True)

    port.get_block.assert_not_called()


def test_f5_rpc_error_code_5() -> None:
    """F5: RPC error code -5 is mapped safely without exposing message."""
    client = BitcoinRpcClient()

    import io
    import urllib.error

    err_body = json.dumps(
        {
            "result": None,
            "error": {
                "code": -5,
                "message": "Private sensitive message that should not be propagated",
            },
            "id": "bitheim-req-hash",
        }
    ).encode("utf-8")

    http_error = urllib.error.HTTPError(
        url="http://mock",
        code=500,
        msg="Internal Server Error",
        hdrs={},  # type: ignore
        fp=io.BytesIO(err_body),
    )

    with (
        patch.object(client._opener, "open", side_effect=http_error),
        patch.object(client, "_read_cookie_header", return_value="Basic dXNlcjpwYXNz"),
    ):
        with pytest.raises(RpcResourceNotFoundError) as exc_info:
            client.get_block(height=10)

        err_msg = str(exc_info.value)
        assert "Private sensitive message" not in err_msg
        assert err_msg == "RPC resource not found."
        assert exc_info.value.__cause__ is None


def test_f8_delegated_json_depth_is_enforced_for_block_output() -> None:
    """F8: Deeply nested JSON raises RpcMalformedResponseError without leaking sentinel."""
    adapter = ComposeLifecycleAdapter(None)

    with patch("subprocess.run") as run:
        res = MagicMock()
        res.returncode = 0

        nested_value: object = "too_deep"
        for _ in range(33):
            nested_value = {"nested": nested_value}
        res.stdout = json.dumps(
            {
                "hash": "0" * 63 + "1",
                "height": 10,
                "confirmations": 1,
                "timestamp": 1_700_000_000,
                "transaction_count": 1,
                "size": 285,
                "weight": 1_140,
                "previous_block_hash": None,
                "next_block_hash": None,
                "future_additive_field": nested_value,
            }
        )
        run.return_value = res

        with pytest.raises(RpcMalformedResponseError) as exc_info:
            adapter.inspect_block("node-id", height=10)

        err_msg = str(exc_info.value)
        assert "too_deep" not in err_msg
        assert err_msg == "Delegated JSON exceeds maximum nesting depth of 32."
        assert exc_info.value.__cause__ is None
