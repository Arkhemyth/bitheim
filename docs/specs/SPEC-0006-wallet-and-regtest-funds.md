# SPEC-0006: Wallet and Regtest Funds

- **Status:** Accepted
- **Author:** Bitheim Contributors
- **Date:** 2026-08-10
- **Target:** `v0.2.0`, Phase 4
- **Related Plan:** [`v0.2.0 Delivery Plan`](../releases/v0.2.0-plan.md)
- **Runtime Contract:** [`SPEC-0004`](SPEC-0004-managed-regtest-node-runtime.md)
- **RPC Foundation:** [`SPEC-0005`](SPEC-0005-secure-rpc-read-only-observation.md)
- **Runtime Topology:** [`ADR-0005`](../adr/ADR-0005-docker-compose-runtime-topology.md)

---

## 1. Context

Phases 2 and 3 established a reproducible Bitcoin Core 31.1 `regtest` node, an isolated RPC-cookie boundary, exact node compatibility checks, and bounded typed observation through the host-to-container facade. Phase 4 adds the first intentional state-changing RPC use cases: local wallet lifecycle and regtest block generation.

Bitcoin Core remains authoritative for wallet storage, descriptors, keys, addresses, balances, UTXOs, block generation, and coinbase maturity. Bitheim validates intent, invokes a closed RPC method set, translates results, and presents safe deterministic output. It does not read wallet files, handle private key material, infer spendability, or reimplement wallet and consensus rules.

## 2. Goals

- Create or explicitly load one local descriptor wallet without exporting key material.
- Generate a receiving address through a wallet-scoped RPC endpoint.
- Expose exact wallet balances and the bounded spendable UTXOs required by the `v0.2.0` workflow.
- Generate a bounded number of blocks only on the supported `regtest` chain.
- Make immature coinbase funds visibly distinct from trusted spendable funds.
- Preserve the existing Compose, cookie, deadline, validation, privacy, and delegation boundaries.
- Deliver the phase through three independently protected vertical increments: 4A, 4B, and 4C.

## 3. Non-Goals

- Exporting private keys, seeds, passphrases, descriptors, or wallet files.
- Importing keys or descriptors, watch-only wallets, multisignature wallets, hardware wallets, or external signers.
- Wallet encryption, unlock flows, passphrase input, backup, restore, migration, unload, deletion, or renaming in `v0.2.0`.
- Sending, signing, funding, decoding, or broadcasting user transactions; these belong to Phase 5.
- Automatic peer mutation, two-node orchestration, TUI behavior, generic RPC access, or arbitrary mining parameters.
- Mainnet, testnet, signet, the future `labnet-v1` fork, or funds with economic value.
- Reading the Bitcoin datadir or mounting it into the Bitheim container.
- Async execution, retries, caching, batching, or speculative wallet abstractions without a current use case.

## 4. Execution and Authority Boundary

The host-installed `bitheim` executable remains the unified user facade. Phase 4 application commands execute through the unprivileged one-shot `bitheim` service on the private Compose network using the existing `docker compose run --rm --no-deps -T` boundary.

Delegation must not start, recreate, repair, or reconfigure Bitcoin Core. A stopped node fails with an actionable typed result. Recursive delegation and lifecycle commands inside the application container remain prohibited.

The Bitcoin Core service alone owns and writes the datadir and wallet files. Bitheim receives only the existing read-only RPC-cookie volume. Wallet persistence across node restarts is a Bitcoin Core datadir responsibility; Bitheim must not copy, inspect, back up, or directly modify wallet data.

Every Phase 4 operation uses one caller-owned positive finite monotonic deadline, with the existing default of 10 seconds and maximum of 60 seconds. Multi-call use cases pass only the remaining budget to subsequent calls.

## 5. Wallet Identity and Lifecycle Contract

### 5.1 Wallet Name

A Bitheim-managed wallet name must:

- be a string from 1 through 64 ASCII characters;
- match `[a-z][a-z0-9_-]{0,63}`;
- contain no path separators, dots, whitespace, percent escapes, control characters, or Unicode confusables; and
- be transported as one validated wallet identity, never concatenated as an unchecked filesystem path or URL fragment.

This conservative public contract avoids path ambiguity and endpoint confusion. Bitcoin Core may support additional names, but Bitheim does not expose them in `v0.2.0`.

### 5.2 Wallet Creation

