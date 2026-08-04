"""Unit tests for domain node models and lifecycle state definitions."""

from bitheim.domain.node import NodeHealth, NodeLifecycleState, NodeStatus


def test_node_lifecycle_states() -> None:
    """Verify all defined domain lifecycle states."""
    assert NodeLifecycleState.STOPPED.value == "stopped"
    assert NodeLifecycleState.STARTING.value == "starting"
    assert NodeLifecycleState.HEALTHY.value == "healthy"
    assert NodeLifecycleState.UNHEALTHY.value == "unhealthy"
    assert NodeLifecycleState.INCOMPATIBLE.value == "incompatible"
    assert NodeLifecycleState.UNKNOWN.value == "unknown"


def test_node_health_is_healthy() -> None:
    """Verify is_healthy property logic."""
    h_healthy = NodeHealth(
        state=NodeLifecycleState.HEALTHY,
        chain="regtest",
        version=310100,
        protocol_version=70016,
        blocks=100,
    )
    assert h_healthy.is_healthy is True

    h_starting = NodeHealth(state=NodeLifecycleState.STARTING)
    assert h_starting.is_healthy is False

    h_unhealthy = NodeHealth(state=NodeLifecycleState.UNHEALTHY)
    assert h_unhealthy.is_healthy is False


def test_node_status_pure_semantics() -> None:
    """Verify NodeStatus representation contains pure domain facts without container leakage."""
    health = NodeHealth(
        state=NodeLifecycleState.HEALTHY,
        chain="regtest",
        version=310100,
        blocks=50,
    )
    status = NodeStatus(
        node_id="regtest-node-1",
        state=NodeLifecycleState.HEALTHY,
        health=health,
        details="Node is responsive",
    )
    assert status.node_id == "regtest-node-1"
    assert status.state == NodeLifecycleState.HEALTHY
    assert status.health is health
    assert status.details == "Node is responsive"
