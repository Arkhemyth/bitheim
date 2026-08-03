# SPEC-0001: Minimal Validated Configuration and Doctor Diagnostic Command

- **Status:** Accepted
- **Author:** Bitheim Contributors
- **Date:** 2026-08-02
- **Related Plan:** [`docs/plan_bitheim.md`](../plan_bitheim.md)

---

## 1. Context

Bitheim requires a deterministic, lightweight, and strictly validated configuration loading mechanism for milestone `v0.1.0`. The configuration foundation must load runtime settings (such as `data_dir`) across standard configuration vectors (defaults, configuration file, environment variables, and CLI flags). 

To ensure developer confidence and verify system prerequisites without side effects, a diagnostic CLI command (`bitheim doctor`) is introduced to validate Python runtime compatibility, configuration integrity, and data directory accessibility.

---

## 2. Goals

- Provide a pure Python 3.13 stdlib configuration loader (`tomllib`, `dataclasses`, `pathlib`) with zero third-party dependencies.
- Define a clear, deterministic configuration precedence hierarchy: default < configuration file < environment variable < CLI argument.
- Implement strict schema validation: reject unknown root sections, unknown fields, and invalid data types.
- Ensure configuration loading and doctor diagnostics are strictly read-only and free of filesystem side effects.
- Provide a human-readable `bitheim doctor` diagnostic subcommand checking Python version, configuration parsing, effective data directory, and filesystem permissions.
- Ensure graceful error reporting without leaking Python tracebacks to stderr during expected failure conditions.

---

## 3. Non-Goals

- Implementing remote network checks, RPC connectivity, Bitcoin Core integration, or mining/wallet operations.
- Supporting arbitrary or nested configuration schemas beyond `[runtime].data_dir` in this milestone.
- Writing to configuration files or creating filesystem directories automatically during configuration loading or doctor diagnostics.
- Implementing structured JSON/YAML output flags for `bitheim doctor` before required by downstream orchestration.

---

## 4. Configuration Schema

The initial TOML configuration schema supports exclusively the `[runtime]` table:

```toml
[runtime]
data_dir = ".bitheim"
```

### Schema Rules
- Root sections: Only `[runtime]` is permitted. Any additional root table or key raises `ConfigurationError`.
- `[runtime]` table: Must be a mapping/table if present.
- `[runtime].data_dir`: Must be a non-empty string if present. Any additional key within `[runtime]` raises `ConfigurationError`.

---

## 5. Precedence and Resolution Hierarchy

When resolving runtime parameters (specifically `data_dir`), sources are evaluated in increasing order of priority:

1. **Default Value:** `data_dir = Path(".bitheim")`
2. **Configuration File:** Default file `bitheim.toml` in the current working directory (optional; silently ignored if absent). If explicitly supplied via `--config`, the file must exist and be readable.
3. **Environment Variables:** `BITHEIM_DATA_DIR` (must be non-empty if defined).
4. **CLI Flags:** `--data-dir` passed to subcommands (must be non-empty).

### Path Resolution Rules
- Paths undergo `Path.expanduser()` to expand user home directories (`~`), but are **not** converted via `Path.resolve()` to avoid filesystem existence coupling and maintain working-directory relativity.
- Loading configuration is strictly read-only and never creates directories or files.

---

## 6. CLI Contract

### 6.1 Subcommand: `bitheim doctor`

```text
usage: bitheim doctor [-h] [--config CONFIG] [--data-dir DATA_DIR]

Run system and environment diagnostic checks.

options:
  -h, --help            show this help message and exit
  --config CONFIG       Path to custom configuration file.
  --data-dir DATA_DIR   Override runtime data directory path.
```

### 6.2 Exit Codes
- `0`: All diagnostic checks passed successfully.
- `1`: One or more diagnostic checks failed (or configuration validation error).
- `2`: Invalid CLI syntax or unrecognized arguments.

---

## 7. Diagnostic Behavior

`bitheim doctor` evaluates four deterministic checks in sequence:

1. **Python Runtime:** Confirms `sys.version_info >= (3, 13)`.
2. **Configuration Loading:** Resolves configuration against specified sources and validates schema integrity.
3. **Effective Data Directory:** Evaluates and displays the effective path resolved from the precedence chain.
4. **Filesystem Accessibility:**
   - If `data_dir` exists: Verifies it is a directory and has write permissions (`os.W_OK`).
   - If `data_dir` does not exist: Traverses parent ancestors to find the nearest existing directory and verifies write permissions on that ancestor (ensuring `data_dir` can be created later by runtime components when needed).

*Note: `bitheim doctor` does not create the data directory or any temporary files.*

---

## 8. Error Handling

- All configuration syntax and validation errors raise `ConfigurationError`.
- In CLI entrypoints, `ConfigurationError` and diagnostic failures print user-friendly messages to stderr/stdout and terminate with non-zero exit codes without printing Python tracebacks.

---

## 9. Security Constraints

- **Least Privilege:** Does not execute shell commands or require elevated permissions.
- **No Secrets:** No secret tokens, credentials, or sensitive data are accepted, parsed, logged, or displayed.
- **Safe Parsing:** Uses standard library `tomllib`, preventing arbitrary object construction or code execution during deserialization, with user-friendly error reporting.
- **Strict Schema Enforcement:** Explicitly restricts parsed content to the defined schema (`[runtime].data_dir`), preventing unexpected parameter injection.

---

## 10. Acceptance Criteria

1. `uv run bitheim --help` and `uv run bitheim --version` continue functioning identically.
2. `uv run bitheim doctor` runs diagnostic checks and exits `0` in standard compliant environments.
3. Invalid TOML, unknown sections, unknown keys, or invalid types produce clear human error messages and exit non-zero without tracebacks.
4. Precedence rules (default -> file -> env -> CLI) are verified via deterministic tests without mutating global `os.environ`.
5. Data directory existence/ancestor checks are validated without creating directories during loading or doctor runs.
6. All quality gates pass: Ruff format/lint, MyPy strict typing, and full Pytest suite.
