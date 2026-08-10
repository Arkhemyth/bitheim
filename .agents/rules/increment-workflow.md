# Rule: Contract-First Increment Workflow

This document defines the reusable delivery workflow for Bitheim increments. It applies to human contributors and AI agents regardless of the active release or phase.

## 1. Sources of Operational Truth

Contributors must recover context in this order:

1. `AGENTS.md` for repository-wide onboarding and mandatory rules;
2. `docs/PROJECT_STATUS.md` for the active release, phase, increment, state, and next action;
3. the active release plan linked from project status for ordered scope and exit criteria;
4. the accepted specifications and ADRs linked from project status for binding behavior and architecture; and
5. the protected executable contracts named by project status or the active increment handoff.

Conversation history, agent memory, issue comments, and external context systems may help explain decisions, but they do not override versioned repository documents.

## 2. Increment Sizing

Each increment must be a narrow vertical slice with one coherent user or operator outcome. It should exercise only the domain models, application ports and services, infrastructure adapters, presentation behavior, and documentation required by that outcome.

Split an increment before implementation when it combines independent behaviors with materially different security, privacy, deadline, persistence, or integration risks. Do not split work merely by architectural layer, because that creates partially integrated abstractions without a working use case.

## 3. Contract-First Sequence

Use the following sequence for each implementation increment:

1. **Plan:** identify the outcome, in-scope and out-of-scope behavior, governing SPECs and ADRs, acceptance criteria, risks, and expected quality gates.
2. **Define executable contracts:** add focused tests for the behavior that must be true before delegating or beginning implementation. Confirm that new behavior tests fail for the intended missing capability while repository quality remains otherwise healthy.
3. **Protect the baseline:** record the protected contract paths and SHA-256 checksums in the handoff, and identify the historical tests that must remain present. The accepted branch or pull request is the durable source of the contract content; checksums make unauthorized rewriting visible during a delegated task.
4. **Implement:** change the minimum production and integration surface needed to satisfy the contracts. Do not create commits, push, or open a pull request until the implementation is independently reviewed unless the maintainer explicitly chooses a different handoff boundary.
5. **Review independently:** inspect production, tests, documentation, security boundaries, and the complete diff against the integration base. Run the applicable gates and verify that passing test counts did not conceal deleted, weakened, skipped, or rewritten coverage.
6. **Correct narrowly:** resolve findings without modifying protected or historical tests merely to obtain a passing result. Repeat independent review after material corrections.
7. **Integrate:** only after review approval, create focused commits and a pull request, run required CI, resolve review conversations, and merge through the protected default branch.
8. **Handoff:** update the release plan and `docs/PROJECT_STATUS.md` in the same delivery when the active increment, phase, or next action changes.

Documentation-only planning increments may omit executable contracts when they change no runtime behavior. They still require link, consistency, diff, and applicable repository quality checks.

## 4. Protected and Historical Tests

Tests integrated into `main` are historical regression contracts and are governed by `AGENTS.md` and `.agents/rules/git-workflow.md`.

Tests created before implementation to define the active increment are additionally protected for that implementation handoff. An implementer must not delete, skip, weaken, replace, or rewrite them. Adding complementary tests is allowed.

A protected or historical test may change only when:

- the observed contract is factually wrong, impossible, insecure, or intentionally superseded;
- the change is supported by an accepted specification, ADR, explicit maintainer decision, or reproducible evidence;
- the architect or independent reviewer, rather than the delegated implementer acting alone, owns or explicitly approves the correction;
- equivalent or stronger relevant coverage remains; and
- the pull request explains the reason.

Checksums are review aids, not substitutes for reading the test diff or understanding its assertions.

## 5. Delegation Handoff

A delegated implementation prompt must state:

- the exact increment and user-visible outcome;
- the governing documents and accepted architectural boundaries;
- the allowed production, test-addition, documentation, and integration scope;
- protected test paths and checksums;
- the prohibition on changing historical or protected tests without explicit approval;
- required local quality and integration gates;
- whether commits, pushes, pull requests, or external mutations are authorized; and
- the expected completion report, including every changed test and the reason for changing it.

Command approvals and temporary infrastructure access remain maintainer responsibilities unless explicitly delegated. A particular terminal multiplexer, agent product, or notification mechanism may be used when available, but is not part of the architectural workflow and must not become a prerequisite for contributing.

## 6. Review Evidence

Before integration, the reviewer must establish evidence for:

- acceptance criteria and negative cases;
- architecture and dependency direction;
- bounded I/O, deadlines, validation, and fail-closed behavior where applicable;
- secrets, personal identifiers, raw payloads, and exception-message leak prevention;
- deterministic public output contracts;
- preservation of historical and protected tests;
- documentation and project-status accuracy; and
- all applicable local and CI gates.

Review findings should identify the violated contract and the smallest safe correction. Broad cleanup, speculative refactoring, and unrelated modernization belong in separately planned increments.

## 7. Reuse in Other Projects

This workflow may be copied into another repository after adapting its paths, quality gates, branch protections, security boundaries, and sources of truth. Copy the method, not Bitheim-specific contracts or assumptions. The receiving project must explicitly adopt the copied document through its own contributor entrypoint.
