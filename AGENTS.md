# Agent and Contributor Onboarding Guide

Welcome to **Bitheim**. This document serves as the primary entry point for AI agents and human contributors onboarding to the repository.

---

## 1. Project Reference & Source of Truth

- **Master Plan & Architecture:**
  [`docs/plan_bitheim.md`](docs/plan_bitheim.md) constitutes the temporary **Source of Truth** for the project. It defines the product vision, domain boundaries, engineering standards, and roadmap up to `v1.0.0`.

- **Current Repository Status:**
  [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) tracks the active milestone, immediate objectives, completed items, and open decisions. Always inspect this file first to understand the current state of work.

---

## 2. Collaboration Rules & Workflow

- **Git & Development Standards:**
  [`.agents/rules/git-workflow.md`](.agents/rules/git-workflow.md) defines the required branch strategy, commit conventions, language standardization, and environment management rules.

---

## 3. General Principles

- **Language:** All repository content (code, comments, documentation, commit messages) must be written in English.
- **Python Environment:** Use [`uv`](https://docs.astral.sh/uv/) exclusively (`uv sync`, `uv run`). Do not use global `pip`.
- **Security:** Never commit private IPs, secrets, RPC cookies, or credentials.
