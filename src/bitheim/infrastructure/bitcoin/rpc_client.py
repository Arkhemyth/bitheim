"""Secure, synchronous standard library JSON-RPC client for Bitcoin Core node observation."""

import base64
import contextlib
import http.client
import json
import math
import os
import re
import stat
import time
import urllib.error
import urllib.request
from decimal import Decimal, DecimalException
from pathlib import Path
from typing import Any, Final

from bitheim.application.ports import NodeObservationPort
from bitheim.bootstrap.logging import get_logger
from bitheim.domain.errors import (
    RpcAuthenticationError,
    RpcError,
    RpcIncompatibleNodeError,
    RpcMalformedResponseError,
    RpcProtocolError,
    RpcResourceNotFoundError,
    RpcResponseSizeExceededError,
    RpcTimeoutError,
    RpcUnavailableError,
)
from bitheim.domain.node import BlockSummary, MempoolSummary, NodeOverview, PeerSummary

logger = get_logger("infrastructure.bitcoin.rpc_client")

# Contractual limits and invariants governed by SPEC-0005
DEFAULT_RPC_HOST: Final[str] = "bitcoin-core"
DEFAULT_RPC_PORT: Final[int] = 18443
DEFAULT_COOKIE_PATH: Final[Path] = Path("/data/rpc/.cookie")

ALLOWED_RPC_HOSTS: Final[frozenset[str]] = frozenset({"bitcoin-core"})
ALLOWED_RPC_METHODS: Final[frozenset[str]] = frozenset(
    {
        "getnetworkinfo",
        "getblockchaininfo",
        "getblockhash",
        "getblock",
        "getmempoolinfo",
        "getpeerinfo",
    }
)

MAX_COOKIE_SIZE_BYTES: Final[int] = 4096  # 4 KiB
MAX_RESPONSE_SIZE_BYTES: Final[int] = 4 * 1024 * 1024  # 4 MiB
MAX_JSON_DEPTH: Final[int] = 32
MAX_TEXT_FIELD_BYTES: Final[int] = 512
DEFAULT_DEADLINE_SECONDS: Final[float] = 10.0
MAX_DEADLINE_SECONDS: Final[float] = 60.0

EXPECTED_BITCOIN_VERSION: Final[int] = 310100
EXPECTED_CHAIN: Final[str] = "regtest"

_HEX_64_REGEX = re.compile(r"^[0-9a-f]{64}$")

SAFE_RPC_ERROR_MAPPINGS: Final[dict[int, str]] = {
    -28: "Bitcoin Core is warming up or loading block index.",
    -18: "Bitcoin Core RPC client in warmup.",
    -32600: "Invalid JSON-RPC request.",
    -32601: "RPC method not found.",
    -32602: "Invalid RPC parameters.",
    -32603: "Internal JSON-RPC error.",
}


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Custom HTTP redirect handler that unconditionally rejects all redirects."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        raise RpcUnavailableError("HTTP redirects are rejected by RPC boundary.")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Object pairs hook for json.loads that rejects duplicate keys."""
    res: dict[str, Any] = {}
    for k, v in pairs:
        if k in res:
            raise ValueError(f"Duplicate JSON key: {k}")
        res[k] = v
    return res


