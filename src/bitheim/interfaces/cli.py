"""Command-line interface entrypoints, argument parsing, and command routing."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from bitheim import __version__
from bitheim.application.service import (
    NodeLifecycleService,
    NodeObservationService,
)
from bitheim.bootstrap.configuration import (
    ConfigurationError,
    load_configuration,
)
from bitheim.bootstrap.logging import get_logger, setup_logging
from bitheim.domain.errors import (
    BitheimError,
    LifecycleError,
    RpcAuthenticationError,
    RpcIncompatibleNodeError,
    RpcMalformedResponseError,
    RpcProtocolError,
    RpcResponseSizeExceededError,
    RpcTimeoutError,
    RpcUnavailableError,
)
from bitheim.domain.node import (
    NodeLifecycleState,
    NodeStatus,
)
from bitheim.infrastructure.bitcoin.rpc_client import BitcoinRpcClient
from bitheim.infrastructure.bitcoin.rpc_probe import probe_rpc_http
from bitheim.infrastructure.compose.adapter import ComposeLifecycleAdapter

logger = get_logger("interfaces.cli")


def _is_container_execution_context() -> bool:
    """Determine whether the current process is executing within a container environment."""
    if os.environ.get("BITHEIM_EXECUTION_CONTEXT") == "container":
        return True
    return bool(Path("/.dockerenv").exists())


def _ensure_host_execution_context(command_name: str) -> None:
    """Ensure that lifecycle commands are only invoked from the host execution context.

    Raises:
        LifecycleError: If invoked from within a container.
    """
    if _is_container_execution_context():
        raise LifecycleError(
            f"Lifecycle command '{command_name}' cannot be run from inside a container. "
            "Execute this command on the host machine."
        )


def _find_nearest_existing_ancestor(path: Path) -> Path | None:
    """Traverse directory hierarchy upward until an existing filesystem path is found.

    Args:
        path: Path to start traversal from.

    Returns:
        Nearest existing Path ancestor, or None if filesystem root is invalid.
    """
    resolved = path.resolve()
    current = resolved.parent
    while True:
        if current.exists():
            return current
        if current.parent == current:
            return None
        current = current.parent


def handle_doctor(args: argparse.Namespace) -> int:
    """Execute diagnostic checks verifying environment, runtime, configuration, and tools.

    Args:
        args: Parsed command-line arguments.

    Returns:
        0 if all diagnostic checks pass, 1 if any check fails.
    """
    logger.debug("Running doctor diagnostic checks", extra={"event": "doctor_started"})
    all_passed = True

    # Check 1: Python runtime compatibility
    if sys.version_info >= (3, 13):  # noqa: UP036
        py_version_str = (
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        )
        sys.stdout.write(f"[✓] Python runtime: {py_version_str} (compatible with >=3.13)\n")
        logger.debug(
            "Python runtime check passed",
            extra={
                "event": "doctor_check_passed",
                "data": {"check": "python_runtime", "version": py_version_str},
            },
        )
    else:
        py_short = sys.version.split()[0]
        sys.stderr.write(f"[✗] Python runtime: {py_short} is incompatible (requires >=3.13)\n")
        logger.error(
            "Python runtime check failed",
            extra={
                "event": "doctor_check_failed",
                "data": {"check": "python_runtime", "version": py_short},
            },
        )
        all_passed = False

    # Check 2: Configuration loading and schema validation
    try:
        config = load_configuration(config_path=args.config, data_dir=args.data_dir)
        source = f"file '{config.config_file}'" if config.config_file else "defaults / environment"
        sys.stdout.write(f"[✓] Configuration: loaded successfully ({source})\n")
        logger.debug(
            "Configuration check passed",
            extra={
                "event": "doctor_check_passed",
                "data": {
                    "check": "configuration",
                    "has_custom_config": config.config_file is not None,
                },
            },
        )
    except ConfigurationError as err:
        sys.stderr.write(f"[✗] Configuration: {err}\n")
        logger.error(
            "Configuration check failed",
            extra={
                "event": "doctor_check_failed",
                "data": {"check": "configuration", "status": "failed"},
            },
        )
        return 1

    # Check 3 & 4: Effective data directory and filesystem accessibility
    data_dir: Path = config.runtime.data_dir
    sys.stdout.write(f"[✓] Effective data directory: {data_dir}\n")

    if data_dir.exists():
        if not data_dir.is_dir():
            sys.stderr.write(
                f"[✗] Data directory access: '{data_dir}' exists but is not a directory\n"
            )
            logger.error(
                "Data directory is not a directory",
                extra={
                    "event": "doctor_check_failed",
                    "data": {"check": "data_dir_access", "reason": "not_a_directory"},
                },
            )
            all_passed = False
        elif not os.access(data_dir, os.W_OK):
            sys.stderr.write(f"[✗] Data directory access: '{data_dir}' is not writable\n")
            logger.error(
                "Data directory is not writable",
                extra={
                    "event": "doctor_check_failed",
                    "data": {"check": "data_dir_access", "reason": "permission_denied"},
                },
            )
            all_passed = False
        else:
            sys.stdout.write("[✓] Data directory access: directory exists and is writable\n")
            logger.debug(
                "Data directory access check passed",
                extra={
                    "event": "doctor_check_passed",
                    "data": {"check": "data_dir_access", "status": "exists_and_writable"},
                },
            )
    else:
        ancestor = _find_nearest_existing_ancestor(data_dir)
        if ancestor is None or not ancestor.exists():
            sys.stderr.write(
                f"[✗] Data directory access: no existing ancestor found for '{data_dir}'\n"
            )
            logger.error(
                "No existing ancestor directory found",
                extra={
                    "event": "doctor_check_failed",
                    "data": {"check": "data_dir_access", "reason": "ancestor_not_found"},
                },
            )
            all_passed = False
        elif not ancestor.is_dir():
            sys.stderr.write(
                f"[✗] Data directory access: nearest ancestor '{ancestor}' is not a directory\n"
            )
            logger.error(
                "Nearest ancestor is not a directory",
                extra={
                    "event": "doctor_check_failed",
                    "data": {"check": "data_dir_access", "reason": "ancestor_not_a_directory"},
                },
            )
            all_passed = False
        elif not os.access(ancestor, os.W_OK):
            sys.stderr.write(
                f"[✗] Data directory access: nearest ancestor '{ancestor}' is not writable\n"
            )
            logger.error(
                "Nearest ancestor is not writable",
                extra={
                    "event": "doctor_check_failed",
                    "data": {"check": "data_dir_access", "reason": "ancestor_permission_denied"},
                },
            )
            all_passed = False
        else:
            sys.stdout.write(
                f"[✓] Data directory access: nearest ancestor '{ancestor}' exists and is writable\n"
            )
            logger.debug(
                "Data directory ancestor access check passed",
                extra={
                    "event": "doctor_check_passed",
                    "data": {"check": "data_dir_access", "status": "ancestor_writable"},
                },
            )

    # Check 5: Container vs Host context diagnostics
    if _is_container_execution_context():
        sys.stdout.write("[✓] Container execution context: skipping host Docker daemon checks\n")
        logger.debug(
            "Container execution context detected, skipping host docker checks",
            extra={"event": "doctor_container_context"},
        )
    else:
        # Check Docker CLI and Daemon
        docker_bin = shutil.which("docker")
        if docker_bin:
            try:
                res = subprocess.run(
                    [docker_bin, "info", "--format", "{{.ServerVersion}}"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=5.0,
                )
                if res.returncode == 0:
                    version_str = res.stdout.strip()
                    sys.stdout.write(f"[✓] Docker Engine: running (version {version_str})\n")
                    logger.debug(
                        "Docker engine check passed",
                        extra={
                            "event": "doctor_check_passed",
                            "data": {"check": "docker_engine", "version": version_str},
                        },
                    )
                else:
                    sys.stderr.write("[✗] Docker Engine: daemon is not running or accessible\n")
                    logger.error(
                        "Docker daemon is not accessible",
                        extra={
                            "event": "doctor_check_failed",
                            "data": {"check": "docker_engine", "reason": "daemon_unreachable"},
                        },
                    )
                    all_passed = False
            except Exception:
                sys.stderr.write("[✗] Docker Engine: failed to query daemon status\n")
                all_passed = False

            # Check Docker Compose plugin
            try:
                res_comp = subprocess.run(
                    [docker_bin, "compose", "version", "--short"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=5.0,
                )
                if res_comp.returncode == 0:
                    comp_ver = res_comp.stdout.strip()
                    sys.stdout.write(f"[✓] Docker Compose: available (version {comp_ver})\n")
                    logger.debug(
                        "Docker compose check passed",
                        extra={
                            "event": "doctor_check_passed",
                            "data": {"check": "docker_compose", "version": comp_ver},
                        },
                    )
                else:
                    sys.stderr.write("[✗] Docker Compose: compose plugin is not available\n")
                    all_passed = False
            except Exception:
                sys.stderr.write("[✗] Docker Compose: failed to query compose plugin\n")
                all_passed = False
        else:
            sys.stderr.write("[✗] Docker Engine: 'docker' executable was not found in PATH\n")
            logger.error(
                "Docker binary not found",
                extra={
                    "event": "doctor_check_failed",
                    "data": {"check": "docker_engine", "reason": "binary_not_found"},
                },
            )
            all_passed = False

    # Check 6: Node RPC observation (SPEC-0005 §10)
    if _is_container_execution_context():
        try:
            client = BitcoinRpcClient(
                rpc_host="bitcoin-core",
                rpc_port=18443,
                cookie_path=Path("/data/rpc/.cookie"),
            )
            service = NodeObservationService(client)
            service.inspect_node(timeout=3.0)
            sys.stdout.write("[✓] Node RPC: authenticated read-only observation verified\n")
            logger.debug("Container RPC check passed", extra={"event": "doctor_rpc_check_passed"})
        except RpcAuthenticationError:
            sys.stderr.write("[✗] Node RPC: authentication rejected or cookie invalid\n")
            all_passed = False
        except RpcIncompatibleNodeError:
            sys.stderr.write("[✗] Node RPC: incompatible chain or version\n")
            all_passed = False
        except (RpcMalformedResponseError, RpcProtocolError, RpcResponseSizeExceededError):
            sys.stderr.write("[✗] Node RPC: malformed protocol response\n")
            all_passed = False
        except (RpcUnavailableError, RpcTimeoutError):
            sys.stderr.write("[✗] Node RPC: RPC transport unavailable\n")
            all_passed = False
        except Exception:
            sys.stderr.write("[✗] Node RPC: observation failed\n")
            all_passed = False
    elif all_passed:
        # On host: check if managed node is currently running
        try:
            bitheim_image = os.environ.get("BITHEIM_IMAGE", "bitheim:local")
            adapter = ComposeLifecycleAdapter(
                compose_subnet=config.node.compose_subnet,
                bitheim_image=bitheim_image,
            )
            state = adapter.get_lifecycle_state(config.node.node_id)
            if state == NodeLifecycleState.STOPPED:
                sys.stdout.write("[✓] Node RPC: managed node is stopped (skipped)\n")
                logger.debug(
                    "Node RPC check skipped (node explicitly stopped)",
                    extra={"event": "doctor_rpc_check_skipped"},
                )
            elif state == NodeLifecycleState.UNKNOWN:
                sys.stderr.write("[✗] Node RPC: managed node state is unknown\n")
                all_passed = False
            elif state in (NodeLifecycleState.STARTING, NodeLifecycleState.HEALTHY):
                try:
                    adapter.inspect_node(config.node.node_id, timeout=3.0)
                    sys.stdout.write("[✓] Node RPC: authenticated read-only observation verified\n")
                    logger.debug(
                        "Node RPC check passed", extra={"event": "doctor_rpc_check_passed"}
                    )
                except RpcAuthenticationError:
                    sys.stderr.write("[✗] Node RPC: authentication rejected\n")
                    all_passed = False
                except RpcIncompatibleNodeError:
                    sys.stderr.write("[✗] Node RPC: incompatible chain or version\n")
                    all_passed = False
                except (RpcMalformedResponseError, RpcProtocolError, RpcResponseSizeExceededError):
                    sys.stderr.write("[✗] Node RPC: malformed protocol response\n")
                    all_passed = False
                except (RpcUnavailableError, RpcTimeoutError):
                    sys.stderr.write("[✗] Node RPC: RPC transport unavailable\n")
                    all_passed = False
                except Exception:
                    sys.stderr.write("[✗] Node RPC: observation failed\n")
                    all_passed = False
            else:
                sys.stderr.write(
                    f"[✗] Node RPC: managed node is in unexpected state '{state.value}'\n"
                )
                all_passed = False
        except Exception:
            sys.stderr.write("[✗] Node RPC: failed to determine node state\n")
            logger.error(
                "Node RPC check failed on exception",
                extra={"event": "doctor_rpc_check_failed"},
            )
            all_passed = False

    logger.debug(
        "Doctor diagnostics completed",
        extra={"event": "doctor_completed", "data": {"passed": all_passed}},
    )
    return 0 if all_passed else 1


def handle_start(args: argparse.Namespace) -> int:
    """Execute 'bitheim start' command to start and verify managed node."""
    _ensure_host_execution_context("start")

    config = load_configuration(
        config_path=args.config,
        data_dir=args.data_dir,
        node_id=args.node_id,
        startup_timeout=args.timeout,
    )
    bitheim_image = os.environ.get("BITHEIM_IMAGE", "bitheim:local")
    adapter = ComposeLifecycleAdapter(
        compose_subnet=config.node.compose_subnet,
        bitheim_image=bitheim_image,
    )
    service = NodeLifecycleService(adapter)

    status = service.start_node(
        node_id=config.node.node_id,
        timeout=config.node.startup_timeout,
    )

    chain_info = f", chain: {status.health.chain}" if status.health.chain else ""
    version_info = f", version: {status.health.version}" if status.health.version else ""
    sys.stdout.write(f"[✓] Node '{status.node_id}' started and healthy{chain_info}{version_info}\n")
    return 0


def handle_stop(args: argparse.Namespace) -> int:
    """Execute 'bitheim stop' command to gracefully shut down managed node."""
    _ensure_host_execution_context("stop")

    config = load_configuration(
        config_path=args.config,
        data_dir=args.data_dir,
        node_id=args.node_id,
        shutdown_timeout=args.timeout,
    )
    bitheim_image = os.environ.get("BITHEIM_IMAGE", "bitheim:local")
    adapter = ComposeLifecycleAdapter(
        compose_subnet=config.node.compose_subnet,
        bitheim_image=bitheim_image,
    )
    service = NodeLifecycleService(adapter)

    status = service.stop_node(
        node_id=config.node.node_id,
        timeout=config.node.shutdown_timeout,
    )

    sys.stdout.write(f"[✓] Node '{status.node_id}' stopped\n")
    return 0


def handle_status(args: argparse.Namespace) -> int:
    """Execute 'bitheim status' command to inspect node state and health."""
    config = load_configuration(
        config_path=args.config,
        data_dir=args.data_dir,
        node_id=args.node_id,
    )

    if _is_container_execution_context():
        # Running inside bitheim container: execute local authenticated HTTP probe
        rpc_host = os.environ.get("BITHEIM_RPC_HOST", "bitcoin-core")
        rpc_port = int(os.environ.get("BITHEIM_RPC_PORT", "18443"))
        cookie_path = os.environ.get("BITHEIM_RPC_COOKIE_FILE", "/data/rpc/.cookie")
        health = probe_rpc_http(rpc_host=rpc_host, rpc_port=rpc_port, cookie_path=cookie_path)
        status = NodeStatus(node_id=config.node.node_id, state=health.state, health=health)
    else:
        bitheim_image = os.environ.get("BITHEIM_IMAGE", "bitheim:local")
        adapter = ComposeLifecycleAdapter(
            compose_subnet=config.node.compose_subnet,
            bitheim_image=bitheim_image,
        )
        service = NodeLifecycleService(adapter)
        status = service.get_node_status(node_id=config.node.node_id)

    if getattr(args, "json", False):
        payload = {
            "node_id": status.node_id,
            "state": status.state.value,
            "health": {
                "state": status.health.state.value,
                "chain": status.health.chain,
                "version": status.health.version,
                "blocks": status.health.blocks,
                "headers": status.health.headers,
                "details": status.health.details,
            },
        }
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    else:
        sys.stdout.write(f"Node ID:  {status.node_id}\n")
        sys.stdout.write(f"State:    {status.state.value}\n")
        if status.health.chain:
            sys.stdout.write(f"Chain:    {status.health.chain}\n")
        if status.health.version:
            sys.stdout.write(f"Version:  {status.health.version}\n")
        if status.health.blocks is not None:
            sys.stdout.write(f"Blocks:   {status.health.blocks}\n")
        if status.health.details:
            sys.stdout.write(f"Details:  {status.health.details}\n")

    return 0


def handle_inspect_node(args: argparse.Namespace) -> int:
    """Execute 'bitheim inspect node' command to retrieve typed node and blockchain overview."""
    config = load_configuration(
        config_path=args.config,
        data_dir=args.data_dir,
        node_id=args.node_id,
    )
    timeout = args.timeout if args.timeout is not None else 10.0

    if _is_container_execution_context():
        client = BitcoinRpcClient(
            rpc_host="bitcoin-core",
            rpc_port=18443,
            cookie_path=Path("/data/rpc/.cookie"),
        )
        service = NodeObservationService(client)
        overview = service.inspect_node(timeout=timeout)
    else:
        bitheim_image = os.environ.get("BITHEIM_IMAGE", "bitheim:local")
        adapter = ComposeLifecycleAdapter(
            compose_subnet=config.node.compose_subnet,
            bitheim_image=bitheim_image,
        )
        overview = adapter.inspect_node(node_id=config.node.node_id, timeout=timeout)

    if getattr(args, "json", False):
        sys.stdout.write(json.dumps(overview.to_dict(), indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(f"Chain:                  {overview.chain}\n")
        sys.stdout.write(f"Version:                {overview.version} ({overview.subversion})\n")
        sys.stdout.write(
            f"Network Active:         {'true' if overview.network_active else 'false'}\n"
        )
        sys.stdout.write(f"Connections:            {overview.connections}\n")
        sys.stdout.write(f"Blocks:                 {overview.blocks}\n")
        sys.stdout.write(f"Headers:                {overview.headers}\n")
        sys.stdout.write(f"Best Block Hash:        {overview.best_block_hash}\n")
        sys.stdout.write(f"Median Time:            {overview.median_time}\n")
        sys.stdout.write(
            f"Initial Block Download: {'true' if overview.initial_block_download else 'false'}\n"
        )
        sys.stdout.write(f"Pruned:                 {'true' if overview.pruned else 'false'}\n")
        if overview.chainwork is not None:
            sys.stdout.write(f"Chainwork:              {overview.chainwork}\n")

    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct and configure the root command-line argument parser.

    Returns:
        Configured ArgumentParser with canonical metadata, standard help,
        version flags, and registered subcommands.
    """
    parser = argparse.ArgumentParser(
        prog="bitheim",
        description="Distributed platform for experimentation, mining, and analysis on Bitcoin.",
    )
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program's version number and exit.",
    )

    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to custom configuration file.",
    )
    common_parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Override runtime data directory path.",
    )

    subparsers = parser.add_subparsers(dest="subcommand", required=False)

    doctor_parser = subparsers.add_parser(
        "doctor",
        parents=[common_parser],
        help="Run system and environment diagnostic checks.",
        description="Run system and environment diagnostic checks.",
    )
    doctor_parser.set_defaults(handler=handle_doctor)

    start_parser = subparsers.add_parser(
        "start",
        parents=[common_parser],
        help="Start managed Bitcoin Core node runtime.",
        description="Start managed Bitcoin Core node runtime.",
    )
    start_parser.add_argument(
        "--node-id",
        type=str,
        default=None,
        help="Target node and project identifier.",
    )
    start_parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Maximum duration in seconds to wait for node readiness.",
    )
    start_parser.set_defaults(handler=handle_start)

    stop_parser = subparsers.add_parser(
        "stop",
        parents=[common_parser],
        help="Gracefully stop managed Bitcoin Core node runtime.",
        description="Gracefully stop managed Bitcoin Core node runtime.",
    )
    stop_parser.add_argument(
        "--node-id",
        type=str,
        default=None,
        help="Target node and project identifier.",
    )
    stop_parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Maximum duration in seconds to wait for node shutdown.",
    )
    stop_parser.set_defaults(handler=handle_stop)

    status_parser = subparsers.add_parser(
        "status",
        parents=[common_parser],
        help="Inspect managed node runtime status and health.",
        description="Inspect managed node runtime status and health.",
    )
    status_parser.add_argument(
        "--node-id",
        type=str,
        default=None,
        help="Target node and project identifier.",
    )
    status_parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Format output as JSON.",
    )
    status_parser.set_defaults(handler=handle_status)

    inspect_parser = subparsers.add_parser(
        "inspect",
        parents=[common_parser],
        help="Inspect Bitcoin Core node and blockchain state.",
        description="Inspect Bitcoin Core node and blockchain state.",
    )
    inspect_subparsers = inspect_parser.add_subparsers(dest="inspect_subcommand", required=True)

    inspect_node_parser = inspect_subparsers.add_parser(
        "node",
        parents=[common_parser],
        help="Inspect node overview and chain facts.",
        description="Inspect node overview and chain facts.",
    )
    inspect_node_parser.add_argument(
        "--node-id",
        type=str,
        default=None,
        help="Target node and project identifier.",
    )
    inspect_node_parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Command deadline in seconds (max 60s).",
    )
    inspect_node_parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Format output as JSON.",
    )
    inspect_node_parser.set_defaults(handler=handle_inspect_node)

    return parser


