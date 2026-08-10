"""Comprehensive unit tests for BitcoinRpcClient, protocol limits, and error handling."""

import base64
import io
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from bitheim.domain.errors import (
    RpcAuthenticationError,
    RpcError,
    RpcIncompatibleNodeError,
    RpcMalformedResponseError,
    RpcProtocolError,
    RpcResponseSizeExceededError,
    RpcUnavailableError,
)
from bitheim.infrastructure.bitcoin.rpc_client import (
    EXPECTED_BITCOIN_VERSION,
    EXPECTED_CHAIN,
    MAX_COOKIE_SIZE_BYTES,
    BitcoinRpcClient,
)


def _make_mock_response(data: dict[str, Any], status: int = 200) -> MagicMock:
    """Helper to construct a mock HTTP response returning serialized JSON bytes."""
    resp = MagicMock()
    resp.status = status
    payload = json.dumps(data).encode("utf-8")
    resp.read.side_effect = [payload, b""]
    resp.__enter__.return_value = resp
    return resp


SAMPLE_BLOCK_HASH = "0f9188f13cb7b2c71f2a335e3a4fc328bf5beb436012afca590b1a11466e2206"
SAMPLE_CHAINWORK = "0000000000000000000000000000000000000000000000000000000000000002"


def test_constants_exact_values() -> None:
    """Verify contractual constants and identity requirements."""
    assert EXPECTED_BITCOIN_VERSION == 310100
    assert EXPECTED_CHAIN == "regtest"
    assert MAX_COOKIE_SIZE_BYTES == 4096


def test_get_node_overview_success(tmp_path: Path) -> None:
    """Verify successful node overview extraction and type conversion."""
    cookie = tmp_path / ".cookie"
    cookie.write_text("__cookie__:verysecretpass123", encoding="utf-8")
    cookie.chmod(0o640)

    client = BitcoinRpcClient()
    client._cookie_path = cookie

    mock_opener = MagicMock()

    def mock_open(req: urllib.request.Request, timeout: float = 10.0) -> MagicMock:
        auth_hdr = req.get_header("Authorization")
        assert auth_hdr is not None and auth_hdr.startswith("Basic ")
        assert isinstance(req.data, bytes)
        body = json.loads(req.data.decode("utf-8"))
        method = body["method"]
        req_id = body["id"]

        if method == "getnetworkinfo":
            return _make_mock_response(
                {
                    "result": {
                        "version": 310100,
                        "subversion": "/Satoshi:31.1.0/",
                        "protocolversion": 70016,
                        "networkactive": True,
                        "connections": 8,
                    },
                    "error": None,
                    "id": req_id,
                }
            )
        if method == "getblockchaininfo":
            return _make_mock_response(
                {
                    "result": {
                        "chain": "regtest",
                        "blocks": 105,
                        "headers": 105,
                        "bestblockhash": SAMPLE_BLOCK_HASH,
                        "mediantime": 1296688602,
                        "initialblockdownload": False,
                        "pruned": False,
                        "chainwork": SAMPLE_CHAINWORK,
                        "verificationprogress": 1.0,
                    },
                    "error": None,
                    "id": req_id,
                }
            )
        raise ValueError(f"Unexpected method: {method}")

    mock_opener.open.side_effect = mock_open
    client._opener = mock_opener

    overview = client.get_node_overview(timeout=10.0)
    assert overview.version == 310100
    assert overview.subversion == "/Satoshi:31.1.0/"
    assert overview.network_active is True
    assert overview.connections == 8
    assert overview.chain == "regtest"
    assert overview.blocks == 105
    assert overview.headers == 105
    assert overview.best_block_hash == SAMPLE_BLOCK_HASH
    assert overview.median_time == 1296688602
    assert overview.initial_block_download is False
    assert overview.pruned is False
    assert overview.chainwork == SAMPLE_CHAINWORK


