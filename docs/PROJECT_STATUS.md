# Project Status

## Current Release
`v0.2.0 — Managed Regtest Node`

## Active Release Plan
[`docs/releases/v0.2.0-plan.md`](releases/v0.2.0-plan.md)

## Current Phase
Phase 3 of 6 — Secure RPC and Read-Only Observation

## Active Increment
Define the secure, typed, read-only RPC observation contract for node, blockchain, block, mempool, and peer inspection before implementation.

## Active Specifications
- [`SPEC-0004: Managed Regtest Node Runtime Contract`](specs/SPEC-0004-managed-regtest-node-runtime.md) (Accepted)
- [`SPEC-0005: Secure RPC and Read-Only Observation`](specs/SPEC-0005-secure-rpc-read-only-observation.md) (Accepted)

## Relevant Architecture Decisions
- [`ADR-0001: Modular Monolith`](adr/ADR-0001-modular-monolith.md)
- [`ADR-0002: Hexagonal Architecture with Incremental Boundaries`](adr/ADR-0002-hexagonal-architecture-with-incremental-boundaries.md)
- [`ADR-0003: uv Project and Environment Management`](adr/ADR-0003-uv-project-and-environment-management.md)
- [`ADR-0005: Docker Compose Runtime Topology`](adr/ADR-0005-docker-compose-runtime-topology.md) (Accepted)

## Status
Architecture and specification planning

## Next Action
Plan and delegate the bounded Phase 3 implementation governed by accepted `SPEC-0005`.

## Blockers
None.

## Completed
- Initialized repository structure with `uv` package management (`src-layout`).
- Translated and integrated the Bitheim Master Plan into [`docs/plan_bitheim.md`](plan_bitheim.md).
- Created the public repository under the `Arkhemyth` organization on GitHub with SSH synchronization.
- Established and refined collaboration entrypoints and standards (`AGENTS.md`, `docs/PROJECT_STATUS.md`, `.agents/rules/git-workflow.md`).
- Established reproducible development and quality baseline (Python 3.13, Ruff, MyPy, Pytest) and validated GitHub Actions CI workflow remotely.
- Implemented and integrated minimal executable CLI (`bitheim`) using stdlib `argparse` with `--help` and `--version` support.
- Defined architectural specification [`docs/specs/SPEC-0001-configuration-and-doctor.md`](specs/SPEC-0001-configuration-and-doctor.md).
- Implemented read-only configuration subsystem with strict schema validation and deterministic precedence (default < file < environment < CLI).
- Added `bitheim doctor` diagnostic subcommand checking Python 3.13 compatibility, configuration validity, and data directory access without side effects.
- Added comprehensive unit and functional tests across configuration loading, error conditions, and CLI diagnostics.
- Defined architectural specification [`docs/specs/SPEC-0002-container-image-foundation.md`](specs/SPEC-0002-container-image-foundation.md).
- Created multi-stage reproducible Dockerfile with pinned multi-arch base images, non-root user model, and isolated runtime virtual environment.
- Configured `.dockerignore` to ensure minimal and clean build context.
- Extended GitHub Actions CI workflow with native container smoke tests and multi-platform (`linux/amd64`, `linux/arm64`) build validation.
- Defined architectural specification [`docs/specs/SPEC-0003-structured-logging.md`](specs/SPEC-0003-structured-logging.md).
- Implemented pure Python standard library JSON Lines structured logging foundation emitting strictly to `stderr` with ISO 8601 UTC timestamps, canonical events, and defense-in-depth sanitization.
- Integrated structured logging into real consumers: configuration loader and `bitheim doctor` diagnostics.
- Added comprehensive unit and functional tests for JSONL schema, stream separation, consumer events, and security properties.
- Established open source governance and community foundation ([`CONTRIBUTING.md`](../CONTRIBUTING.md), [`SECURITY.md`](../SECURITY.md), [`CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md), [`GOVERNANCE.md`](../GOVERNANCE.md)).
- Formulated foundational Architecture Decision Records ([`ADR-0001: Modular Monolith`](adr/ADR-0001-modular-monolith.md), [`ADR-0002: Hexagonal Architecture with Incremental Boundaries`](adr/ADR-0002-hexagonal-architecture-with-incremental-boundaries.md), [`ADR-0003: uv Project and Environment Management`](adr/ADR-0003-uv-project-and-environment-management.md)).
- Aligned GitHub Actions CI type checking gate (`uv run mypy src tests`) with project configuration.
- Configured and verified GitHub repository ruleset protecting `main` with required pull requests, no bypass actors, conversation resolution, and mandatory strict status checks (`Code Quality & Tests` and `Container Image & Multi-Arch Build`).
- Defined architectural specification [`docs/specs/SPEC-0004-managed-regtest-node-runtime.md`](specs/SPEC-0004-managed-regtest-node-runtime.md) and [`ADR-0005: Docker Compose Runtime Topology`](adr/ADR-0005-docker-compose-runtime-topology.md) for Phase 1.
- Implemented and integrated Phase 2 managed node lifecycle and health through PR #10: verified Bitcoin Core 31.1 images for `amd64` and `arm64`, isolated Compose topology, typed lifecycle boundaries, delegated authenticated health probing, secure storage separation, and real CI integration validation.

## In Progress
- Phase 3 contract definition and independent review for secure RPC and read-only observation.

## Future Hardening (Post-v0.1.0 / Towards v1.0, Non-Blocking)
- Automated code coverage measurement and thresholds.
- Automated dependency vulnerability audits and license checks.
- Automated secret detection and repository history scanning.
- Static application security testing (SAST) and advanced static analysis.
- Extended integration and endurance test fixtures.
