# Bitheim

Distributed platform for experimentation, mining, and analysis on Bitcoin.

## Project Status

In development.

## Documentation

To review the full project specification, planning, and architectural decisions, refer to:
- [`docs/plan_bitheim.md`](docs/plan_bitheim.md) — Master planning and specification document.
- [`docs/adr/`](docs/adr/) — Architecture Decision Records (ADRs).

## Development Environment

This project uses [`uv`](https://docs.astral.sh/uv/) for package and virtual environment management.

### Environment Initialization

```bash
uv sync --locked --all-groups
```

### Running the CLI

```bash
uv run bitheim --help
uv run bitheim --version
uv run bitheim doctor
```

## Container Usage

Build the reproducible container image locally:

```bash
docker build -t bitheim:local .
```

Run CLI commands and diagnostics inside the container:

```bash
docker run --rm bitheim:local --help
docker run --rm bitheim:local --version
docker run --rm bitheim:local doctor
```

## Community & Governance

- [Contributing Guidelines](CONTRIBUTING.md) — Development setup, branching workflow, quality gates, and contribution guidelines.
- [Security Policy](SECURITY.md) — Vulnerability reporting channels and disclosure process.
- [Code of Conduct](CODE_OF_CONDUCT.md) — Community standards, pledge, and enforcement.
- [Project Governance](GOVERNANCE.md) — Maintainer-led governance model and decision-making.
- [License](LICENSE) — Released under the MIT License.
