# Stage 1: Build virtual environment using uv
FROM python:3.13.14-slim-bookworm@sha256:9d7f287598e1a5a978c015ee176d8216435aaf335ed69ac3c38dd1bbb10e8d64 AS builder

# Copy uv binary from official pinned multi-arch image
COPY --from=ghcr.io/astral-sh/uv:0.11.31@sha256:ecd4de2f060c64bea0ff8ecb182ddf46ba3fcccdc8a60cfdbaf20d1a047d7437 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PYTHON=/usr/local/bin/python \
    UV_PROJECT_ENVIRONMENT=/opt/bitheim/.venv

WORKDIR /build

# Copy packaging manifests and project metadata
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src/ ./src/

# Install dependencies and project in non-editable mode without dev packages
RUN uv sync --locked --no-dev --no-editable

# Stage 2: Minimal runtime image
FROM python:3.13.14-slim-bookworm@sha256:9d7f287598e1a5a978c015ee176d8216435aaf335ed69ac3c38dd1bbb10e8d64 AS runtime

# Standard OCI metadata labels
LABEL org.opencontainers.image.title="Bitheim" \
      org.opencontainers.image.description="Distributed platform for experimentation, mining, and analysis on Bitcoin" \
      org.opencontainers.image.url="https://github.com/Arkhemyth/bitheim" \
      org.opencontainers.image.source="https://github.com/Arkhemyth/bitheim" \
      org.opencontainers.image.vendor="Arkhemyth" \
      org.opencontainers.image.licenses="MIT"

# Create non-root system user, runtime data directory (/data), and ensure /opt/bitheim is root-owned
RUN groupadd --gid 10001 bitheim \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin bitheim \
    && mkdir -p /data /opt/bitheim \
    && chown -R bitheim:bitheim /data \
    && chmod 0750 /data

# Copy production virtualenv from builder (root-owned, read-only to runtime user)
COPY --from=builder /opt/bitheim/.venv /opt/bitheim/.venv

ENV PATH="/opt/bitheim/.venv/bin:$PATH" \
    BITHEIM_DATA_DIR=/data \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER 10001:10001
WORKDIR /data

ENTRYPOINT ["/opt/bitheim/.venv/bin/bitheim"]
CMD ["--help"]
