"""Docker Compose infrastructure adapter for managed Bitcoin Core regtest nodes."""

import ipaddress
import json
import math
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from bitheim.application.ports import NodeLifecyclePort
from bitheim.bootstrap.logging import get_logger
from bitheim.domain.errors import (
    LifecycleError,
    RpcAuthenticationError,
    RpcError,
    RpcIncompatibleNodeError,
    RpcMalformedResponseError,
    RpcResourceNotFoundError,
    RpcResponseSizeExceededError,
    RpcTimeoutError,
    RpcUnavailableError,
    RuntimeUnavailableError,
    ShutdownTimeoutError,
    StartupTimeoutError,
)
from bitheim.domain.node import (
    BlockSummary,
    MempoolSummary,
    NodeHealth,
    NodeLifecycleState,
    NodeOverview,
    NodeStatus,
)
from bitheim.infrastructure.bitcoin.rpc_probe import (
    EXPECTED_BITCOIN_VERSION,
    EXPECTED_CHAIN,
)
from bitheim.infrastructure.compose.resources import (
    get_bitcoin_core_resource_dir,
    get_compose_template_path,
)

logger = get_logger("infrastructure.compose.adapter")

MAX_DELEGATED_JSON_DEPTH = 32

# Compose project network suffix used by Docker Compose
_COMPOSE_NETWORK_SUFFIX = "_bitheim-net"

# Known container lifecycle states
_RUNNING_STATES = frozenset({"running"})
_STOPPED_STATES = frozenset({"exited", "dead", "created"})

