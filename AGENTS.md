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
