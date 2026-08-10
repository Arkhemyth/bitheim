"""Unit tests for NodeObservationService application service and domain ports."""

from unittest.mock import MagicMock

import pytest

from bitheim.application.ports import NodeObservationPort
from bitheim.application.service import NodeObservationService
from bitheim.domain.errors import (
    RpcError,
    RpcIncompatibleNodeError,
    RpcTimeoutError,
    RpcUnavailableError,
)
from bitheim.domain.node import NodeOverview


def _make_overview() -> NodeOverview:
    return NodeOverview(
        version=310100,
        subversion="/Satoshi:31.1.0/",
        network_active=True,
        connections=8,
        chain="regtest",
        blocks=100,
        headers=100,
        best_block_hash="0f9188f13cb7b2c71f2a335e3a4fc328bf5beb436012afca590b1a11466e2206",
        median_time=1296688602,
        initial_block_download=False,
        pruned=False,
        chainwork="0000000000000000000000000000000000000000000000000000000000000002",
    )


def test_observation_service_success() -> None:
    """Verify NodeObservationService delegates to port and returns NodeOverview."""
    expected = _make_overview()
    mock_port = MagicMock(spec=NodeObservationPort)
    mock_port.get_node_overview.return_value = expected

    service = NodeObservationService(observation_port=mock_port)
    overview = service.inspect_node(timeout=15.0)

    assert overview == expected
    mock_port.get_node_overview.assert_called_once_with(timeout=15.0)


def test_observation_service_invalid_timeout() -> None:
    """Verify NodeObservationService validates timeout boundaries."""
    mock_port = MagicMock(spec=NodeObservationPort)
    service = NodeObservationService(observation_port=mock_port)

    with pytest.raises(RpcError) as exc_info:
        service.inspect_node(timeout=-5.0)
    assert "deadline" in str(exc_info.value).lower()

    with pytest.raises(RpcError):
        service.inspect_node(timeout=61.0)


def test_observation_service_propagates_rpc_errors() -> None:
    """Verify NodeObservationService preserves typed domain RpcErrors without modification."""
    mock_port = MagicMock(spec=NodeObservationPort)
    mock_port.get_node_overview.side_effect = RpcIncompatibleNodeError("Incompatible node version")

    service = NodeObservationService(observation_port=mock_port)
    with pytest.raises(RpcIncompatibleNodeError):
        service.inspect_node()

    mock_port.get_node_overview.side_effect = RpcUnavailableError("Node stopped")
    with pytest.raises(RpcUnavailableError):
        service.inspect_node()

    mock_port.get_node_overview.side_effect = RpcTimeoutError("Operation timed out")
    with pytest.raises(RpcTimeoutError):
        service.inspect_node()
