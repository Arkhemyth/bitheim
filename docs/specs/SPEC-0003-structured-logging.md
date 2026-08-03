# SPEC-0003: Structured Logging Foundation and Real Consumers

- **Status:** Accepted
- **Author:** Bitheim Contributors
- **Date:** 2026-08-02
- **Related Plan:** [`docs/plan_bitheim.md`](../plan_bitheim.md)
- **Related Specs:** [`docs/specs/SPEC-0001-configuration-and-doctor.md`](SPEC-0001-configuration-and-doctor.md), [`docs/specs/SPEC-0002-container-image-foundation.md`](SPEC-0002-container-image-foundation.md)

---

## 1. Context

As defined in the Bitheim Master Plan ([`docs/plan_bitheim.md`](../plan_bitheim.md)), Bitheim requires an observable, machine-parseable, and secure structured logging foundation for milestone `v0.1.0`. In distributed Bitcoin experimentation, node diagnostics, and automated workflows, unstructured text logging introduces ambiguity, breaks automated log indexing, and risks sensitive data leakage.

To establish this foundation, Bitheim implements a pure Python standard library structured logger that formats records as JSON Lines (`JSONL`) written to `stderr`, leaving `stdout` clean for human-facing CLI output. The system is directly integrated into and exercised by existing production consumers: configuration loading and the `bitheim doctor` diagnostic command.

---

## 2. Goals

- Implement a standard library `logging.Formatter` emitting single-line JSON (`JSON Lines`) to `sys.stderr`.
- Preserve clean separation of concerns: `stdout` is reserved for functional CLI output, while operational structured logs are written to `stderr`.
- Define a canonical, strictly validated JSON log record schema with ISO 8601 UTC timestamps, uppercase level names, logger module names, explicit event identifiers, and optional domain context fields (`correlation_id`, `node_id`, `experiment_id`).
- Exercise the logging foundation in real consumers: `bitheim.bootstrap.configuration` and `bitheim.interfaces.cli` (`handle_doctor`).
- Enforce conservative emission: default log level is `WARNING` so that standard successful CLI executions produce no structured logs on `stderr` unless explicitly configured via `BITHEIM_LOG_LEVEL` or programmatic override.
- Establish strict security and privacy discipline: prohibit logging personal file paths, raw configuration text, credentials, seed phrases, private keys, cookies, or sensitive environment tokens, backed by defense-in-depth sanitization and safe-by-construction design.
- Implement zero external dependencies, no file rotation, no background daemon threads, and no remote telemetry.

---

## 3. Non-Goals

- Implementing remote log shipping, OpenTelemetry, Fluentd/Logstash exporters, or syslog daemons.
- Implementing disk file logging, rotation, or retention policies in this milestone.
- Introducing third-party logging packages (such as `structlog`, `loguru`, or `picologging`).
- Modifying `stdout` output formatting of existing CLI commands (`bitheim doctor`, `--help`, `--version`).
- Adding CLI flags for logging levels in this milestone (runtime configuration is managed via `BITHEIM_LOG_LEVEL` or programmatic invocation).
- Logging speculative future domains (e.g. Bitcoin peer protocol events, wallet transactions) before those modules exist.

---

## 4. JSON Lines Schema Contract

Every log record emitted is a single JSON object terminated by a newline (`\n`).

### 4.1 Schema Fields

| Field | Type | Requirement | Description |
| :--- | :--- | :--- | :--- |
| `timestamp` | `string` | **Required** | ISO 8601 UTC timestamp with microsecond resolution and `Z` suffix (e.g., `"2026-08-02T22:30:00.123456Z"`). |
| `level` | `string` | **Required** | Uppercase severity name: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, `"CRITICAL"`. |
| `module` | `string` | **Required** | Emitting logger name within the `bitheim` hierarchy (e.g., `"bitheim.bootstrap.configuration"`). |
| `event` | `string` | **Required** | Canonical snake_case event identifier describing the occurrence (e.g., `"configuration_loaded"`, `"doctor_check_failed"`). Falls back to `"unspecified_event"` if unset. |
| `correlation_id` | `string` | Optional | Identifier linking related operations across processes or requests. Omitted if `None`. |
| `node_id` | `string` | Optional | Identifier of the active Bitheim node. Omitted if `None`. |
| `experiment_id` | `string` | Optional | Identifier of the active research experiment. Omitted if `None`. |
| `data` | `object` | Optional | Structured key-value mapping of explicit, categorical, non-sensitive event attributes. Omitted if empty. |
| `exception` | `object` | Optional | Exception metadata when `exc_info` is recorded: `{"type": "<ExceptionClassName>"}`. |

### 4.2 Example JSON Lines Record

```json
{"timestamp": "2026-08-02T22:30:00.123456Z", "level": "DEBUG", "module": "bitheim.bootstrap.configuration", "event": "configuration_loaded", "data": {"source": "file", "has_custom_config": true}}
```

---

## 5. Architecture and Lifecycle

