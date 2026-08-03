"""Configuration data structures, validation, and deterministic loader."""

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from bitheim.bootstrap.logging import get_logger

logger = get_logger("bootstrap.configuration")


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


@dataclass(frozen=True)
class RuntimeConfiguration:
    """Runtime domain configuration parameters.

    Attributes:
        data_dir: Effective local filesystem path for Bitheim data and state.
    """

    data_dir: Path


@dataclass(frozen=True)
class BitheimConfiguration:
    """Root configuration model for Bitheim.

    Attributes:
        runtime: Runtime configuration section.
        config_file: Resolved configuration file path if loaded from disk, or None.
    """

    runtime: RuntimeConfiguration
    config_file: Path | None = None


def load_configuration(
    config_path: Path | str | None = None,
    data_dir: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
    default_config_path: Path | str | None = Path("bitheim.toml"),
) -> BitheimConfiguration:
    """Load and validate Bitheim configuration across the precedence hierarchy.

    Precedence order (lowest to highest):
    1. Default parameters (data_dir = ".bitheim")
    2. TOML configuration file (default_config_path if exists, or explicit config_path)
    3. Environment variable BITHEIM_DATA_DIR
    4. Explicit data_dir parameter (CLI override)

    Args:
        config_path: Optional explicit configuration file path.
        data_dir: Optional explicit runtime data directory override.
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
            if section_key != "runtime":
                _raise_config_error(
                    f"Unexpected section '[{section_key}]' in '{resolved_config_file}'. "
                    "Only '[runtime]' is supported.",
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

    # Step 3: Environment variable override
    if "BITHEIM_DATA_DIR" in env:
        env_val = env["BITHEIM_DATA_DIR"]
        if not env_val.strip():
            _raise_config_error(
                "Environment variable 'BITHEIM_DATA_DIR' cannot be empty.",
                error_type="validation_error",
            )
        effective_data_dir = Path(env_val).expanduser()
        source_type = "environment"

    # Step 4: CLI override
    if data_dir is not None:
        data_dir_str = str(data_dir)
        if not data_dir_str.strip():
            _raise_config_error(
                "CLI option '--data-dir' cannot be empty.", error_type="validation_error"
            )
        effective_data_dir = Path(data_dir_str).expanduser()
        source_type = "cli"

    config = BitheimConfiguration(
        runtime=RuntimeConfiguration(data_dir=effective_data_dir),
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
