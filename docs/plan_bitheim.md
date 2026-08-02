# Bitheim Implementation Master Plan up to `v1.0.0`

## Distributed platform for experimentation, mining, and analysis on Bitcoin

**Status:** Source of Truth  
**Document Version:** 1.1  
**Project Name:** Bitheim  
**Horizon:** From repository initialization to `v1.0.0`  
**Nature:** Open source project  
**Confirmed Initial Users:** 2  
**Design Scale:** From 2 to dozens of nodes without structural redesign  
**Primary Language:** Python  
**Python Project Management:** `uv`  
**Private Network:** Pre-established, e.g., via Headscale/Tailscale  
**Initial Blockchain Network:** Bitcoin Core `regtest`  
**Target Blockchain Network:** `labnet-v1`  
**Target Platforms for `v1.0.0`:**

* Linux `amd64`
* Linux `arm64`
* macOS Apple Silicon via Docker Desktop
* Windows via WSL2 and Docker Desktop

---

# 1. Document Purpose

This document defines the architecture, scope, conventions, engineering standards, security controls, modules, development phases, release process, and acceptance criteria that will govern Bitheim until reaching version `1.0.0`.

Its content constitutes the primary normative reference of the project.

Every implementation must respect this document unless:

1. a technical error is identified;
2. an unconsidered constraint arises;
3. sufficient evidence exists to justify an alternative;
4. the change is documented through an Architecture Decision Record (ADR);
5. both maintainers approve the modification.

Significant architectural changes must not be introduced solely for immediate convenience, personal preference, or impulsive adoption of a new technology.

---

# 2. Project Identity

## 2.1 Name

The official project name shall be:

> **Bitheim**

The name shall be used consistently across:

* repository;
* Python package;
* CLI command;
* Docker images;
* documentation;
* configuration;
* logs;
* releases;
* artifacts;
* service names.

## 2.2 Naming Conventions

| Element                             | Name                         |
| ----------------------------------- | ---------------------------- |
| Project                             | `Bitheim`                    |
| Main repository                     | `bitheim`                    |
| Python package                      | `bitheim`                    |
| CLI command                         | `bitheim`                    |
| Main image                          | `ghcr.io/<org>/bitheim`      |
| Bitcoin Core fork                   | `bitheim-bitcoin-core`       |
| Labnet node image                   | `ghcr.io/<org>/bitheim-core` |
| Experimental network                | `labnet-v1`                  |
| Main configuration file             | `bitheim.toml`               |
| Default local directory             | `.bitheim/`                  |

## 2.3 Usage Examples

```bash
uv run bitheim doctor
uv run bitheim start
uv run bitheim status
uv run bitheim tui
```

In a Docker distribution:

```bash
docker compose up -d
docker compose run --rm bitheim tui
```

---

# 3. Product Vision

Bitheim will be a lightweight, reproducible, and extensible platform for deploying, operating, observing, and analyzing private networks based on Bitcoin Core.

The system will allow:

* running a private blockchain node;
* creating and managing wallets;
* executing valid Bitcoin transactions;
* observing blocks, mempool, UTXOs, and peers;
* participating in competitive mining;
* observing real proof of work;
* utilizing distributed difficulty;
* generating optional synthetic activity;
* executing reproducible experiments;
* capturing events and metrics;
* querying and exporting data;
* using a TUI without necessarily depending on commands;
* accessing a CLI and an RPC console for advanced usage;
* deploying the same implementation across different architectures.

The coins used will have no economic value, but transactions must be authentic from the protocol perspective.

Transactions will:

* spend real UTXOs;
* be cryptographically signed;
* be validated by Bitcoin Core;
* enter the mempool;
* propagate among peers;
* be included in blocks;
* receive confirmations;
* modify balances;
* potentially return to the mempool after a reorganization;
* potentially be invalidated by a competing chain.

Bitheim will not be a visual simulation disconnected from Bitcoin.

It will be an operational, experimental, and analytical layer built around real nodes.

---

# 4. Background

Bitheim originates from the **Bitcoin Local Lab** project, in which the following was progressively developed:

1. an autonomous node in `regtest`;
2. a two-node local P2P network;
3. JSON-RPC automation;
4. transaction propagation;
5. fork simulation;
6. chain reorganizations;
7. a distributed mesh across heterogeneous machines;
8. instrumentation;
9. reproducibility documentation;
10. resolution of real network, memory, and container issues.

The lab proved the technical feasibility of the concept.

Bitheim will transform that lab into a maintainable, deployable product usable by people who do not necessarily wish to operate Bitcoin Core exclusively from a terminal.

---

# 5. Objectives

## 5.1 Functional Objectives

Bitheim must allow:

* installing and deploying a node with minimal configuration;
* joining an existing private network;
* creating and managing wallets;
* sending and receiving lab coins;
* checking balances and UTXOs;
* observing the P2P network;
* inspecting blocks and transactions;
* participating in mining;
* generating synthetic activity;
* running experiments;
* storing observations;
* analyzing results;
* exporting datasets.

## 5.2 Educational Objectives

The product must allow observing:

