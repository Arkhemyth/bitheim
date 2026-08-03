# Contributing to Bitheim

Thank you for your interest in contributing to **Bitheim**! We welcome contributions that help advance our distributed platform for experimentation, mining, and analysis on Bitcoin.

This document outlines the workflow, development environment, quality standards, and collaboration rules required for all contributors.

---

## 1. Code of Conduct

All participants in the Bitheim project are expected to adhere to our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it to understand our community standards and enforcement guidelines.

---

## 2. Development Environment

Bitheim uses [`uv`](https://docs.astral.sh/uv/) exclusively for Python package, virtual environment, and dependency management.

### Prerequisites

- Python 3.13 or higher
- `uv` (version `0.11.31` or later recommended)
- `git`
- Docker (optional, for local container image validation)

### Initializing the Environment

Clone the repository and synchronize the locked dependencies:

```bash
git clone git@github.com:Arkhemyth/bitheim.git
cd bitheim
uv sync --locked --all-groups
```

### Running the CLI

Run the local CLI entrypoint using `uv run`:

```bash
uv run bitheim --help
uv run bitheim --version
uv run bitheim doctor
```

---

## 3. Git and Branching Workflow

Bitheim uses a trunk-based development workflow centered around the `main` branch.

### 3.1 Language Policy

English is the mandatory official language for all repository content:
- Code, docstrings, and inline comments
- Commit messages and pull request descriptions
- Documentation, issues, and discussions

### 3.2 Feature Branches

1. Ensure your local `main` branch is clean and up to date with `origin/main`.
2. Create a focused, short-lived feature branch with a descriptive prefix:
   - `feat/<short-description>`: New features or capabilities.
   - `fix/<short-description>`: Bug fixes and defect corrections.
   - `docs/<short-description>`: Documentation improvements.
   - `chore/<short-description>`: Tooling, dependency, or maintenance tasks.
   - `refactor/<short-description>`: Structural code improvements without behavioral changes.
   - `test/<short-description>`: Test suite additions or enhancements.

```bash
git checkout main
git pull origin main
git checkout -b feat/my-feature-name
```

### 3.3 Commit Message Standards

Bitheim follows the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```text
<type>: <short description in imperative mood>

[optional detailed body]
```

Examples:
- `feat: add structured logging foundation and consumer instrumentation`
- `fix: correct return type annotations in test helpers`
- `docs: update project roadmap and status`

---

## 4. Quality Gates and Local Verification

All contributions integrated into `main` must pass all local quality gates cleanly before opening a pull request.

Run the following checks locally:

```bash
# 1. Ensure dependency lockfile consistency
uv sync --locked --all-groups

# 2. Verify code formatting
uv run ruff format --check .

# 3. Lint the codebase
uv run ruff check .

# 4. Strict static type analysis
uv run mypy src tests

# 5. Execute automated test suite
uv run pytest

# 6. Check for whitespace or git diff anomalies
git diff --check
```

---

## 5. Architectural Changes and Specifications (SPECs / ADRs)

- **Small & Reversible Changes:** Bug fixes, small CLI extensions, minor refactorings, and documentation updates do not require a formal specification.
- **Durable Architectural Changes:** Cross-cutting subsystems, public API contracts, new schema definitions, data storage models, and protocol-level integrations require an architectural specification (SPEC) under `docs/specs/` or an Architecture Decision Record (ADR) under `docs/adr/` before implementation, as outlined in [`docs/plan_bitheim.md`](docs/plan_bitheim.md).

---

## 6. Security and Privacy Discipline

- **Zero-Secret Policy:** Never commit API keys, passwords, authentication tokens, RPC cookie files, Bitcoin private keys, seed phrases, personal directory paths, or sensitive credentials.
- **Safe Structured Logging:** Operational log events must use categorical metadata and must never record raw configuration strings, un-sanitized exception messages, or personal file paths.
- For reporting security vulnerabilities, see [`SECURITY.md`](SECURITY.md).

---

## 7. Pull Request and Review Process

1. Push your feature branch to your fork or `origin`.
2. Open a Pull Request against `main`.
3. Provide a clear title and description summarizing:
   - The problem or motivation.
   - The implemented solution and architectural impact.
   - Associated SPEC/ADR if applicable.
   - Verification steps and test evidence.
4. Ensure all automated CI checks pass (Code Quality & Tests and Container Image & Multi-Arch Build).
5. Address any review feedback directly on the same feature branch.
6. Once approved and CI is green, the pull request will be merged by a maintainer.
