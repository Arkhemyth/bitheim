# Project Status

## Current Release
`v0.2.0 — Managed Regtest Node`

## Active Release Plan
[`docs/releases/v0.2.0-plan.md`](releases/v0.2.0-plan.md)

## Current Phase
Phase 4 of 6 — Wallet and Regtest Funds

## Active Increment
Phase 4 planning: define the wallet and regtest-funds contract and split it into narrow contract-first increments before implementation begins.

## Active Specifications
- Phase 4 wallet and regtest-funds specification: pending planning and acceptance.
- [`SPEC-0004: Managed Regtest Node Runtime Contract`](specs/SPEC-0004-managed-regtest-node-runtime.md) (Accepted)
- [`SPEC-0005: Secure RPC and Read-Only Observation`](specs/SPEC-0005-secure-rpc-read-only-observation.md) (Accepted)

## Relevant Architecture Decisions
- [`ADR-0001: Modular Monolith`](adr/ADR-0001-modular-monolith.md)
- [`ADR-0002: Hexagonal Architecture with Incremental Boundaries`](adr/ADR-0002-hexagonal-architecture-with-incremental-boundaries.md)
- [`ADR-0003: uv Project and Environment Management`](adr/ADR-0003-uv-project-and-environment-management.md)
- [`ADR-0005: Docker Compose Runtime Topology`](adr/ADR-0005-docker-compose-runtime-topology.md) (Accepted)

## Status
Phase 3 secure RPC and read-only observation is complete across node, blockchain, block, mempool, and peer use cases. Peer inspection reflects the Bitcoin Core 31.x removal of `startingheight`, preserves unknown synced heights as optional values, enforces the 256-peer bound at both RPC and delegated boundaries, and protects endpoint privacy. Phase 4 has not begun implementation.

## Most Recently Protected Executable Contracts
- Path: [`tests/test_phase3b2_peer_contracts.py`](../tests/test_phase3b2_peer_contracts.py)
- SHA-256: `afaaa8f63a31f4315b7dd14a994f1d65284dfcfc9a86d86f7c53d1260a835c02`
- Baseline: 78 protected peer contract cases are active and passing without modification, supplemented by 6 focused correction regressions in [`tests/test_phase3b2_peer_corrections.py`](../tests/test_phase3b2_peer_corrections.py). All historical tests remain active.
- Preservation rule: implementation may add complementary tests but must not modify this file or remove, skip, weaken, replace, or broadly rewrite tests integrated into `main` without explicit maintainer approval under [the increment workflow](../.agents/rules/increment-workflow.md).

## Next Action
Plan Phase 4, accept its wallet and regtest-funds specification, split it into narrow vertical increments, and define the first protected executable contracts before delegating implementation.

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
- Implemented and integrated Phase 3A secure node and chain observation through PR #12: bounded authenticated JSON-RPC, immutable node overview, application and Compose delegation boundaries, deterministic human and JSON CLI output, read-only doctor integration, protected contracts, and real Bitcoin Core 31.1 validation.
- Established the reusable contract-first increment workflow and split Phase 3B into independently reviewable block-inspection and mempool/peer vertical increments.
- Completed and independently reviewed Phase 3B.1 read-only block inspection by hash or height while preserving its 48 protected contracts and all historical tests.
- Completed and independently reviewed Phase 3B.2a read-only mempool observation while preserving its 45 protected contracts and all historical tests.
- Completed and independently reviewed Phase 3B.2b read-only peer observation while preserving its 78 protected contracts and all historical tests.

## In Progress
- Phase 4 wallet and regtest-funds planning and contract definition.

## Future Hardening (Post-v0.1.0 / Towards v1.0, Non-Blocking)
- Automated code coverage measurement and thresholds.
- Automated dependency vulnerability audits and license checks.
- Automated secret detection and repository history scanning.
- Static application security testing (SAST) and advanced static analysis.
- Extended integration and endurance test fixtures.
