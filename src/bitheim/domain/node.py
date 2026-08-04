"""Domain models and lifecycle states for managed Bitcoin Core nodes."""

import enum
from dataclasses import dataclass, field


class NodeLifecycleState(enum.StrEnum):
    """Semantic states for a managed Bitcoin Core node lifecycle.

    SPEC-0004 & ADR-0002 Compliance:
    - STOPPED: Node runtime is not executing
    - STARTING: Node runtime has been started and is initializing its subsystems
    - HEALTHY: Node runtime is actively responsive on regtest
    - UNHEALTHY: Node runtime is executing but fails health probes or reports internal errors
    - INCOMPATIBLE: Node is executing on an unsupported blockchain network or version
    - UNKNOWN: Node state cannot be conclusively determined due to runtime query errors
    """

    STOPPED = "stopped"
    STARTING = "starting"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class NodeHealth:
    """Read-only diagnostic health snapshot of a Bitcoin Core node.

    SPEC-0004: Pure domain facts without mutation operations or transport details.
    """

    state: NodeLifecycleState
    chain: str | None = None
    version: int | None = None
    protocol_version: int | None = None
    blocks: int | None = None
    headers: int | None = None
    details: str | None = None

    @property
    def is_healthy(self) -> bool:
        """Return True if node is strictly healthy on regtest."""
        return self.state == NodeLifecycleState.HEALTHY


@dataclass(frozen=True)
class NodeStatus:
    """Consolidated semantic status report of a managed node instance."""

    node_id: str
    state: NodeLifecycleState
    health: NodeHealth = field(default_factory=lambda: NodeHealth(state=NodeLifecycleState.UNKNOWN))
    details: str | None = None
