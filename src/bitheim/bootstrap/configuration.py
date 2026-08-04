"""Configuration data structures, validation, and deterministic loader."""

import ipaddress
import os
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import NoReturn

from bitheim.bootstrap.logging import get_logger

logger = get_logger("bootstrap.configuration")

_VALID_NODE_ID_REGEX = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


class ConfigurationError(Exception):
    """Raised when configuration file parsing, schema validation, or parameter resolution fails."""


def _raise_config_error(
    message: str, error_type: str = "validation_error", cause: BaseException | None = None
) -> NoReturn:
    """Log structured error event and raise ConfigurationError.

    Args:
        message: Human-readable error description for exception message.
        error_type: Categorical error identifier for structured logging.
        cause: Optional underlying exception causing this error.

    Raises:
        ConfigurationError: Always raised with specified human-readable message.
    """
    logger.error(
        "Configuration load failed",
        extra={"event": "configuration_load_failed", "data": {"error_type": error_type}},
    )
    if cause is not None:
        raise ConfigurationError(message) from cause
    raise ConfigurationError(message)


def _validate_node_id(node_id: str) -> str:
    """Validate that node_id satisfies Compose project naming requirements."""
    if not isinstance(node_id, str) or not node_id.strip():
        _raise_config_error(
            "Invalid 'node_id': must be a non-empty string.",
            error_type="validation_error",
        )
    trimmed = node_id.strip()
    if not _VALID_NODE_ID_REGEX.match(trimmed):
        _raise_config_error(
            f"Invalid 'node_id' '{trimmed}': must contain only alphanumeric characters, "
            "dashes, and underscores, starting with an alphanumeric character.",
            error_type="validation_error",
        )
    return trimmed


def _validate_compose_subnet(subnet_str: str) -> str:
    """Validate that compose_subnet is a valid private IPv4 CIDR block."""
    if not isinstance(subnet_str, str) or not subnet_str.strip():
        _raise_config_error(
            "Invalid 'compose_subnet': must be a non-empty string.",
            error_type="validation_error",
        )
    trimmed = subnet_str.strip()
    try:
        network = ipaddress.ip_network(trimmed, strict=False)
    except ValueError as err:
        _raise_config_error(
            f"Invalid 'compose_subnet' '{trimmed}': not a valid IP network CIDR.",
            error_type="validation_error",
            cause=err,
        )
    if not isinstance(network, ipaddress.IPv4Network):
        _raise_config_error(
            f"Invalid 'compose_subnet' '{trimmed}': only IPv4 subnets are supported.",
            error_type="validation_error",
        )
    if not network.is_private:
        _raise_config_error(
            f"Invalid 'compose_subnet' '{trimmed}': must be a private RFC 1918 IPv4 subnet.",
            error_type="validation_error",
        )
    return str(network)


def _validate_timeout(val: object, field_name: str) -> float:
    """Validate that a timeout value is a positive finite float."""
    if isinstance(val, (int, float)):
        float_val = float(val)
    elif isinstance(val, str) and val.strip():
        try:
            float_val = float(val.strip())
        except ValueError as err:
            _raise_config_error(
                f"Invalid '{field_name}': must be a numeric value.",
                error_type="validation_error",
                cause=err,
            )
    else:
        _raise_config_error(
            f"Invalid '{field_name}': must be a positive number.",
            error_type="validation_error",
        )

    if float_val <= 0 or not (float_val == float_val and float_val != float("inf")):
        _raise_config_error(
            f"Invalid '{field_name}': must be a positive finite number.",
            error_type="validation_error",
        )
    return float_val


@dataclass(frozen=True)
class RuntimeConfiguration:
    """Runtime domain configuration parameters.

    Attributes:
        data_dir: Effective local filesystem path for Bitheim data and state.
    """

    data_dir: Path


@dataclass(frozen=True)
class NodeConfiguration:
    """Managed node runtime configuration parameters.

    Attributes:
        node_id: Canonical project and node identifier.
        compose_subnet: Dedicated private RFC 1918 IPv4 subnet for the Compose bridge network.
        startup_timeout: Maximum duration in seconds to wait for node readiness.
        shutdown_timeout: Maximum duration in seconds to wait for graceful node shutdown.
    """

    node_id: str = "regtest-node-1"
    compose_subnet: str = "172.28.0.0/16"
    startup_timeout: float = 30.0
    shutdown_timeout: float = 30.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", _validate_node_id(self.node_id))
        object.__setattr__(self, "compose_subnet", _validate_compose_subnet(self.compose_subnet))
        object.__setattr__(
            self, "startup_timeout", _validate_timeout(self.startup_timeout, "startup_timeout")
        )
        object.__setattr__(
            self, "shutdown_timeout", _validate_timeout(self.shutdown_timeout, "shutdown_timeout")
        )


