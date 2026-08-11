"""Domain and application lifecycle exception hierarchy."""


class BitheimError(Exception):
    """Base exception for all domain and application errors in Bitheim."""


class LifecycleError(BitheimError):
    """Base exception for node lifecycle management failures."""


class RuntimeUnavailableError(LifecycleError):
    """Raised when the container runtime (Docker/Compose) is unavailable or unresponsive."""


class StartupTimeoutError(LifecycleError):
    """Raised when node readiness polling exceeds the configured deadline."""


class ShutdownTimeoutError(LifecycleError):
    """Raised when graceful node shutdown exceeds the configured deadline."""


class NodeIncompatibleError(LifecycleError):
    """Raised when a running node reports an unsupported chain or version."""


class ExecutionContextError(LifecycleError):
    """Raised when an operation is executed in an unauthorized or unsupported execution context."""


class RpcError(BitheimError):
    """Base exception for read-only RPC observation operations."""


class RpcUnavailableError(RpcError):
    """Raised when the target RPC endpoint cannot be reached or connection is refused."""


class RpcTimeoutError(RpcError):
    """Raised when an RPC request exceeds the caller's monotonic deadline."""


class RpcAuthenticationError(RpcError):
    """Raised when RPC authentication via cookie fails or credentials are rejected."""


class RpcIncompatibleNodeError(RpcError):
    """Raised when Bitcoin Core reports an unsupported chain or version."""


class RpcMalformedResponseError(RpcError):
    """Raised when an RPC response fails structural or type validation."""


class RpcResponseSizeExceededError(RpcError):
    """Raised when an RPC response exceeds the maximum allowed payload size."""


class RpcResourceNotFoundError(RpcError):
    """Raised when a requested resource (e.g., block) is not found."""


class RpcProtocolError(RpcError):
    """Raised when Bitcoin Core returns a JSON-RPC error response object."""


class RpcExecutionContextError(RpcError):
    """Raised when an observation operation is invoked in an unauthorized execution context."""
