# ADR-0001: Modular Monolith Architecture

## Status
Accepted

## Date
2026-08-02

## Context
Bitheim is designed as a distributed experimentation, mining, and telemetry platform for Bitcoin research. A fundamental architectural choice during early-stage development is whether to split system components into distinct microservices or to structure the system as a single deployable application.

Premature decomposition into microservices introduces significant operational overhead: distributed transaction management, network latency across internal boundaries, complex serialization/deserialization, fragmented CI/CD pipelines, and premature interface lock-in before domain boundaries have stabilized.

## Decision
We choose a **modular monolith** architecture for Bitheim:
1. All core capabilities, daemon runtime, CLI interfaces, storage engines, and domain components reside in a single codebase (`src/bitheim/*`).
2. The application is distributed and packaged as a single deployable runtime artifact and container image.
3. Internal module boundaries are established through explicit package structure and architectural design rules, and maintained through code reviews, automated unit/functional tests, and static type analysis.

## Alternatives Considered
- **Microservices Architecture:** Rejected due to excessive operational complexity, network overhead, complex local orchestration, and unnecessary cognitive burden for early-stage development.
- **Unstructured Monolith:** Rejected because lack of clear internal modular boundaries leads to circular dependencies, tight coupling, and fragile refactoring.

## Consequences
- **Positive:**
  - Simplified local development and single-command startup (`uv run bitheim ...`).
  - Fast in-memory function calls between internal subsystems without network serialization costs.
  - Unified testing, linting, and type checking across the entire codebase.
  - Clear refactoring paths with immediate compiler/linter feedback.
- **Negative / Trade-offs:**
  - Requires architectural discipline during code review to preserve package boundaries without dedicated boundary-enforcement linters.
  - Subsystems share a single deployment cycle and Python runtime environment.