* transaction lifecycle;
* P2P propagation;
* mempool;
* confirmations;
* coinbase;
* maturity;
* UTXOs;
* mining;
* nonce;
* SHA-256d hash;
* target;
* difficulty;
* chainwork;
* forks;
* reorganizations;
* difficulty adjustment;
* latency impact;
* behavior of a small network.

## 5.3 Engineering Objectives

The project must:

* be reproducible;
* operate on `amd64` and `arm64`;
* be maintainable by two people;
* follow current Python best practices;
* use `uv`;
* feature strict typing;
* possess clear architectural boundaries;
* apply security by default;
* include automated testing;
* produce verifiable releases;
* support upgrade and rollback;
* be safe for open source publication.

---

# 6. Guiding Principles

## 6.1 Bitcoin Core Retains Validation Authority

Bitheim must never substitute the validation of:

* blocks;
* transactions;
* scripts;
* UTXOs;
* proof of work;
* difficulty;
* accumulated work;
* reorganizations.

Bitheim may:

* create;
* request;
* automate;
* observe;
* present;
* record;
* analyze.

Bitcoin Core will be the final authority on data validity.

---

## 6.2 Complexity Will Be Optional

A user must be able to:

1. install Bitheim;
2. import a configuration;
3. start the node;
4. create a wallet;
5. execute a transaction;
6. observe the result;

without being forced to type commands.

The same user may subsequently access:

* CLI;
* RPC console;
* configuration;
* logs;
* SQL;
* raw data;
* protocol details.

---

## 6.3 Transparent Automation

Every significant action initiated from the TUI must allow inspecting:

* executed use case;
* equivalent RPC call;
* parameters;
* response;
* events;
* persisted modifications.

The TUI must not become a black box.

---

## 6.4 Security by Default

Default configurations must adopt:

* least privilege;
* deny by default;
* local RPC;
* separation of secrets;
* immutable images;
* pinned versions;
* restrictive permissions;
* absence of remote telemetry;
* minimal port exposure;
* log sanitization.

---

## 6.5 Design for Two Users Without Precluding Growth

The only confirmed initial users are the two maintainers.

Therefore:

* it will not be prematurely optimized for hundreds of participants;
* unnecessary infrastructure will not be implemented;
* microservices will not be introduced without justification;
* a large organization will not be assumed.

However, the design will avoid decisions that prevent using multiple nodes or onboarding more participants.

---

## 6.6 Modularity Without Premature Microservices

Bitheim will initially be a:

> **Modular monolith with hexagonal architecture.**

It will not be split into microservices as long as:

* there are two maintainers;
* it is distributed as a single unit;
* components share the same release cycle;
* there is no real need to scale them independently.

---

## 6.7 Reproducibility

Given the same:

* version;
* configuration;
* manifest;
* scenario;
* seed;
* initial state;
* Bitcoin Core version;

experiments must produce functionally equivalent results.

---

## 6.8 Safe Open Source

No public artifact must contain:

* real mesh network addresses;
* private domains;
* internal names;
* Headscale keys;
* private keys;
* seeds;
* RPC cookies;
* tokens;
* real OCI configurations;
* local dumps;
* personal paths;
* participant names;
* wallet addresses used in private environments.

---

# 7. Scope up to `v1.0.0`

## 7.1 Included

Bitheim will include before `v1.0.0`:

* Python project managed with `uv`;
* reproducible distribution via Docker Compose;
* multi-architecture images;
* Bitcoin Core lifecycle management;
* node configuration;
* wallets;
* human transactions;
* TUI;
* CLI;
* RPC console;
* peer visualization;
* block visualization;
* mempool visualization;
* manual mining;
* competitive mining;
* `labnet-v1`;
* distributed difficulty;
* optional synthetic agents;
* reproducible scenarios;
* event collection;
* analytical storage;
* CSV export;
* Parquet export;
* experiments;
* diagnostics;
* update;
* rollback;
* user documentation;
* development documentation;
* secure release pipeline.

## 7.2 Out of Scope

The following will not be implemented before `v1.0.0`:

* automatic Headscale installation;
* Headscale user administration;
* automatic private network creation;
* mainnet;
* real funds;
* Lightning Network;
* web dashboard;
* native mobile app;
* Kubernetes;
* Databricks;
* native Power BI connector;
* multi-user authentication;
* high availability;
* centralized telemetry;
* plugin marketplace;
* remote RPC execution;
* public node exposure.

---

# 8. Core Architecture

## 8.1 Architectural Style

Bitheim will use:

> **Modular monolith with hexagonal architecture and domain separation.**

The design will combine:

* Ports and Adapters;
* lightweight Domain-Driven Design;
* Application Services;
* pragmatic separation between commands and queries;
* dependency inversion;
* typed internal events;
* explicit module boundaries.

Full tactical DDD will not be implemented where it provides no direct value.

## 8.2 Rationale

A modular monolith is appropriate because:

* there are only two maintainers;
* the application is distributed as a unit;
* operations are primarily local;
* it simplifies debugging;
* it simplifies releases;
* it reduces internal distributed problems;
* it allows refactoring without coordinating multiple services;
* it retains the ability to extract modules in the future.

## 8.3 Hexagonal Architecture

The domain must not depend directly on:

* Bitcoin Core;
* Docker;
* Textual;
* DuckDB;
* ZMQ;
* `urllib`;
* operating system;
* configuration framework;
* process manager.

