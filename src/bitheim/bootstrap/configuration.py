"""Configuration data structures, validation, and deterministic loader."""

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


class ConfigurationError(Exception):
    """Raised when configuration file parsing, schema validation, or parameter resolution fails."""


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

    # Step 1 & 2: Determine and load configuration file
    if config_path is not None:
        target_path = Path(config_path).expanduser()
        if not target_path.exists():
            raise ConfigurationError(f"Configuration file not found: '{target_path}'")
        if not target_path.is_file():
            raise ConfigurationError(f"Configuration path is not a regular file: '{target_path}'")
        resolved_config_file = target_path
    elif default_config_path is not None:
        def_path = Path(default_config_path).expanduser()
        if def_path.exists():
            if not def_path.is_file():
                raise ConfigurationError(f"Default configuration path is not a file: '{def_path}'")
            resolved_config_file = def_path

    if resolved_config_file is not None:
        try:
            with resolved_config_file.open("rb") as f:
                raw_data = tomllib.load(f)
        except tomllib.TOMLDecodeError as err:
            raise ConfigurationError(
                f"Failed to parse TOML configuration '{resolved_config_file}': {err}"
            ) from err
        except OSError as err:
            raise ConfigurationError(
                f"Failed to read configuration file '{resolved_config_file}': {err}"
            ) from err

        if not isinstance(raw_data, dict):
            raise ConfigurationError(
                f"Invalid configuration root in '{resolved_config_file}': expected mapping table."
            )

        for section_key in raw_data:
            if section_key != "runtime":
                raise ConfigurationError(
                    f"Unexpected section '[{section_key}]' in '{resolved_config_file}'. "
                    "Only '[runtime]' is supported."
                )

        if "runtime" in raw_data:
            runtime_section = raw_data["runtime"]
            if not isinstance(runtime_section, dict):
                raise ConfigurationError(
                    f"Invalid section '[runtime]' in '{resolved_config_file}': must be a table."
                )

            for key in runtime_section:
                if key != "data_dir":
                    raise ConfigurationError(
                        f"Unexpected field '{key}' in '[runtime]' of '{resolved_config_file}'. "
                        "Only 'data_dir' is supported."
                    )

            if "data_dir" in runtime_section:
                val = runtime_section["data_dir"]
                if not isinstance(val, str) or not val.strip():
                    raise ConfigurationError(
                        f"Invalid 'data_dir' in '{resolved_config_file}': "
                        "must be a non-empty string."
                    )
                effective_data_dir = Path(val).expanduser()

    # Step 3: Environment variable override
    if "BITHEIM_DATA_DIR" in env:
        env_val = env["BITHEIM_DATA_DIR"]
        if not env_val.strip():
            raise ConfigurationError("Environment variable 'BITHEIM_DATA_DIR' cannot be empty.")
        effective_data_dir = Path(env_val).expanduser()

    # Step 4: CLI override
    if data_dir is not None:
        data_dir_str = str(data_dir)
        if not data_dir_str.strip():
            raise ConfigurationError("CLI option '--data-dir' cannot be empty.")
        effective_data_dir = Path(data_dir_str).expanduser()

    return BitheimConfiguration(
        runtime=RuntimeConfiguration(data_dir=effective_data_dir),
        config_file=resolved_config_file,
    )
