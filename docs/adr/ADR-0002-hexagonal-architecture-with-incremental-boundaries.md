# ADR-0002: Hexagonal Architecture with Incremental Boundaries

## Status
Accepted

## Date
2026-08-02

## Context
Bitheim interacts with multiple external systems, protocols, and data sources (such as Bitcoin Core nodes via JSON-RPC/ZMQ, DuckDB analytical storage, local filesystem configurations, and CLI/API interfaces). A core architectural goal is to protect domain business logic from tight coupling with third-party libraries, database drivers, or communication protocols.

The master plan specifies Hexagonal Architecture (Ports and Adapters) as the foundational architectural pattern. However, during the initial foundation milestone (`v0.1.0`), only foundational runtime capabilities exist (bootstrap, configuration loading, structured logging, containerization, and diagnostic CLI). Creating speculative domain directories, abstract ports, and dummy adapters before actual domain functionality is implemented would introduce dead code and unnecessary cognitive overhead.

## Decision
1. We adopt **Hexagonal Architecture (Ports and Adapters)** for all core domain capabilities, starting with domain feature milestones in `v0.2.0`+.
2. Core domain models and business logic must never import from or depend on external infrastructure or adapters. Application services define the ports required to coordinate the domain, and infrastructure adapters implement those application ports.
3. Application ports and infrastructure adapters are introduced **incrementally and just-in-time** when real external data sources, consumers, or storage engines are implemented.
4. Foundational runtime facilities (`bitheim.bootstrap.configuration`, `bitheim.bootstrap.logging`, and `bitheim.interfaces.cli`) are recognized as foundational bootstrap and CLI entrypoint mechanisms; they are not artificially forced into speculative domain layers or refactored for empty symmetry.

## Alternatives Considered
- **Upfront Full Hexagonal Scaffolding:** Creating empty `domain/`, `ports/`, and `adapters/` packages with stub interfaces during `v0.1.0`. Rejected as speculative architecture and dead code.
- **Traditional Layered / N-Tier Architecture:** Rejected because it allows persistence or framework abstractions to leak into business logic, making isolated testing and database engine substitution difficult.

## Consequences
- **Positive:**
  - Zero dead code or speculative abstractions in `v0.1.0`.
  - Core domain logic will remain pure, testable without network/database mocks, and decoupled from infrastructure details in future milestones.
  - Clear, pragmatic progression: architecture grows organically with each real consumer.
- **Negative / Trade-offs:**
  - Requires architectural vigilance during feature additions in `v0.2.0`+ to ensure contributors do not bypass application ports when connecting external infrastructure.
