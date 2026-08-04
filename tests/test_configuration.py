"""Unit tests for the Bitheim configuration loader and schema validation."""

from pathlib import Path

import pytest

from bitheim.bootstrap.configuration import (
    BitheimConfiguration,
    ConfigurationError,
    NodeConfiguration,
    RuntimeConfiguration,
    load_configuration,
)


def test_load_configuration_default_values(tmp_path: Path) -> None:
    """Verify that default configuration produces expected data_dir with no config file."""
    config = load_configuration(
        config_path=None,
        default_config_path=tmp_path / "nonexistent.toml",
        environ={},
    )
    assert isinstance(config, BitheimConfiguration)
    assert isinstance(config.runtime, RuntimeConfiguration)
    assert isinstance(config.node, NodeConfiguration)
    assert config.runtime.data_dir == Path(".bitheim").expanduser()
    assert config.node.node_id == "regtest-node-1"
    assert config.node.compose_subnet == "172.28.0.0/16"
    assert config.node.startup_timeout == 30.0
    assert config.node.shutdown_timeout == 30.0
    assert config.config_file is None


def test_load_configuration_default_config_discovery(tmp_path: Path) -> None:
    """Verify default_config_path is discovered and loaded when config_path is None."""
    default_file = tmp_path / "bitheim.toml"
    default_file.write_text('[runtime]\ndata_dir = "discovered_data_dir"\n', encoding="utf-8")

    config = load_configuration(
        config_path=None,
        default_config_path=default_file,
        environ={},
    )
    assert config.runtime.data_dir == Path("discovered_data_dir").expanduser()
    assert config.config_file == default_file


def test_load_configuration_valid_toml(tmp_path: Path) -> None:
    """Verify that a valid TOML configuration file is correctly parsed and applied."""
    config_file = tmp_path / "bitheim.toml"
    config_file.write_text(
        '[runtime]\ndata_dir = "custom/node_data"\n'
        '[node]\nnode_id = "test-node"\ncompose_subnet = "10.10.0.0/16"\nstartup_timeout = 45.0\n',
        encoding="utf-8",
    )

    config = load_configuration(config_path=config_file, environ={})
    assert config.runtime.data_dir == Path("custom/node_data").expanduser()
    assert config.node.node_id == "test-node"
    assert config.node.compose_subnet == "10.10.0.0/16"
    assert config.node.startup_timeout == 45.0
    assert config.config_file == config_file


def test_load_configuration_explicit_file_not_found(tmp_path: Path) -> None:
    """Verify that an explicitly provided non-existent config file raises ConfigurationError."""
    missing_file = tmp_path / "missing.toml"
    with pytest.raises(ConfigurationError, match="Configuration file not found"):
        load_configuration(config_path=missing_file, environ={})


def test_load_configuration_explicit_path_is_directory(tmp_path: Path) -> None:
    """Verify that providing a directory path as config_path raises ConfigurationError."""
    with pytest.raises(ConfigurationError, match="not a regular file"):
        load_configuration(config_path=tmp_path, environ={})


def test_load_configuration_malformed_toml(tmp_path: Path) -> None:
    """Verify that a syntactically invalid TOML file raises ConfigurationError."""
    bad_toml = tmp_path / "bad.toml"
    bad_toml.write_text("[runtime\ninvalid_syntax", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="Failed to parse TOML configuration"):
        load_configuration(config_path=bad_toml, environ={})


def test_load_configuration_unexpected_root_section(tmp_path: Path) -> None:
    """Verify that unexpected root sections outside [runtime] and [node] are rejected."""
    bad_section = tmp_path / "bad_section.toml"
    bad_section.write_text('[database]\nhost = "localhost"\n', encoding="utf-8")

    with pytest.raises(ConfigurationError, match="Unexpected section '\\[database\\]'"):
        load_configuration(config_path=bad_section, environ={})


def test_load_configuration_unexpected_field_in_runtime(tmp_path: Path) -> None:
    """Verify that unknown keys in [runtime] are rejected."""
    bad_field = tmp_path / "bad_field.toml"
    bad_field.write_text('[runtime]\ndata_dir = ".bitheim"\nunknown_key = 123\n', encoding="utf-8")

    with pytest.raises(
        ConfigurationError, match="Unexpected field 'unknown_key' in '\\[runtime\\]'"
    ):
        load_configuration(config_path=bad_field, environ={})


def test_load_configuration_runtime_not_a_table(tmp_path: Path) -> None:
    """Verify that a non-table [runtime] entry raises ConfigurationError."""
    bad_runtime = tmp_path / "bad_runtime.toml"
    bad_runtime.write_text('runtime = "invalid_string_instead_of_table"\n', encoding="utf-8")

    with pytest.raises(ConfigurationError, match="Invalid section '\\[runtime\\]'"):
        load_configuration(config_path=bad_runtime, environ={})


