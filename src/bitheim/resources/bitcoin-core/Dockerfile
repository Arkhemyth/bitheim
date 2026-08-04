# Multi-stage Dockerfile for Bitheim Managed Bitcoin Core 31.1 Regtest Node
# Security: Multi-architecture pinned base, non-root user (10001:10000), verified SHA256 checksums

FROM debian:bookworm-slim@sha256:7b140f374b289a7c2befc338f42ebe6441b7ea838a042bbd5acbfca6ec875818 AS downloader

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    tar \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /download

ARG TARGETARCH
RUN set -eux; \
    if [ "${TARGETARCH}" = "amd64" ]; then \
        ARCH="x86_64-linux-gnu"; \
        EXPECTED_SHA256="b80d9c3e04da78fb6f0569685673418cf686fadba9042d926d13fb87ff503f9e"; \
    elif [ "${TARGETARCH}" = "arm64" ]; then \
        ARCH="aarch64-linux-gnu"; \
        EXPECTED_SHA256="dcf1873f2208ba4f962f3398d47e154c39c0084be8f4553e05c940d0ace3d004"; \
    else \
        echo "Unsupported target architecture: ${TARGETARCH}" >&2; \
        exit 1; \
    fi; \
    TARBALL="bitcoin-31.1-${ARCH}.tar.gz"; \
    URL="https://bitcoincore.org/bin/bitcoin-core-31.1/${TARBALL}"; \
    curl -fsSL -O "${URL}"; \
    echo "${EXPECTED_SHA256}  ${TARBALL}" | sha256sum -c -; \
    mkdir -p /opt/bitcoin; \
    tar -xzf "${TARBALL}" -C /opt/bitcoin --strip-components=1

FROM debian:bookworm-slim@sha256:7b140f374b289a7c2befc338f42ebe6441b7ea838a042bbd5acbfca6ec875818 AS runtime

# Standard OCI metadata labels
LABEL org.opencontainers.image.title="Bitheim Bitcoin Core" \
      org.opencontainers.image.description="Managed Bitcoin Core 31.1 Regtest Node" \
      org.opencontainers.image.version="31.1" \
      org.opencontainers.image.vendor="Arkhemyth" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/Arkhemyth/bitheim"

# Group 10000 (bitheim-rpc) is shared between bitcoind and bitheim containers
# Daemon runs as UID 10001 (bitcoind) with primary GID 10000
RUN groupadd --gid 10000 bitheim-rpc \
    && useradd --uid 10001 --gid 10000 --shell /usr/sbin/nologin --no-create-home bitcoind \
    && mkdir -p /data/bitcoin /data/rpc /etc/bitcoin \
    && chown -R 10001:10000 /data/bitcoin /data/rpc /etc/bitcoin \
    && chmod 0700 /data/bitcoin \
    && chmod 0750 /data/rpc

COPY --from=downloader /opt/bitcoin/bin/bitcoind /usr/local/bin/bitcoind
COPY --from=downloader /opt/bitcoin/bin/bitcoin-cli /usr/local/bin/bitcoin-cli
COPY bitcoin.conf /etc/bitcoin/bitcoin.conf

USER 10001:10000
WORKDIR /data/bitcoin

EXPOSE 18443 18444

ENTRYPOINT ["bitcoind"]
CMD ["-conf=/etc/bitcoin/bitcoin.conf", "-datadir=/data/bitcoin"]
