"""Domain models and lifecycle states for managed Bitcoin Core nodes."""

import enum
import re
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


@dataclass(frozen=True, slots=True)
class NodeOverview:
    """Typed, immutable observation snapshot of Bitcoin Core node and blockchain state.

    SPEC-0005 §8.1: Validated domain facts without transport details or raw payloads.
    """

    version: int
    subversion: str
    network_active: bool
    connections: int
    chain: str
    blocks: int
    headers: int
    best_block_hash: str
    median_time: int
    initial_block_download: bool
    pruned: bool
    chainwork: str | None = None

    def __post_init__(self) -> None:
        """Validate domain invariants per SPEC-0005 §8.1."""
        if type(self.version) is not int or self.version != 310100:
            raise ValueError(f"Incompatible or invalid node version: {self.version}")

        if (
            not isinstance(self.subversion, str)
            or not (0 < len(self.subversion.encode("utf-8")) <= 512)
            or not all(" " <= c <= "~" for c in self.subversion)
        ):
            raise ValueError("Subversion must be a non-empty printable ASCII string <= 512 bytes")

        if not isinstance(self.network_active, bool):
            raise ValueError("network_active must be a boolean")

        if type(self.connections) is not int or self.connections < 0:
            raise ValueError("connections must be a non-negative integer")

        if not isinstance(self.chain, str) or self.chain != "regtest":
            raise ValueError(f"Incompatible chain: {self.chain}")

        if type(self.blocks) is not int or self.blocks < 0:
            raise ValueError("blocks must be a non-negative integer")

        if type(self.headers) is not int or self.headers < 0:
            raise ValueError("headers must be a non-negative integer")

        if (
            not isinstance(self.best_block_hash, str)
            or len(self.best_block_hash) != 64
            or not all(c in "0123456789abcdef" for c in self.best_block_hash)
        ):
            raise ValueError("best_block_hash must be a 64-character lowercase hex string")

        if type(self.median_time) is not int or self.median_time < 0:
            raise ValueError("median_time must be a non-negative integer")

        if not isinstance(self.initial_block_download, bool):
            raise ValueError("initial_block_download must be a boolean")

        if not isinstance(self.pruned, bool):
            raise ValueError("pruned must be a boolean")

        if self.chainwork is not None and (
            not isinstance(self.chainwork, str)
            or len(self.chainwork) != 64
            or not all(c in "0123456789abcdef" for c in self.chainwork)
        ):
            raise ValueError("chainwork must be None or a 64-character lowercase hex string")

    def to_dict(self) -> dict[str, object]:
        """Return deterministic dictionary representation for JSON serialization."""
        return {
            "best_block_hash": self.best_block_hash,
            "blocks": self.blocks,
            "chain": self.chain,
            "chainwork": self.chainwork,
            "connections": self.connections,
            "headers": self.headers,
            "initial_block_download": self.initial_block_download,
            "median_time": self.median_time,
            "network_active": self.network_active,
            "pruned": self.pruned,
            "subversion": self.subversion,
            "version": self.version,
        }


@dataclass(frozen=True, slots=True)
class BlockSummary:
    """Immutable, slotted summary of a single Bitcoin block."""

    hash: str
    height: int
    confirmations: int
    timestamp: int
    transaction_count: int
    size: int
    weight: int
    previous_block_hash: str | None
    next_block_hash: str | None

    def __post_init__(self) -> None:
        _hex_re = re.compile(r"^[0-9a-f]{64}$")
        if not isinstance(self.hash, str) or not _hex_re.match(self.hash):
            raise ValueError("Block hash must be a 64-character lowercase hex string.")
        if not isinstance(self.height, int) or isinstance(self.height, bool) or self.height < 0:
            raise ValueError("Height must be a non-negative integer.")
        if (
            not isinstance(self.confirmations, int)
            or isinstance(self.confirmations, bool)
            or self.confirmations < 0
        ):
            raise ValueError("Confirmations must be a non-negative integer.")
        if (
            not isinstance(self.timestamp, int)
            or isinstance(self.timestamp, bool)
            or self.timestamp < 0
        ):
            raise ValueError("Timestamp must be a non-negative integer.")
        if (
            not isinstance(self.transaction_count, int)
            or isinstance(self.transaction_count, bool)
            or self.transaction_count < 0
        ):
            raise ValueError("Transaction count must be a non-negative integer.")
        if not isinstance(self.size, int) or isinstance(self.size, bool) or self.size < 0:
            raise ValueError("Size must be a non-negative integer.")
        if not isinstance(self.weight, int) or isinstance(self.weight, bool) or self.weight < 0:
            raise ValueError("Weight must be a non-negative integer.")
        if self.previous_block_hash is not None and (
            not isinstance(self.previous_block_hash, str)
            or not _hex_re.match(self.previous_block_hash)
        ):
            raise ValueError("Previous block hash must be a 64-character string or None.")
        if self.next_block_hash is not None and (
            not isinstance(self.next_block_hash, str) or not _hex_re.match(self.next_block_hash)
        ):
            raise ValueError("Next block hash must be a 64-character string or None.")

    def to_dict(self) -> dict[str, object]:
        """Return deterministic dictionary representation for JSON serialization."""
        return {
            "confirmations": self.confirmations,
            "hash": self.hash,
            "height": self.height,
            "next_block_hash": self.next_block_hash,
            "previous_block_hash": self.previous_block_hash,
            "size": self.size,
            "timestamp": self.timestamp,
            "transaction_count": self.transaction_count,
            "weight": self.weight,
        }


@dataclass(frozen=True, slots=True)
class MempoolSummary:
    """Typed, immutable observation snapshot of the Bitcoin Core memory pool."""

    loaded: bool
    transaction_count: int
    serialized_bytes: int
    dynamic_memory_usage: int
    max_memory: int
    total_fees_satoshis: int

    def __post_init__(self) -> None:
        """Validate domain invariants."""
        if type(self.loaded) is not bool:
            raise ValueError("loaded must be a boolean.")
        if type(self.transaction_count) is not int or self.transaction_count < 0:
            raise ValueError("transaction_count must be a non-negative integer.")
        if type(self.serialized_bytes) is not int or self.serialized_bytes < 0:
            raise ValueError("serialized_bytes must be a non-negative integer.")
        if type(self.dynamic_memory_usage) is not int or self.dynamic_memory_usage < 0:
            raise ValueError("dynamic_memory_usage must be a non-negative integer.")
        if type(self.max_memory) is not int or self.max_memory < 0:
            raise ValueError("max_memory must be a non-negative integer.")
        if type(self.total_fees_satoshis) is not int or self.total_fees_satoshis < 0:
            raise ValueError("total_fees_satoshis must be a non-negative integer.")

    def to_dict(self) -> dict[str, object]:
        """Return deterministic dictionary representation for JSON serialization."""
        return {
            "dynamic_memory_usage": self.dynamic_memory_usage,
            "loaded": self.loaded,
            "max_memory": self.max_memory,
            "serialized_bytes": self.serialized_bytes,
            "total_fees_satoshis": self.total_fees_satoshis,
            "transaction_count": self.transaction_count,
        }