def test_cookie_missing_fails_closed(tmp_path: Path) -> None:
    """Verify that missing cookie file raises RpcAuthenticationError."""
    missing_cookie = tmp_path / "nonexistent.cookie"
    client = BitcoinRpcClient()
    client._cookie_path = missing_cookie

    with pytest.raises(RpcAuthenticationError) as exc_info:
        client.get_node_overview()
    assert "unavailable or inaccessible" in str(exc_info.value).lower()


def test_cookie_empty_fails_closed(tmp_path: Path) -> None:
    """Verify that empty cookie file raises RpcAuthenticationError."""
    empty_cookie = tmp_path / ".cookie"
    empty_cookie.write_text("", encoding="utf-8")
    empty_cookie.chmod(0o640)
    client = BitcoinRpcClient()
    client._cookie_path = empty_cookie

    with pytest.raises(RpcAuthenticationError) as exc_info:
        client.get_node_overview()
    assert "empty" in str(exc_info.value)


def test_cookie_oversized_fails_closed(tmp_path: Path) -> None:
    """Verify that cookie file exceeding 4 KiB raises RpcAuthenticationError."""
    oversized_cookie = tmp_path / ".cookie"
    oversized_cookie.write_text("a" * 4097, encoding="utf-8")
    oversized_cookie.chmod(0o640)
    client = BitcoinRpcClient()
    client._cookie_path = oversized_cookie

    with pytest.raises(RpcAuthenticationError) as exc_info:
        client.get_node_overview()
    assert "exceeds maximum allowed size" in str(exc_info.value)


def test_cookie_malformed_no_colon(tmp_path: Path) -> None:
    """Verify that cookie file without colon raises RpcAuthenticationError."""
    bad_cookie = tmp_path / ".cookie"
    bad_cookie.write_text("no_colon_in_cookie_content", encoding="utf-8")
    bad_cookie.chmod(0o640)
    client = BitcoinRpcClient()
    client._cookie_path = bad_cookie

    with pytest.raises(RpcAuthenticationError) as exc_info:
        client.get_node_overview()
    assert "format is invalid" in str(exc_info.value)


def test_cookie_malformed_with_newlines(tmp_path: Path) -> None:
    """Verify that cookie file with newline characters raises RpcAuthenticationError."""
    bad_cookie = tmp_path / ".cookie"
    bad_cookie.write_text("__cookie__:pass\nnewline", encoding="utf-8")
    bad_cookie.chmod(0o640)
    client = BitcoinRpcClient()
    client._cookie_path = bad_cookie

    with pytest.raises(RpcAuthenticationError) as exc_info:
        client.get_node_overview()
    assert "newline characters" in str(exc_info.value)


def test_cookie_non_utf8(tmp_path: Path) -> None:
    """Verify that non-UTF-8 cookie bytes raise RpcAuthenticationError."""
    bad_cookie = tmp_path / ".cookie"
    bad_cookie.write_bytes(b"\x80\x81\xff:secret")
    bad_cookie.chmod(0o640)
    client = BitcoinRpcClient()
    client._cookie_path = bad_cookie

    with pytest.raises(RpcAuthenticationError) as exc_info:
        client.get_node_overview()
    assert "invalid UTF-8" in str(exc_info.value)


def test_cookie_read_per_request_no_caching(tmp_path: Path) -> None:
    """Verify cookie file is re-read on every request and never cached."""
    cookie = tmp_path / ".cookie"
    cookie.write_text("__cookie__:initial_pass", encoding="utf-8")
    cookie.chmod(0o640)

    client = BitcoinRpcClient()
    client._cookie_path = cookie
    header1 = client._read_cookie_header()
    assert base64.b64decode(header1.split()[1]).decode("utf-8") == "__cookie__:initial_pass"

    # Mutate cookie file on disk
    cookie.write_text("__cookie__:rotated_pass", encoding="utf-8")
    cookie.chmod(0o640)
    header2 = client._read_cookie_header()
    assert base64.b64decode(header2.split()[1]).decode("utf-8") == "__cookie__:rotated_pass"
    assert header1 != header2