External dependencies will be implemented as adapters.

---

# 9. Runtime Architecture

```text
┌────────────────────────── Host ────────────────────────────┐
│                                                           │
│ Headscale / Tailscale                                     │
│ └── Out of scope for Bitheim                              │
│                                                           │
│ Docker Compose                                            │
│ ├── bitheim-core                                          │
│ ├── bitheim-daemon                                        │
│ ├── bitheim-tui                                           │
│ ├── bitheim-miner             optional                    │
│ ├── bitheim-simulator         optional                    │
│ └── bitheim-analytics         optional                    │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

All Bitheim processes will use the same Python package and distinct entrypoints:

```bash
bitheim daemon
bitheim tui
bitheim miner
bitheim simulate
bitheim analytics
bitheim doctor
```

This avoids maintaining separate, divergent applications.

---

# 10. Repositories

## 10.1 Main Repository: `bitheim`

Contains:

* Python application;
* TUI;
* CLI;
* daemon;
* miner;
* simulator;
* analytics;
* configurations;
* Docker Compose;
* documentation;
* tests;
* pipelines;
* scenarios.

## 10.2 Fork: `bitheim-bitcoin-core`

Contains a minimal fork of Bitcoin Core.

Must only modify what is necessary to:

* register `labnet`;
* define genesis;
* define magic bytes;
* define ports;
* configure `powLimit`;
* enable retargeting;
* define timing parameters;
* identify the network;
* validate difficulty.

Must not unnecessarily modify:

* wallets;
* mempool;
* scripts;
* RPC;
* serialization;
* P2P;
* chain selection;
* storage.

---

# 11. Repository Structure

```text
bitheim/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── dependabot.yml
│   └── workflows/
├── docs/
│   ├── architecture/
│   ├── adr/
│   ├── development/
│   ├── operations/
│   ├── releases/
│   └── user-guide/
├── src/
│   └── bitheim/
│       ├── bootstrap/
│       ├── shared/
│       ├── node/
│       ├── wallet/
│       ├── network/
│       ├── mining/
│       ├── activity/
│       ├── experiments/
│       ├── analytics/
│       ├── runtime/
│       ├── interfaces/
│       │   ├── cli/
│       │   └── tui/
│       └── infrastructure/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   ├── e2e/
│   ├── security/
│   ├── performance/
│   └── fixtures/
├── scenarios/
├── schemas/
├── docker/
├── scripts/
├── examples/
│   ├── configs/
│   └── network-manifests/
├── compose.yaml
├── compose.dev.yaml
├── pyproject.toml
├── uv.lock
├── .python-version
├── README.md
├── CONTRIBUTING.md
├── SECURITY.md
├── CODE_OF_CONDUCT.md
├── GOVERNANCE.md
├── CHANGELOG.md
├── LICENSE
└── .gitignore
```

`src-layout` will be used.

---

# 12. Python Project Management with `uv`

## 12.1 Official Tool

`uv` will be the official tool for:

* creating the project;
* managing the virtual environment;
* installing Python when necessary;
* resolving dependencies;
* locking versions;
* running commands;
* installing development groups;
* building packages;
* reproducing environments.

`pip install` will not be used directly during the normal development workflow.

Project dependencies will not be installed into the global environment.

## 12.2 Initialization

The project is initialized via:

```bash
uv init --package bitheim
```

Package structure in `src/` will be used.

## 12.3 Virtual Environment

The local environment will be managed by `uv`:

```bash
uv sync
```

This will create or update `.venv/`.

`.venv/` will be ignored by Git.

## 12.4 Execution

All Python commands for the project will be executed via:

```bash
uv run <command>
```

Examples:

```bash
uv run bitheim doctor
uv run bitheim start
uv run bitheim tui
uv run pytest
uv run ruff check .
uv run mypy src
```

## 12.5 Dependencies

Add a production dependency:

```bash
uv add textual
```

Add a development dependency:

```bash
uv add --dev pytest
```

Remove a dependency:

```bash
uv remove <package>
```

Lockfile dependencies must not be edited manually.

## 12.6 Lockfile

`uv.lock` must:

* be versioned;
* be updated via `uv`;
* be reviewed in pull requests;
* be used in CI;
* be used in Docker;
* be the reference for reproducible resolution.

## 12.7 Locked Synchronization

In CI and builds:

```bash
uv sync --locked
```

This prevents an environment from silently changing the lockfile.

## 12.8 Frozen Installation

In contexts requiring strict reproducibility:

```bash
uv sync --frozen
```

## 12.9 Dependency Groups

At a minimum, the following will exist:

* production dependencies;
* `dev` group;
* `test` group;
* `docs` group;
* `security` group.

The exact division will be defined in `pyproject.toml`.

## 12.10 Python Version

`.python-version` will declare the version used by the project.

Example:

```text
3.13
```

The initial workflow may be:

```bash
uv python install
uv sync
```

## 12.11 Developer Bootstrap

A new contributor should be able to run:

```bash
git clone <repository>
cd bitheim
uv python install
uv sync --all-groups
uv run bitheim doctor
```

## 12.12 Development Commands

Wrappers via `Makefile` or scripts may exist, but internally they will use `uv`.

Example:

```makefile
check:
	uv run ruff format --check .
	uv run ruff check .
	uv run mypy src
	uv run pytest