`wallet create` invokes `createwallet` at the root RPC endpoint with explicit named intent equivalent to:

- private keys enabled;
- a descriptor wallet;
- no passphrase;
- a non-blank wallet;
- external signer disabled; and
- `load_on_startup` enabled.

The wallet is intentionally unencrypted for the initial local laboratory milestone because Bitheim does not yet define a secure passphrase acquisition, unlock, recovery, or automation contract. Its private material remains confined to the Bitcoin Core datadir protected by the existing container and volume boundary. This choice must be stated in user documentation and reconsidered before any non-local or economically valuable network is supported.

Creation is not an idempotent ensure operation. If the wallet already exists or is already loaded, Bitheim returns a stable typed conflict and does not silently treat it as a new creation, overwrite it, or switch to another wallet.

### 5.3 Wallet Loading

`wallet load` invokes `loadwallet` for an existing unloaded wallet. An already loaded wallet produces a stable successful result with `already_loaded = true`; an absent wallet produces a typed not-found result. Bitheim must establish already-loaded state through bounded authoritative RPC behavior, not filesystem inspection.

No command scans arbitrary wallet directories, changes `load_on_startup`, unloads another wallet, or selects an implicit wallet when more than one is loaded.

### 5.4 Wallet-Scoped RPC

After creation or loading, wallet operations use the explicit `/wallet/<wallet-name>/` RPC endpoint. The root endpoint must not be relied on for implicit single-wallet selection. The infrastructure boundary constructs the endpoint only from a previously validated wallet name and rejects redirects or alternate destinations exactly as in SPEC-0005.

## 6. Phase 4A — Wallet Lifecycle and Receiving Address

Phase 4A provides:

```text
bitheim wallet create --name NAME [--json]
bitheim wallet load --name NAME [--json]
bitheim wallet address --name NAME [--json]
```

`wallet address` invokes wallet-scoped `getnewaddress` with an empty label and an explicit `bech32` address type. A successful result is a non-empty UTF-8 string no greater than 128 bytes. Bitheim does not decode or independently certify ownership of an address returned by the selected compatible wallet.

The typed result for create/load contains only the validated wallet name and categorical creation/loading facts. It excludes warnings returned as unrestricted text. The address result contains the wallet name and address because the user explicitly requested it; neither value may enter structured logs, unrelated diagnostics, or unrestricted errors.

Phase 4A exits when create, load, and address generation work through both application-container and host-facade contexts against real Bitcoin Core 31.1 while all stopped, conflict, absent, malformed, timeout, privacy, and no-auto-start contracts pass.

## 7. Monetary Representation

All Bitcoin amounts cross the infrastructure boundary as JSON decimals and enter the domain only as integer satoshis. Conversion must use exact decimal arithmetic and reject:

- binary floating-point inputs;
- booleans or textual numeric coercion;
- negative or non-finite values;
- precision smaller than one satoshi;
- values outside the maximum Bitcoin money range; and
- arithmetic overflow or malformed result shapes.

Domain models, application ports, human rendering inputs, and JSON output use integer satoshis. Presentation may additionally format BTC for humans only from the integer value and without changing the machine contract.

## 8. Phase 4B — Balance and UTXO Observation

Phase 4B provides:

```text
bitheim wallet balance --name NAME [--json]
bitheim wallet utxos --name NAME [--json]
```

### 8.1 Balance

Wallet-scoped `getbalances` produces an immutable summary containing:

- trusted spendable satoshis;
- untrusted-pending satoshis; and
- immature satoshis.

Required fields must be present and exactly validated. Bitheim does not combine the categories into an inferred spendable total. Optional watch-only balances are outside the initial managed-wallet contract and must not be silently mixed into `mine` balances.

### 8.2 UTXOs

Wallet-scoped `listunspent` accepts at most 1,000 immutable summaries ordered deterministically by transaction ID and output index. The existing 4 MiB bounded-response contract from SPEC-0005 remains independently authoritative, so a response that exceeds 4 MiB fails closed even when it contains fewer than 1,000 entries. The collection limit is a maximum accepted count, not a guarantee that every response at that count fits the byte limit. Each summary contains:

- lowercase 64-character transaction ID;
- non-negative output index;
- optional bounded address;
- exact amount in satoshis;
- non-negative confirmations; and
- `spendable`, `solvable`, and `safe` flags.

