"""Unit tests for JSON-RPC health probe and version/chain compatibility verification."""

import json
import urllib.error
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from bitheim.domain.node import NodeLifecycleState
from bitheim.infrastructure.bitcoin.rpc_probe import (
    EXPECTED_BITCOIN_VERSION,
    EXPECTED_CHAIN,
    probe_rpc_http,
)


def test_constants_exact_values() -> None:
    """Verify that expected Bitcoin version is exactly 310100 (31.1) and chain is regtest."""
    assert EXPECTED_BITCOIN_VERSION == 310100
    assert EXPECTED_CHAIN == "regtest"


def test_probe_rpc_http_healthy_success(tmp_path: Path) -> None:
    """Verify probe returns HEALTHY when chain is regtest and version is 310100."""
    cookie_file = tmp_path / ".cookie"
    cookie_file.write_text("__cookie__:secretpassword123", encoding="utf-8")

    def mock_urlopen(req: Any, timeout: float = 2.0) -> Any:
        data = json.loads(req.data.decode("utf-8"))
        method = data.get("method")
        mock_resp = MagicMock()
        if method == "getblockchaininfo":
            mock_resp.read.return_value = json.dumps(
                {
                    "result": {"chain": "regtest", "blocks": 100, "headers": 100},
                    "error": None,
                    "id": "bitheim-probe",
                }
            ).encode("utf-8")
        elif method == "getnetworkinfo":
            mock_resp.read.return_value = json.dumps(
                {
                    "result": {"version": 310100, "protocolversion": 70016},
                    "error": None,
                    "id": "bitheim-probe",
                }
            ).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        health = probe_rpc_http(cookie_path=cookie_file)

    assert health.state == NodeLifecycleState.HEALTHY
    assert health.chain == "regtest"
    assert health.version == 310100
    assert health.blocks == 100


def test_probe_rpc_http_incompatible_version(tmp_path: Path) -> None:
    """Verify probe returns INCOMPATIBLE when version is not exactly 310100."""
    cookie_file = tmp_path / ".cookie"
    cookie_file.write_text("__cookie__:secret", encoding="utf-8")

    def mock_urlopen(req: Any, timeout: float = 2.0) -> Any:
        data = json.loads(req.data.decode("utf-8"))
        method = data.get("method")
        mock_resp = MagicMock()
        if method == "getblockchaininfo":
            mock_resp.read.return_value = json.dumps(
                {
                    "result": {"chain": "regtest", "blocks": 0, "headers": 0},
                    "error": None,
                    "id": "bitheim-probe",
                }
            ).encode("utf-8")
        elif method == "getnetworkinfo":
            mock_resp.read.return_value = json.dumps(
                {
                    "result": {"version": 310000},  # Older 31.0 instead of 31.1 (310100)
                    "error": None,
                    "id": "bitheim-probe",
                }
            ).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        health = probe_rpc_http(cookie_path=cookie_file)

    assert health.state == NodeLifecycleState.INCOMPATIBLE
    assert health.details == "incompatible_version"


def test_probe_rpc_http_incompatible_chain(tmp_path: Path) -> None:
    """Verify probe returns INCOMPATIBLE when chain is not regtest."""
    cookie_file = tmp_path / ".cookie"
    cookie_file.write_text("__cookie__:secret", encoding="utf-8")

    def mock_urlopen(req: Any, timeout: float = 2.0) -> Any:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {
                "result": {"chain": "mainnet", "blocks": 800000, "headers": 800000},
                "error": None,
                "id": "bitheim-probe",
            }
        ).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        health = probe_rpc_http(cookie_path=cookie_file)

    assert health.state == NodeLifecycleState.INCOMPATIBLE
    assert health.details == "incompatible_chain"


def test_probe_rpc_http_warming_up(tmp_path: Path) -> None:
    """Verify probe returns STARTING when RPC responds with warming up error code -28."""
    cookie_file = tmp_path / ".cookie"
    cookie_file.write_text("__cookie__:secret", encoding="utf-8")

    err = urllib.error.HTTPError(
        url="http://127.0.0.1:18443/",
        code=500,
        msg="Internal Server Error",
        hdrs={},  # type: ignore[arg-type]
        fp=MagicMock(
            read=lambda: json.dumps(
                {"error": {"code": -28, "message": "Loading block index..."}}
            ).encode("utf-8")
        ),
    )

    with patch("urllib.request.urlopen", side_effect=err):
        health = probe_rpc_http(cookie_path=cookie_file)

    assert health.state == NodeLifecycleState.STARTING
    assert health.details == "warming_up"


def test_probe_rpc_http_unauthorized(tmp_path: Path) -> None:
    """Verify probe returns UNHEALTHY when RPC returns 401 Unauthorized."""
    cookie_file = tmp_path / ".cookie"
    cookie_file.write_text("__cookie__:badsecret", encoding="utf-8")

    err = urllib.error.HTTPError(
        url="http://127.0.0.1:18443/",
        code=401,
        msg="Unauthorized",
        hdrs={},  # type: ignore[arg-type]
        fp=None,
    )

    with patch("urllib.request.urlopen", side_effect=err):
        health = probe_rpc_http(cookie_path=cookie_file)

    assert health.state == NodeLifecycleState.UNHEALTHY
    assert health.details == "authentication_failed"


def test_probe_rpc_http_malformed_response(tmp_path: Path) -> None:
    """Verify probe returns UNHEALTHY when RPC payload is malformed."""
    cookie_file = tmp_path / ".cookie"
    cookie_file.write_text("__cookie__:secret", encoding="utf-8")

    mock_resp = MagicMock()
    mock_resp.read.return_value = b"invalid json response"
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        health = probe_rpc_http(cookie_path=cookie_file)

    assert health.state == NodeLifecycleState.UNHEALTHY
    assert health.details == "malformed_rpc_response"
