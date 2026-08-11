"""Application port interfaces for managed node lifecycle and health operations."""

from typing import Protocol

from bitheim.domain.node import (
    BlockSummary,
    NodeHealth,
    NodeLifecycleState,
    NodeOverview,
    NodeStatus,
)


class NodeLifecyclePort(Protocol):
    """Port defining operations for executing and monitoring a managed node runtime."""

    def start(self, node_id: str, timeout: float = 30.0) -> None:
        """Start the managed node runtime instance.

        Args:
            node_id: Cleaned and validated node identifier.
            timeout: Maximum time allowed for initial runtime container startup.

        Raises:
            LifecycleError: If runtime startup encounters an unrecoverable failure.
            RuntimeUnavailableError: If the underlying runtime system is missing or inaccessible.
        """
        ...

    def stop(self, node_id: str, timeout: float = 15.0) -> None:
        """Gracefully stop the managed node runtime instance while preserving data volumes.

        Args:
            node_id: Cleaned and validated node identifier.
            timeout: Maximum grace period allowed for flushing state before termination.

        Raises:
            ShutdownTimeoutError: If the runtime fails to stop within the specified timeout.
            LifecycleError: If runtime shutdown encounters an unrecoverable failure.
            RuntimeUnavailableError: If the underlying runtime system is missing or inaccessible.
        """
        ...

    def probe_health(self, node_id: str, timeout: float = 5.0) -> NodeHealth:
        """Execute a non-mutating diagnostic probe against the node's RPC endpoints.

        Args:
            node_id: Cleaned and validated node identifier.
            timeout: Network and probe evaluation timeout in seconds.

        Returns:
            NodeHealth snapshot containing confirmed blockchain and software facts.
        """
        ...

    def get_lifecycle_state(self, node_id: str) -> NodeLifecycleState:
        """Inspect the current semantic lifecycle state of the node instance.

        Args:
            node_id: Cleaned and validated node identifier.

        Returns:
            Semantic NodeLifecycleState without exposing infrastructure container details.
        """
        ...

    def get_status(self, node_id: str) -> NodeStatus:
        """Inspect the consolidated semantic status and health of the node instance.

        Args:
            node_id: Cleaned and validated node identifier.

        Returns:
            NodeStatus snapshot containing state and health.
        """
        ...


class NodeObservationPort(Protocol):
    """Port defining read-only observation operations against Bitcoin Core."""

    def get_node_overview(self, timeout: float = 10.0) -> NodeOverview:
        """Retrieve validated node and blockchain overview facts.

        Args:
            timeout: Maximum command deadline in seconds (must be positive and <= 60.0).

        Returns:
            NodeOverview snapshot verified on Bitcoin Core 31.1 regtest.

        Raises:
            RpcError: On transport, authentication, protocol, incompatibility,
                or validation failure.
        """
        ...

    def get_block(
        self,
        *,
        block_hash: str | None = None,
        height: int | None = None,
        timeout: float = 10.0,
    ) -> BlockSummary:
        """Retrieve a validated block summary by hash or height.

        Args:
            block_hash: Exactly 64-character block hash (mutually exclusive with height).
            height: Non-negative block height (mutually exclusive with block_hash).
            timeout: Maximum command deadline in seconds (must be positive and <= 60.0).

        Returns:
            BlockSummary immutable snapshot.

        Raises:
            RpcError: On lookup or validation failure.
            RpcResourceNotFoundError: If the block is not found.
        """
        ...
