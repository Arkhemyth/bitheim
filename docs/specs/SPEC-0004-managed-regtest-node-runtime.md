# SPEC-0004: Managed Regtest Node Runtime Contract

- **Status:** Accepted
- **Author:** Bitheim Contributors
- **Date:** 2026-08-03
- **Target:** `v0.2.0`, Phase 1
- **Related Plan:** [`v0.2.0 Delivery Plan`](../releases/v0.2.0-plan.md)
- **Related ADR:** [`ADR-0005: Docker Compose Runtime Topology`](../adr/ADR-0005-docker-compose-runtime-topology.md)

---

## 1. Context

Bitheim `v0.2.0` must manage a real Bitcoin Core node in `regtest`. The first increment establishes the runtime contract before lifecycle code is written so that process control, storage, authentication, networking, compatibility, and failure behavior do not emerge accidentally inside a Compose file or infrastructure adapter.

Bitcoin Core remains the validation authority. This specification governs how Bitheim starts, stops, observes, and safely reaches Bitcoin Core; it does not reproduce consensus, wallet, transaction, or peer validation.

## 2. Goals

- Define one reproducible, Compose-managed Bitcoin Core 31.1 runtime for Linux `amd64` and `arm64` container hosts.
- Build the Bitcoin Core image from official release binaries verified against pinned SHA-256 checksums, rather than trusting a mutable or community-maintained runtime image.
- Define strict separation between Bitcoin data, Bitheim state, and RPC credentials.
- Establish safe lifecycle, readiness, shutdown, networking, and compatibility semantics.
- Provide the concrete contract required to implement Phase 2 node lifecycle and health through a real application port and infrastructure adapter.
- Preserve a path to future runtime adapters without implementing them in this phase.

## 3. Non-Goals

- Implementing lifecycle code, Compose files, container builds, RPC clients, wallets, transactions, peer management, or a TUI in this documentation increment.
- Supporting an externally managed Bitcoin Core process in `v0.2.0`.
- Implementing a native managed-process runtime before `v1.0.0`.
- Supporting `mainnet`, `testnet`, `signet`, or `labnet-v1`.
- Publishing a Bitcoin Core or Bitheim container image.
- Exposing Bitcoin Core RPC to the host, a private mesh, or the public Internet.
- Allowing Bitheim to mount the Docker Engine socket or invoke Docker from inside its application container.
- Defining automatic backup, restore, migration, update, or destructive teardown behavior.

## 4. Supported Bitcoin Core Distribution

### 4.1 Version

The initial supported version is **Bitcoin Core 31.1** (reported numeric version `310100`). It is an exact compatibility target, not a minimum version or floating release series.

The runtime must reject an incompatible reported version with a typed, actionable status. A different Bitcoin Core version requires an explicit compatibility update, tests, release-note review, and a lockfile/build-input change. It must never be selected automatically at runtime.

### 4.2 Provenance and Verification

The Bitcoin Core runtime image must be constructed by Bitheim from the official release archives hosted under:

```text
https://bitcoincore.org/bin/bitcoin-core-31.1/
```

The build must:

1. select only the official `x86_64-linux-gnu` or `aarch64-linux-gnu` archive matching the build platform;
2. pin the expected SHA-256 value for each archive in version-controlled build inputs;
3. verify the downloaded archive before extraction and fail closed on mismatch;
4. copy only the runtime executables required by the accepted design into a minimal pinned base image;
5. run as an explicit non-root UID/GID; and
6. contain OCI source, version, revision, license, and vendor metadata.

Maintainers updating the pinned release must verify the official `SHA256SUMS` and its signed attestations out of band before changing the version-controlled hashes. Network-fetched checksum content alone is not a trust root.

A mutable tag, unverified archive, or community Bitcoin Core image is not an acceptable production input. CI may build but must not publish the image until a separate publication and supply-chain specification authorizes it.

## 5. Runtime Topology

The supported topology consists of:

