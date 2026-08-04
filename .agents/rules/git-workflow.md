# Rule: Git & Development Workflow

This document establishes the collaboration rules and Git workflow for **Bitheim**. All contributors (human and AI agents) must adhere to these standards.

---

## 1. Repository Language

- **Permanent Rule:** English is the mandatory official language for all repository content:
  - Documentation and READMEs
  - Source code, docstrings, and inline comments
  - Commit messages and pull request descriptions
  - Issue templates and discussions

---

## 2. Branching & Trunk-Based Strategy

- **`main` Branch:** The primary trunk. Must remain buildable, tested, and passing at all times.
- **Feature Branches:** Use short-lived, focused branches for proposed changes:
  - Format: `<type>/<short-description>` (e.g., `feat/add-cli-doctor`, `chore/setup-ci`, `docs/update-status`).
- **Scope & Cohesion:** Keep commits and pull requests atomic, focused on a single concern, and bounded to the immediate task scope.

---

## 3. Commit Message Conventions

Bitheim strictly follows [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>: <description in imperative mood>

[optional body]
```

### Allowed Types:
- `feat`: A new feature or user-facing capability.
- `fix`: A bug fix.
- `docs`: Documentation changes only.
- `chore`: Maintenance tasks, dependency updates, tooling setup.
- `refactor`: Code changes that neither fix a bug nor add a feature.
- `test`: Adding or correcting automated tests.
- `ci`: Changes to CI/CD workflows and scripts.

---

## 4. Environment & Quality Standards

- **Environment Management:** Use `uv` exclusively.
  - Sync environment: `uv sync --locked`
  - Execute commands: `uv run <command>`
  - Never run `pip install` globally or manually edit `uv.lock`.
- **Quality Gates:** Changes integrated into `main` must adhere to project quality standards:
  - Formatting & Linting (`ruff format`, `ruff check`)
  - Static Typing (`mypy src`)
  - Automated Tests (`pytest`)
  - Automated CI validation once workflows are introduced.

---

## 5. Security & Secret Protection

- **Zero-Secret Policy:** Never commit secrets, tokens, API keys, `.cookie` files, private network IP addresses, or sensitive credentials.
- **Gitignore Compliance:** Ensure local runtime artifacts, databases (`*.duckdb`, `*.sqlite`), and virtual environments (`.venv/`) remain untracked.

---

## 6. Regression Test Preservation

- Tests already integrated into `main` are regression contracts. Default to preserving them and adding new tests for new behavior.
- Do not delete, replace, weaken, skip, or broadly rewrite an integrated test merely to make a change pass.
- An integrated test may change only for an intentional contract change backed by an accepted SPEC, ADR, or explicit maintainer decision. Document the rationale in the pull request, retain equivalent relevant coverage, and obtain explicit reviewer approval.
- Test-only refactoring is acceptable only when the original assertions and behavioral intent remain at least as strong.
- Review the test diff against `main`. Passing gates and total test counts do not prove preservation of historical coverage.
