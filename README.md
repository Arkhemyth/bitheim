# Bitheim

Distributed platform for experimentation, mining, and analysis on Bitcoin.

## Project Status

In development.

## Documentation

To review the full project specification and planning, refer to the master document:
- [`docs/plan_bitheim.md`](docs/plan_bitheim.md)

## Development Environment

This project uses [`uv`](https://docs.astral.sh/uv/) for package and virtual environment management.

### Environment Initialization

```bash
uv sync
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