def test_load_configuration_data_dir_not_string(tmp_path: Path) -> None:
    """Verify that a non-string data_dir raises ConfigurationError."""
    bad_type = tmp_path / "bad_type.toml"
    bad_type.write_text("[runtime]\ndata_dir = 12345\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="Invalid 'data_dir'"):
        load_configuration(config_path=bad_type, environ={})


def test_load_configuration_data_dir_empty_string(tmp_path: Path) -> None:
    """Verify that an empty string for data_dir in TOML raises ConfigurationError."""
    empty_dir = tmp_path / "empty_dir.toml"
    empty_dir.write_text('[runtime]\ndata_dir = "   "\n', encoding="utf-8")

    with pytest.raises(ConfigurationError, match="Invalid 'data_dir'"):
        load_configuration(config_path=empty_dir, environ={})


def test_load_configuration_precedence_chain(tmp_path: Path) -> None:
    """Verify precedence: default < TOML file < environment variable < CLI parameter."""
    config_file = tmp_path / "bitheim.toml"
    config_file.write_text(
        '[runtime]\ndata_dir = "from_file"\n[node]\nnode_id = "file-node"\n', encoding="utf-8"
    )

    # 1. Config file overrides default
    c1 = load_configuration(config_path=config_file, environ={})
    assert c1.runtime.data_dir == Path("from_file").expanduser()
    assert c1.node.node_id == "file-node"

    # 2. Environment variable overrides config file
    c2 = load_configuration(
        config_path=config_file,
        environ={"BITHEIM_DATA_DIR": "from_env", "BITHEIM_NODE_ID": "env-node"},
    )
    assert c2.runtime.data_dir == Path("from_env").expanduser()
    assert c2.node.node_id == "env-node"

    # 3. CLI argument overrides environment variable and file
    c3 = load_configuration(
        config_path=config_file,
        data_dir="from_cli",
        node_id="cli-node",
        environ={"BITHEIM_DATA_DIR": "from_env", "BITHEIM_NODE_ID": "env-node"},
    )
    assert c3.runtime.data_dir == Path("from_cli").expanduser()
    assert c3.node.node_id == "cli-node"


def test_load_configuration_empty_environment_variable() -> None:
    """Verify that an empty BITHEIM_DATA_DIR environment variable raises ConfigurationError."""
    with pytest.raises(
        ConfigurationError, match="Environment variable 'BITHEIM_DATA_DIR' cannot be empty"
    ):
        load_configuration(environ={"BITHEIM_DATA_DIR": "   "})


def test_load_configuration_empty_cli_data_dir() -> None:
    """Verify that an empty CLI data_dir parameter raises ConfigurationError."""
    with pytest.raises(ConfigurationError, match="CLI option '--data-dir' cannot be empty"):
        load_configuration(data_dir="  ", environ={})


def test_load_configuration_is_read_only(tmp_path: Path) -> None:
    """Verify that loading configuration does not create the data directory on disk."""
    target_dir = tmp_path / "non_existent_data_dir"
    assert not target_dir.exists()

    config = load_configuration(data_dir=target_dir, environ={})
    assert config.runtime.data_dir == target_dir
    assert not target_dir.exists()


def test_node_configuration_invalid_node_id() -> None:
    """Verify that invalid node identifiers are rejected."""
    with pytest.raises(ConfigurationError, match="Invalid 'node_id'"):
        load_configuration(node_id="invalid node with spaces", environ={})

    with pytest.raises(ConfigurationError, match="Invalid 'node_id'"):
        load_configuration(node_id="-starts-with-dash", environ={})


def test_node_configuration_invalid_compose_subnet() -> None:
    """Verify that non-private or malformed subnets are rejected."""
    with pytest.raises(ConfigurationError, match="not a valid IP network CIDR"):
        load_configuration(compose_subnet="invalid_subnet", environ={})

    with pytest.raises(ConfigurationError, match="must be a private RFC 1918 IPv4 subnet"):
        load_configuration(compose_subnet="8.8.8.0/24", environ={})


def test_node_configuration_invalid_timeouts() -> None:
    """Verify that zero, negative, or invalid timeouts are rejected."""
    with pytest.raises(ConfigurationError, match="must be a positive finite number"):
        load_configuration(startup_timeout=0.0, environ={})

    with pytest.raises(ConfigurationError, match="must be a positive finite number"):
        load_configuration(shutdown_timeout=-5.0, environ={})
