"""Robust JSON-RPC health probe for Bitcoin Core regtest node."""

import base64
import http.client
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Final

from bitheim.bootstrap.logging import get_logger
from bitheim.domain.node import NodeHealth, NodeLifecycleState

logger = get_logger("infrastructure.bitcoin.rpc_probe")

EXPECTED_BITCOIN_VERSION: Final[int] = 310100
EXPECTED_CHAIN: Final[str] = "regtest"


def _read_cookie_auth_header(cookie_path: Path | str) -> str | None:
    """Read .cookie file and generate Basic authorization header value."""
    path = Path(cookie_path)
    if not path.exists() or not path.is_file():
        return None
    try:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return None
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        return f"Basic {encoded}"
    except (OSError, UnicodeDecodeError):
        return None


def probe_rpc_http(
    rpc_host: str = "127.0.0.1",
    rpc_port: int = 18443,
    cookie_path: Path | str | None = None,
    timeout: float = 2.0,
) -> NodeHealth:
    """Execute authenticated read-only JSON-RPC health check against Bitcoin Core over HTTP.

    Queries getblockchaininfo and getnetworkinfo and verifies exact version (310100)
    and chain (regtest).

    Args:
        rpc_host: Target Bitcoin Core RPC hostname or IP address.
        rpc_port: Target Bitcoin Core RPC port number.
        cookie_path: Optional path to .cookie file for authentication.
        timeout: Maximum duration in seconds to wait for each RPC response.

    Returns:
        NodeHealth indicating node lifecycle state, chain, version, blocks, and details.
    """
    if timeout <= 0:
        return NodeHealth(state=NodeLifecycleState.UNKNOWN, details="timeout_expired")
    safe_timeout = float(timeout)
    url = f"http://{rpc_host}:{rpc_port}/"

    auth_header: str | None = None
    if cookie_path is not None:
        auth_header = _read_cookie_auth_header(cookie_path)
        if auth_header is None:
            return NodeHealth(
                state=NodeLifecycleState.STARTING,
                details="cookie_file_unavailable",
            )

    # 1. Query getblockchaininfo
    chain_result = _send_rpc_call(url, "getblockchaininfo", auth_header, safe_timeout)
    if not chain_result.get("success"):
        return _categorize_rpc_failure(chain_result)

    chain_data = chain_result.get("data", {})
    if not isinstance(chain_data, dict):
        return NodeHealth(
            state=NodeLifecycleState.UNHEALTHY,
            details="malformed_blockchain_info",
        )

    chain = chain_data.get("chain")
    blocks = chain_data.get("blocks")
    headers = chain_data.get("headers")

    if not isinstance(chain, str) or chain != EXPECTED_CHAIN:
        logger.warning(
            "Bitcoin Core reported unexpected chain",
            extra={
                "event": "rpc_probe_incompatible_chain",
                "data": {"reported_chain": str(chain)},
            },
        )
        return NodeHealth(
            state=NodeLifecycleState.INCOMPATIBLE,
            chain=str(chain) if chain is not None else None,
            blocks=int(blocks) if isinstance(blocks, int) else None,
            headers=int(headers) if isinstance(headers, int) else None,
            details="incompatible_chain",
        )

    # 2. Query getnetworkinfo for exact version verification
    net_result = _send_rpc_call(url, "getnetworkinfo", auth_header, safe_timeout)
    if not net_result.get("success"):
        return _categorize_rpc_failure(net_result)

    net_data = net_result.get("data", {})
    if not isinstance(net_data, dict):
        return NodeHealth(
            state=NodeLifecycleState.UNHEALTHY,
            details="malformed_network_info",
        )

    version = net_data.get("version")
    if not isinstance(version, int) or version != EXPECTED_BITCOIN_VERSION:
        logger.warning(
            "Bitcoin Core reported incompatible version",
            extra={
                "event": "rpc_probe_incompatible_version",
                "data": {
                    "reported_version": version if isinstance(version, int) else None,
                    "expected_version": EXPECTED_BITCOIN_VERSION,
                },
            },
        )
        return NodeHealth(
            state=NodeLifecycleState.INCOMPATIBLE,
            chain=chain,
            version=version if isinstance(version, int) else None,
            blocks=int(blocks) if isinstance(blocks, int) else None,
            headers=int(headers) if isinstance(headers, int) else None,
            details="incompatible_version",
        )

    return NodeHealth(
        state=NodeLifecycleState.HEALTHY,
        chain=chain,
        version=version,
        blocks=int(blocks) if isinstance(blocks, int) else None,
        headers=int(headers) if isinstance(headers, int) else None,
        details="ready",
    )


def _send_rpc_call(
    url: str,
    method: str,
    auth_header: str | None,
    timeout: float,
) -> dict[str, Any]:
    """Dispatch a single JSON-RPC POST request and return parsed response or error."""
    payload = json.dumps({"jsonrpc": "1.0", "id": "bitheim-probe", "method": method, "params": []})
    headers = {"Content-Type": "application/json"}
    if auth_header is not None:
        headers["Authorization"] = auth_header

    req = urllib.request.Request(
        url,
        data=payload.encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                return {"success": False, "error_type": "malformed_response"}
            if data.get("error") is not None:
                err_obj = data["error"]
                code = err_obj.get("code") if isinstance(err_obj, dict) else None
                return {"success": False, "error_type": "rpc_error", "code": code}
            return {"success": True, "data": data.get("result")}
    except urllib.error.HTTPError as err:
        if err.code == 401:
            return {"success": False, "error_type": "unauthorized"}
        if err.code == 500:
            try:
                body = err.read().decode("utf-8")
                err_data = json.loads(body)
                if isinstance(err_data, dict) and isinstance(err_data.get("error"), dict):
                    code = err_data["error"].get("code")
                    if code == -28:
                        return {"success": False, "error_type": "warming_up", "code": -28}
            except Exception:
                pass
            return {"success": False, "error_type": "http_error", "status_code": err.code}
        return {"success": False, "error_type": "http_error", "status_code": err.code}
    except (urllib.error.URLError, TimeoutError, http.client.RemoteDisconnected, OSError):
        return {"success": False, "error_type": "connection_failed"}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"success": False, "error_type": "malformed_response"}


def _categorize_rpc_failure(res: dict[str, Any]) -> NodeHealth:
    """Map RPC dispatch error result into typed domain NodeHealth."""
    err_type = res.get("error_type", "unknown_error")
    if err_type == "warming_up" or res.get("code") == -28:
        return NodeHealth(state=NodeLifecycleState.STARTING, details="warming_up")
    if err_type == "unauthorized":
        return NodeHealth(state=NodeLifecycleState.UNHEALTHY, details="authentication_failed")
    if err_type == "connection_failed":
        return NodeHealth(state=NodeLifecycleState.STARTING, details="rpc_unreachable")
    if err_type == "malformed_response":
        return NodeHealth(state=NodeLifecycleState.UNHEALTHY, details="malformed_rpc_response")
    return NodeHealth(state=NodeLifecycleState.UNHEALTHY, details="rpc_error")