def _map_error_category(err: Exception) -> str:
    name = type(err).__name__
    mapping = {
        "RpcAuthenticationError": "authentication",
        "RpcIncompatibleNodeError": "incompatible",
        "RpcTimeoutError": "timeout",
        "RpcUnavailableError": "unavailable",
        "RpcMalformedResponseError": "malformed_response",
        "RpcProtocolError": "malformed_response",
        "RpcResponseSizeExceededError": "malformed_response",
        "ConfigurationError": "configuration",
    }
    return mapping.get(name, "unexpected")


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the command-line interface with specified argument vector.

    Args:
        argv: Optional sequence of command-line arguments. When None,
            sys.argv[1:] is processed by the underlying parser.

    Returns:
        Integer exit code (0 for success, non-zero on diagnostic or configuration failure).
    """
    if _is_container_execution_context():
        import logging

        setup_logging(level=logging.CRITICAL + 1)
    else:
        setup_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    if hasattr(args, "handler") and args.handler is not None:
        try:
            return int(args.handler(args))
        except BitheimError as err:
            logger.error(
                "CLI execution failed",
                extra={
                    "event": "cli_command_failed",
                    "data": {"error_type": type(err).__name__},
                },
            )
            if _is_container_execution_context():
                sys.stderr.write(
                    json.dumps(
                        {
                            "schema": "bitheim.delegated-error",
                            "version": 1,
                            "category": _map_error_category(err),
                        }
                    )
                    + "\n"
                )
            sys.stderr.write(f"bitheim: error: {err}\n")
            return 1
        except Exception as err:
            logger.error(
                "Unexpected error during CLI execution",
                extra={
                    "event": "cli_unexpected_error",
                    "data": {"error_type": type(err).__name__},
                },
            )
            if _is_container_execution_context():
                sys.stderr.write(
                    json.dumps(
                        {
                            "schema": "bitheim.delegated-error",
                            "version": 1,
                            "category": _map_error_category(err),
                        }
                    )
                    + "\n"
                )
            sys.stderr.write("bitheim: error: An unexpected error occurred.\n")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
