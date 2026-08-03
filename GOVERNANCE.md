# Project Governance

This document describes the governance structure and decision-making model for **Bitheim**.

---

## 1. Overview and Philosophy

Bitheim operates under a **maintainer-led** open-source governance model. Our goal is to maintain technical rigor, security discipline, and rapid iterative progress while encouraging open collaboration from the broader Bitcoin research and developer community.

---

## 2. Roles and Responsibilities

### 2.1 Contributors

Contributors are community members who participate in the project by:
- Submitting bug reports, feature proposals, and feedback via GitHub Issues.
- Opening pull requests with code, tests, documentation, or specifications.
- Participating in technical reviews and architectural discussions.

Anyone who contributes to Bitheim in accordance with our [Code of Conduct](CODE_OF_CONDUCT.md) and [Contributing Guidelines](CONTRIBUTING.md) is considered a contributor.

### 2.2 Maintainers

Maintainers are the stewards of the project. They hold repository write access and are responsible for:
- Triaging issues and pull requests.
- Reviewing and approving contributions against repository quality and architectural standards.
- Merging pull requests into `main`.
- Overseeing the security lifecycle, private vulnerability remediation, and disclosure.
- Authorizing releases, version tagging, and published packages or container images.
- Maintaining documentation, roadmaps, and architectural specifications.

**Current Lead Maintainer:**
- Diego Peralta ([@PeraltaHD4K](https://github.com/PeraltaHD4K))

---

## 3. Decision-Making Process

### 3.1 Ordinary Technical Decisions

Everyday technical decisions (bug fixes, small feature additions, refactoring, performance improvements, documentation updates) are resolved through normal GitHub Pull Requests:
1. Proposed changes are reviewed by a maintainer.
2. All automated CI checks must pass cleanly.
3. In a sole-maintainer state, the lead maintainer holds final decision authority. When multiple maintainers are active, decisions are reached via consensus among active maintainers.

### 3.2 Architectural and Durable Decisions

For non-trivial architectural changes, new subsystems, breaking changes, or cross-cutting contracts, proposals must be formalized as:
- **SPEC (Specification):** For subsystem contracts, JSON/data schemas, or protocol implementations (located in `docs/specs/`).
- **ADR (Architecture Decision Record):** For durable design choices, database engine selection, or architectural trade-offs (located in `docs/adr/`).

SPECs and ADRs must be reviewed and accepted before implementation proceeds.

---

## 4. Maintainer Roster, Onboarding, and Succession

All changes to the maintainer roster, roles, and administrative authority must be documented and committed directly to this repository.

### 4.1 Onboarding New Maintainers

New maintainers may be appointed based on a demonstrated track record of:
- Consistent, high-quality contributions across code, tests, or documentation.
- Deep understanding of Bitheim's architecture, security rules, and development standards.
- Collaborative, respectful communication adhering to the Code of Conduct.

In a sole-maintainer state, the lead maintainer holds authority to appoint additional maintainers. In a multi-maintainer state, new maintainers are appointed by consensus of existing maintainers.

### 4.2 Succession and Offboarding

- **Sole-Maintainer Succession:** While the project has a single lead maintainer, if the maintainer intends to step down, they should arrange, vet, and document succession to a qualified contributor before relinquishing repository permissions. The transition must be recorded in an update to this document.
- **Voluntary Resignation:** When multiple maintainers exist, any maintainer may step down at any time by notifying the roster and submitting a documentation update.
- **Maintainer Removal:** In a multi-maintainer state, a maintainer may be removed by consensus of the remaining maintainers in cases of prolonged unexplained inactivity, severe or unresolved Code of Conduct violations, or actions compromising project security.