Scripts, descriptors, parent descriptors, labels, redeem scripts, witness scripts, and raw transaction data are excluded. Transaction IDs and addresses are explicit requested output and must not enter logs or unrelated errors.

Bitcoin Core excludes immature coinbase outputs from ordinary available-coin selection, and `listunspent` does not provide a reliable coinbase/generated flag. Bitheim therefore must not infer coinbase identity from a UTXO. Coinbase maturity is communicated through the authoritative `getbalances.mine.immature` category and the documented generation workflow.

Phase 4B exits when exact balance and UTXO observations work through both execution contexts against real Bitcoin Core 31.1, including empty results, bounds, malformed responses, deterministic output, privacy, and monetary precision cases.

## 9. Phase 4C — Regtest Block Generation and Maturity

Phase 4C provides:

```text
bitheim mine generate --blocks COUNT --address ADDRESS [--json]
```

The operation first confirms the exact supported node identity (`version == 310100` and `chain == "regtest"`) within the same deadline, then invokes root-endpoint `generatetoaddress` with:

- an integer block count from 1 through 1,000;
- a non-empty UTF-8 destination address no greater than 128 bytes; and
- no user-controlled `maxtries` or additional mining parameter.

Network verification must occur before the state-changing RPC dispatch. Any unavailable, incompatible, or malformed identity fails closed without attempting generation. Bitcoin Core remains authoritative for address validity, block construction, proof of work, and rejection.

A successful result contains exactly `COUNT` unique lowercase block hashes in generation order. Missing, extra, duplicate, malformed, or oversized results fail as malformed responses rather than partial success.

Generating one block pays a coinbase output that is not spendable until it has 101 confirmations: the creation block plus the 100-block consensus maturity interval. The supported initial-funding workflow is therefore:

1. obtain a wallet receiving address;
2. generate 101 blocks to that address;
3. inspect the wallet balance; and
4. observe that the earliest coinbase reward has moved from immature to trusted funds.

Bitheim must not promise that every reward from a 101-block batch is mature. It reports the categories returned by Bitcoin Core and does not synthesize maturity state.

Phase 4C exits when bounded real block generation and the immature-to-trusted transition are verified against Bitcoin Core 31.1 through the delegated boundary without exposing addresses or hashes outside explicitly requested output.

## 10. RPC Method Allowlist

Phase 4 extends the closed internal method set only with:

| Use case | Endpoint | Bitcoin Core methods |
| --- | --- | --- |
| Create wallet | Root | `createwallet` |
| Load wallet | Root | `loadwallet` |
| Establish loaded state | Root | `listwallets` |
| Receiving address | Wallet-scoped | `getnewaddress` |
| Balance | Wallet-scoped | `getbalances` |
| UTXOs | Wallet-scoped | `listunspent` |
| Pre-generation identity check | Root | `getnetworkinfo`, `getblockchaininfo` |
| Generate blocks | Root | `generatetoaddress` |

No generic call surface is public. Application ports express use cases rather than arbitrary method names. Infrastructure may share the authenticated bounded transport from SPEC-0005, but read-only and mutating capabilities must remain explicit and reviewable.

## 11. Domain and Application Boundaries

New wallet behavior begins in cohesive modules rather than extending Phase 3 node modules indefinitely:

- `domain/wallet.py` for immutable wallet identity, lifecycle result, balance, and UTXO value objects;
- `application/wallet_ports.py` for the wallet and regtest-generation capabilities required by current use cases;
- `application/wallet_service.py` for validation, deadline ownership, and orchestration; and
- focused Bitcoin infrastructure modules when separation avoids expanding the existing observation client into an unrestricted adapter.

The exact file split is not itself a public API. Dependency direction remains domain <- application <- infrastructure/interfaces. No layer may be introduced without an exercised behavior, and Phase 4 must not perform an unrelated refactor of historical node observation code.

## 12. CLI and Output Contract

Human output is concise and explicitly labels amounts as satoshis and coinbase funds as trusted, pending, or immature. It must not describe immature funds as spendable.

`--json` emits one deterministic UTF-8 JSON object followed by a newline. Keys use snake_case; amounts are integer satoshis; counts and indices are integers; flags are booleans; hashes, addresses, and wallet names are strings; and `null` appears only for documented optional address values. Errors go to standard error with a stable non-zero exit and no partial JSON on standard output.