```

`uv` will remain the source of truth for the environment.

## 12.13 Docker

Dockerfiles will use `uv` to install dependencies.

Principles:

* copy `pyproject.toml` and `uv.lock` first;
* use `uv sync --locked`;
* leverage layer caching;
* separate build and runtime;
* do not include development dependencies in production;
* use a minimal final image;
* run as a non-root user.

Conceptual example:

```dockerfile
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

COPY src/ ./src/
```

## 12.14 CI

Workflows will use the same sequence as developers:

```bash
uv sync --locked --all-groups
uv run ruff check .
uv run mypy src
uv run pytest
```

A parallel manual `requirements.txt` will not be maintained.

One will only be generated when an external tool expressly requires it.

---

# 13. Layer Dependency Rules

The direction will be:

```text
Interfaces
    ↓
Application
    ↓
Domain
```

Infrastructure adapters will implement ports defined by the application.

```text
Infrastructure
    ↓
Application Ports
    ↓
Domain
```

Domain will never import:

* Textual;
* DuckDB;
* ZMQ;
* Docker SDK;
* concrete HTTP libraries;
* process controllers;
* operating system configuration.

---

# 14. Internal Module Structure

Each module may contain:

```text
module/
├── domain/
│   ├── entities.py
│   ├── value_objects.py
│   ├── events.py
│   ├── policies.py
│   └── errors.py
├── application/
│   ├── commands.py
│   ├── queries.py
│   ├── handlers.py
│   ├── ports.py
│   └── dto.py
└── infrastructure/
    ├── adapters/
    ├── repositories/
    └── mappers/
```

Empty directories or files must not be created solely for symmetry.

---

# 15. Functional Modules

## 15.1 `bootstrap`

Responsibilities:

* initialization;
* dependency container;
* adapter selection;
* migrations;
* handler registration;
* startup;
* shutdown.

Will contain no business logic.

---

## 15.2 `node`

Responsibilities:

* node lifecycle;
* configuration;
* health checks;
* datadir;
* blockchain status;
* synchronization;
* logs;
* version compatibility.

Entities:

* `Node`
* `NodeStatus`
* `NodeConfiguration`
* `NodeHealth`
* `ChainIdentity`

Ports:

* `NodeProcessPort`
* `BlockchainRpcPort`
* `NodeConfigurationRepository`
* `NodeLogPort`

---

## 15.3 `wallet`

Responsibilities:

* creation;
* loading;
* addresses;
* balances;
* UTXOs;
* transactions;
* history;
* coinbase maturity.

Rules:

* no private keys will leave the node;
* Bitheim will not persist seeds;
* Bitheim will not log secrets;
* wallets will be managed via local RPC.

---

## 15.4 `network`

Responsibilities:

* peers;
* connections;
* topology;
* latency;
* transport;
* bytes;
* manifests;
* bootstrap peers;
* network identity.

The module will not configure Headscale.

---

## 15.5 `mining`

Responsibilities:

* manual mining;
* competitive mining;
* templates;
* coinbase;
* Merkle root;
* headers;
* nonces;
* SHA-256d;
* hashrate;
* block submission;
* difficulty.

Backends:

* `RpcBlockProducer`
* `ProofOfWorkMiner`

---

## 15.6 `activity`

Responsibilities:

* synthetic agents;
* profiles;
* transaction generation;
* stochastic processes;
* amounts;
* scheduling;
* seeds;
* origin tagging.

Origins:

```text
human
synthetic
experiment
external
faucet
```

---

## 15.7 `experiments`

Responsibilities:

* plans;
* preconditions;
* execution;
* checkpoints;
* compensation;
* results;
* metadata;
* reproducibility.

Included experiments:

1. transfer and confirmation;
2. propagation;
3. mempool growth;
4. disconnection and resynchronization;
5. mining competition;
6. reorganization;
7. difficulty;
8. UTXO consolidation.

---

## 15.8 `analytics`

Responsibilities:

* events;
* snapshots;
* analytical schema;
* queries;
* datasets;
* metrics;
* exports.

Technologies:

* DuckDB;
* Parquet;
* SQLite, only if operational state requires it.

---

## 15.9 `runtime`

Responsibilities:

* processes;
* scheduler;
* tasks;
* signals;
* graceful shutdown;
* locks;
* supervision;
* recovery;
* local communication.

---

## 15.10 `interfaces`

Contains:

* CLI;
* TUI;
* presentation;
* error mapping;
* DTOs.

Will not execute RPC directly.

---

## 15.11 `shared`

Will only include genuinely shared elements:

* `Clock`;
* `EventBus`;
* identifiers;
* satoshis;
* base errors;
* serialization;
* verified utilities.

Will not be a generic dumping ground for helper functions.

---

# 16. Processes

## 16.1 Daemon

`bitheim daemon` will be the main process.

Responsibilities:

* operational state;
* use cases;
* supervision;
* events;
* tasks;
* local API.

## 16.2 Local API

TUI and CLI will communicate via:

* Unix Domain Socket on Linux/macOS;
* equivalent local mechanism on Windows/WSL2;
* HTTP loopback as fallback.

Will never be exposed to the mesh network by default.

## 16.3 TUI

The TUI will be a disposable client.

Closing the TUI will not stop:

* node;
* miner;
* simulator;
* collection;
* analytics.

---

# 17. Blockchain Network

## 17.1 Initial Stage: `regtest`

Used to develop:

* node;
* wallets;
* TUI;
* transactions;
* RPC;
* analytics;
* simulator;
* mining engine;
* updates.

## 17.2 Target Stage: `labnet-v1`

Will feature:

* custom genesis;
* custom identifier;
* custom magic bytes;
* custom port;
* worthless coins;
* mandatory PoW;
* initial difficulty;
* retargeting;
* distributed validation;
* independent chain.

---

# 18. Distributed Difficulty

## 18.1 Rule

Each node will independently compute the expected target.

No central authority can change difficulty during operation.

A block will only be accepted when:

$$SHA256d(header) \leq target$$

and `nBits` represents the expected target.

## 18.2 Initial Parameters

```yaml
target_spacing_seconds: 30
adjustment_interval_blocks: 20
target_timespan_seconds: 600
maximum_adjustment_factor: 4
allow_min_difficulty_blocks: false
no_retargeting: false
```

## 18.3 Adjustment

$$target_{new} = target_{old} \times \frac{actual\ timespan}{expected\ timespan}$$

With boundaries:

$$\frac{expected}{4} \leq actual \leq 4 \times expected$$

The target will never exceed `powLimit`.

## 18.4 Future Changes

Any incompatible change will require:

* `labnet-v2`;
* a new network; or
* an explicit activation mechanism.

Until `v1.0.0`, a new network will be created.

---

# 19. Network Manifest

Example:

```yaml
format_version: 1