### 5.1 Module Structure
- Module: `src/bitheim/bootstrap/logging.py`
- Main classes and functions:
  - `StructuredFormatter`: Custom `logging.Formatter` serializing `logging.LogRecord` to canonical JSONL.
  - `setup_logging(level: str | int | None = None, stream: TextIO | None = None, environ: Mapping[str, str] | None = None, force: bool = False) -> logging.Logger`: Configures the `"bitheim"` top-level logger hierarchy with a `StreamHandler` and `StructuredFormatter`.
  - `get_logger(name: str) -> logging.Logger`: Returns a child logger within the `"bitheim"` namespace.
  - `parse_log_level(level_name: str | int | None, default: int = logging.WARNING) -> int`: Parses log level names safely.

### 5.2 Default Level and Configuration Precedence
1. **Default:** `logging.WARNING` (standard CLI commands produce no `stderr` logs on clean executions).
2. **Environment Variable:** `BITHEIM_LOG_LEVEL` (e.g. `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).
3. **Programmatic Override:** Explicit `level` argument passed to `setup_logging()`.

### 5.3 Stream Separation
- **`stdout`**: Reserved exclusively for human-facing CLI output and structured diagnostic checkmarks (`[✓]`).
- **`stderr`**: Receives operational structured JSON Lines logs (when level allows) and human-facing error diagnostics (`[✗]`) when failures occur.

---

## 6. Integration with Real Consumers

### 6.1 Configuration Subsystem (`bitheim.bootstrap.configuration`)
- **Success:** When configuration is successfully validated and constructed, logs event `configuration_loaded` at `DEBUG` level with categorical metadata:
  ```python
  logger.debug(
      "Configuration loaded successfully",
      extra={
          "event": "configuration_loaded",
          "data": {
              "source": source_type,
              "has_custom_config": resolved_config_file is not None,
          },
      },
  )
  ```
- **Failure:** When configuration file parsing, section validation, or parameter resolution fails, logs event `configuration_load_failed` at `ERROR` level with categorical `error_type` before raising `ConfigurationError`:
  ```python
  logger.error(
      "Configuration load failed",
      extra={"event": "configuration_load_failed", "data": {"error_type": error_type}},
  )
  ```

### 6.2 CLI and Doctor Subcommand (`bitheim.interfaces.cli`)
- **Doctor Diagnostics (`handle_doctor`):**
  - Logs event `doctor_started` at `DEBUG` level.
  - For each individual diagnostic check (Python runtime, configuration, data directory existence, data directory permissions), logs `doctor_check_passed` (`DEBUG`) or `doctor_check_failed` (`ERROR`) with categorical fields (e.g. `{"check": "data_dir_access", "status": "exists_and_writable"}` or `{"check": "data_dir_access", "reason": "not_a_directory"}`).
  - Logs `doctor_completed` at `DEBUG` level with `{"passed": true|false}`.
- **CLI Exception Dispatch (`main`):**
  - When `ConfigurationError` occurs in CLI entrypoint, logs `cli_command_failed` at `ERROR` level to `stderr` with categorical `error_type`.

---

## 7. Security and Data Protection Policy

1. **Safe-by-Construction Design:**
   - Structured logs must never contain personal file paths, raw configuration data, passwords, authentication tokens, RPC credentials, private keys, or seed phrases.
   - The formatter never converts arbitrary log message strings into event identifiers. If `event` is not provided, the formatter uses a safe fallback (`"unspecified_event"`).
   - Exception metadata serializes only the exception class name (`type`), avoiding raw exception messages that could contain un-sanitized file paths or user data.
2. **Defense-in-Depth Sanitization:**
   - The `StructuredFormatter` automatically scans keys in `data` mappings against a sensitive blacklist (`token`, `password`, `secret`, `key`, `cookie`, `seed`, `auth`, `credential`, `privkey`, `private_key`).
   - If any blacklisted key is detected, its value is masked with `"[REDACTED]"`.
   - Sanitization is documented strictly as a secondary safeguard and never as an excuse to relax preventive code discipline.

---

## 8. Acceptance Criteria

1. `StructuredFormatter` produces valid single-line JSON matching the schema on every emitted record.
2. Timestamps are formatted as ISO 8601 UTC with microsecond precision and `Z` suffix.
3. Operational logs are written to `sys.stderr`, preserving `sys.stdout` exclusively for CLI human output.
4. Default log level ensures `bitheim doctor` outputs only formatted checkmarks to `stdout` without noise on `stderr`.
5. Configuration loading errors and doctor failures emit structured JSONL `ERROR` events to `stderr`.
6. Sensitive keys in `data` payloads are redacted.
7. Personal file paths, raw configuration text, and un-sanitized exception messages never appear in JSON Lines output.
8. Comprehensive unit and functional tests validate schema compliance, stream separation, consumer events, and security properties.
9. All repository quality gates (`ruff format`, `ruff check`, `mypy src tests`, `pytest`) pass cleanly with 0 errors.
