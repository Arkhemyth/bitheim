# SPEC-0002: Container Image Foundation and Multi-Platform CI Validation

- **Status:** Accepted
- **Author:** Bitheim Contributors
- **Date:** 2026-08-02
- **Related Plan:** [`docs/plan_bitheim.md`](../plan_bitheim.md)
- **Related Specs:** [`docs/specs/SPEC-0001-configuration-and-doctor.md`](SPEC-0001-configuration-and-doctor.md)

---

## 1. Context

As outlined in the Bitheim Master Plan ([`docs/plan_bitheim.md`](../plan_bitheim.md)), containerization is a core delivery and execution mechanism for running nodes reproducibly across heterogeneous environments (Linux `amd64`, Linux `arm64`, macOS via Docker Desktop, and Windows via WSL2/Docker).

To establish an immutable and secure foundation for container-based execution in milestone `v0.1.0`, Bitheim requires a multi-stage `Dockerfile`, explicit dependency and base-image pinning, non-root execution model, immutable application code, and automated multi-platform validation in GitHub Actions CI without premature image publication.

---

## 2. Goals

- Provide a multi-stage, reproducible `Dockerfile` targeting `linux/amd64` and `linux/arm64`.
- Pin all base images and tooling (`python:3.13.14-slim-bookworm`, `ghcr.io/astral-sh/uv:0.11.31`) with verified multi-architecture manifest-list digests.
- Enforce least privilege: non-root user (`bitheim`, UID/GID `10001`), root-owned immutable virtual environment at `/opt/bitheim/.venv`, and runtime data storage at `/data`.
- Ensure runtime cleanliness: exclude `uv`, compilers, tests, development dependencies, caches, and repository metadata from the final stage.
- Align runtime configuration with [`SPEC-0001`](SPEC-0001-configuration-and-doctor.md) by defining `ENV BITHEIM_DATA_DIR=/data`.
- Integrate multi-platform (`linux/amd64`, `linux/arm64`) build and smoke-test validation into GitHub Actions CI using pinned actions, isolated cache scopes, and BuildKit cache.

---

## 3. Non-Goals

- Publishing or pushing container images to GitHub Container Registry (GHCR) or Docker Hub in this increment.
- Implementing Docker Compose stacks, multi-service orchestration, Bitcoin Core sidecars, or network daemons.
- Defining a Docker `HEALTHCHECK` directive (the `bitheim doctor` subcommand is an environment and configuration diagnostic tool, not a background service health monitor).
- Generating container provenance attestations, SBOMs, or image signing before publication workflows are authorized.

---

## 4. Supported Platforms

The container image and CI build matrix support:
- `linux/amd64`
- `linux/arm64`

Base images must be multi-arch manifest lists resolving natively to both target architectures.

---

## 5. Pinning and Reproducibility

To ensure deterministic builds, all base images and tools are pinned by patch version and immutable SHA256 multi-arch manifest list digest:

1. **Python Base Image:**
   `python:3.13.14-slim-bookworm@sha256:9d7f287598e1a5a978c015ee176d8216435aaf335ed69ac3c38dd1bbb10e8d64`
2. **Uv Tooling Image:**
   `ghcr.io/astral-sh/uv:0.11.31@sha256:ecd4de2f060c64bea0ff8ecb182ddf46ba3fcccdc8a60cfdbaf20d1a047d7437`
3. **Build Flags:**
   `UV_PYTHON_DOWNLOADS=0`, `UV_LINK_MODE=copy`, `UV_COMPILE_BYTECODE=1`, `UV_PROJECT_ENVIRONMENT=/opt/bitheim/.venv`, `uv sync --locked --no-dev --no-editable`.

---

## 6. Image Architecture and Runtime Contract

