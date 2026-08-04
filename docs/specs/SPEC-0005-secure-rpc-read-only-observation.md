# SPEC-0005: Secure RPC and Read-Only Observation

- **Status:** Proposed
- **Author:** Bitheim Contributors
- **Date:** 2026-08-04
- **Target:** `v0.2.0`, Phase 3
- **Related Plan:** [`v0.2.0 Delivery Plan`](../releases/v0.2.0-plan.md)
- **Runtime Contract:** [`SPEC-0004`](SPEC-0004-managed-regtest-node-runtime.md)
- **Runtime Topology:** [`ADR-0005`](../adr/ADR-0005-docker-compose-runtime-topology.md)

---

## 1. Context

Phase 2 established a Compose-managed Bitcoin Core 31.1 `regtest` node, cookie isolation, exact compatibility checks, and a host facade that delegates authenticated health probing to an unprivileged Bitheim container. Phase 3 turns that narrow probe into a reusable read-only observation boundary without exposing a generic RPC console or importing Bitcoin Core protocol details into the domain.

Bitcoin Core remains authoritative for every returned node, chain, block, mempool, and peer fact. Bitheim validates, translates, and presents those facts; it does not infer consensus state or repair malformed responses.

## 2. Goals

- Define one authenticated, bounded JSON-RPC client boundary for the currently supported Bitcoin Core runtime.
- Expose typed node, blockchain, block, mempool, and peer observations required by the `v0.2.0` milestone.
- Provide deterministic human-readable and JSON CLI representations through the existing host-to-container delegation boundary.
- Fail closed on missing credentials, transport failures, authentication failures, RPC errors, incompatible node identity, and malformed response shapes.
- Prove that credentials, raw payloads, personal paths, and private operational identifiers do not enter logs or unrestricted errors.

## 3. Non-Goals

- A generic `bitcoin-cli` replacement, arbitrary method execution, batch RPC, subscriptions, streaming, caching, or connection pooling.
- Wallet creation or loading, addresses, balances, UTXOs, private keys, seeds, block generation, or coinbase maturity.
- Creating, signing, broadcasting, or decoding user transactions.
- Adding or removing peers, publishing P2P ports, or managing remote private-network configuration.
- Supporting a Bitcoin Core version other than exactly `31.1` (`310100`) or a chain other than `regtest`.
- Exposing RPC to the host or changing the Compose, cookie-volume, UID/GID, or Docker authority decisions in SPEC-0004 and ADR-0005.
- Introducing an asynchronous framework or third-party RPC SDK without measured need.

## 4. Execution and Authority Boundary

The host-installed `bitheim` executable remains the user facade. Read-only observation commands execute as one-shot `bitheim` service processes on the private Compose network using `docker compose run --rm --no-deps -T`. Delegation must not start, recreate, or repair Bitcoin Core.

Inside the Bitheim container, the infrastructure adapter reads the cookie from the dedicated read-only cookie volume and connects to the `bitcoin-core` service. The application service and domain models receive no cookie path, authorization header, HTTP object, Compose service name, container identifier, or raw JSON-RPC mapping.

Execution context must prevent recursive delegation. If the node is stopped or its required image is unavailable, the host facade returns the corresponding typed, actionable failure without implicitly mutating runtime state.

## 5. RPC Client Contract

### 5.1 Request Semantics

The infrastructure client must:

1. accept only an internal closed set of methods exercised by Phase 3 use cases;
2. use HTTP POST on the private service network with cookie-derived Basic authentication;
3. read the cookie only immediately before an authenticated request and never cache it beyond the request lifecycle;
4. apply explicit positive finite connect/request timeouts bounded by the caller's remaining monotonic deadline;
5. send one request at a time with a deterministic request identifier;
6. reject redirects and any destination outside the configured internal RPC endpoint;
7. impose bounded response-size and JSON nesting/collection limits before constructing DTOs; and
8. never retry authentication, protocol, or application RPC errors automatically.

A narrowly bounded retry may be considered later only for a demonstrated transient transport failure and must remain inside the original deadline. Phase 3 begins without automatic retries.

The initial limits are part of the contract:

- default command deadline: 10 seconds, configurable only as a positive finite value no greater than 60 seconds;
- cookie file: 4 KiB maximum;
- response body: 4 MiB maximum, enforced while reading rather than after an unbounded read;
- decoded JSON nesting: 32 levels maximum;
- peer collection: 256 entries maximum;
- textual fields, including subversion and peer endpoint: 512 UTF-8 bytes maximum; and
- block lookup: exactly one hash or height per command.