- a `bitcoin-core` service containing `bitcoind` and the required diagnostic CLI;
- a `bitheim` service containing the Bitheim application; and
- a private Compose network shared only by services that require node access.

Compose is the lifecycle authority for `v0.2.0`. The host invokes Compose directly or through a host-side infrastructure adapter. The Bitheim application container must not receive the Docker socket, container-management privileges, or a nested container runtime.

The `bitheim` service may be used as a one-shot CLI/TUI process on the private network. A long-running Bitheim daemon is not required by this specification.

### 5.1 Execution Contexts

The host-installed `bitheim` executable is the canonical user interface and a unified command facade. Users must not need to decide whether a command belongs on the host or inside a container.

The facade routes commands according to their authority:

- lifecycle commands (`bitheim start`, `bitheim stop`, and runtime inspection for `bitheim status`) execute through the host-side Compose adapter;
- application and RPC commands execute through an unprivileged one-shot `bitheim` service on the private Compose network; and
- status may combine host runtime facts with a read-only probe executed inside the authorized runtime boundary.

Delegated application commands must use an execution mode that does not implicitly start dependencies. If the managed node is stopped, the command fails with an actionable stopped-state result rather than silently starting it. The facade preserves the delegated command's standard output, standard error, and exit status.

The implementation must prevent recursive delegation by identifying its execution context explicitly. An unsupported lifecycle invocation from inside the application container must fail clearly rather than attempting to find or mount a Docker socket.

Direct `docker compose` commands remain an advanced operational and recovery interface, not the normal user experience.

## 6. Storage Contract

Three storage classes must remain distinct:

| Storage | Writer | Readers | Purpose |
| --- | --- | --- | --- |
| Bitcoin datadir | `bitcoin-core` only | `bitcoin-core` only | Chainstate, blocks, indexes, settings, and wallets managed by Bitcoin Core. |
| RPC cookie volume | `bitcoin-core` | `bitcoin-core`, `bitheim` read-only | Ephemeral authentication cookie only. |
| Bitheim state | `bitheim` only | `bitheim` only | Bitheim configuration and future application state. |

Bitcoin Core must receive an absolute `rpccookiefile` path located in the dedicated cookie volume. Bitheim must mount that volume read-only. Bitheim must never receive the Bitcoin datadir merely to discover the cookie.

The cookie volume is runtime state, not a secret backup. The cookie is generated at node startup, removed or invalidated by shutdown/restart, and must not be copied into images, configuration, logs, diagnostics, test artifacts, or release assets.

Named volumes are the default portable storage mechanism. Any future bind-mount mode requires a separate documented ownership and cross-platform contract.

No Bitheim command may implicitly delete named volumes or datadirs. Destructive reset is excluded from `v0.2.0` unless specified separately with explicit confirmation, exact targets, and recovery consequences.

## 7. Identity and Permissions

- Both images must run as explicit non-root users.
- Bitcoin Core alone has read/write access to its datadir.
- Bitcoin Core creates the RPC cookie with group-readable permissions for a dedicated shared runtime group; no world-readable cookie is permitted.
- Bitheim receives only read access to the cookie volume and no write access to Bitcoin data.
- Application code and installed dependencies remain root-owned and immutable to runtime UIDs.
- Linux capabilities must not be added unless an implemented requirement demonstrates the need.
- `privileged: true`, host PID/network namespaces, and the Docker socket are prohibited.

## 8. Network Contract

### 8.1 RPC

RPC is reachable only on the private Compose network. It must not be declared under Compose `ports` in the default topology.

Bitcoin Core may bind RPC to the container interface only when paired with an explicit `rpcallowip` limited to the dedicated Compose subnet. The topology must assign and validate an explicit configurable private subnet so the allow-list is deterministic. The deployment must detect local subnet collisions before startup and must not use a universal source range such as `0.0.0.0/0` or `::/0`.

Cookie authentication is mandatory. Static `rpcuser`/`rpcpassword` configuration is prohibited. RPC traffic is unencrypted, so it must never leave the trusted local container network in this milestone.

