"""Unit tests for the application lifecycle orchestration service using a typed fake port."""

import pytest

from bitheim.application.ports import NodeLifecyclePort
from bitheim.application.service import NodeLifecycleService
from bitheim.domain.errors import (
    LifecycleError,
    NodeIncompatibleError,
    StartupTimeoutError,
)
from bitheim.domain.node import NodeHealth, NodeLifecycleState, NodeStatus


class FakeLifecyclePort(NodeLifecyclePort):
    """Deterministic typed fake port for unit testing service orchestration."""

    def __init__(
        self,
        initial_state: NodeLifecycleState = NodeLifecycleState.STOPPED,
        initial_health: NodeHealth | None = None,
        health_sequence: list[NodeHealth] | None = None,
    ) -> None:
        self.state = initial_state
        self.health = initial_health or NodeHealth(state=initial_state)
        self.health_sequence = health_sequence or []
        self.start_called_with: list[tuple[str, float]] = []
        self.stop_called_with: list[tuple[str, float]] = []

    def start(self, node_id: str, timeout: float = 30.0) -> None:
        self.start_called_with.append((node_id, timeout))
        self.state = NodeLifecycleState.STARTING

    def stop(self, node_id: str, timeout: float = 30.0) -> None:
        self.stop_called_with.append((node_id, timeout))
        self.state = NodeLifecycleState.STOPPED
        self.health = NodeHealth(state=NodeLifecycleState.STOPPED, details="node_stopped")

    def get_lifecycle_state(self, node_id: str) -> NodeLifecycleState:
        return self.state

    def probe_health(self, node_id: str, timeout: float = 5.0) -> NodeHealth:
        if self.health_sequence:
            return self.health_sequence.pop(0)
        return self.health

    def get_status(self, node_id: str) -> NodeStatus:
        return NodeStatus(node_id=node_id, state=self.state, health=self.health)


def test_start_node_immediate_success() -> None:
    """Verify start_node returns HEALTHY status when port reports ready."""
    fake_port = FakeLifecyclePort(
        health_sequence=[
            NodeHealth(
                state=NodeLifecycleState.HEALTHY,
                chain="regtest",
                version=310100,
                blocks=0,
                headers=0,
                details="ready",
            )
        ]
    )
    service = NodeLifecycleService(fake_port)
    status = service.start_node("node-1", timeout=10.0)

    assert status.state == NodeLifecycleState.HEALTHY
    assert status.health.chain == "regtest"
    assert status.health.version == 310100
    assert len(fake_port.start_called_with) == 1


def test_start_node_incompatible_raises() -> None:
    """Verify start_node raises NodeIncompatibleError when node reports wrong chain/version."""
    fake_port = FakeLifecyclePort(
        health_sequence=[
            NodeHealth(
                state=NodeLifecycleState.INCOMPATIBLE,
                chain="mainnet",
                version=310100,
                details="incompatible_chain",
            )
        ]
    )
    service = NodeLifecycleService(fake_port)
    with pytest.raises(NodeIncompatibleError, match="incompatible"):
        service.start_node("node-1", timeout=5.0)


def test_start_node_timeout_raises() -> None:
    """Verify start_node raises StartupTimeoutError when readiness deadline expires."""
    fake_port = FakeLifecyclePort(
        initial_health=NodeHealth(state=NodeLifecycleState.STARTING, details="warming_up")
    )
    service = NodeLifecycleService(fake_port)
    with pytest.raises(StartupTimeoutError, match="failed to become healthy"):
        service.start_node("node-1", timeout=0.1)


def test_stop_node_success() -> None:
    """Verify stop_node returns STOPPED status and passes parameters to adapter."""
    fake_port = FakeLifecyclePort(initial_state=NodeLifecycleState.HEALTHY)
    service = NodeLifecycleService(fake_port)
    status = service.stop_node("node-1", timeout=15.0)

    assert status.state == NodeLifecycleState.STOPPED
    assert status.health.details == "node_stopped"
    assert fake_port.stop_called_with == [("node-1", 15.0)]


def test_parameter_validation_node_id() -> None:
    """Verify invalid node IDs are rejected at service boundary."""
    service = NodeLifecycleService(FakeLifecyclePort())
    with pytest.raises(LifecycleError, match="non-empty string"):
        service.start_node("", timeout=10.0)

    with pytest.raises(LifecycleError, match="Invalid node identifier"):
        service.start_node("invalid node with spaces", timeout=10.0)


def test_parameter_validation_timeout() -> None:
    """Verify non-positive or non-finite timeouts are rejected at service boundary."""
    service = NodeLifecycleService(FakeLifecyclePort())
    with pytest.raises(LifecycleError, match="positive finite number"):
        service.start_node("valid-node", timeout=0.0)

    with pytest.raises(LifecycleError, match="positive finite number"):
        service.start_node("valid-node", timeout=-1.0)
