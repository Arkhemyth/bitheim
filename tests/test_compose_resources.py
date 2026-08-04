"""Tests for packaged runtime resource resolution and wheel distribution."""

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from bitheim.infrastructure.compose.resources import (
    get_bitcoin_core_resource_dir,
    get_compose_template_path,
)


def test_runtime_resource_resolution() -> None:
    """Verify that resource functions resolve valid and existing packaged assets."""
    compose_path = get_compose_template_path()
    assert compose_path.exists()
    assert compose_path.is_file()
    assert "bitcoin-core:" in compose_path.read_text(encoding="utf-8")

    btc_dir = get_bitcoin_core_resource_dir()
    assert btc_dir.exists()
    assert btc_dir.is_dir()
    assert (btc_dir / "Dockerfile").exists()
    assert (btc_dir / "bitcoin.conf").exists()


def test_resource_and_docker_directory_synchronization() -> None:
    """Verify byte-for-byte synchronization between resources and repository docker directory."""
    repo_root = Path(__file__).resolve().parent.parent
    docker_dir = repo_root / "docker"
    resources_dir = repo_root / "src" / "bitheim" / "resources"

    if docker_dir.exists():
        # Compare compose.yml
        compose_docker = (docker_dir / "compose.yml").read_text(encoding="utf-8")
        compose_res = (resources_dir / "compose" / "compose.yml").read_text(encoding="utf-8")
        assert compose_docker == compose_res, "docker/compose.yml differs from packaged resource"

        # Compare Dockerfile
        dockerfile_docker = (docker_dir / "bitcoin-core" / "Dockerfile").read_text(encoding="utf-8")
        dockerfile_res = (resources_dir / "bitcoin-core" / "Dockerfile").read_text(encoding="utf-8")
        assert dockerfile_docker == dockerfile_res, (
            "docker/bitcoin-core/Dockerfile differs from packaged resource"
        )

        # Compare bitcoin.conf
        conf_docker = (docker_dir / "bitcoin-core" / "bitcoin.conf").read_text(encoding="utf-8")
        conf_res = (resources_dir / "bitcoin-core" / "bitcoin.conf").read_text(encoding="utf-8")
        assert conf_docker == conf_res, (
            "docker/bitcoin-core/bitcoin.conf differs from packaged resource"
        )


def test_wheel_packaging_and_isolated_resource_resolution(tmp_path: Path) -> None:
    """Verify building wheel includes runtime assets and resolves from site-packages."""
    uv_bin = shutil.which("uv")
    if not uv_bin:
        pytest.skip("uv binary not found in PATH")

    repo_root = Path(__file__).resolve().parent.parent
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()

    # 1. Build wheel archive using uv build
    build_res = subprocess.run(
        [uv_bin, "build", "--wheel", "--out-dir", str(dist_dir)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert build_res.returncode == 0, f"uv build failed: {build_res.stderr}"

    wheel_files = list(dist_dir.glob("*.whl"))
    assert len(wheel_files) == 1, f"Expected 1 wheel file, found {len(wheel_files)}"
    wheel_path = wheel_files[0]

    # 2. Inspect wheel zip contents
    with zipfile.ZipFile(wheel_path, "r") as zf:
        namelist = zf.namelist()
        assert any("bitheim/resources/compose/compose.yml" in name for name in namelist)
        assert any("bitheim/resources/bitcoin-core/Dockerfile" in name for name in namelist)
        assert any("bitheim/resources/bitcoin-core/bitcoin.conf" in name for name in namelist)

        # 3. Extract wheel into isolated mock site-packages directory
        extract_dir = tmp_path / "site-packages"
        extract_dir.mkdir()
        zf.extractall(extract_dir)

    # 4. Execute standalone Python subprocess with PYTHONPATH pointing only to extract_dir
    test_script = (
        "import sys\n"
        "from bitheim.infrastructure.compose.resources import (\n"
        "    get_compose_template_path,\n"
        "    get_bitcoin_core_resource_dir,\n"
        ")\n"
        "compose_path = get_compose_template_path()\n"
        "assert compose_path.exists() and compose_path.is_file()\n"
        "assert 'services:' in compose_path.read_text()\n"
        "btc_dir = get_bitcoin_core_resource_dir()\n"
        "assert btc_dir.exists() and btc_dir.is_dir()\n"
        "assert (btc_dir / 'Dockerfile').exists()\n"
        "assert (btc_dir / 'bitcoin.conf').exists()\n"
        "print('ISOLATED_RESOLVE_SUCCESS')\n"
    )
    clean_env = {
        "PYTHONPATH": str(extract_dir),
        "PATH": sys.path[0] or "/usr/bin",
    }
    proc = subprocess.run(
        [sys.executable, "-c", test_script],
        capture_output=True,
        text=True,
        check=False,
        env=clean_env,
    )
    assert proc.returncode == 0, f"Subprocess isolated resolution failed: {proc.stderr}"
    assert "ISOLATED_RESOLVE_SUCCESS" in proc.stdout