These are defensive interoperability bounds, not performance targets. Raising one requires a reviewed contract and corresponding resource-limit tests.

### 5.2 Response Envelope

Every response must be a JSON object containing the matching request `id`, a `result` member, and an `error` member. Exactly one of `result` or a non-null `error` is accepted. HTTP success alone is not RPC success.

The adapter rejects:

- invalid JSON, duplicate or missing envelope fields, and mismatched identifiers;
- non-object RPC error values;
- unrecognized or incorrectly typed result fields required by a DTO;
- booleans where an integer is required;
- negative counts, sizes, heights, confirmations, timestamps, or durations where prohibited;
- non-finite numeric values; and
- collections exceeding documented Phase 3 bounds.

Unknown extra fields from Bitcoin Core may be ignored at the adapter boundary so compatible additive responses do not leak into domain contracts.

## 6. Authentication and Credential Handling

- Cookie authentication is mandatory; static RPC usernames and passwords are prohibited.
- Missing, empty, malformed, unreadable, oversized, or unexpectedly permissive cookie input fails closed before network I/O.
- Cookie contents and derived authorization values must never appear in standard output, standard error, structured logs, exceptions, test snapshots, diagnostics, or CI artifacts.
- Raw request and response bodies are never logged.
- Exception chaining must not expose filesystem paths, cookie values, HTTP headers, response bodies, or unrestricted transport messages through user-facing output or structured fields.
- Tests use sentinel credentials and paths and assert their absence from every observable channel.

## 7. Read-Only Use Cases and RPC Methods

Phase 3 permits only the following observations:

| Use case | Bitcoin Core methods | Required outcome |
| --- | --- | --- |
| Node and chain overview | `getnetworkinfo`, `getblockchaininfo` | Exact version/chain identity, connection count, network activity, height, headers, best block, sync and pruning facts. |
| Block inspection | `getblockhash` when a height is supplied, then `getblock` with verbosity `1` | A bounded block summary without raw transaction bodies. |
| Mempool summary | `getmempoolinfo` | Aggregate transaction count, byte/usage limits, and total fee converted exactly to satoshis. |
| Peer listing | `getpeerinfo` | A bounded list of typed connection summaries needed for observation. |

No Phase 3 method may create or load wallets, generate blocks, change settings, add peers, submit transactions, invalidate blocks, or mutate node state.

## 8. Typed Observation Models

Models are immutable, slotted dataclasses or equivalent typed value objects. Hashes are validated lowercase 64-character hexadecimal strings. Counts and sizes are non-negative integers. Bitcoin amounts are converted from JSON decimals to integer satoshis without binary floating-point arithmetic.

### 8.1 Node and Blockchain Overview

The combined overview contains:

- supported numeric node version and sanitized subversion;
- `network_active` and total connection count;
- chain name, block height, header height, and best block hash;
- median time, initial-block-download state, and pruning state; and
- chain work only if represented as a validated hexadecimal value.

The adapter must independently enforce `version == 310100` and `chain == "regtest"` before returning a successful overview.

### 8.2 Block Summary

A block summary contains hash, height, confirmations, timestamp, transaction count, serialized size, weight, and optional validated previous/next block hashes. Phase 3 does not return raw transactions, scripts, witnesses, or full block hex.

Block lookup accepts either a validated block hash or a non-negative height, never an ambiguous free-form locator.

Height lookup performs `getblockhash` followed by `getblock` under one caller-owned monotonic deadline. The second request receives only the remaining time; the pair does not receive two independent timeout budgets.

### 8.3 Mempool Summary

A mempool summary contains loaded state, transaction count, serialized bytes, dynamic memory usage, configured maximum memory, and total fees in integer satoshis. Fee conversion rejects precision beyond one satoshi, negative values, and non-finite numbers.

### 8.4 Peer Summary

Each peer summary contains a non-negative peer ID, network, inbound flag, connection type, protocol version, sanitized subversion, starting height, synced header/block heights, and optional bounded ping duration. The peer endpoint may be presented because the user explicitly requested peer inspection, but it is sensitive operational output and must never enter structured logs or unrelated diagnostics.

Peer results have a conservative maximum collection size. Exceeding it is a typed malformed-response failure rather than an invitation to allocate an unbounded collection.

## 9. CLI Contract

Phase 3 adds a single command family:

```text
bitheim inspect node [--json]
bitheim inspect block (--hash HASH | --height HEIGHT) [--json]
bitheim inspect mempool [--json]
bitheim inspect peers [--json]
```

