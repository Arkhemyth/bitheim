"""Application service orchestrating managed node lifecycle operations."""

import math
import re
import time

from bitheim.application.ports import NodeLifecyclePort, NodeObservationPort
from bitheim.bootstrap.logging import get_logger
from bitheim.domain.errors import (
    LifecycleError,
    NodeIncompatibleError,
    RpcError,
    StartupTimeoutError,
)
from bitheim.domain.node import (
    NodeHealth,
    NodeLifecycleState,
    NodeOverview,
    NodeStatus,
)

logger = get_logger("application.service")

_VALID_NODE_ID_REGEX = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


def _validate_service_node_id(node_id: str) -> str:
    """Validate node identifier at application service boundary."""
    if not isinstance(node_id, str) or not node_id.strip():
        raise LifecycleError("Node identifier must be a non-empty string.")
    trimmed = node_id.strip()
    if not _VALID_NODE_ID_REGEX.match(trimmed):
        raise LifecycleError(
            "Invalid node identifier: must contain only alphanumeric characters, "
            "dashes, and underscores, starting with an alphanumeric character."
        )
    return trimmed


def _validate_service_timeout(timeout: float, param_name: str = "timeout") -> float:
    """Validate positive finite timeout at application service boundary."""
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool):
        raise LifecycleError(f"Parameter '{param_name}' must be a numeric value.")
    float_val = float(timeout)
    if float_val <= 0 or math.isnan(float_val) or math.isinf(float_val):
        raise LifecycleError(f"Parameter '{param_name}' must be a positive finite number.")
    return float_val


class NodeLifecycleService:
    """Orchestrates managed node lifecycle, readiness, health probing, and shutdown."""

    def __init__(self, lifecycle_adapter: NodeLifecyclePort) -> None:
        self._adapter = lifecycle_adapter

    def start_node(self, node_id: str, timeout: float = 30.0) -> NodeStatus:
        """Start managed node and wait for bounded readiness and health.

        Args:
            node_id: Validated node/project identifier.
            timeout: Maximum duration in seconds to wait for readiness.

        Returns:
            NodeStatus with verified HEALTHY state.

        Raises:
            LifecycleError: If node_id or timeout is invalid.
            StartupTimeoutError: If node does not achieve HEALTHY state within timeout.
            NodeIncompatibleError: If node reports wrong chain or incompatible version.
            RuntimeUnavailableError: If underlying runtime is unreachable.
        """
        valid_node_id = _validate_service_node_id(node_id)
        valid_timeout = _validate_service_timeout(timeout, "timeout")

        logger.info(
            "Initiating node startup",
            extra={"event": "node_start_requested", "data": {}},
        )

        # Check if already running and healthy
        current_status = self._adapter.get_status(valid_node_id)
        if current_status.state == NodeLifecycleState.HEALTHY:
            logger.info(
                "Node is already running and healthy",
                extra={"event": "node_already_healthy", "data": {}},
            )
            return current_status

        # Trigger adapter start
        self._adapter.start(valid_node_id, timeout=valid_timeout)

        # Monotonic deadline polling for authenticated readiness
        deadline = time.monotonic() + valid_timeout
        last_health: NodeHealth | None = None

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break

            probe_budget = min(2.0, remaining)
            health = self._adapter.probe_health(valid_node_id, timeout=probe_budget)
            last_health = health

            if health.state == NodeLifecycleState.HEALTHY:
                logger.info(
                    "Node successfully reached healthy state",
                    extra={
                        "event": "node_startup_succeeded",
                        "data": {
                            "chain": health.chain,
                            "version": health.version,
                        },
                    },
                )
                return NodeStatus(
                    node_id=valid_node_id,
                    state=NodeLifecycleState.HEALTHY,
                    health=health,
                )

            if health.state == NodeLifecycleState.INCOMPATIBLE:
                logger.error(
                    "Node reported incompatible runtime environment",
                    extra={
                        "event": "node_incompatible_detected",
                        "data": {
                            "chain": health.chain,
                            "version": health.version,
                        },
                    },
                )
                raise NodeIncompatibleError(
                    "Managed node is incompatible with required chain or version."
                )

            remaining_after_probe = deadline - time.monotonic()
            if remaining_after_probe <= 0:
                break
            time.sleep(min(0.5, remaining_after_probe))

        detail_suffix = (
            f" (last state: {last_health.details})" if last_health and last_health.details else ""
        )
        logger.error(
            "Node startup timed out waiting for readiness",
            extra={
                "event": "node_startup_timed_out",
                "data": {"timeout_seconds": valid_timeout},
            },
        )
        raise StartupTimeoutError(
            f"Node failed to become healthy within {valid_timeout:.1f}s{detail_suffix}"
        )

    def stop_node(self, node_id: str, timeout: float = 30.0) -> NodeStatus:
        """Gracefully stop managed node within specified timeout.

        Args:
            node_id: Validated node/project identifier.
            timeout: Maximum duration in seconds to wait for shutdown.

        Returns:
            NodeStatus with verified STOPPED state.

        Raises:
            LifecycleError: If node_id or timeout is invalid.
            ShutdownTimeoutError: If node fails to stop within timeout.
            RuntimeUnavailableError: If underlying runtime is unreachable.
        """
        valid_node_id = _validate_service_node_id(node_id)
        valid_timeout = _validate_service_timeout(timeout, "timeout")

        logger.info(
            "Initiating node shutdown",
            extra={"event": "node_stop_requested", "data": {}},
        )

        self._adapter.stop(valid_node_id, timeout=valid_timeout)

        return NodeStatus(
            node_id=valid_node_id,
            state=NodeLifecycleState.STOPPED,
            health=NodeHealth(state=NodeLifecycleState.STOPPED, details="node_stopped"),
        )

    def get_node_status(self, node_id: str) -> NodeStatus:
        """Retrieve current domain status and health for specified node.

        Args:
            node_id: Validated node/project identifier.

        Returns:
            NodeStatus representing observed runtime state.
        """
        valid_node_id = _validate_service_node_id(node_id)
        return self._adapter.get_status(valid_node_id)