def test_redirect_handler_rejects_redirects() -> None:
    """Verify that custom redirect handler unconditionally rejects HTTP 3xx redirects."""
    from bitheim.infrastructure.bitcoin.rpc_client import _NoRedirectHandler

    handler = _NoRedirectHandler()
    req = urllib.request.Request("http://127.0.0.1:18443/")
    with pytest.raises(RpcUnavailableError) as exc_info:
        handler.redirect_request(req, None, 302, "Found", {}, "http://evil.com/")
    assert "HTTP redirects are rejected" in str(exc_info.value)


def test_response_id_mismatch_raises_malformed(tmp_path: Path) -> None:
    """Verify that mismatched RPC response ID raises RpcMalformedResponseError."""
    cookie = tmp_path / ".cookie"
    cookie.write_text("__cookie__:pass", encoding="utf-8")
    cookie.chmod(0o640)
    client = BitcoinRpcClient()
    client._cookie_path = cookie

    mock_opener = MagicMock()
    mock_opener.open.return_value = _make_mock_response(
        {
            "result": {"version": 310100},
            "error": None,
            "id": "wrong-id",
        }
    )
    client._opener = mock_opener

    with pytest.raises(RpcMalformedResponseError) as exc_info:
        client.get_node_overview()
    assert "response ID does not match request ID" in str(exc_info.value)


def test_response_size_exceeded_raises_error(tmp_path: Path) -> None:
    """Verify that responses exceeding 4 MiB raise RpcResponseSizeExceededError."""
    cookie = tmp_path / ".cookie"
    cookie.write_text("__cookie__:pass", encoding="utf-8")
    cookie.chmod(0o640)
    client = BitcoinRpcClient()
    client._cookie_path = cookie

    mock_resp = MagicMock()
    # Return 1 MiB chunk 5 times (total 5 MiB > 4 MiB)
    mock_resp.read.side_effect = [b"x" * (1024 * 1024)] * 5
    mock_resp.__enter__.return_value = mock_resp

    mock_opener = MagicMock()
    mock_opener.open.return_value = mock_resp
    client._opener = mock_opener

    with pytest.raises(RpcResponseSizeExceededError) as exc_info:
        client.get_node_overview()
    assert "payload exceeded maximum size limit" in str(exc_info.value)


def test_json_depth_exceeded_raises_malformed(tmp_path: Path) -> None:
    """Verify that deeply nested JSON (> 32 levels) raises RpcMalformedResponseError."""
    cookie = tmp_path / ".cookie"
    cookie.write_text("__cookie__:pass", encoding="utf-8")
    cookie.chmod(0o640)
    client = BitcoinRpcClient()
    client._cookie_path = cookie

    # Build 35 levels of nesting
    nested: dict[str, Any] = {"version": 310100}
    for _ in range(35):
        nested = {"nested": nested}

    mock_opener = MagicMock()
    mock_opener.open.return_value = _make_mock_response(
        {
            "result": nested,
            "error": None,
            "id": "bitheim-req-1",
        }
    )
    client._opener = mock_opener

    with pytest.raises(RpcMalformedResponseError) as exc_info:
        client.get_node_overview()
    assert "maximum JSON nesting depth" in str(exc_info.value)