The host facade delegates these commands without starting dependencies. Human output is concise and stable enough for users but is not a machine API. `--json` emits one deterministic UTF-8 JSON object followed by a newline, with documented snake_case keys, stable nesting, no ANSI styling, and no environment-specific paths or container facts.

JSON output uses integers for counts, sizes, heights, timestamps, versions, and satoshis; booleans for binary facts; strings for hashes, enums, subversions, and peer endpoints; and `null` only for documented optional values. Key order is deterministic for snapshots, but consumers must rely on keys rather than textual order.

Errors go to standard error with a stable non-zero exit code and no partial success JSON on standard output.

## 10. Doctor Integration

`bitheim doctor` may add a read-only node RPC diagnostic that reports categorical results for:

- managed node stopped;
- cookie unavailable or invalid;
- RPC transport unavailable;
- authentication rejected;
- incompatible chain or version;
- malformed protocol response; and
- successful authenticated read-only observation.

Doctor must not start services, wait for extended readiness, create files, repair credentials, or print raw RPC details. Host/container context routing follows the same authority boundary as observation commands.

## 11. Error Model

Expected failures map to typed categories at the infrastructure boundary and remain meaningful through the application and CLI layers:

- runtime stopped or unavailable;
- credential unavailable or invalid;
- transport timeout or unreachable endpoint;
- authentication rejected;
- malformed HTTP or JSON-RPC envelope;
- Bitcoin Core RPC rejection with a safe mapped category;
- incompatible chain or version;
- resource not found, including an unknown block or height; and
- malformed or out-of-bounds method result.

Bitcoin Core numeric error codes may be used internally for mapping but raw messages and response bodies are not propagated. Unknown codes map to a safe generic RPC rejection.

## 12. Logging and Privacy

Structured logs contain only canonical event names and categorical metadata such as operation kind, outcome category, and safe error type. They must not contain:

- cookie or authorization data;
- RPC request parameters or raw responses;
- block hashes, peer endpoints, node IDs, Compose project/network names, or private addresses;
- local paths, container identifiers, environment variables, or raw exception messages; or
- user-facing human or JSON output payloads.

Metrics and tracing are outside Phase 3. Correlation identifiers already supported by the logging schema may be used only when generated and validated under the existing safe logging contract.

## 13. Verification Requirements

Phase 3 must include:

- unit tests for every typed model invariant and exact decimal-to-satoshi conversion;
- application-service tests using typed fake ports;
- RPC contract tests for request construction, authentication, deadlines, envelope IDs, error mapping, response bounds, and every malformed required field;
- sentinel leak tests covering logs, exceptions, stdout, stderr, and JSON output;
- CLI functional tests for every human and JSON command, stopped-node behavior, and deterministic output;
- real integration tests against the pinned Bitcoin Core 31.1 regtest runtime for node overview, block lookup, mempool summary, and peer listing;
- tests proving every Phase 3 call is read-only and does not implicitly start Compose dependencies;
- preservation of all tests already integrated into `main`; and
- Ruff format/check, strict MyPy over `src` and `tests`, Pytest, diff checks, Compose integration, and existing multi-architecture gates.

Integration diagnostics must remain bounded and must not upload raw cookie, request, response, peer endpoint, or environment artifacts.

## 14. Acceptance Criteria

Phase 3 is complete when:

1. a running compatible node can be inspected through all four use cases using authenticated cookie RPC;
2. the same application services produce human-readable and deterministic JSON CLI output;
3. stopped, unreachable, unauthenticated, incompatible, rejected, and malformed cases produce typed safe failures;
4. block, mempool, and peer results satisfy the typed bounds and monetary precision rules;
5. no observation command starts, mutates, repairs, or reconfigures the managed runtime;
6. leak tests demonstrate that credentials and unsafe payloads do not cross output or logging boundaries;
7. real Bitcoin Core 31.1 integration tests pass through the unprivileged Bitheim container boundary; and
8. all historical and new quality gates pass without weakening existing tests.

## 15. Deferred Decisions

- Wallet-scoped RPC, block generation, and integer-satoshi wallet models belong to Phase 4.
- Peer mutation and two-node networking belong to Phase 5.
- TUI presentation belongs to Phase 6 and must reuse these application services.
- Official immutable Bitheim image publication remains a pre-release Phase 6 distribution requirement recorded in the delivery plan.
- Performance optimization, retries, batching, async I/O, caching, and alternate transports require operational evidence and a separate accepted change.