def _check_json_depth(obj: Any, depth: int = 1) -> None:
    """Recursively verify that JSON object depth does not exceed maximum nesting limit."""
    if depth > MAX_JSON_DEPTH:
        raise RpcMalformedResponseError("RPC response exceeds maximum JSON nesting depth.")
    if isinstance(obj, dict):
        for v in obj.values():
            _check_json_depth(v, depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            _check_json_depth(item, depth + 1)


class BitcoinRpcClient(NodeObservationPort):
    """Secure synchronous standard library JSON-RPC client for Bitcoin Core."""

    def __init__(
        self,
        rpc_host: str = DEFAULT_RPC_HOST,
        rpc_port: int = DEFAULT_RPC_PORT,
        cookie_path: Path | str = DEFAULT_COOKIE_PATH,
        opener: urllib.request.OpenerDirector | None = None,
    ) -> None:
        if rpc_host != DEFAULT_RPC_HOST:
            raise RpcError("Invalid RPC host.")
        if rpc_port != DEFAULT_RPC_PORT:
            raise RpcError("Invalid RPC port.")
        if Path(cookie_path) != DEFAULT_COOKIE_PATH:
            raise RpcError("Invalid RPC cookie path.")

        self._rpc_host = rpc_host
        self._rpc_port = rpc_port
        self._cookie_path = DEFAULT_COOKIE_PATH
        self._url = f"http://{self._rpc_host}:{self._rpc_port}/"
        self._opener = opener or urllib.request.build_opener(_NoRedirectHandler)

    def _read_cookie_header(self) -> str:
        """Read and validate the cookie file immediately before request dispatch.

        Enforces per-request read without caching, symlink rejection, secure permissions,
        bounded read, no newline/whitespace trimming, and fails closed without leaking paths.
        """
        cookie_path_str = str(self._cookie_path)
        try:
            lstat_res = os.lstat(cookie_path_str)
        except OSError:
            raise RpcAuthenticationError("RPC cookie is unavailable or inaccessible.") from None

        if stat.S_ISLNK(lstat_res.st_mode):
            raise RpcAuthenticationError("RPC cookie must not be a symbolic link.") from None

        if not stat.S_ISREG(lstat_res.st_mode):
            raise RpcAuthenticationError("RPC cookie must be a regular file.") from None

        # Reject if group write/execute or any other permissions (0o037)
        if lstat_res.st_mode & 0o037 != 0:
            raise RpcAuthenticationError("RPC cookie has insecure write permissions.") from None

        if lstat_res.st_size == 0:
            raise RpcAuthenticationError("RPC cookie is empty.") from None
        if lstat_res.st_size > MAX_COOKIE_SIZE_BYTES:
            raise RpcAuthenticationError("RPC cookie exceeds maximum allowed size.") from None

        # Race-conscious bounded read via file descriptor
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW

        try:
            fd = os.open(cookie_path_str, flags)
        except OSError:
            raise RpcAuthenticationError("RPC cookie is unavailable or inaccessible.") from None

        try:
            fstat_res = os.fstat(fd)
            if not stat.S_ISREG(fstat_res.st_mode):
                raise RpcAuthenticationError("RPC cookie must be a regular file.") from None
            if fstat_res.st_mode & 0o037 != 0:
                raise RpcAuthenticationError("RPC cookie has insecure write permissions.") from None
            if fstat_res.st_ino != lstat_res.st_ino or fstat_res.st_dev != lstat_res.st_dev:
                raise RpcAuthenticationError("RPC cookie identity changed during read.") from None
            if fstat_res.st_size == 0:
                raise RpcAuthenticationError("RPC cookie is empty.") from None
            if fstat_res.st_size > MAX_COOKIE_SIZE_BYTES:
                raise RpcAuthenticationError("RPC cookie exceeds maximum allowed size.") from None

            content_bytes = os.read(fd, MAX_COOKIE_SIZE_BYTES + 1)
            if len(content_bytes) > MAX_COOKIE_SIZE_BYTES:
                raise RpcAuthenticationError("RPC cookie exceeds maximum allowed size.") from None
            if not content_bytes:
                raise RpcAuthenticationError("RPC cookie is empty.") from None
        except RpcAuthenticationError:
            raise
        except OSError:
            raise RpcAuthenticationError("Failed to read RPC cookie.") from None
        finally:
            with contextlib.suppress(OSError):
                os.close(fd)

        try:
            content_str = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raise RpcAuthenticationError("RPC cookie contains invalid UTF-8 encoding.") from None

        # Exact credential contract: username:password or username:password\n
        if content_str.endswith("\n"):
            content_str = content_str[:-1]
        if "\r" in content_str or "\n" in content_str:
            raise RpcAuthenticationError(
                "RPC cookie contains invalid newline characters."
            ) from None
        if content_str != content_str.strip():
            raise RpcAuthenticationError(
                "RPC cookie contains leading or trailing whitespace."
            ) from None
        if ":" not in content_str:
            raise RpcAuthenticationError("RPC cookie format is invalid.") from None

        parts = content_str.split(":", 1)
        if not parts[0] or not parts[1]:
            raise RpcAuthenticationError("RPC cookie format is invalid.") from None

        encoded = base64.b64encode(content_str.encode("utf-8")).decode("ascii")
        return f"Basic {encoded}"

    def _send_request(
        self,
        method: str,
        params: list[Any],
        req_id: str,
        deadline: float,
    ) -> Any:
        """Dispatch a single authenticated JSON-RPC request under the shared deadline."""
        if method not in ALLOWED_RPC_METHODS:
            raise RpcError("RPC method is not permitted.")

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RpcTimeoutError("Command deadline expired before RPC dispatch.") from None

        auth_header = self._read_cookie_header()

        remaining_after_auth = deadline - time.monotonic()
        if remaining_after_auth <= 0:
            raise RpcTimeoutError("Command deadline expired after reading cookie.") from None

        payload = {
            "jsonrpc": "1.0",
            "id": req_id,
            "method": method,
            "params": params,
        }
        try:
            payload_bytes = json.dumps(payload).encode("utf-8")
        except (TypeError, ValueError):
            raise RpcMalformedResponseError("Failed to serialize RPC request.") from None

        headers = {
            "Content-Type": "application/json",
            "Authorization": auth_header,
        }
        req = urllib.request.Request(
            self._url,
            data=payload_bytes,
            headers=headers,
            method="POST",
        )

        logger.debug(
            "Dispatching RPC request",
            extra={"event": "rpc_request_started", "data": {"method": method}},
        )

        try:
            with self._opener.open(req, timeout=remaining_after_auth) as resp:
                result = self._read_and_parse_envelope(resp, req_id, deadline)
        except urllib.error.HTTPError as err:
            if err.code in (401, 403):
                raise RpcAuthenticationError(
                    "RPC authentication rejected by Bitcoin Core."
                ) from None
            if err.code == 500:
                self._read_and_parse_envelope(err, req_id, deadline)
                raise RpcProtocolError(
                    "Bitcoin Core returned HTTP 500 without a valid RPC error envelope."
                ) from None
            raise RpcUnavailableError(f"RPC endpoint returned HTTP status {err.code}.") from None
        except (
            urllib.error.URLError,
            TimeoutError,
            http.client.RemoteDisconnected,
            OSError,
        ) as err:
            if isinstance(err, TimeoutError) or (
                isinstance(err, urllib.error.URLError) and isinstance(err.reason, TimeoutError)
            ):
                raise RpcTimeoutError("RPC request timed out.") from None
            raise RpcUnavailableError("Unable to connect to Bitcoin Core RPC endpoint.") from None

        logger.debug(
            "RPC request succeeded",
            extra={"event": "rpc_request_succeeded", "data": {"method": method}},
        )
        return result

    def _apply_response_timeout(self, resp: Any, timeout: float) -> None:
        """Apply timeout to the underlying socket or double before a blocking read."""
        if hasattr(resp, "settimeout"):
            resp.settimeout(timeout)
        else:
            sock = getattr(getattr(resp, "fp", None), "raw", None)
            real_sock = getattr(sock, "_sock", None)
            if real_sock is not None and hasattr(real_sock, "settimeout"):
                real_sock.settimeout(timeout)

    def _read_and_parse_envelope(self, resp: Any, req_id: str, deadline: float) -> Any:
        """Read and parse the JSON-RPC envelope under a strict deadline and size limit."""
        chunks: list[bytes] = []
        total_bytes = 0
        while True:
            remaining_chunk = deadline - time.monotonic()
            if remaining_chunk <= 0:
                raise RpcTimeoutError(
                    "Timeout budget expired while reading response payload."
                ) from None

            self._apply_response_timeout(resp, remaining_chunk)
            try:
                chunk = resp.read(65536)
            except (TimeoutError, OSError) as e:
                if isinstance(e, TimeoutError) or "timed out" in str(e).lower():
                    raise RpcTimeoutError(
                        "Timeout budget expired while reading response payload."
                    ) from None
                raise RpcUnavailableError("Socket error while reading response payload.") from None
            if deadline - time.monotonic() <= 0:
                raise RpcTimeoutError(
                    "Timeout budget expired while reading response payload."
                ) from None
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > MAX_RESPONSE_SIZE_BYTES:
                raise RpcResponseSizeExceededError(
                    "RPC response payload exceeded maximum size limit."
                )
            chunks.append(chunk)
        body_bytes = b"".join(chunks)

        try:
            raw_text = body_bytes.decode("utf-8")
            data = json.loads(
                raw_text, object_pairs_hook=_reject_duplicate_keys, parse_float=Decimal
            )
        except UnicodeDecodeError:
            raise RpcMalformedResponseError("RPC response is not valid UTF-8.") from None
        except (json.JSONDecodeError, ValueError):
            raise RpcMalformedResponseError(
                "RPC response is not valid JSON or contains duplicate keys."
            ) from None

        if not isinstance(data, dict):
            raise RpcMalformedResponseError("RPC response envelope must be a JSON object.")

        _check_json_depth(data, depth=1)

        if "id" not in data or "result" not in data or "error" not in data:
            raise RpcMalformedResponseError("RPC response envelope missing required members.")

        if data["id"] != req_id:
            raise RpcMalformedResponseError("RPC response ID does not match request ID.")

        # Exclusivity: exactly one of result or non-null error
        if data["error"] is not None:
            if data["result"] is not None:
                raise RpcMalformedResponseError(
                    "RPC response envelope contains both result and error."
                )
            if not isinstance(data["error"], dict):
                raise RpcMalformedResponseError("RPC error member must be a JSON object.")
            code = data["error"].get("code")
            if type(code) is not int or isinstance(code, bool):
                raise RpcMalformedResponseError("RPC error code must be a valid integer.")

            if code == -5:
                raise RpcResourceNotFoundError("RPC resource not found.")

            safe_msg = SAFE_RPC_ERROR_MAPPINGS.get(
                code, f"Bitcoin Core returned RPC error code {code}."
            )
            raise RpcProtocolError(safe_msg) from None

        if data["result"] is None:
            raise RpcMalformedResponseError("RPC result member cannot be null.")

        return data["result"]

    def get_node_overview(self, timeout: float = DEFAULT_DEADLINE_SECONDS) -> NodeOverview:
        """Retrieve validated node and blockchain overview facts under one shared deadline.

        SPEC-0005 §5 & §8.1: Validates version 310100 and chain regtest under
        shared monotonic deadline.
        """
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool):
            raise RpcError("Parameter 'timeout' must be a numeric value.")
        float_timeout = float(timeout)
        if (
            float_timeout <= 0
            or math.isnan(float_timeout)
            or math.isinf(float_timeout)
            or float_timeout > MAX_DEADLINE_SECONDS
        ):
            raise RpcError("Command deadline must be a positive finite value no greater than 60s.")

        deadline = time.monotonic() + float_timeout

        net_info = self._send_request(
            "getnetworkinfo", [], req_id="bitheim-req-1", deadline=deadline
        )
        if not isinstance(net_info, dict):
            raise RpcMalformedResponseError("RPC result must be a JSON object.")

        # 1. Validate getnetworkinfo fields
        version = net_info.get("version")
        if type(version) is not int or isinstance(version, bool):
            raise RpcMalformedResponseError("Field 'version' must be an integer.")

        subversion = net_info.get("subversion")
        if (
            not isinstance(subversion, str)
            or not (0 < len(subversion.encode("utf-8")) <= MAX_TEXT_FIELD_BYTES)
            or not all(" " <= c <= "~" for c in subversion)
        ):
            raise RpcMalformedResponseError(
                "Field 'subversion' must be a bounded printable ASCII string."
            )

        network_active = net_info.get("networkactive")
        if not isinstance(network_active, bool):
            raise RpcMalformedResponseError("Field 'networkactive' must be a boolean.")

        connections = net_info.get("connections")
        if type(connections) is not int or isinstance(connections, bool) or connections < 0:
            raise RpcMalformedResponseError("Field 'connections' must be a non-negative integer.")

        if version != EXPECTED_BITCOIN_VERSION:
            raise RpcIncompatibleNodeError(
                f"Incompatible Bitcoin Core version: got {version}, "
                f"expected {EXPECTED_BITCOIN_VERSION}"
            )

        chain_info = self._send_request(
            "getblockchaininfo", [], req_id="bitheim-req-2", deadline=deadline
        )
        if not isinstance(chain_info, dict):
            raise RpcMalformedResponseError("RPC result must be a JSON object.")

        # 2. Validate getblockchaininfo fields
        chain = chain_info.get("chain")
        if not isinstance(chain, str) or len(chain.encode("utf-8")) > MAX_TEXT_FIELD_BYTES:
            raise RpcMalformedResponseError("Field 'chain' must be a bounded string.")

        blocks = chain_info.get("blocks")
        if type(blocks) is not int or isinstance(blocks, bool) or blocks < 0:
            raise RpcMalformedResponseError("Field 'blocks' must be a non-negative integer.")

        headers = chain_info.get("headers")
        if type(headers) is not int or isinstance(headers, bool) or headers < 0:
            raise RpcMalformedResponseError("Field 'headers' must be a non-negative integer.")

        best_block_hash = chain_info.get("bestblockhash")
        if not isinstance(best_block_hash, str) or not _HEX_64_REGEX.match(best_block_hash):
            raise RpcMalformedResponseError(
                "Field 'bestblockhash' must be a 64-character lowercase hexadecimal string."
            )

        median_time = chain_info.get("mediantime")
        if type(median_time) is not int or isinstance(median_time, bool) or median_time < 0:
            raise RpcMalformedResponseError("Field 'mediantime' must be a non-negative integer.")

        initial_block_download = chain_info.get("initialblockdownload")
        if not isinstance(initial_block_download, bool):
            raise RpcMalformedResponseError("Field 'initialblockdownload' must be a boolean.")

        pruned = chain_info.get("pruned")
        if not isinstance(pruned, bool):
            raise RpcMalformedResponseError("Field 'pruned' must be a boolean.")

        raw_chainwork = chain_info.get("chainwork")
        chainwork: str | None = None
        if raw_chainwork is not None:
            if not isinstance(raw_chainwork, str) or not _HEX_64_REGEX.match(raw_chainwork):
                raise RpcMalformedResponseError(
                    "Field 'chainwork' must be a 64-character lowercase hexadecimal string."
                )
            chainwork = raw_chainwork

        # 3. Independent identity enforcement (SPEC-0005 §8.1)
        if chain != EXPECTED_CHAIN:
            raise RpcIncompatibleNodeError(
                f"Incompatible chain: expected '{EXPECTED_CHAIN}', got '{chain}'."
            )

        try:
            return NodeOverview(
                version=version,
                subversion=subversion,
                network_active=network_active,
                connections=connections,
                chain=chain,
                blocks=blocks,
                headers=headers,
                best_block_hash=best_block_hash,
                median_time=median_time,
                initial_block_download=initial_block_download,
                pruned=pruned,
                chainwork=chainwork,
            )
        except ValueError as err:
            raise RpcMalformedResponseError(f"Invalid domain overview facts: {err}") from None

    def get_block(
        self,
        *,
        block_hash: str | None = None,
        height: int | None = None,
        timeout: float = DEFAULT_DEADLINE_SECONDS,
    ) -> BlockSummary:
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool):
            raise RpcError("Parameter 'timeout' must be a numeric value.")
        float_timeout = float(timeout)
        if (
            float_timeout <= 0
            or math.isnan(float_timeout)
            or math.isinf(float_timeout)
            or float_timeout > MAX_DEADLINE_SECONDS
        ):
            raise RpcError("Command deadline must be a positive finite value no greater than 60s.")

        has_hash = block_hash is not None
        has_height = height is not None
        if has_hash == has_height:
            raise RpcError("Exactly one of block_hash or height must be provided.")

        deadline = time.monotonic() + float_timeout

        if has_height:
            if type(height) is not int or isinstance(height, bool) or height < 0:
                raise RpcError("Height must be a non-negative integer.")
            hash_res = self._send_request(
                "getblockhash", [height], req_id="bitheim-req-hash", deadline=deadline
            )
            if not isinstance(hash_res, str):
                raise RpcMalformedResponseError("getblockhash result must be a string.")
            resolved_hash = hash_res
        else:
            resolved_hash = str(block_hash)

        if not _HEX_64_REGEX.match(resolved_hash):
            raise RpcMalformedResponseError("Resolved block hash is invalid.")

        block_data = self._send_request(
            "getblock", [resolved_hash, 1], req_id="bitheim-req-block", deadline=deadline
        )
        if not isinstance(block_data, dict):
            raise RpcMalformedResponseError("getblock result must be a JSON object.")

        summary = self._parse_block_summary(block_data)
        if summary.hash != resolved_hash:
            raise RpcMalformedResponseError(
                "Returned block hash does not match requested block hash."
            )
        return summary

    def _parse_block_summary(self, data: dict[str, Any]) -> BlockSummary:
        hash_val = data.get("hash")
        if not isinstance(hash_val, str) or not _HEX_64_REGEX.match(hash_val):
            raise RpcMalformedResponseError("Field 'hash' must be a valid 64-character hex string.")

        height = data.get("height")
        if type(height) is not int or isinstance(height, bool) or height < 0:
            raise RpcMalformedResponseError("Field 'height' must be a non-negative integer.")

        confirmations = data.get("confirmations")
        if type(confirmations) is not int or isinstance(confirmations, bool) or confirmations < 0:
            raise RpcMalformedResponseError("Field 'confirmations' must be a non-negative integer.")

        timestamp = data.get("time")
        if type(timestamp) is not int or isinstance(timestamp, bool) or timestamp < 0:
            raise RpcMalformedResponseError("Field 'time' must be a non-negative integer.")

        tx = data.get("tx")
        if not isinstance(tx, list):
            raise RpcMalformedResponseError("Field 'tx' must be a list.")
        for txid in tx:
            if not isinstance(txid, str) or not _HEX_64_REGEX.match(txid):
                raise RpcMalformedResponseError(
                    "Field 'tx' must contain only 64-character hex strings."
                )
        transaction_count = len(tx)

        size = data.get("size")
        if type(size) is not int or isinstance(size, bool) or size < 0:
            raise RpcMalformedResponseError("Field 'size' must be a non-negative integer.")

        weight = data.get("weight")
        if type(weight) is not int or isinstance(weight, bool) or weight < 0:
            raise RpcMalformedResponseError("Field 'weight' must be a non-negative integer.")

        previousblockhash = data.get("previousblockhash")
        if previousblockhash is not None and (
            not isinstance(previousblockhash, str) or not _HEX_64_REGEX.match(previousblockhash)
        ):
            raise RpcMalformedResponseError(
                "Field 'previousblockhash' must be a valid hex string or missing."
            )

        nextblockhash = data.get("nextblockhash")
        if nextblockhash is not None and (
            not isinstance(nextblockhash, str) or not _HEX_64_REGEX.match(nextblockhash)
        ):
            raise RpcMalformedResponseError(
                "Field 'nextblockhash' must be a valid hex string or missing."
            )

        return BlockSummary(
            hash=hash_val,
            height=height,
            confirmations=confirmations,
            timestamp=timestamp,
            transaction_count=transaction_count,
            size=size,
            weight=weight,
            previous_block_hash=previousblockhash,
            next_block_hash=nextblockhash,
        )

    def get_mempool(self, timeout: float = DEFAULT_DEADLINE_SECONDS) -> MempoolSummary:
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool):
            raise RpcError("Parameter 'timeout' must be a numeric value.")
        float_timeout = float(timeout)
        if (
            float_timeout <= 0
            or math.isnan(float_timeout)
            or math.isinf(float_timeout)
            or float_timeout > MAX_DEADLINE_SECONDS
        ):
            raise RpcError("Command deadline must be a positive finite value no greater than 60s.")

        deadline = time.monotonic() + float_timeout

        mempool_data = self._send_request(
            "getmempoolinfo", [], req_id="bitheim-req-mempool", deadline=deadline
        )
        if not isinstance(mempool_data, dict):
            raise RpcMalformedResponseError("getmempoolinfo result must be a JSON object.")

        return self._parse_mempool_summary(mempool_data)

    def _parse_mempool_summary(self, data: dict[str, Any]) -> MempoolSummary:
        loaded = data.get("loaded")
        if type(loaded) is not bool:
            raise RpcMalformedResponseError("Field 'loaded' must be a boolean.")

        size = data.get("size")
        if type(size) is not int or isinstance(size, bool) or size < 0:
            raise RpcMalformedResponseError("Field 'size' must be a non-negative integer.")

        bytes_val = data.get("bytes")
        if type(bytes_val) is not int or isinstance(bytes_val, bool) or bytes_val < 0:
            raise RpcMalformedResponseError("Field 'bytes' must be a non-negative integer.")

        usage = data.get("usage")
        if type(usage) is not int or isinstance(usage, bool) or usage < 0:
            raise RpcMalformedResponseError("Field 'usage' must be a non-negative integer.")

        maxmempool = data.get("maxmempool")
        if type(maxmempool) is not int or isinstance(maxmempool, bool) or maxmempool < 0:
            raise RpcMalformedResponseError("Field 'maxmempool' must be a non-negative integer.")

        total_fee = data.get("total_fee")
        if not isinstance(total_fee, Decimal):
            raise RpcMalformedResponseError("Field 'total_fee' must be exactly a Decimal.")

        if not total_fee.is_finite() or total_fee < 0:
            raise RpcMalformedResponseError(
                "Field 'total_fee' must be a non-negative finite value."
            )

        # Convert to exact satoshis
        try:
            fee_sats = total_fee * Decimal("100000000")
            if fee_sats != fee_sats.to_integral_value():
                raise RpcMalformedResponseError(
                    "Field 'total_fee' cannot have sub-satoshi precision."
                )
            total_fees_satoshis = int(fee_sats)
        except (DecimalException, OverflowError, ValueError):
            raise RpcMalformedResponseError("Field 'total_fee' conversion failed.") from None

        try:
            return MempoolSummary(
                loaded=loaded,
                transaction_count=size,
                serialized_bytes=bytes_val,
                dynamic_memory_usage=usage,
                max_memory=maxmempool,
                total_fees_satoshis=total_fees_satoshis,
            )
        except ValueError:
            raise RpcMalformedResponseError("Invalid domain mempool facts.") from None

    def get_peers(self, timeout: float = DEFAULT_DEADLINE_SECONDS) -> tuple[PeerSummary, ...]:
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool):
            raise RpcError("Parameter 'timeout' must be a numeric value.")
        float_timeout = float(timeout)
        if (
            float_timeout <= 0
            or math.isnan(float_timeout)
            or math.isinf(float_timeout)
            or float_timeout > MAX_DEADLINE_SECONDS
        ):
            raise RpcError("Command deadline must be a positive finite value no greater than 60s.")

        deadline = time.monotonic() + float_timeout

        peers_data = self._send_request(
            "getpeerinfo", [], req_id="bitheim-req-peers", deadline=deadline
        )
        if not isinstance(peers_data, list):
            raise RpcMalformedResponseError("getpeerinfo result must be a JSON array.")

        if len(peers_data) > 256:
            raise RpcMalformedResponseError("getpeerinfo returned more than 256 peers.")

        parsed_peers = []
        peer_ids = set()
        for p in peers_data:
            if not isinstance(p, dict):
                raise RpcMalformedResponseError("Each peer must be a JSON object.")
            peer = self._parse_peer(p)
            if peer.peer_id in peer_ids:
                raise RpcMalformedResponseError("RPC getpeerinfo returned duplicate peer.")
            peer_ids.add(peer.peer_id)
            parsed_peers.append(peer)

        parsed_peers.sort(key=lambda peer_obj: peer_obj.peer_id)
        return tuple(parsed_peers)

    def _parse_peer(self, data: dict[str, Any]) -> PeerSummary:
        peer_id = data.get("id")
        if type(peer_id) is not int or isinstance(peer_id, bool) or peer_id < 0:
            raise RpcMalformedResponseError("Field 'id' must be a non-negative integer.")

        endpoint = data.get("addr")
        if not isinstance(endpoint, str):
            raise RpcMalformedResponseError("Field 'addr' must be a string.")

        network = data.get("network")
        if not isinstance(network, str):
            raise RpcMalformedResponseError("Field 'network' must be a string.")

        inbound = data.get("inbound")
        if type(inbound) is not bool:
            raise RpcMalformedResponseError("Field 'inbound' must be a boolean.")

        connection_type = data.get("connection_type")
        if not isinstance(connection_type, str):
            raise RpcMalformedResponseError("Field 'connection_type' must be a string.")

        version = data.get("version")
        if type(version) is not int or isinstance(version, bool) or version < 0:
            raise RpcMalformedResponseError("Field 'version' must be a non-negative integer.")

        subver = data.get("subver")
        if not isinstance(subver, str):
            raise RpcMalformedResponseError("Field 'subver' must be a string.")

        synced_headers = data.get("synced_headers")
        if (
            type(synced_headers) is not int
            or isinstance(synced_headers, bool)
            or synced_headers < -1
        ):
            raise RpcMalformedResponseError("Field 'synced_headers' must be an integer >= -1.")
        mapped_headers = None if synced_headers == -1 else synced_headers

        synced_blocks = data.get("synced_blocks")
        if type(synced_blocks) is not int or isinstance(synced_blocks, bool) or synced_blocks < -1:
            raise RpcMalformedResponseError("Field 'synced_blocks' must be an integer >= -1.")
        mapped_blocks = None if synced_blocks == -1 else synced_blocks

        ping_time_seconds = None
        if "pingtime" in data:
            pt = data["pingtime"]
            if not isinstance(pt, Decimal):
                raise RpcMalformedResponseError("Field 'pingtime' must be a Decimal.")
            if not pt.is_finite() or pt < 0:
                raise RpcMalformedResponseError(
                    "Field 'pingtime' must be a finite non-negative Decimal."
                )
            try:
                ping_time_seconds = float(pt)
            except OverflowError:
                raise RpcMalformedResponseError("Field 'pingtime' conversion failed.") from None

        try:
            return PeerSummary(
                peer_id=peer_id,
                endpoint=endpoint,
                network=network,
                inbound=inbound,
                connection_type=connection_type,
                protocol_version=version,
                subversion=subver,
                synced_headers=mapped_headers,
                synced_blocks=mapped_blocks,
                ping_time_seconds=ping_time_seconds,
            )
        except ValueError:
            raise RpcMalformedResponseError("Invalid domain peer facts.") from None