def test_incompatible_bitcoin_version(tmp_path: Path) -> None:
    """Verify that node version != 310100 raises RpcIncompatibleNodeError."""
    cookie = tmp_path / ".cookie"
    cookie.write_text("__cookie__:pass", encoding="utf-8")
    cookie.chmod(0o640)
    client = BitcoinRpcClient()
    client._cookie_path = cookie

    mock_opener = MagicMock()

    def mock_open(req: urllib.request.Request, timeout: float = 10.0) -> MagicMock:
        assert isinstance(req.data, bytes)
        body = json.loads(req.data.decode("utf-8"))
        method = body["method"]
        req_id = body["id"]
        if method == "getnetworkinfo":
            return _make_mock_response(
                {
                    "result": {
                        "version": 310000,  # 31.0 instead of 31.1 (310100)
                        "subversion": "/Satoshi:31.0.0/",
                        "protocolversion": 70016,
                        "networkactive": True,
                        "connections": 0,
                    },
                    "error": None,
                    "id": req_id,
                }
            )
        if method == "getblockchaininfo":
            return _make_mock_response(
                {
                    "result": {
                        "chain": "regtest",
                        "blocks": 0,
                        "headers": 0,
                        "bestblockhash": SAMPLE_BLOCK_HASH,
                        "mediantime": 1296688602,
                        "initialblockdownload": False,
                        "pruned": False,
                        "chainwork": SAMPLE_CHAINWORK,
                        "verificationprogress": 1.0,
                    },
                    "error": None,
                    "id": req_id,
                }
            )
        raise ValueError(method)

    mock_opener.open.side_effect = mock_open
    client._opener = mock_opener

    with pytest.raises(RpcIncompatibleNodeError) as exc_info:
        client.get_node_overview()
    assert "Incompatible Bitcoin Core version" in str(exc_info.value)
    assert "310100" in str(exc_info.value)


def test_incompatible_chain(tmp_path: Path) -> None:
    """Verify that node chain != 'regtest' raises RpcIncompatibleNodeError."""
    cookie = tmp_path / ".cookie"
    cookie.write_text("__cookie__:pass", encoding="utf-8")
    cookie.chmod(0o640)
    client = BitcoinRpcClient()
    client._cookie_path = cookie

    mock_opener = MagicMock()

    def mock_open(req: urllib.request.Request, timeout: float = 10.0) -> MagicMock:
        assert isinstance(req.data, bytes)
        body = json.loads(req.data.decode("utf-8"))
        method = body["method"]
        req_id = body["id"]
        if method == "getnetworkinfo":
            return _make_mock_response(
                {
                    "result": {
                        "version": 310100,
                        "subversion": "/Satoshi:31.1.0/",
                        "protocolversion": 70016,
                        "networkactive": True,
                        "connections": 0,
                    },
                    "error": None,
                    "id": req_id,
                }
            )
        if method == "getblockchaininfo":
            return _make_mock_response(
                {
                    "result": {
                        "chain": "mainnet",  # mainnet instead of regtest
                        "blocks": 850000,
                        "headers": 850000,
                        "bestblockhash": (
                            "000000000000000000029b3c434997e09880f0c0597397b91d2937077bd8ebcb"
                        ),
                        "mediantime": 1720000000,
                        "initialblockdownload": False,
                        "pruned": False,
                        "chainwork": SAMPLE_CHAINWORK,
                        "verificationprogress": 1.0,
                    },
                    "error": None,
                    "id": req_id,
                }
            )
        raise ValueError(method)

    mock_opener.open.side_effect = mock_open
    client._opener = mock_opener

    with pytest.raises(RpcIncompatibleNodeError) as exc_info:
        client.get_node_overview()
    assert "Incompatible chain" in str(exc_info.value)
    assert "regtest" in str(exc_info.value)


def test_boolean_int_type_confusion_rejected(tmp_path: Path) -> None:
    """Verify that booleans in integer fields (e.g. version=True) are strictly rejected."""
    cookie = tmp_path / ".cookie"
    cookie.write_text("__cookie__:pass", encoding="utf-8")
    cookie.chmod(0o640)
    client = BitcoinRpcClient()
    client._cookie_path = cookie

    mock_opener = MagicMock()
    mock_opener.open.return_value = _make_mock_response(
        {
            "result": {
                "version": True,  # Bool where int is required
                "subversion": "/Satoshi:31.1.0/",
                "protocolversion": 70016,
                "networkactive": True,
                "connections": 0,
            },
            "error": None,
            "id": "bitheim-req-1",
        }
    )
    client._opener = mock_opener

    with pytest.raises(RpcMalformedResponseError) as exc_info:
        client.get_node_overview()
    assert "must be an integer" in str(exc_info.value)


