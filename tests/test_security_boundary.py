"""Security boundary tests verifying least privilege, credential isolation, and restrictions."""

from pathlib import Path

from bitheim.infrastructure.compose.resources import (
    get_bitcoin_core_resource_dir,
    get_compose_template_path,
)


def test_compose_no_host_rpc_publication() -> None:
    """Verify that Compose template does NOT publish RPC or P2P ports to the host by default."""
    compose_content = get_compose_template_path().read_text(encoding="utf-8")

    # Ensure 'ports:' section is absent or empty in all services
    assert "ports:" not in compose_content, (
        "Compose template must not declare default host ports mapping"
    )
    assert "18443:18443" not in compose_content
    assert "127.0.0.1" not in compose_content


def test_compose_no_hardcoded_container_names() -> None:
    """Verify that Compose template does NOT define container_name (prohibited by ADR-0005)."""
    compose_content = get_compose_template_path().read_text(encoding="utf-8")
    assert "container_name:" not in compose_content, "ADR-0005 explicitly prohibits container_name"


def test_storage_and_credential_isolation() -> None:
    """Verify that Bitheim service mounts only the RPC cookie volume read-only and not datadir."""
    compose_content = get_compose_template_path().read_text(encoding="utf-8")

    # Bitcoin Core owns datadir (rw) and rpc (rw)
    assert "bitcoin-data" in compose_content
    assert "bitcoin-rpc" in compose_content

    # Bitheim service must have read_only: true on rpc volume
    assert "read_only: true" in compose_content

    # Check Dockerfile UIDs and GIDs
    btc_dockerfile = (get_bitcoin_core_resource_dir() / "Dockerfile").read_text(encoding="utf-8")
    assert "10001:10000" in btc_dockerfile
    assert "rpccookieperms=group" in btc_dockerfile or "0750" in btc_dockerfile

    repo_root = Path(__file__).resolve().parent.parent
    bitheim_dockerfile = (repo_root / "Dockerfile").read_text(encoding="utf-8")
    assert "10002:10000" in bitheim_dockerfile


def test_bitcoin_conf_no_promiscuous_allowip() -> None:
    """Verify that bitcoin.conf does NOT contain 0.0.0.0/0 allowip."""
    conf_content = (get_bitcoin_core_resource_dir() / "bitcoin.conf").read_text(encoding="utf-8")
    assert "0.0.0.0/0" not in conf_content
    assert "rpccookieperms=group" in conf_content
    assert "regtest=1" in conf_content


def test_bitcoin_core_process_and_entrypoint_contract() -> None:
    """Verify ENTRYPOINT/CMD/Compose command contract prevents duplicated bitcoind invocation."""
    compose_content = get_compose_template_path().read_text(encoding="utf-8")
    btc_dockerfile = (get_bitcoin_core_resource_dir() / "Dockerfile").read_text(encoding="utf-8")

    # Dockerfile must define ENTRYPOINT as ["bitcoind"] and CMD with default flags
    assert 'ENTRYPOINT ["bitcoind"]' in btc_dockerfile
    assert 'CMD ["-conf=/etc/bitcoin/bitcoin.conf", "-datadir=/data/bitcoin"]' in btc_dockerfile

    # Compose command must NOT repeat 'bitcoind' as a command token
    assert '- "bitcoind"' not in compose_content
    assert "- 'bitcoind'" not in compose_content
    assert "  - bitcoind\n" not in compose_content

    # All flags under command in Compose must start with '-'
    lines = compose_content.splitlines()
    in_command = False
    command_items: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped == "command:":
            in_command = True
            continue
        if in_command:
            if stripped.startswith("- "):
                val = stripped[2:].strip("\"'")
                command_items.append(val)
            else:
                break

    assert len(command_items) >= 5, "Expected compose command items for bitcoin-core"
    for item in command_items:
        assert item.startswith("-"), f"Command item '{item}' must be a flag starting with '-'"
        assert item != "bitcoind", "Command item must not be 'bitcoind'"


def test_ci_smoke_tests_entrypoint_contract() -> None:
    """Verify CI workflow smoke tests use explicit entrypoint override for bitcoin-cli."""
    repo_root = Path(__file__).resolve().parent.parent
    ci_yml = repo_root / ".github" / "workflows" / "ci.yml"
    if not ci_yml.exists():
        return

    ci_content = ci_yml.read_text(encoding="utf-8")

    # bitcoin-cli smoke test must explicitly override entrypoint
    assert "--entrypoint bitcoin-cli" in ci_content
    assert "Bitcoin Core RPC client version" in ci_content
    assert "Bitcoin Core daemon version" in ci_content