network:
  name: example-labnet
  protocol: labnet-v1
  network_id: "<generated>"
  genesis_hash: "<generated>"

bootstrap:
  peers:
    - node-a.example.internal:19444
    - node-b.example.internal:19444

features:
  simulation_enabled: false
  analytics_enabled: true
```

Real manifests will remain outside the repository.

---

# 20. Human and Synthetic Activity

Both will coexist.

```text
Human wallet ───────┐
                    ├── Bitcoin Core ── mempool ── blocks
Synthetic agent ────┘
```

Bitcoin Core will treat both as real transactions.

Bitheim will retain analytical metadata regarding origin.

## 20.1 Included Models

* homogeneous Poisson;
* time-slotted Poisson;
* lognormal amounts;
* recurring payments;
* retail;
* merchant;
* payroll;
* simulated exchange;
* whale;
* stress agent.

## 20.2 Reproducibility

```yaml
random_seed: 12345
duration_seconds: 3600
```

The random source will be injectable.

---

# 21. Analytical Storage

## 21.1 Minimum Tables

```text
nodes
node_snapshots
peers
peer_observations
blocks
block_observations
transactions
transaction_observations
mempool_events
wallet_events
utxo_snapshots
mining_sessions
mining_samples
difficulty_adjustments
experiments
experiment_events
system_metrics
```

## 21.2 Timestamps

* UTC;
* timezone-aware;
* ISO 8601 when exporting;
* documented precision.

## 21.3 Sensitive Data

Do not store:

* keys;
* seeds;
* cookies;
* passwords;
* tokens;
* personal paths;
* public IPs without consent.

---

# 22. Python Standards

## 22.1 Version

The initial baseline will use Python 3.13.

The minimum supported version will be declared in `pyproject.toml`.

## 22.2 Packaging

The following will be used:

* `pyproject.toml`;
* `src-layout`;
* wheel;
* source distribution;
* `uv.lock`;
* `.python-version`.

## 22.3 PEPs

Code will follow:

* PEP 8;
* PEP 257;
* PEP 484;
* PEP 440;
* PEP 621.

## 22.4 Pythonic Code

Preference will be given to:

* composition;
* dataclasses;
* enums;
* context managers;
* iterators;
* `pathlib`;
* specific exceptions;
* protocols;
* immutable value objects;
* integer satoshis;
* `Decimal` when necessary.

`float` must never be used for monetary amounts.

## 22.5 Typing

All production code will be typed.

Rules:

* avoid `Any`;
* justify `# type: ignore`;
* validate JSON;
* typed DTOs;
* explicit interfaces;
* strict typing in CI.

## 22.6 Functions

Functions must:

* have clear responsibility;
* avoid hidden side effects;
* receive explicit dependencies;
* avoid ambiguous booleans;
* return predictable types.

## 22.7 Docstrings

Will explain:

* contract;
* invariants;
* errors;
* side effects.

Will not simply repeat the code.

---

# 23. Error Handling

```text
BitheimError
├── ConfigurationError
├── NodeError
├── WalletError
├── NetworkError
├── MiningError
├── ExperimentError
├── AnalyticsError
└── SecurityError
```

Adapters will translate external errors.

Stack traces will only be displayed in debug mode.

---

# 24. Logging

Logs will contain:

* UTC timestamp;
* level;
* module;
* event;
* correlation ID;
* node ID;
* experiment ID.

Must never contain:

* cookies;
* keys;
* seeds;
* passwords;
* `Authorization`;
* secrets;
* unsanitized configuration.

---