def test_invalid_hash_format_rejected(tmp_path: Path) -> None:
    """Verify that non-hexadecimal or non-64-character hash is rejected."""
    cookie = tmp_path / ".cookie"
    cookie.write_text("__cookie__:pass", encoding="utf-8")
    cookie.chmod(0o640)
    client = BitcoinRpcClient()
    client._cookie_path = cookie

    mock_opener = MagicMock()

    def mock_open(req: urllib.request.Request, timeout: float = 10.0) -> MagicMock:
        assert isinstance(req.data, bytes)
        body = json.loads(req.data.decode("utf-8"))
        method = body["method"]
        req_id = body["id"]
        if method == "getnetworkinfo":
            return _make_mock_response(
                {
                    "result": {
                        "version": 310100,
                        "subversion": "/Satoshi:31.1.0/",
                        "protocolversion": 70016,
                        "networkactive": True,
                        "connections": 0,
                    },
                    "error": None,
                    "id": req_id,
                }
            )
        if method == "getblockchaininfo":
            return _make_mock_response(
                {
                    "result": {
                        "chain": "regtest",
                        "blocks": 0,
                        "headers": 0,
                        "bestblockhash": "INVALID_HASH_NOT_HEX",
                        "mediantime": 1296688602,
                        "initialblockdownload": False,
                        "pruned": False,
                        "chainwork": SAMPLE_CHAINWORK,
                        "verificationprogress": 1.0,
                    },
                    "error": None,
                    "id": req_id,
                }
            )
        raise ValueError(method)

    mock_opener.open.side_effect = mock_open
    client._opener = mock_opener

    with pytest.raises(RpcMalformedResponseError) as exc_info:
        client.get_node_overview()
    assert "bestblockhash" in str(exc_info.value)


def test_http_401_raises_authentication_error(tmp_path: Path) -> None:
    """Verify that HTTP 401 raises RpcAuthenticationError without credentials."""
    cookie = tmp_path / ".cookie"
    cookie.write_text("__cookie__:badpass", encoding="utf-8")
    cookie.chmod(0o640)
    client = BitcoinRpcClient()
    client._cookie_path = cookie

    err = urllib.error.HTTPError(
        url="http://127.0.0.1:18443/",
        code=401,
        msg="Unauthorized",
        hdrs={},  # type: ignore[arg-type]
        fp=None,
    )

    mock_opener = MagicMock()
    mock_opener.open.side_effect = err
    client._opener = mock_opener

    with pytest.raises(RpcAuthenticationError) as exc_info:
        client.get_node_overview()
    assert "authentication rejected" in str(exc_info.value)
    assert "badpass" not in str(exc_info.value)


def test_http_500_with_rpc_error_object(tmp_path: Path) -> None:
    """Verify that HTTP 500 with RPC error object raises typed RpcProtocolError."""
    cookie = tmp_path / ".cookie"
    cookie.write_text("__cookie__:pass", encoding="utf-8")
    cookie.chmod(0o640)
    client = BitcoinRpcClient()
    client._cookie_path = cookie

    err_fp = io.BytesIO(
        json.dumps(
            {
                "result": None,
                "error": {"code": -28, "message": "Loading block index..."},
                "id": "bitheim-req-1",
            }
        ).encode("utf-8")
    )
    err = urllib.error.HTTPError(
        url="http://127.0.0.1:18443/",
        code=500,
        msg="Internal Server Error",
        hdrs={},  # type: ignore[arg-type]
        fp=err_fp,
    )

    mock_opener = MagicMock()
    mock_opener.open.side_effect = err
    client._opener = mock_opener

    with pytest.raises(RpcProtocolError) as exc_info:
        client.get_node_overview()
    assert "warming up or loading block index" in str(exc_info.value).lower()