Mutating commands must state the completed operation and its bounded result. They do not run implicitly from read-only commands, `doctor`, startup, wallet creation, or address generation.

## 13. Error, Security, and Privacy Contract

Expected failures map to typed safe categories including invalid input, stopped runtime, authentication failure, timeout, incompatible node, wallet conflict, wallet not found, wallet not loaded, RPC rejection, malformed response, and resource-limit violation.

Bitcoin Core numeric error codes may be used internally for mapping. Raw RPC messages, warnings, request parameters, response bodies, exception chains, and command transcripts must not reach user-facing errors or structured logs.

The following are prohibited from logs, diagnostics, CI artifacts, and unrestricted errors:

- cookie and authorization material;
- wallet names, addresses, transaction IDs, block hashes, descriptors, scripts, labels, and balances;
- private keys, seeds, passphrases, wallet files, and datadir contents;
- personal paths, container identifiers, private endpoints, and environment dumps; and
- raw request or response payloads.

Sentinel leak tests cover stdout, stderr, structured logs, exceptions, and integration failure paths. Explicit command output may contain only the identifiers and financial facts required by that requested use case.

## 14. Increment and Test-Preservation Strategy

Phase 4 follows three complete contract-first cycles:

1. **4A — Wallet lifecycle and receiving address**;
2. **4B — Balance and UTXO observation**; and
3. **4C — Regtest block generation and maturity**.

For each cycle, executable contracts are integrated and checksummed before implementation begins. The implementer may add complementary tests but may not modify the protected contract or historical tests without explicit maintainer approval under the increment workflow. Each implementation receives independent review before commit, push, pull request, and integration.

## 15. Verification Requirements

Each applicable increment must include:

- domain invariant and exact satoshi-conversion unit tests;
- application tests with typed fake ports and monotonic deadline control;
- RPC contract tests for endpoint selection, named parameters, allowlists, response bounds, malformed fields, safe error mapping, and no unintended dispatch;
- host/container functional tests for deterministic human and JSON forms, standard stream separation, exit codes, stopped-node behavior, and no automatic dependency start;
- sentinel security tests across credentials, wallet identifiers, financial facts, addresses, hashes, paths, raw messages, and payloads;
- real Bitcoin Core 31.1 integration for wallet creation/loading, address generation, empty and funded balances, bounded UTXOs, generation, and coinbase maturity;
- byte-for-byte synchronization or equivalent checks for packaged runtime resources when those resources change;
- preservation of every historical and active protected test; and
- Ruff format/check, strict MyPy over `src` and `tests`, Pytest, Compose validation, diff checks, and existing container/multi-architecture CI gates.

Integration diagnostics remain categorical and bounded. They must not upload wallet state, addresses, transaction IDs, block hashes, RPC payloads, cookies, or environment artifacts.

## 16. Phase Acceptance Criteria

Phase 4 is complete when:

1. a user can explicitly create or load a managed descriptor wallet;
2. wallet operations always use an explicit validated wallet context;
3. the user can obtain a receiving address and inspect exact trusted, pending, and immature satoshi balances;
4. bounded UTXO output satisfies the typed precision, privacy, and deterministic-order contracts;
5. block generation is dispatched only after exact Bitcoin Core 31.1 `regtest` identity is confirmed;
6. a real 101-block workflow demonstrates the authoritative immature-to-trusted balance transition;
7. no private key, seed, descriptor, passphrase, wallet file, credential, raw payload, or unrestricted identifier leaks across boundaries;
8. all three protected increments and every historical test pass without weakening; and
9. the wallet-and-funds user guide documents the verified workflow and its local-lab security limitations.

## 17. Deferred Decisions

- Transaction creation, fee selection, signing, broadcast, and two-node transfer belong to Phase 5.
- Wallet encryption and passphrase lifecycle require a separate accepted security contract and are not silently added to `v0.2.0`.
- Wallet unload, deletion, backup, restore, migration, imports, watch-only behavior, labels, history, coin selection, and UTXO locking require future use cases.
- A convenience `wallet fund` orchestration command may be considered only after the explicit address-plus-generation workflow is integrated and remains inspectable.
- TUI presentation belongs to Phase 6 and must reuse the same application services.
- Alternate Bitcoin Core versions, networks, transports, native runtimes, retries, batching, async I/O, caching, and performance optimization require separate evidence and accepted decisions.