# 25. Security

## 25.1 Threat Model

The following will be documented:

* curious participant;
* misconfigured node;
* compromised image;
* vulnerable dependency;
* Git leak;
* exposed RPC;
* manipulated manifest;
* malicious scenario;
* local access;
* supply-chain attacks.

## 25.2 RPC

RPC:

* localhost only;
* cookie authentication;
* never sent over network;
* never logged;
* read on demand;
* held in memory for minimum duration.

## 25.3 P2P

Only the P2P port will be published.

Bind must be explicit.

`0.0.0.0` will not be used as default public value.

## 25.4 Containers

* non-root user;
* read-only root filesystem when possible;
* dropped capabilities;
* `no-new-privileges`;
* health checks;
* limits;
* no privileged mode;
* no Docker socket.

## 25.5 Secrets

Must not be stored in:

* Dockerfile;
* build args;
* repository;
* images;
* versioned `.env`.

## 25.6 Gitignore

```text
.venv/
.env
.env.*
!.env.example
.local/
data/
wallets/
*.cookie
*.sqlite
*.duckdb
*.parquet
*.log
*.pem
*.key
*.crt
network.local.yaml
compose.override.yaml
secrets/
backups/
```

---

# 26. Dependencies

Every dependency must:

* have a purpose;
* be maintained;
* have a compatible license;
* be declared via `uv`;
* be pinned in `uv.lock`;
* pass review.

A PR introducing a dependency must explain:

* problem;
* alternatives;
* impact;
* license;
* risk;
* removal strategy.

---

# 27. Quality Tooling

Configuration will live in `pyproject.toml`.

Mandatory categories:

* formatting;
* linting;
* static typing;
* tests;
* coverage;
* dependency audit;
* secret detection;
* static security;
* Dockerfile validation;
* YAML/JSON validation.

Commands:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
```

Wrappers:

```bash
make check
make test
make security
make build
```

---

# 28. Testing

## 28.1 Unit Tests

Will cover:

* domain;
* value objects;
* policies;
* difficulty;
* mining;
* serialization;
* random generators;
* handlers.

## 28.2 Integration Tests

Will cover:

* RPC;
* DuckDB;
* ZMQ;
* filesystem;
* daemon;
* migrations.

## 28.3 Contract Tests

Will cover:

* Bitheim ↔ Bitcoin Core;
* TUI ↔ daemon;
* manifests ↔ schemas;
* scenarios ↔ runner;
* exporters.

## 28.4 End-to-End Tests

Will spin up ephemeral networks of:

* one node;
* two nodes;
* three nodes.

Will validate:

* wallets;
* transactions;
* mining;
* propagation;
* reorg;
* retarget;
* updates.

## 28.5 Security Tests

Will validate:

* closed RPC;
* permissions;
* secrets;
* path traversal;
* non-root containers;
* ports.

## 28.6 Property-Based Testing

For difficulty:

* same history → same target;
* target ≤ `powLimit`;
* bounded adjustment;
* fast blocks → higher difficulty;
* slow blocks → lower difficulty;
* high hash → rejection;
* monotonic chainwork.

## 28.7 Coverage

Targets:

* domain: 95%;
* difficulty: full relevant branches;
* initial total: 85%.

---

# 29. Local Development

## 29.1 Bootstrap

```bash
git clone <repository>
cd bitheim
uv python install
uv sync --all-groups
uv run bitheim doctor
```

## 29.2 Execution

```bash
uv run bitheim start
uv run bitheim tui
```

## 29.3 Tests

```bash
uv run pytest
```

## 29.4 Local Data

```text
.local/
├── data/
├── logs/
├── secrets/
├── exports/
└── networks/
```

---

# 30. Docker

## 30.1 Architectures

* `linux/amd64`;
* `linux/arm64`.

## 30.2 Profiles

```text
default
mining
simulation
analytics
development
```

## 30.3 Examples

```bash
docker compose up -d

docker compose --profile mining up -d

docker compose \
  --profile mining \
  --profile simulation \
  --profile analytics \
  up -d
