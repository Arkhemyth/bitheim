"""Tests for Phase 3B.2b narrow corrections."""

import pytest

from bitheim.domain.errors import RpcMalformedResponseError
from bitheim.domain.node import PeerSummary
from bitheim.infrastructure.bitcoin.rpc_client import BitcoinRpcClient
from bitheim.infrastructure.compose.adapter import ComposeLifecycleAdapter


def test_delegated_peer_adapter_rejects_257_entries() -> None:
    adapter = ComposeLifecycleAdapter()
    data = {"peers": [{"peer_id": i} for i in range(257)]}
    with pytest.raises(
        RpcMalformedResponseError, match=r"Delegated peer output exceeds 256 items\."
    ):
        adapter._parse_peers(data)


def test_delegated_peer_adapter_rejects_duplicate_peer_id() -> None:
    adapter = ComposeLifecycleAdapter()
    peer_data = {
        "peer_id": 1,
        "endpoint": "localhost:18444",
        "network": "ipv4",
        "inbound": False,
        "connection_type": "outbound-full-relay",
        "protocol_version": 70016,
        "subversion": "/Satoshi:25.0.0/",
        "synced_headers": 0,
        "synced_blocks": 0,
        "ping_time_seconds": 0.1,
    }
    data = {"peers": [peer_data, peer_data]}
    with pytest.raises(
        RpcMalformedResponseError, match=r"Delegated peer output contains duplicate peer\."
    ):
        adapter._parse_peers(data)


def test_delegated_peer_adapter_sorts_peers() -> None:
    adapter = ComposeLifecycleAdapter()

    def make_peer(pid: int) -> dict[str, object]:
        return {
            "peer_id": pid,
            "endpoint": f"localhost:{18444 + pid}",
            "network": "ipv4",
            "inbound": False,
            "connection_type": "outbound-full-relay",
            "protocol_version": 70016,
            "subversion": "/Satoshi:25.0.0/",
            "synced_headers": 0,
            "synced_blocks": 0,
            "ping_time_seconds": 0.1,
        }

    data = {"peers": [make_peer(5), make_peer(1)]}
    peers = adapter._parse_peers(data)
    assert peers[0].peer_id == 1
    assert peers[1].peer_id == 5


def test_null_ping_time_serialization() -> None:
    summary = PeerSummary(
        peer_id=1,
        endpoint="localhost:18444",
        network="ipv4",
        inbound=False,
        connection_type="outbound-full-relay",
        protocol_version=70016,
        subversion="/Satoshi:25.0.0/",
        synced_headers=0,
        synced_blocks=0,
        ping_time_seconds=None,
    )
    d = summary.to_dict()
    assert "ping_time_seconds" in d
    assert d["ping_time_seconds"] is None


def test_safe_duplicate_error_text_in_rpc_client() -> None:
    from decimal import Decimal

    peer_data = {
        "id": 1,
        "addr": "localhost:18444",
        "network": "ipv4",
        "inbound": False,
        "connection_type": "outbound-full-relay",
        "version": 70016,
        "subver": "/Satoshi:25.0.0/",
        "synced_headers": 0,
        "synced_blocks": 0,
        "pingtime": Decimal("0.1"),
    }

    class MockClient(BitcoinRpcClient):
        def _send_request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return [peer_data, peer_data]

    client = MockClient()
    with pytest.raises(RpcMalformedResponseError) as exc_info:
        client.get_peers()
    assert str(exc_info.value) == "RPC getpeerinfo returned duplicate peer."
    assert "1" not in str(exc_info.value)


def test_ci_workflow_delegated_peer_inspection() -> None:
    from pathlib import Path

    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    # Assert network is ci-integration_bitheim-net and not ci-integration_default
    assert "--network ci-integration_bitheim-net" in workflow
    assert "--network ci-integration_default" not in workflow

    # Assert bounded polling and cleanup
    assert "for i in {1..30}; do" in workflow
    assert "sleep 1" in workflow
    assert "trap 'docker stop ci-temp-peer" in workflow

    # Assert it fails early with categorical message
    assert "docker inspect --format '{{.State.Running}}' ci-temp-peer" in workflow
    assert ')" != "true" ]; then' in workflow
    assert "Error: ci-temp-peer exited prematurely." in workflow
    assert "exit 1" in workflow

    # Assert deterministic outbound connection and rpcbind
    assert "-connect=bitcoin-core:18444" in workflow
    assert "-rpcbind=0.0.0.0" in workflow
    assert "-addnode=bitcoin-core:18444" not in workflow

    # Assert it does not echo the payload
    assert 'echo "${PEERS_JSON}"' not in workflow

    # Assert it checks the optional field types
    assert 'synced_headers | (type == "number" or type == "null")' in workflow
    assert 'synced_blocks | (type == "number" or type == "null")' in workflow
    assert 'ping_time_seconds | (type == "number" or type == "null")' in workflow