### 8.2 Peer-to-Peer

The Bitcoin P2P port may be published only when required to connect independently deployed participants. Publication must bind to an explicitly configured host or private-mesh address; an implicit all-interface binding is not allowed.

The host port must be configurable per deployment to avoid collisions. Internal service ports remain stable. Remote participant addresses belong in private deployment configuration and must never be committed to the public repository.

### 8.3 Isolation

Each deployment uses an explicit Compose project name derived from a validated Bitheim node identifier. The identifier must be portable, deterministic, and restricted to a conservative character set. Project naming isolates service, network, and volume resources for multiple nodes on one host.

## 9. Configuration Contract

The generated or mounted Bitcoin Core configuration must:

- enable `regtest` explicitly outside network-specific sections;
- place network-specific settings under `[regtest]` where supported;
- disable any assumption of mainnet defaults;
- set the absolute RPC cookie path;
- configure RPC binding and allow-listing narrowly for the private service network;
- avoid static RPC passwords and repository-owned secrets;
- contain no real private-mesh addresses in tracked examples; and
- be deterministic from validated Bitheim configuration.

Phase 2 may extend the Bitheim configuration schema only with values required by the implemented lifecycle and topology. Unknown fields must continue to fail strict validation.

## 10. Lifecycle Semantics

### 10.1 Start

Start is idempotent for an already running compatible project. It must:

1. validate Bitheim configuration and node identifier;
2. verify availability of the required Compose implementation without mutating state;
3. select only pinned Compose and image/build inputs;
4. start the project without recreating or deleting data volumes unnecessarily;
5. wait for bounded readiness; and
6. return a typed final state rather than treating container creation as node readiness.

Concurrent lifecycle operations for the same project must fail safely or serialize through an explicit mechanism. They must not race into duplicate or destructive Compose operations.

### 10.2 Readiness and Health

Container process state and node health are separate facts. A node is `healthy` only when all of the following hold:

- the `bitcoin-core` container is running;
- the RPC cookie exists and is readable by the authorized client;
- an authenticated RPC request succeeds within the configured timeout;
- `getblockchaininfo` reports `chain == "regtest"`; and
- `getnetworkinfo` reports the exactly supported Bitcoin Core compatibility version.

The initial health probe must be read-only. It must not create wallets, generate blocks, connect peers, or modify settings.

The state model must distinguish at least:

- `stopped`;
- `starting`;
- `healthy`;
- `unhealthy`;
- `incompatible`; and
- `unknown` when the runtime itself cannot be inspected safely.

Startup waits must use bounded polling with a monotonic deadline. Fixed unbounded sleeps are prohibited. Timeout errors must preserve safe categorical diagnostics without including cookie contents, raw RPC responses, personal paths, or unrestricted container logs.

### 10.3 Stop

Stop is idempotent when the project is already stopped. Compose must request a graceful stop with a documented grace period long enough for Bitcoin Core to flush state. Forceful termination may occur only after the grace period expires and must be reported distinctly.

Stop must not remove volumes, project data, or images. A successful container exit is not evidence that deleting data is safe.

### 10.4 Status

Status is read-only and must not start, recreate, repair, migrate, or stop services. It combines runtime inspection and, when reachable, the authenticated health probe. It must produce deterministic domain states independent of presentation format.

## 11. Application Boundary for Phase 2

Phase 2 must introduce only the boundary exercised by lifecycle use cases. The application layer defines a process/runtime port capable of start, stop, and inspection operations. The Compose implementation is an infrastructure adapter.

Domain status and health models must contain portable facts rather than Compose service names, container IDs, command output, HTTP response objects, or raw JSON-RPC payloads.

CLI handlers invoke application services. They must not construct Compose commands or parse RPC responses directly.

An external-process adapter may be added in a future milestone without changing the domain contract, but no unused adapter or speculative abstraction is required now.