```

## 30.4 Versions

`latest` will not be used.

```yaml
image: ghcr.io/example/bitheim:0.4.0
image: ghcr.io/example/bitheim-core:31.1-labnet.1
```

## 30.5 Persistence

```text
bitcoin-data
wallet-data
bitheim-state
analytics-data
exports
```

---

# 31. TUI

Views:

```text
Overview
Wallet
Transactions
Blocks
Mempool
Peers
Mining
Difficulty
Activity
Experiments
Analytics
Logs
Settings
RPC Console
```

The TUI must:

* work without color;
* support small terminals;
* document shortcuts;
* confirm destructive actions;
* show actionable errors.

---

# 32. CLI

```text
bitheim install
bitheim start
bitheim stop
bitheim status
bitheim tui
bitheim wallet create
bitheim wallet send
bitheim peers list
bitheim miner start
bitheim miner stop
bitheim simulate start
bitheim experiment run
bitheim export
bitheim doctor
bitheim update check
bitheim update apply
```

From development:

```bash
uv run bitheim status
```

Outputs:

* `human`;
* `json`.

---

# 33. Configuration

Priority:

```text
defaults
→ bitheim.toml
→ allowed variables
→ CLI flags
```

Secrets will not be accepted via flags.

The application will fail on:

* invalid fields;
* insecure paths;
* invalid ports;
* unexpected public IP;
* incompatible protocol;
* exposed RPC.

---

# 34. Versioning

Semantic Versioning will be used.

The following will be versioned separately:

```text
Bitheim version
Node distribution version
Labnet protocol version
Manifest format version
Analytics schema version
```

Example:

```yaml
bitheim_version: 0.6.0
bitcoin_base_version: 31.1
node_distribution: 31.1-labnet.3
labnet_protocol: 1
manifest_format: 1
analytics_schema: 4
```

---

# 35. Git

## 35.1 Workflow

Lightweight trunk-based development:

* `main` always deployable;
* short-lived branches;
* pull requests;
* feature flags.

## 35.2 Pull Requests

Every PR will include:

* problem;
* solution;
* risks;
* tests;
* architectural impact;
* security impact;
* documentation.

Cannot be merged with:

* failing CI;
* secrets;
* pending review;
* critical vulnerability;
* architectural change without ADR.

## 35.3 Review

Changes to:

* consensus;
* security;
* wallets;
* releases;
* Docker;
* manifests;
* migrations;

will require review by both maintainers.

---

# 36. Architecture Decision Records

```text
ADR-0001: Modular Monolith
ADR-0002: Hexagonal Architecture
ADR-0003: uv Project Management
ADR-0004: DuckDB and Parquet
ADR-0005: Docker Compose
ADR-0006: Labnet Parameters
ADR-0007: Local Daemon API
ADR-0008: Multi-Architecture Images
ADR-0009: Project Naming — Bitheim
```

Each ADR will contain:

* context;
* decision;
* alternatives;
* consequences;
* status.

---

# 37. CI/CD

## 37.1 Pull Request

1. `uv sync --locked`;
2. format check;
3. lint;
4. typing;
5. unit tests;
6. integration tests;
7. dependency review;
8. secret scanning;
9. security analysis;
10. package build;
11. image build;
12. smoke test;
13. documentation validation.

## 37.2 Main

Additionally:

* multi-node E2E;
* `amd64`;
* `arm64`;
* reorg;
* retarget;
* upgrade;
* rollback.

## 37.3 Release

1. validate tag;
2. generate changelog;
3. run test suite;
4. build images;
5. build wheel;
6. generate SBOM;
7. scan;
8. sign;
9. generate provenance;
10. publish RC;
11. smoke test;
12. manual promotion.

---

# 38. Supply-Chain Security

Before `v1.0.0`:

* pinned dependencies;
* `uv.lock`;
* dependency review;
* SBOM;
* signed images;
* provenance;
* pinned GitHub Actions;
* minimal permissions;
* branch protection;
* container scanning;
* OpenSSF Scorecard.

---

# 39. Releases and Updates

## 39.1 Channels

```text
dev
alpha
beta
rc
stable
```

## 39.2 Process

```text
1. Verify compatibility.
2. Display release notes.
3. Verify signature.
4. Create backup.
5. Download artifacts.
6. Validate disk space.
7. Stop processes.
8. Migrate.
9. Start.
10. Run health checks.
11. Confirm.
12. Rollback if failure occurs.
```

No regular update will silently alter `labnet-v1`.

---

# 40. Roadmap up to `v1.0.0`

## `v0.1.0` — Foundation

### Deliverables

* `bitheim` repository;
* project managed by `uv`;
* `pyproject.toml`;
* `uv.lock`;
* `.python-version`;
* `src-layout`;
* modular monolith;
* hexagonal architecture;
* minimal CLI;
* configuration;
* logging;
* CI;
* Docker;
* documentation;
* open source policies;
* ADRs.

### Acceptance

* `uv sync` reproduces the environment;
* `uv run bitheim --help` works;
* `amd64` and `arm64` images;
* mandatory CI;
* zero secrets.

---

## `v0.2.0` — Managed Regtest Node

### Deliverables

* Bitcoin Core management;
* datadir;
* health;
* RPC cookie;
* wallet;
* human transactions;
* blocks;
* mempool;
* peers;
* JSON CLI;
* basic TUI.

### Acceptance

Two users can start nodes, connect them, create wallets, and execute a transaction.

---

## `v0.3.0` — Analytics Foundation

### Deliverables

* collector;
* events;
* DuckDB;
* snapshots;
* CSV;
* Parquet;
* queries;
* TUI panels.

### Acceptance

A transaction can be tracked from creation to confirmation.

---

## `v0.4.0` — Synthetic Activity

### Deliverables

* agents;
* scheduler;
* Poisson;
* amounts;
* seeds;
* profiles;
* scenarios;
* origin.

### Acceptance

A scenario generates valid, reproducible Bitcoin transactions.

---

## `v0.5.0` — External PoW Miner

### Deliverables

* `getblocktemplate`;
* coinbase;
* Merkle root;
* header;
* SHA-256d;
* workers;
* hashrate;
* `submitblock`;
* limits.

### Acceptance

Two miners compete to produce a block.

---

## `v0.6.0` — Labnet Prototype

### Deliverables

* minimal fork;
* genesis;
* magic bytes;
* ports;
* mandatory PoW;
* retarget;
* manifest;
* tests.

### Acceptance

A block with insufficient PoW is rejected by all nodes.

---

## `v0.7.0` — Distributed Mining

### Deliverables

* profiles;
* visible difficulty;
* retarget;
* stale blocks;
* reorgs;
* metrics;
* hashrate change.

### Acceptance

Two different teams maintain a chain with distributed difficulty.

---

## `v0.8.0` — Experiment Workbench

### Deliverables

* runner;
* transfer;
* propagation;
* congestion;
* partition;
* reorg;
* UTXO consolidation;
* difficulty experiment;
* checkpoints;
* reports.

### Acceptance

Experiments can be executed, repeated, and exported.

---

## `v0.9.0` — Operational Hardening

### Deliverables

* update;
* rollback;
* backups;
* doctor;
* security tests;
* SBOM;
* signatures;
* provenance;
* documentation;
* performance;
* Mac/Linux/WSL2.

### Acceptance

The system can update and recover from an induced failure.

---

## `v1.0.0` — Stable Release

### Requirements

* stable API;
* stable CLI;
* stable manifest;
* stable configuration;
* frozen `labnet-v1`;
* migrations;
* rollback;
* signed images;
* SBOM;
* complete documentation;
* documented security;
* `amd64`;
* `arm64`;
* tested with both users;
* zero known critical vulnerabilities;
* release candidate validated in real-world use.

---

# 41. Non-Functional Criteria

## Security

* RPC not accessible from the mesh.
* No secrets in repository.
* Non-root containers.
* Verifiable releases.
* Secure configuration.

## Performance

In baseline state:

* Bitheim under 150 MiB of RAM;
* responsive TUI;
* reasonable startup;
* configurable mining;
* prolonged sessions supported.

## Reliability

* graceful shutdown;
* restart without corruption;
* recovery;
* idempotent migrations;
* verifiable backups.

## Maintainability

* no circular dependencies;
* strict typing;
* documentation;
* tests;
* ADRs;
* recorded tech debt.

## Scalability

Two nodes will be the primary case.

The design must tolerate more participants without altering the core architecture.

---

# 42. Definition of Done

A task will be considered done when:

* code implemented;
* tests;
* typing;
* lint;
* documentation;
* security review;
* sanitized logs;
* handled errors;
* fulfilled criteria;
* green CI;
* lockfile updated when applicable.

---

# 43. Governance

The two maintainers will be responsible for:

* roadmap;
* architecture;
* security;
* releases;
* review;
* support.

In case of disagreement:

1. document alternatives;
2. create an experiment;
3. measure;
4. choose the safest and most reversible option.

---

# 44. Licensing and Contributions

Before the first public release, the following will be established:

* license;
* contribution policy;
* code of conduct;
* security policy;
* governance.

Mandatory files:

```text
LICENSE
CONTRIBUTING.md
CODE_OF_CONDUCT.md
SECURITY.md
GOVERNANCE.md
```

Contributions will not be accepted if they:

* introduce non-consensual telemetry;
* relax security;
* expose RPC;
* incorporate real private data;
* bypass consensus;
* add dependencies without review.

---

# 45. Mandatory Documentation

```text
README
Quick Start
Installation
uv Development Workflow
Architecture Overview
Module Boundaries
Security Model
Threat Model
Configuration Reference
Network Manifest Reference
CLI Reference
TUI Guide
Mining Guide
Analytics Guide
Experiment Guide
Update and Rollback
Backup and Recovery
Troubleshooting
Development Guide
Release Process
Contribution Guide
```

---

# 46. Risks

## Bitcoin Core Fork

Mitigation:

* minimal delta;
* isolated commits;
* tests;
* tracking upstream;
* documentation.

## Network Exposure

Mitigation:

* explicit bind;
* doctor;
* tests;
* fictitious examples;
* local RPC.

## Complexity

Mitigation:

* modular monolith;
* incremental roadmap;
* strict scope;
* no web dashboard before `1.0.0`.

## Low User Base

Mitigation:

* design for two;
* automated multi-node tests;
* optional simulator;
* avoid overengineering.

## Platforms

Mitigation:

* Docker;
* multi-architecture;
* CI;
* real testing;
* doctor.

## Python Environment Divergence

Mitigation:

* `uv`;
* `.python-version`;
* `uv.lock`;
* `uv sync --locked`;
* identical commands in local, CI, and Docker.

## Data Loss

Mitigation:

* volumes;
* backups;
* migrations;
* rollback;
* snapshots.

---

# 47. Expected Outcome

Upon reaching `v1.0.0`, Bitheim will enable two users to:

1. clone or install the same distribution;
2. reproduce the Python environment with `uv`;
3. run the system across distinct architectures;
4. join an existing private network;
5. create a `labnet-v1` network;
6. run real nodes;
7. create wallets;
8. execute valid transactions;
9. participate in competitive mining;
10. observe distributed difficulty;
11. generate optional synthetic activity;
12. run experiments;
13. analyze data;
14. export results;
15. update Bitheim;
16. roll back a failed update;
17. understand what occurs behind every abstraction.

Bitheim must remain small enough to be operated and maintained by two people, while having technical, architectural, and security foundations that allow extending it after `v1.0.0` without a complete rewrite.
