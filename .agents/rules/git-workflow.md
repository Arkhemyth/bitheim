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
