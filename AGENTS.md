# Agent and Contributor Entrypoint

Welcome to **Bitheim**. This document serves as the single entrypoint for AI agents and human contributors onboarding to the repository.

---

## Recommended Onboarding Sequence

To understand the project and begin contributing, read the repository documents in the following order:

1. **[`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md)**

   Start here. It identifies the active release, delivery phase, increment, governing specifications, relevant architecture decisions, and next action.

2. **The active release plan linked from `docs/PROJECT_STATUS.md`**

   Read the active release scope, ordered delivery phases, acceptance criteria, risks, and quality strategy. Do not infer the active plan from version numbers or repository history.

3. **The active specifications and relevant ADRs linked from `docs/PROJECT_STATUS.md`**

   Read the binding behavioral contracts and architectural decisions for the assigned increment before proposing or changing implementation.

4. **[`docs/plan_bitheim.md`](docs/plan_bitheim.md)**

   The project-level **Source of Truth** for Bitheim. It defines the overarching vision, architecture, domain boundaries, engineering standards, and roadmap up to `v1.0.0`.

5. **[`.agents/rules/git-workflow.md`](.agents/rules/git-workflow.md)**

   The official rules for branch strategy, commit conventions, language standardization, and environment management.

Before making changes, verify the repository state and work only within the assigned increment. When an integrated change advances the active phase, update the release plan and `docs/PROJECT_STATUS.md` in the same delivery so that the next contributor receives an accurate handoff.

## Regression Test Preservation

Tests integrated into `main` are regression contracts. Preserve them by default and add coverage for new behavior instead of deleting, replacing, weakening, skipping, or broadly rewriting existing tests to make an implementation pass.

An integrated test may change only when an intentional contract change is supported by an accepted SPEC, ADR, or explicit maintainer decision. The pull request must explain the reason, preserve equivalent relevant coverage, and receive explicit reviewer approval. Structural test refactoring is allowed only when the original assertions and behavioral intent remain at least as strong. Reviewers must inspect the test diff against `main`; a passing suite or increased test count is not evidence that historical coverage was preserved.