### 11.1 Minimal Native-Runtime Preparation

Compose is the only supported runtime through `v1.0.0` unless operational evidence justifies reprioritization. The implementation prepares for a possible post-`v1.0.0` native runtime only by preserving the following properties:

- lifecycle application ports express semantic operations and states, not Compose commands, container IDs, YAML structures, or Docker SDK types;
- domain models contain no container-specific fields;
- lifecycle services receive their runtime port explicitly and are tested with a typed fake;
- configuration distinguishes portable node intent from Compose adapter configuration; and
- user-facing errors identify the failed capability without requiring Docker terminology where the failure is runtime-independent.

This preparation must not create a native adapter, platform process manager, binary installer, unused factory, empty package, or abstraction with no current Compose consumer.

## 12. Error and Logging Contract

Expected failures must map to specific categories, including:

- runtime unavailable;
- invalid runtime configuration;
- image/build input unavailable;
- startup timeout;
- graceful shutdown timeout;
- RPC unavailable;
- RPC authentication failure;
- wrong chain;
- unsupported Bitcoin Core version; and
- malformed runtime or RPC response.

User-facing errors must be actionable without exposing command transcripts that may contain host information. Structured logs use categorical fields only. Cookie values, authorization data, RPC request bodies, raw exception messages, local paths, container environment dumps, and private addresses are prohibited.

## 13. Verification Requirements

Phase 2 implementation must provide:

- unit tests for lifecycle services and state transitions using a typed fake port;
- contract tests for Compose command construction, project isolation, timeout handling, and output parsing;
- integration tests against the pinned Bitcoin Core 31.1 image;
- tests proving wrong-chain and wrong-version rejection;
- tests proving the cookie volume is read-only to Bitheim and the Bitcoin datadir is not mounted there;
- tests proving RPC has no default host port publication;
- tests proving graceful stop retains volumes and permits restart;
- security tests demonstrating no cookie or authorization leakage through output or structured logs;
- native `amd64` smoke validation and multi-architecture image build validation for `amd64` and `arm64`; and
- the existing Ruff, strict MyPy, Pytest, link, and diff gates.

## 14. Acceptance Criteria

This specification is satisfied by the Phase 2 implementation when:

1. a clean supported host can build or obtain the exact verified Bitcoin Core 31.1 runtime for its architecture;
2. Bitheim can start one isolated regtest project and report `starting` until authenticated readiness succeeds;
3. health rejects the wrong chain and unsupported versions;
4. Bitheim can stop and restart the node without losing its named datadir volume;
5. the Bitheim service can read the dedicated cookie volume but cannot write it or read the Bitcoin datadir;
6. RPC is reachable from the authorized service network and is not published to the host by default;
7. no lifecycle operation implicitly deletes persistent data;
8. failures are bounded, typed, actionable, and safe to log; and
9. all required local and CI gates pass.

## 15. Deferred Decisions

The following remain outside this runtime contract until a consumer requires them:

- remote RPC access;
- external-process and system-service adapters;
- a native managed Bitcoin Core runtime, provisioner, or installer, provisionally deferred until after `v1.0.0`;
- image publication, signing, SBOMs, and provenance;
- automated Bitcoin Core upgrades or datadir migrations;
- backups and destructive reset workflows;
- a long-running Bitheim daemon API; and
- `labnet-v1` runtime replacement.

## 16. Primary References

- [Bitcoin Core 31.1 release notes](https://bitcoincore.org/en/releases/31.1/)
- [Official Bitcoin Core 31.1 release directory](https://bitcoincore.org/bin/bitcoin-core-31.1/)
- [Bitcoin Core JSON-RPC interface and security guidance](https://github.com/bitcoin/bitcoin/blob/v31.1/doc/JSON-RPC-interface.md)
- [Docker Compose services reference](https://docs.docker.com/reference/compose-file/services/)
- [Docker Compose volumes reference](https://docs.docker.com/reference/compose-file/volumes/)