_HEX_64_REGEX = re.compile(r"^[0-9a-fA-F]{64}$")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Parse JSON object rejecting duplicate object keys."""
    res: dict[str, Any] = {}
    for k, v in pairs:
        if k in res:
            raise ValueError(f"Duplicate JSON key: {k}")
        res[k] = v
    return res


def _check_json_depth(obj: Any, depth: int = 1, max_depth: int = MAX_DELEGATED_JSON_DEPTH) -> None:
    """Validate JSON nesting depth."""
    if depth > max_depth:
        raise RpcMalformedResponseError(
            f"Delegated JSON exceeds maximum nesting depth of {max_depth}."
        )
    if isinstance(obj, dict):
        for v in obj.values():
            _check_json_depth(v, depth + 1, max_depth)
    elif isinstance(obj, list):
        for item in obj:
            _check_json_depth(item, depth + 1, max_depth)


def _remaining(deadline: float) -> float:
    """Return seconds until deadline. Negative means expired."""
    return deadline - time.monotonic()


class ComposeLifecycleAdapter(NodeLifecyclePort):
    """Infrastructure adapter managing Bitcoin Core nodes via Docker Compose."""

    def __init__(
        self,
        compose_template: Path | None = None,
        compose_subnet: str = "172.28.0.0/16",
        bitcoin_core_image: str = "bitheim-bitcoin-core:31.1",
        bitheim_image: str = "bitheim:local",
        docker_cmd: str = "docker",
    ) -> None:
        self._compose_template = compose_template or get_compose_template_path()
        self._compose_subnet = compose_subnet
        self._bitcoin_core_image = bitcoin_core_image
        self._bitheim_image = bitheim_image
        self._docker_cmd = docker_cmd

    def _build_env(self, node_id: str) -> dict[str, str]:
        """Construct isolated immutable environment variables for Compose execution."""
        env = {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", "/root"),
            "BITHEIM_NODE_ID": node_id,
            "BITHEIM_COMPOSE_SUBNET": self._compose_subnet,
            "BITHEIM_BITCOIN_CORE_IMAGE": self._bitcoin_core_image,
            "BITHEIM_IMAGE": self._bitheim_image,
        }
        if "DOCKER_HOST" in os.environ:
            env["DOCKER_HOST"] = os.environ["DOCKER_HOST"]
        return env

    # ------------------------------------------------------------------
    # Internal helpers — all accept a monotonic deadline, never a duration
    # ------------------------------------------------------------------

    def _check_docker_runtime_available(self, deadline: float) -> None:
        """Verify Docker executable exists and Docker daemon is responsive."""
        if not shutil.which(self._docker_cmd):
            raise RuntimeUnavailableError("Docker executable was not found in PATH")
        r = _remaining(deadline)
        if r <= 0:
            raise RuntimeUnavailableError("Timeout budget expired before Docker daemon check")
        try:
            res = subprocess.run(
                [self._docker_cmd, "info", "--format", "{{.ServerVersion}}"],
                capture_output=True,
                text=True,
                check=False,
                timeout=r,
            )
            if res.returncode != 0:
                logger.error(
                    "Docker daemon check failed",
                    extra={
                        "event": "docker_daemon_unavailable",
                        "data": {"error_type": "daemon_unreachable"},
                    },
                )
                raise RuntimeUnavailableError("Docker daemon is not running or accessible")
        except subprocess.TimeoutExpired:
            raise RuntimeUnavailableError("Docker daemon check timed out") from None
        except OSError:
            raise RuntimeUnavailableError("Failed to execute Docker daemon check") from None

    def _check_subnet_collision(self, node_id: str, deadline: float) -> None:
        """Verify configured compose subnet does not overlap with existing networks.

        Each blocking call recomputes remaining from the shared deadline.
        """
        try:
            target_net = ipaddress.ip_network(self._compose_subnet, strict=False)
        except ValueError:
            raise LifecycleError("Configured compose subnet is invalid") from None

        r = _remaining(deadline)
        if r <= 0:
            raise RuntimeUnavailableError("Timeout budget expired before subnet collision check")

        try:
            res = subprocess.run(
                [self._docker_cmd, "network", "ls", "--format", "{{.Name}}"],
                capture_output=True,
                text=True,
                check=False,
                timeout=r,
            )
            if res.returncode != 0:
                raise RuntimeUnavailableError("Failed to list existing Docker networks")

            network_names = [n.strip() for n in res.stdout.splitlines() if n.strip()]
            project_network = f"{node_id}{_COMPOSE_NETWORK_SUFFIX}"

            for name in network_names:
                if name == project_network:
                    continue

                r = _remaining(deadline)
                if r <= 0:
                    raise RuntimeUnavailableError(
                        "Timeout budget expired during subnet collision check"
                    )

                insp = subprocess.run(
                    [
                        self._docker_cmd,
                        "network",
                        "inspect",
                        name,
                        "--format",
                        "{{range .IPAM.Config}}{{.Subnet}} {{end}}",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=r,
                )
                if insp.returncode != 0:
                    raise RuntimeUnavailableError(
                        "Failed to inspect Docker network during subnet collision check"
                    )

                subnets = [s.strip() for s in insp.stdout.split() if s.strip()]
                for sub in subnets:
                    try:
                        existing_net = ipaddress.ip_network(sub, strict=False)
                    except ValueError:
                        raise LifecycleError(
                            "Malformed subnet encountered during collision check"
                        ) from None

                    if target_net.overlaps(existing_net):
                        logger.error(
                            "Subnet collision detected during preflight check",
                            extra={
                                "event": "subnet_collision_detected",
                                "data": {"error_type": "network_collision"},
                            },
                        )
                        raise LifecycleError(
                            "Configured compose subnet overlaps with an existing Docker network"
                        )
        except (subprocess.TimeoutExpired, OSError):
            raise RuntimeUnavailableError("Docker network inspection failed") from None

    def _ensure_image_available(
        self,
        image_ref: str,
        build_context: Path | None,
        deadline: float,
    ) -> None:
        """Ensure a container image exists locally, optionally building from context.

        Distinguishes confirmed image-not-found from daemon/permission/malformed
        failures. Non-not-found errors fail closed.
        """
        r = _remaining(deadline)
        if r <= 0:
            raise RuntimeUnavailableError("Timeout budget expired before image availability check")

        try:
            insp = subprocess.run(
                [self._docker_cmd, "image", "inspect", image_ref],
                capture_output=True,
                text=True,
                check=False,
                timeout=r,
            )
            if insp.returncode == 0:
                return

            # Distinguish "not found" from other failures.
            # Docker CLI outputs "No such image" on stderr for a clean miss.
            stderr_lower = (insp.stderr or "").lower()
            is_not_found = "no such image" in stderr_lower or "not found" in stderr_lower
            if not is_not_found:
                raise RuntimeUnavailableError(
                    "Container image inspection failed with unexpected error"
                )
        except subprocess.TimeoutExpired:
            raise RuntimeUnavailableError("Container image inspection timed out") from None
        except OSError:
            raise RuntimeUnavailableError("Failed to inspect container image") from None

        # Image is confirmed missing — build if context is provided
        if build_context is None:
            raise RuntimeUnavailableError(
                "Required container image is not available and no build context is configured"
            )

        dockerfile = build_context / "Dockerfile"
        if not dockerfile.exists():
            raise RuntimeUnavailableError("Dockerfile asset is missing from packaged resources")

        logger.info(
            "Building container image from packaged assets",
            extra={
                "event": "image_build_started",
                "data": {"build_target": "infrastructure"},
            },
        )
        r = _remaining(deadline)
        if r <= 0:
            raise RuntimeUnavailableError("Timeout budget expired before image build")

        try:
            build_res = subprocess.run(
                [self._docker_cmd, "build", "-t", image_ref, str(build_context)],
                capture_output=True,
                text=True,
                check=False,
                timeout=r,
            )
            if build_res.returncode != 0:
                logger.error(
                    "Container image build failed",
                    extra={
                        "event": "image_build_failed",
                        "data": {"error_type": "build_error"},
                    },
                )
                raise RuntimeUnavailableError("Failed to build required container image")
        except subprocess.TimeoutExpired:
            raise RuntimeUnavailableError("Container image build timed out") from None
        except OSError:
            raise RuntimeUnavailableError("Failed to invoke Docker build") from None

    # ------------------------------------------------------------------
    # Public port implementations
    # ------------------------------------------------------------------

    def start(self, node_id: str, timeout: float = 30.0) -> None:
        """Start managed node project via Docker Compose.

        Ensures both Bitcoin Core and Bitheim images are available before
        starting the long-running bitcoin-core service.
        """
        deadline = time.monotonic() + timeout

        self._check_docker_runtime_available(deadline)
        self._check_subnet_collision(node_id, deadline)

        # Ensure Bitcoin Core image
        btc_resource_dir = get_bitcoin_core_resource_dir()
        self._ensure_image_available(self._bitcoin_core_image, btc_resource_dir, deadline)

        # Ensure Bitheim application image (needed for delegated health probes).
        # The Bitheim image requires a project-root build context (pyproject.toml,
        # uv.lock, src/) that is only available from a repository checkout.
        # When the image does not exist and no checkout-relative Dockerfile is
        # found, _ensure_image_available raises RuntimeUnavailableError with a
        # clear message.  Installed-wheel users must pre-build or pull the image.
        bitheim_build_ctx = self._locate_bitheim_build_context()
        self._ensure_image_available(self._bitheim_image, bitheim_build_ctx, deadline)

        env = self._build_env(node_id)
        cmd = [
            self._docker_cmd,
            "compose",
            "-f",
            str(self._compose_template),
            "--project-name",
            node_id,
            "up",
            "-d",
            "bitcoin-core",
        ]

        r = _remaining(deadline)
        if r <= 0:
            raise StartupTimeoutError("Timeout budget expired before compose up")

        logger.debug(
            "Executing compose up command",
            extra={"event": "compose_up_invoked", "data": {}},
        )
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=r,
            )
            if res.returncode != 0:
                logger.error(
                    "Compose up command failed",
                    extra={
                        "event": "compose_up_failed",
                        "data": {"error_type": "process_error"},
                    },
                )
                raise LifecycleError("Failed to start node services via Docker Compose")
        except subprocess.TimeoutExpired:
            raise StartupTimeoutError("Docker Compose up timed out") from None
        except OSError:
            raise RuntimeUnavailableError("Failed to execute Docker Compose") from None

    def stop(self, node_id: str, timeout: float = 30.0) -> None:
        """Gracefully stop managed node project via Docker Compose.

        All internal calls share a single monotonic deadline.
        """
        deadline = time.monotonic() + timeout

        self._check_docker_runtime_available(deadline)

        current_state = self._get_lifecycle_state_deadline(node_id, deadline)
        if current_state == NodeLifecycleState.STOPPED:
            logger.debug(
                "Node is already stopped",
                extra={"event": "compose_stop_noop", "data": {}},
            )
            return

        r = _remaining(deadline)
        if r <= 0:
            raise ShutdownTimeoutError("Timeout budget expired before compose stop")

        grace_seconds = max(1, int(r))
        env = self._build_env(node_id)
        cmd = [
            self._docker_cmd,
            "compose",
            "-f",
            str(self._compose_template),
            "--project-name",
            node_id,
            "stop",
            "-t",
            str(grace_seconds),
        ]

        logger.debug(
            "Executing compose stop command",
            extra={"event": "compose_stop_invoked", "data": {}},
        )
        try:
            # subprocess timeout is capped to remaining budget, not grace + padding
            r = _remaining(deadline)
            if r <= 0:
                raise ShutdownTimeoutError("Timeout budget expired before compose stop")
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=r,
            )
            if res.returncode != 0:
                logger.error(
                    "Compose stop command failed",
                    extra={
                        "event": "compose_stop_failed",
                        "data": {"error_type": "process_error"},
                    },
                )
                raise LifecycleError("Failed to stop node services via Docker Compose")

            post_state = self._get_lifecycle_state_deadline(node_id, deadline)
            if post_state != NodeLifecycleState.STOPPED:
                raise ShutdownTimeoutError("Node services failed to stop within grace period")
        except subprocess.TimeoutExpired:
            raise ShutdownTimeoutError("Docker Compose stop timed out") from None
        except OSError:
            raise RuntimeUnavailableError("Failed to execute Docker Compose") from None

    def get_lifecycle_state(self, node_id: str) -> NodeLifecycleState:
        """Inspect container process state for the project via Docker Compose.

        Uses a default 10 s budget. For deadline-scoped calls use
        _get_lifecycle_state_deadline.
        """
        return self._get_lifecycle_state_deadline(node_id, time.monotonic() + 10.0)

    def probe_health(self, node_id: str, timeout: float = 5.0) -> NodeHealth:
        """Execute read-only health probe through the authorized Bitheim boundary.

        SPEC-0004 §5.1: application/RPC probes run through the unprivileged
        one-shot bitheim service on the private network without implicitly
        starting dependencies (--no-deps).

        All internal calls share a single monotonic deadline derived from
        *timeout*.  Never raises StartupTimeoutError — returns UNKNOWN on
        expired budget so callers (status) stay read-only.
        """
        if timeout <= 0:
            return NodeHealth(state=NodeLifecycleState.UNKNOWN, details="timeout_expired")

        deadline = time.monotonic() + timeout

        try:
            self._check_docker_runtime_available(deadline)
        except RuntimeUnavailableError:
            return NodeHealth(state=NodeLifecycleState.UNKNOWN, details="runtime_unavailable")

        state = self._get_lifecycle_state_deadline(node_id, deadline)
        if state == NodeLifecycleState.STOPPED:
            return NodeHealth(state=NodeLifecycleState.STOPPED, details="node_stopped")

        r = _remaining(deadline)
        if r <= 0:
            return NodeHealth(state=NodeLifecycleState.UNKNOWN, details="timeout_expired")

        env = self._build_env(node_id)
        cmd = [
            self._docker_cmd,
            "compose",
            "-f",
            str(self._compose_template),
            "--project-name",
            node_id,
            "run",
            "--rm",
            "--no-deps",
            "-T",
            "bitheim",
            "status",
            "--json",
        ]

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=r,
            )

            if res.returncode != 0:
                stderr_lower = res.stderr.lower() if res.stderr else ""
                if "no such service" in stderr_lower or "not found" in stderr_lower:
                    return NodeHealth(
                        state=NodeLifecycleState.UNHEALTHY,
                        details="bitheim_service_unavailable",
                    )
                return NodeHealth(
                    state=NodeLifecycleState.UNHEALTHY,
                    details="delegated_probe_failed",
                )

            return self._parse_delegated_health(res.stdout)
        except (subprocess.TimeoutExpired, OSError):
            return NodeHealth(state=NodeLifecycleState.UNKNOWN, details="probe_failed")

    def get_status(self, node_id: str) -> NodeStatus:
        """Inspect and return combined domain status and health.

        Read-only — never raises StartupTimeoutError.
        """
        state = self.get_lifecycle_state(node_id)
        if state == NodeLifecycleState.STOPPED:
            return NodeStatus(
                node_id=node_id,
                state=NodeLifecycleState.STOPPED,
                health=NodeHealth(state=NodeLifecycleState.STOPPED, details="node_stopped"),
            )

        health = self.probe_health(node_id)

        if state == NodeLifecycleState.UNKNOWN:
            return NodeStatus(
                node_id=node_id,
                state=NodeLifecycleState.UNKNOWN,
                health=health,
            )

        return NodeStatus(
            node_id=node_id,
            state=health.state,
            health=health,
        )

    def inspect_node(self, node_id: str, timeout: float = 10.0) -> NodeOverview:
        """Execute delegated read-only node inspection through the Bitheim boundary.

        SPEC-0005 §4: Host facade delegates observation commands as one-shot
        bitheim service processes on the private Compose network using
        `docker compose run --rm --no-deps -T`. Delegation does not start,
        recreate, or repair Bitcoin Core.

        Args:
            node_id: Cleaned and validated node identifier.
            timeout: Command deadline in seconds.

        Returns:
            Validated NodeOverview domain object.

        Raises:
            RpcUnavailableError: If node is stopped or runtime is unreachable.
            RpcTimeoutError: If execution exceeds deadline.
            RpcError: On delegated inspection failure.
        """
        if type(timeout) not in (int, float) or isinstance(timeout, bool):
            raise RpcError("Command deadline must be a numeric value.")
        float_timeout = float(timeout)

        if (
            float_timeout <= 0
            or math.isnan(float_timeout)
            or math.isinf(float_timeout)
            or float_timeout > 60.0
        ):
            raise RpcError("Command deadline must be a positive finite value no greater than 60s.")

        deadline = time.monotonic() + float_timeout

        try:
            self._check_docker_runtime_available(deadline)
        except RuntimeUnavailableError:
            raise RpcUnavailableError(
                "Docker runtime is unavailable for node inspection."
            ) from None

        state = self._get_lifecycle_state_deadline(node_id, deadline)
        if state == NodeLifecycleState.STOPPED:
            raise RpcUnavailableError(
                f"Managed node '{node_id}' is stopped. Start the node before inspecting."
            )

        data = self._run_delegated_inspection(node_id, deadline, "node", [])

        # Strict field validation without coercion
        version = data.get("version")
        if type(version) is not int or isinstance(version, bool):
            raise RpcMalformedResponseError("Invalid 'version' field in delegated output.")

        subversion = data.get("subversion")
        if (
            not isinstance(subversion, str)
            or not (0 < len(subversion.encode("utf-8")) <= 512)
            or not all(" " <= c <= "~" for c in subversion)
        ):
            raise RpcMalformedResponseError("Invalid 'subversion' field in delegated output.")

        network_active = data.get("network_active")
        if not isinstance(network_active, bool):
            raise RpcMalformedResponseError("Invalid 'network_active' field in delegated output.")

        connections = data.get("connections")
        if type(connections) is not int or isinstance(connections, bool) or connections < 0:
            raise RpcMalformedResponseError("Invalid 'connections' field in delegated output.")

        chain = data.get("chain")
        if not isinstance(chain, str):
            raise RpcMalformedResponseError("Invalid 'chain' field in delegated output.")

        blocks = data.get("blocks")
        if type(blocks) is not int or isinstance(blocks, bool) or blocks < 0:
            raise RpcMalformedResponseError("Invalid 'blocks' field in delegated output.")

        headers = data.get("headers")
        if type(headers) is not int or isinstance(headers, bool) or headers < 0:
            raise RpcMalformedResponseError("Invalid 'headers' field in delegated output.")

        best_block_hash = data.get("best_block_hash")
        if not isinstance(best_block_hash, str) or not _HEX_64_REGEX.match(best_block_hash):
            raise RpcMalformedResponseError("Invalid 'best_block_hash' field in delegated output.")

        median_time = data.get("median_time")
        if type(median_time) is not int or isinstance(median_time, bool) or median_time < 0:
            raise RpcMalformedResponseError("Invalid 'median_time' field in delegated output.")

        initial_block_download = data.get("initial_block_download")
        if not isinstance(initial_block_download, bool):
            raise RpcMalformedResponseError(
                "Invalid 'initial_block_download' field in delegated output."
            )

        pruned = data.get("pruned")
        if not isinstance(pruned, bool):
            raise RpcMalformedResponseError("Invalid 'pruned' field in delegated output.")

        raw_chainwork = data.get("chainwork")
        chainwork: str | None = None
        if raw_chainwork is not None:
            if not isinstance(raw_chainwork, str) or not _HEX_64_REGEX.match(raw_chainwork):
                raise RpcMalformedResponseError("Invalid 'chainwork' field in delegated output.")
            chainwork = raw_chainwork

        if version != 310100 or chain != "regtest":
            raise RpcIncompatibleNodeError("Delegated node reported incompatible version or chain.")

        return NodeOverview(
            version=version,
            subversion=subversion,
            network_active=network_active,
            connections=connections,
            chain=chain,
            blocks=blocks,
            headers=headers,
            best_block_hash=best_block_hash,
            median_time=median_time,
            initial_block_download=initial_block_download,
            pruned=pruned,
            chainwork=chainwork,
        )

    def inspect_block(
        self,
        node_id: str,
        *,
        block_hash: str | None = None,
        height: int | None = None,
        timeout: float = 10.0,
    ) -> BlockSummary:
        """Execute delegated read-only block inspection through the Bitheim boundary.

        Args:
            node_id: Cleaned and validated node identifier.
            block_hash: Block hash.
            height: Block height.
            timeout: Command deadline in seconds.

        Returns:
            Validated BlockSummary domain object.

        Raises:
            RpcUnavailableError: If node is stopped or runtime is unreachable.
            RpcTimeoutError: If execution exceeds deadline.
            RpcError: On delegated inspection failure.
        """
        if type(timeout) not in (int, float) or isinstance(timeout, bool):
            raise RpcError("Command deadline must be a numeric value.")
        float_timeout = float(timeout)

        if (
            float_timeout <= 0
            or math.isnan(float_timeout)
            or math.isinf(float_timeout)
            or float_timeout > 60.0
        ):
            raise RpcError("Command deadline must be a positive finite value no greater than 60s.")

        has_hash = block_hash is not None
        has_height = height is not None
        if has_hash == has_height:
            raise RpcError("Exactly one of block_hash or height must be provided.")

        if has_hash and (
            not isinstance(block_hash, str) or not re.match(r"^[0-9a-f]{64}$", block_hash)
        ):
            raise RpcError("block_hash must be a 64-character lowercase hex string.")

        if has_height and (type(height) is not int or isinstance(height, bool) or height < 0):
            raise RpcError("height must be a non-negative integer.")

        deadline = time.monotonic() + float_timeout

        try:
            self._check_docker_runtime_available(deadline)
        except RuntimeUnavailableError:
            raise RpcUnavailableError(
                "Docker runtime is unavailable for node inspection."
            ) from None

        state = self._get_lifecycle_state_deadline(node_id, deadline)
        if state == NodeLifecycleState.STOPPED:
            raise RpcUnavailableError(
                f"Managed node '{node_id}' is stopped. Start the node before inspecting."
            )

        extra_args = []
        if block_hash is not None:
            extra_args.extend(["--hash", block_hash])
        elif height is not None:
            extra_args.extend(["--height", str(height)])

        data = self._run_delegated_inspection(node_id, deadline, "block", extra_args)
        return self._parse_block_summary(data)

    def inspect_mempool(self, node_id: str, timeout: float = 10.0) -> MempoolSummary:
        """Execute a safe delegated mempool inspection via compose run.

        Args:
            node_id: Cleaned and validated node identifier.
            timeout: Command deadline in seconds.

        Returns:
            Validated MempoolSummary domain object.

        Raises:
            RpcUnavailableError: If node is stopped or runtime is unreachable.
            RpcTimeoutError: If execution exceeds deadline.
            RpcError: On delegated inspection failure.
        """
        if type(timeout) not in (int, float) or isinstance(timeout, bool):
            raise RpcError("Command deadline must be a numeric value.")
        float_timeout = float(timeout)

        if (
            float_timeout <= 0
            or math.isnan(float_timeout)
            or math.isinf(float_timeout)
            or float_timeout > 60.0
        ):
            raise RpcError("Command deadline must be a positive finite value no greater than 60s.")

        deadline = time.monotonic() + float_timeout

        try:
            self._check_docker_runtime_available(deadline)
        except RuntimeUnavailableError:
            raise RpcUnavailableError(
                "Docker runtime is unavailable for mempool inspection."
            ) from None

        state = self._get_lifecycle_state_deadline(node_id, deadline)
        if state == NodeLifecycleState.STOPPED:
            raise RpcUnavailableError("Managed node is stopped. Start the node before inspecting.")

        data = self._run_delegated_inspection(node_id, deadline, "mempool", [])
        return self._parse_mempool_summary(data)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _run_delegated_inspection(
        self, node_id: str, deadline: float, inspection_type: str, extra_args: list[str]
    ) -> dict[str, Any]:
        r = _remaining(deadline)
        if r <= 0:
            raise RpcTimeoutError(
                f"Timeout budget expired before delegated {inspection_type} inspection."
            )

        env = self._build_env(node_id)
        cmd = [
            self._docker_cmd,
            "compose",
            "-f",
            str(self._compose_template),
            "--project-name",
            node_id,
            "run",
            "--rm",
            "--no-deps",
            "-T",
            "bitheim",
            "inspect",
            inspection_type,
        ]
        cmd.extend(extra_args)
        cmd.append("--json")

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=r,
            )
        except subprocess.TimeoutExpired:
            raise RpcTimeoutError(f"Delegated {inspection_type} inspection timed out.") from None
        except OSError:
            raise RpcError(f"Failed to execute delegated {inspection_type} inspection.") from None

        if res.returncode != 0:
            if res.stderr and len(res.stderr.encode("utf-8")) <= 16384:
                err_lines = res.stderr.strip().splitlines()
                if err_lines and (
                    len(err_lines) == 1
                    or (len(err_lines) == 2 and err_lines[1].startswith("bitheim: error:"))
                ):
                    err_str = err_lines[0].strip()
                    if err_str.startswith("{") and err_str.endswith("}"):
                        import contextlib

                        with contextlib.suppress(ValueError, TypeError):
                            err_info = json.loads(err_str, object_pairs_hook=_reject_duplicate_keys)
                            if isinstance(err_info, dict):
                                err_type = None
                                if (
                                    err_info.get("schema") == "bitheim.delegated-error"
                                    and err_info.get("version") == 1
                                    and set(err_info.keys()) == {"schema", "version", "category"}
                                ):
                                    err_type = err_info.get("category")

                                if err_type == "authentication":
                                    raise RpcAuthenticationError(
                                        "Delegated RPC authentication failed."
                                    )
                                if err_type == "incompatible":
                                    raise RpcIncompatibleNodeError(
                                        "Node reported incompatible chain or version."
                                    )
                                if err_type == "timeout":
                                    raise RpcTimeoutError(
                                        f"Delegated {inspection_type} inspection timed out."
                                    )
                                if err_type == "malformed_response":
                                    raise RpcMalformedResponseError(
                                        f"Delegated {inspection_type} returned malformed response."
                                    )
                                if err_type == "not_found":
                                    raise RpcResourceNotFoundError(
                                        "Requested resource was not found."
                                    )
                                if err_type == "unavailable":
                                    raise RpcUnavailableError(
                                        f"Delegated {inspection_type} endpoint unavailable."
                                    )
            raise RpcUnavailableError(f"Delegated {inspection_type} inspection failed.")

        if len(res.stdout.encode("utf-8")) > 65536:
            raise RpcResponseSizeExceededError(
                f"Delegated {inspection_type} inspection output exceeded size limit."
            )

        try:
            parsed = json.loads(res.stdout.strip(), object_pairs_hook=_reject_duplicate_keys)
        except (json.JSONDecodeError, ValueError):
            raise RpcMalformedResponseError(
                "Failed to parse delegated inspection response."
            ) from None

        if not isinstance(parsed, dict):
            raise RpcMalformedResponseError("Delegated inspection returned non-object JSON.")

        _check_json_depth(parsed, depth=1)

        return parsed

    def _parse_block_summary(self, data: dict[str, Any]) -> BlockSummary:
        try:
            return BlockSummary(
                hash=data.get("hash"),  # type: ignore[arg-type]
                height=data.get("height"),  # type: ignore[arg-type]
                confirmations=data.get("confirmations"),  # type: ignore[arg-type]
                timestamp=data.get("timestamp"),  # type: ignore[arg-type]
                transaction_count=data.get("transaction_count"),  # type: ignore[arg-type]
                size=data.get("size"),  # type: ignore[arg-type]
                weight=data.get("weight"),  # type: ignore[arg-type]
                previous_block_hash=data.get("previous_block_hash"),
                next_block_hash=data.get("next_block_hash"),
            )
        except ValueError:
            raise RpcMalformedResponseError("Invalid domain block facts.") from None

    def _parse_mempool_summary(self, data: dict[str, Any]) -> MempoolSummary:
        try:
            return MempoolSummary(
                loaded=data.get("loaded"),  # type: ignore[arg-type]
                transaction_count=data.get("transaction_count"),  # type: ignore[arg-type]
                serialized_bytes=data.get("serialized_bytes"),  # type: ignore[arg-type]
                dynamic_memory_usage=data.get("dynamic_memory_usage"),  # type: ignore[arg-type]
                max_memory=data.get("max_memory"),  # type: ignore[arg-type]
                total_fees_satoshis=data.get("total_fees_satoshis"),  # type: ignore[arg-type]
            )
        except ValueError:
            raise RpcMalformedResponseError("Invalid domain mempool facts.") from None

    def _locate_bitheim_build_context(self) -> Path | None:
        """Locate the repository-root Dockerfile for building the Bitheim image.

        Returns None when the Dockerfile cannot be found (installed-wheel case).
        The caller receives None and _ensure_image_available will raise a clear
        RuntimeUnavailableError if the image is also missing from the daemon.
        """
        # Relative to compose resources module
        repo_root = Path(__file__).resolve().parents[4]
        candidate = repo_root / "Dockerfile"
        if candidate.is_file():
            return repo_root
        return None

    def _get_lifecycle_state_deadline(self, node_id: str, deadline: float) -> NodeLifecycleState:
        """Inspect container process state using the shared deadline.

        Returns UNKNOWN for ambiguous, malformed, or unexpected output.
        Returns UNKNOWN when containers exist but bitcoin-core is absent
        (non-empty unexpected services).
        """
        self._check_docker_runtime_available(deadline)
        env = self._build_env(node_id)
        cmd = [
            self._docker_cmd,
            "compose",
            "-f",
            str(self._compose_template),
            "--project-name",
            node_id,
            "ps",
            "--format",
            "json",
        ]

        r = _remaining(deadline)
        if r <= 0:
            raise RuntimeUnavailableError("Timeout budget expired before lifecycle state check")

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=r,
            )
            if res.returncode != 0:
                logger.error(
                    "Compose ps command failed",
                    extra={
                        "event": "compose_ps_failed",
                        "data": {"error_type": "process_error"},
                    },
                )
                raise RuntimeUnavailableError("Failed to inspect node services via Docker Compose")

            stdout = res.stdout.strip()
            if not stdout:
                return NodeLifecycleState.STOPPED

            containers: list[dict[str, Any]] = []
            try:
                if stdout.startswith("["):
                    parsed = json.loads(stdout)
                    if isinstance(parsed, list):
                        containers = [c for c in parsed if isinstance(c, dict)]
                else:
                    for line in stdout.splitlines():
                        stripped = line.strip()
                        if stripped:
                            obj = json.loads(stripped)
                            if isinstance(obj, dict):
                                containers.append(obj)
            except json.JSONDecodeError:
                return NodeLifecycleState.UNKNOWN

            if not containers:
                return NodeLifecycleState.STOPPED

            # Find bitcoin-core service by exact name match
            for c in containers:
                service = c.get("Service", "")
                if service != "bitcoin-core":
                    continue

                state = str(c.get("State", "")).lower()
                if state in _RUNNING_STATES:
                    health = str(c.get("Health", "")).lower()
                    if health == "unhealthy":
                        return NodeLifecycleState.UNHEALTHY
                    return NodeLifecycleState.STARTING
                if state in _STOPPED_STATES:
                    return NodeLifecycleState.STOPPED

                # Unrecognized state → UNKNOWN
                return NodeLifecycleState.UNKNOWN

            # Containers exist but bitcoin-core is not among them → UNKNOWN
            return NodeLifecycleState.UNKNOWN
        except subprocess.TimeoutExpired:
            raise RuntimeUnavailableError("Docker Compose ps timed out") from None
        except OSError:
            raise RuntimeUnavailableError("Failed to execute Docker Compose ps") from None

    @staticmethod
    def _parse_delegated_health(stdout: str) -> NodeHealth:
        """Parse and validate delegated health probe JSON.

        Enforces exact chain/version at this boundary — does not blindly trust
        a state string from the delegated container.  A HEALTHY result requires
        chain == "regtest" and version == 310100 with correct types.
        """
        raw = stdout.strip()
        if not raw:
            return NodeHealth(state=NodeLifecycleState.UNKNOWN, details="empty_probe_response")

        try:
            probe_data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return NodeHealth(state=NodeLifecycleState.UNKNOWN, details="malformed_probe_response")

        if not isinstance(probe_data, dict):
            return NodeHealth(state=NodeLifecycleState.UNKNOWN, details="malformed_probe_response")

        health_data = probe_data.get("health", {})
        if not isinstance(health_data, dict):
            return NodeHealth(state=NodeLifecycleState.UNKNOWN, details="malformed_probe_response")

        state_str = str(health_data.get("state", "unknown")).lower()
        chain = health_data.get("chain")
        version = health_data.get("version")
        blocks = health_data.get("blocks")
        headers = health_data.get("headers")
        details = health_data.get("details")

        try:
            health_state = NodeLifecycleState(state_str)
        except ValueError:
            health_state = NodeLifecycleState.UNKNOWN

        # Independent enforcement: HEALTHY requires exact chain and version
        if health_state == NodeLifecycleState.HEALTHY and (
            chain != EXPECTED_CHAIN or version != EXPECTED_BITCOIN_VERSION
        ):
            health_state = NodeLifecycleState.INCOMPATIBLE
            if details is None or details == "ready":
                details = "delegated_contract_mismatch"

        return NodeHealth(
            state=health_state,
            chain=str(chain) if isinstance(chain, str) else None,
            version=int(version) if isinstance(version, int) else None,
            blocks=int(blocks) if isinstance(blocks, int) else None,
            headers=int(headers) if isinstance(headers, int) else None,
            details=str(details) if details is not None else None,
        )