@dataclass(frozen=True)
class BitheimConfiguration:
    """Root configuration model for Bitheim.

    Attributes:
        runtime: Runtime configuration section.
        node: Managed node configuration section.
        config_file: Resolved configuration file path if loaded from disk, or None.
    """

    runtime: RuntimeConfiguration
    node: NodeConfiguration = field(default_factory=NodeConfiguration)
    config_file: Path | None = None


def load_configuration(
    config_path: Path | str | None = None,
    data_dir: Path | str | None = None,
    node_id: str | None = None,
    compose_subnet: str | None = None,
    startup_timeout: float | str | None = None,
    shutdown_timeout: float | str | None = None,
    environ: Mapping[str, str] | None = None,
    default_config_path: Path | str | None = Path("bitheim.toml"),
) -> BitheimConfiguration:
    """Load and validate Bitheim configuration across the precedence hierarchy.

    Precedence order (lowest to highest):
    1. Default parameters
    2. TOML configuration file (default_config_path if exists, or explicit config_path)
    3. Environment variables (BITHEIM_*)
    4. Explicit CLI parameters

    Args:
        config_path: Optional explicit configuration file path.
        data_dir: Optional explicit runtime data directory override.
        node_id: Optional explicit node identifier override.
        compose_subnet: Optional explicit compose subnet CIDR override.
        startup_timeout: Optional explicit startup timeout override.
        shutdown_timeout: Optional explicit shutdown timeout override.
        environ: Optional mapping of environment variables (defaults to os.environ).
        default_config_path: Optional fallback config path if no explicit path is given.

    Returns:
        Validated immutable BitheimConfiguration instance.

    Raises:
        ConfigurationError: If configuration file is missing/unreadable, contains invalid
            TOML, unexpected root sections, unexpected keys, invalid types, or empty values.
    """
    env = os.environ if environ is None else environ
    effective_data_dir: Path = Path(".bitheim").expanduser()
    effective_node_id: str = "regtest-node-1"
    effective_compose_subnet: str = "172.28.0.0/16"
    effective_startup_timeout: float = 30.0
    effective_shutdown_timeout: float = 30.0
    resolved_config_file: Path | None = None
    source_type: str = "defaults"

    # Step 1 & 2: Determine and load configuration file
    if config_path is not None:
        target_path = Path(config_path).expanduser()
        if not target_path.exists():
            _raise_config_error(
                f"Configuration file not found: '{target_path}'", error_type="file_not_found"
            )
        if not target_path.is_file():
            _raise_config_error(
                f"Configuration path is not a regular file: '{target_path}'",
                error_type="not_a_file",
            )
        resolved_config_file = target_path
        source_type = "file"
    elif default_config_path is not None:
        def_path = Path(default_config_path).expanduser()
        if def_path.exists():
            if not def_path.is_file():
                _raise_config_error(
                    f"Default configuration path is not a file: '{def_path}'",
                    error_type="not_a_file",
                )
            resolved_config_file = def_path
            source_type = "file"

    if resolved_config_file is not None:
        try:
            with resolved_config_file.open("rb") as f:
                raw_data = tomllib.load(f)
        except tomllib.TOMLDecodeError as err:
            _raise_config_error(
                f"Failed to parse TOML configuration '{resolved_config_file}': {err}",
                error_type="toml_decode_error",
                cause=err,
            )
        except OSError as err:
            _raise_config_error(
                f"Failed to read configuration file '{resolved_config_file}': {err}",
                error_type="io_error",
                cause=err,
            )

        if not isinstance(raw_data, dict):
            _raise_config_error(
                f"Invalid configuration root in '{resolved_config_file}': expected mapping table.",
                error_type="schema_error",
            )

        for section_key in raw_data:
            if section_key not in ("runtime", "node"):
                _raise_config_error(
                    f"Unexpected section '[{section_key}]' in '{resolved_config_file}'. "
                    "Only '[runtime]' and '[node]' are supported.",
                    error_type="schema_error",
                )

        if "runtime" in raw_data:
            runtime_section = raw_data["runtime"]
            if not isinstance(runtime_section, dict):
                _raise_config_error(
                    f"Invalid section '[runtime]' in '{resolved_config_file}': must be a table.",
                    error_type="schema_error",
                )

            for key in runtime_section:
                if key != "data_dir":
                    _raise_config_error(
                        f"Unexpected field '{key}' in '[runtime]' of '{resolved_config_file}'. "
                        "Only 'data_dir' is supported.",
                        error_type="schema_error",
                    )

            if "data_dir" in runtime_section:
                val = runtime_section["data_dir"]
                if not isinstance(val, str) or not val.strip():
                    _raise_config_error(
                        f"Invalid 'data_dir' in '{resolved_config_file}': "
                        "must be a non-empty string.",
                        error_type="validation_error",
                    )
                effective_data_dir = Path(val).expanduser()

        if "node" in raw_data:
            node_section = raw_data["node"]
            if not isinstance(node_section, dict):
                _raise_config_error(
                    f"Invalid section '[node]' in '{resolved_config_file}': must be a table.",
                    error_type="schema_error",
                )

            allowed_node_keys = {
                "node_id",
                "compose_subnet",
                "startup_timeout",
                "shutdown_timeout",
            }
            for key in node_section:
                if key not in allowed_node_keys:
                    _raise_config_error(
                        f"Unexpected field '{key}' in '[node]' of '{resolved_config_file}'.",
                        error_type="schema_error",
                    )

            if "node_id" in node_section:
                effective_node_id = _validate_node_id(node_section["node_id"])

            if "compose_subnet" in node_section:
                effective_compose_subnet = _validate_compose_subnet(node_section["compose_subnet"])

            if "startup_timeout" in node_section:
                effective_startup_timeout = _validate_timeout(
                    node_section["startup_timeout"], "startup_timeout"
                )

            if "shutdown_timeout" in node_section:
                effective_shutdown_timeout = _validate_timeout(
                    node_section["shutdown_timeout"], "shutdown_timeout"
                )

    # Step 3: Environment variable overrides
    if "BITHEIM_DATA_DIR" in env:
        env_val = env["BITHEIM_DATA_DIR"]
        if not env_val.strip():
            _raise_config_error(
                "Environment variable 'BITHEIM_DATA_DIR' cannot be empty.",
                error_type="validation_error",
            )
        effective_data_dir = Path(env_val).expanduser()
        source_type = "environment"

    if "BITHEIM_NODE_ID" in env:
        effective_node_id = _validate_node_id(env["BITHEIM_NODE_ID"])
        source_type = "environment"

    if "BITHEIM_COMPOSE_SUBNET" in env:
        effective_compose_subnet = _validate_compose_subnet(env["BITHEIM_COMPOSE_SUBNET"])
        source_type = "environment"

    if "BITHEIM_STARTUP_TIMEOUT" in env:
        effective_startup_timeout = _validate_timeout(
            env["BITHEIM_STARTUP_TIMEOUT"], "startup_timeout"
        )
        source_type = "environment"

    if "BITHEIM_SHUTDOWN_TIMEOUT" in env:
        effective_shutdown_timeout = _validate_timeout(
            env["BITHEIM_SHUTDOWN_TIMEOUT"], "shutdown_timeout"
        )
        source_type = "environment"

    # Step 4: CLI overrides
    if data_dir is not None:
        data_dir_str = str(data_dir)
        if not data_dir_str.strip():
            _raise_config_error(
                "CLI option '--data-dir' cannot be empty.", error_type="validation_error"
            )
        effective_data_dir = Path(data_dir_str).expanduser()
        source_type = "cli"

    if node_id is not None:
        effective_node_id = _validate_node_id(node_id)
        source_type = "cli"

    if compose_subnet is not None:
        effective_compose_subnet = _validate_compose_subnet(compose_subnet)
        source_type = "cli"

    if startup_timeout is not None:
        effective_startup_timeout = _validate_timeout(startup_timeout, "startup_timeout")
        source_type = "cli"

    if shutdown_timeout is not None:
        effective_shutdown_timeout = _validate_timeout(shutdown_timeout, "shutdown_timeout")
        source_type = "cli"

    node_config = NodeConfiguration(
        node_id=effective_node_id,
        compose_subnet=effective_compose_subnet,
        startup_timeout=effective_startup_timeout,
        shutdown_timeout=effective_shutdown_timeout,
    )

    config = BitheimConfiguration(
        runtime=RuntimeConfiguration(data_dir=effective_data_dir),
        node=node_config,
        config_file=resolved_config_file,
    )

    logger.debug(
        "Configuration loaded successfully",
        extra={
            "event": "configuration_loaded",
            "data": {
                "source": source_type,
                "has_custom_config": resolved_config_file is not None,
            },
        },
    )

    return config