### 6.1 Builder Stage (`builder`)
- Based on the pinned Python slim base image.
- Imports `uv` binary from the pinned official uv image.
- Copies only required packaging metadata (`pyproject.toml`, `uv.lock`, `README.md`, `LICENSE`) and application source (`src/`).
- Builds and bytecode-compiles the virtual environment directly at `/opt/bitheim/.venv` using `UV_PROJECT_ENVIRONMENT=/opt/bitheim/.venv`.

### 6.2 Runtime Stage (`runtime`)
- Based on the pinned Python slim base image.
- Copies the virtual environment from `builder` into `/opt/bitheim/.venv`. The `/opt/bitheim` path remains root-owned (`root:root`) with standard read and execute permissions (`a+rx`), preventing the runtime user from mutating application code or installed dependencies.
- Creates dedicated system group and user:
  - User: `bitheim`
  - UID: `10001`
  - GID: `10001`
- Sets up `/data` volume directory owned exclusively by `bitheim:bitheim` (`chmod 0750`). `/data` is the only writable application directory at runtime.
- Sets environment variables:
  - `PATH="/opt/bitheim/.venv/bin:$PATH"`
  - `BITHEIM_DATA_DIR=/data`
  - `PYTHONUNBUFFERED=1`
  - `PYTHONDONTWRITEBYTECODE=1`
- Declares standard OCI annotations (title, description, URL, source, vendor, license).
- Sets `USER 10001:10001`.
- Sets `WORKDIR /data`.
- Sets `ENTRYPOINT ["/opt/bitheim/.venv/bin/bitheim"]` and `CMD ["--help"]`.

---

## 7. CI Validation Strategy

The CI pipeline is extended with a dedicated `container` job that validates:

1. **Setup:** Installs QEMU (`docker/setup-qemu-action`) and Docker Buildx (`docker/setup-buildx-action`) using verified full commit SHAs.
2. **Native Build & Smoke Tests:**
   - Builds `linux/amd64` image with tag `bitheim:ci` loaded into the local Docker daemon.
   - Executes smoke tests:
     - `docker run --rm bitheim:ci --help` (verifies help output and exit code 0)
     - `docker run --rm bitheim:ci --version` (verifies canonical version and exit code 0)
     - `docker run --rm bitheim:ci doctor` (verifies Python 3.13, configuration loading, `/data` resolution, and filesystem write access)
     - `docker run --rm --entrypoint id bitheim:ci -u` (asserts UID `10001` != `0`)
     - Read-only filesystem test: asserts that attempting to write to `/opt/bitheim/.venv` fails under UID `10001`.
     - Writable data directory test: asserts that writing to `/data` succeeds under UID `10001`.
3. **Multi-Platform Build Validation:**
   - Executes multi-platform build for `linux/amd64,linux/arm64` with `outputs: type=cacheonly`, isolated cache scope, and GitHub Actions cache (`type=gha`).

---

## 8. Security Constraints

- **Least Privilege:** Container runs strictly as non-root user `10001:10001`.
- **Immutable Application Environment:** `/opt/bitheim` and `/opt/bitheim/.venv` are root-owned and read-only to UID `10001`.
- **Minimal Attack Surface:** No compilers (`gcc`, `clang`), package managers used for runtime alterations (`uv`), development dependencies, test suites, or git metadata in the runtime image. The baseline `pip` binary inherited from the official Python slim base image is unused.
- **No Secrets:** No secrets, credentials, API keys, or private files are baked into the image or build contexts.
- **Immutable Entrypoint:** Entrypoint is pinned to `/opt/bitheim/.venv/bin/bitheim`.

---

## 9. Acceptance Criteria

1. `docker build -t bitheim:local .` builds cleanly and reproducibly.
2. `docker run --rm bitheim:local --help`, `--version`, and `doctor` exit `0` with expected outputs.
3. Non-root user `10001` is verified at runtime.
4. Mutation of `/opt/bitheim/.venv` fails while `/data` is writable.
5. `.dockerignore` excludes sensitive files, databases, and local overrides.
6. GitHub Actions workflow runs native smoke tests and multi-platform (`amd64`, `arm64`) builds successfully.