class NodeObservationService:
    """Application service for read-only node observation operations."""

    def __init__(self, observation_port: NodeObservationPort) -> None:
        self._port = observation_port

    def inspect_node(self, timeout: float = 10.0) -> NodeOverview:
        """Retrieve typed node and chain overview facts.

        Args:
            timeout: Command deadline in seconds (must be positive and <= 60.0).

        Returns:
            NodeOverview snapshot verified on Bitcoin Core 31.1 regtest.

        Raises:
            RpcError: If timeout validation or observation operation fails.
        """
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool):
            raise RpcError("Parameter 'timeout' must be a numeric value.")
        valid_timeout = float(timeout)
        if (
            valid_timeout <= 0
            or math.isnan(valid_timeout)
            or math.isinf(valid_timeout)
            or valid_timeout > 60.0
        ):
            raise RpcError("Command deadline must be a positive finite value no greater than 60s.")

        logger.debug(
            "Inspecting node overview",
            extra={
                "event": "node_inspect_requested",
                "data": {"operation": "node_overview"},
            },
        )
        try:
            overview = self._port.get_node_overview(timeout=valid_timeout)
        except Exception as err:
            logger.error(
                "Node overview inspection failed",
                extra={
                    "event": "node_overview_failed",
                    "data": {
                        "operation": "node_overview",
                        "outcome": "failure",
                        "error_type": type(err).__name__,
                    },
                },
            )
            raise

        logger.info(
            "Node overview successfully retrieved",
            extra={
                "event": "node_overview_inspected",
                "data": {
                    "operation": "node_overview",
                    "outcome": "success",
                },
            },
        )
        return overview