def test_deadline_expired_raises_timeout(tmp_path: Path) -> None:
    """Verify that expired deadline raises RpcTimeoutError without issuing request."""
    cookie = tmp_path / ".cookie"
    cookie.write_text("__cookie__:pass", encoding="utf-8")
    cookie.chmod(0o640)
    client = BitcoinRpcClient()
    client._cookie_path = cookie

    with pytest.raises(RpcError) as exc_info:
        client.get_node_overview(timeout=0)
    assert "Command deadline must be a positive finite value" in str(exc_info.value)


def test_invalid_timeout_parameter(tmp_path: Path) -> None:
    """Verify that negative, infinite, NaN, or >60s timeouts are rejected."""
    cookie = tmp_path / ".cookie"
    cookie.write_text("__cookie__:pass", encoding="utf-8")
    cookie.chmod(0o640)
    client = BitcoinRpcClient()
    client._cookie_path = cookie

    bad_timeouts: list[Any] = [-1.0, float("nan"), float("inf"), 60.1, True]
    for bad_t in bad_timeouts:
        with pytest.raises(RpcError):
            client.get_node_overview(timeout=bad_t)


def test_invalid_rpc_endpoint_hosts_rejected() -> None:
    """Verify that non-whitelisted RPC hosts are rejected at construction."""
    invalid_hosts = ["0.0.0.0", "192.168.1.100", "example.com", "attacker.local", ""]
    for host in invalid_hosts:
        with pytest.raises(RpcError, match=r"Invalid RPC host\."):
            BitcoinRpcClient(rpc_host=host)


def test_invalid_rpc_endpoint_ports_rejected() -> None:
    """Verify that invalid RPC ports are rejected at construction."""
    invalid_ports = [-1, 0, 65536, 99999]
    for port in invalid_ports:
        with pytest.raises(RpcError, match="Invalid RPC port"):
            BitcoinRpcClient(rpc_port=port)


def test_symlink_cookie_rejected_fails_closed(tmp_path: Path) -> None:
    """Verify that symlinked cookie files are rejected with RpcAuthenticationError."""
    real_cookie = tmp_path / "real_cookie"
    real_cookie.write_text("__cookie__:secret123", encoding="utf-8")
    real_cookie.chmod(0o640)
    real_cookie.chmod(0o600)

    symlink_cookie = tmp_path / "sym_cookie"
    symlink_cookie.symlink_to(real_cookie)

    client = BitcoinRpcClient()
    client._cookie_path = symlink_cookie
    with pytest.raises(RpcAuthenticationError, match="must not be a symbolic link"):
        client.get_node_overview()


def test_world_writable_cookie_rejected(tmp_path: Path) -> None:
    """Verify that world-writable or group-writable cookie files are rejected."""
    cookie = tmp_path / ".cookie"
    cookie.write_text("__cookie__:secret123", encoding="utf-8")
    cookie.chmod(0o640)
    cookie.chmod(0o666)

    client = BitcoinRpcClient()
    client._cookie_path = cookie
    with pytest.raises(RpcAuthenticationError, match="insecure write permissions"):
        client.get_node_overview()


def test_node_overview_invariant_validation() -> None:
    """Verify NodeOverview post-init invariants fail fast on invalid domain state."""
    from bitheim.domain.node import NodeOverview

    # Invalid version
    with pytest.raises(ValueError):
        NodeOverview(
            version=310000,
            subversion="/Satoshi:31.1.0/",
            network_active=True,
            connections=0,
            chain="regtest",
            blocks=0,
            headers=0,
            best_block_hash=SAMPLE_BLOCK_HASH,
            median_time=1296688602,
            initial_block_download=False,
            pruned=False,
            chainwork=SAMPLE_CHAINWORK,
        )

    # Invalid chain
    with pytest.raises(ValueError):
        NodeOverview(
            version=310100,
            subversion="/Satoshi:31.1.0/",
            network_active=True,
            connections=0,
            chain="mainnet",
            blocks=0,
            headers=0,
            best_block_hash=SAMPLE_BLOCK_HASH,
            median_time=1296688602,
            initial_block_download=False,
            pruned=False,
            chainwork=SAMPLE_CHAINWORK,
        )

    # Negative blocks
    with pytest.raises(ValueError):
        NodeOverview(
            version=310100,
            subversion="/Satoshi:31.1.0/",
            network_active=True,
            connections=0,
            chain="regtest",
            blocks=-1,
            headers=0,
            best_block_hash=SAMPLE_BLOCK_HASH,
            median_time=1296688602,
            initial_block_download=False,
            pruned=False,
            chainwork=SAMPLE_CHAINWORK,
        )

    # Invalid hash format
    with pytest.raises(ValueError):
        NodeOverview(
            version=310100,
            subversion="/Satoshi:31.1.0/",
            network_active=True,
            connections=0,
            chain="regtest",
            blocks=0,
            headers=0,
            best_block_hash="not_a_64_hex_string",
            median_time=1296688602,
            initial_block_download=False,
            pruned=False,
            chainwork=SAMPLE_CHAINWORK,
        )


