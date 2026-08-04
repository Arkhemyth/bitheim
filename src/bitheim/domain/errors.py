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


class RpcAuthenticationError(LifecycleError):
    """Raised when RPC authentication via cookie fails."""


class ExecutionContextError(LifecycleError):
    """Raised when an operation is executed in an unauthorized or unsupported execution context."""
