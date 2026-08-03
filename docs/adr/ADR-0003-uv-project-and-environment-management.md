# ADR-0003: uv Project and Environment Management

## Status
Accepted

## Date
2026-08-02

## Context
Bitheim requires deterministic dependency resolution, reproducible virtual environment isolation across development environments and CI, a declarative configuration complying with modern Python packaging standards (PEP 517, PEP 518, PEP 621), and multi-stage container image builds for Python 3.13.

## Decision
We adopt [`uv`](https://docs.astral.sh/uv/) as the sole official tool for project configuration, dependency management, virtual environment isolation, lockfile generation, tool execution, and build backend in Bitheim:
1. Project metadata, runtime dependencies, and the `dev` dependency group (Ruff, MyPy, Pytest) are declared in `pyproject.toml`.
2. Environment synchronization is performed using `uv sync --locked --all-groups`.
3. Quality gates and development commands are executed using `uv run <command>`.
4. The multi-stage Docker build uses official `uv` binaries to install dependencies into an isolated runtime virtual environment.

## Alternatives Considered
- **Poetry:** A viable project and dependency management workflow, but adopting it would require a separate toolchain from the `uv`-based CI, container, and command workflow already established for Bitheim.
- **Pipenv:** A viable environment and lockfile workflow, but it was not selected because Bitheim uses `pyproject.toml`, `uv.lock`, and `uv` commands as one consistent project interface.
- **Standard `pip` + `venv` + `requirements.txt`:** Viable as separate packaging and environment tools, but it would require additional conventions or tooling to provide the unified lockfile synchronization, command execution, build backend, CI, and container workflow adopted by Bitheim.

## Consequences
- **Positive:**
  - Unified workflow for package management, virtual environment creation, and tool execution.
  - Standardized `pyproject.toml` conforming to modern Python packaging PEPs.
  - Cross-platform, deterministic `uv.lock` for reproducible builds.
  - Direct integration into CI workflows and multi-stage container builds.
- **Negative / Trade-offs:**
  - Contributors must install `uv` on their local development environments.