def test_oversized_response_stream_rejected(tmp_path: Path) -> None:
    """Verify that responses exceeding 64 KiB raise RpcResponseSizeExceededError."""
    cookie = tmp_path / ".cookie"
    cookie.write_text("__cookie__:pass", encoding="utf-8")
    cookie.chmod(0o640)
    client = BitcoinRpcClient()
    client._cookie_path = cookie

    mock_opener = MagicMock()
    resp = MagicMock()
    resp.status = 200
    # Single read returning > 65536 bytes
    resp.read.return_value = b"x" * 70000
    resp.__enter__.return_value = resp
    mock_opener.open.return_value = resp
    client._opener = mock_opener

    with pytest.raises(RpcResponseSizeExceededError):
        client.get_node_overview()


def test_duplicate_json_keys_rejected(tmp_path: Path) -> None:
    """Verify that responses containing duplicate JSON keys are rejected."""
    cookie = tmp_path / ".cookie"
    cookie.write_text("__cookie__:pass", encoding="utf-8")
    cookie.chmod(0o640)
    client = BitcoinRpcClient()
    client._cookie_path = cookie

    mock_opener = MagicMock()

    def mock_open(req: Any, timeout: float = 10.0) -> MagicMock:
        req_id = json.loads(req.data.decode("utf-8"))["id"]
        raw_payload = (
            f'{{"result": {{"version": 310100, "version": 310100, '
            f'"subversion": "/Satoshi:31.1.0/", "networkactive": true, '
            f'"connections": 0}}, "error": null, "id": "{req_id}"}}'
        ).encode()
        resp = MagicMock()
        resp.status = 200
        resp.read.side_effect = [raw_payload, b""]
        resp.__enter__.return_value = resp
        return resp

    mock_opener.open.side_effect = mock_open
    client._opener = mock_opener

    with pytest.raises(RpcMalformedResponseError, match="duplicate keys"):
        client.get_node_overview()


def test_nested_json_depth_limit(tmp_path: Path) -> None:
    """Verify that responses exceeding maximum JSON nesting depth of 32 are rejected."""
    cookie = tmp_path / ".cookie"
    cookie.write_text("__cookie__:pass", encoding="utf-8")
    cookie.chmod(0o640)
    client = BitcoinRpcClient()
    client._cookie_path = cookie

    mock_opener = MagicMock()

    deep_dict: dict[str, Any] = {"leaf": "value"}
    for _ in range(35):
        deep_dict = {"nested": deep_dict}

    def mock_open(req: Any, timeout: float = 10.0) -> MagicMock:
        req_id = json.loads(req.data.decode("utf-8"))["id"]
        raw_payload = json.dumps(
            {
                "result": deep_dict,
                "error": None,
                "id": req_id,
            }
        ).encode()
        resp = MagicMock()
        resp.status = 200
        resp.read.side_effect = [raw_payload, b""]
        resp.__enter__.return_value = resp
        return resp

    mock_opener.open.side_effect = mock_open
    client._opener = mock_opener

    with pytest.raises(RpcMalformedResponseError, match="nesting depth"):
        client.get_node_overview()
