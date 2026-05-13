# syntax=docker/dockerfile:1
# Build from this directory: cd infra/lila-openingexplorer && docker build -t lila-openingexplorer:local .

FROM rust:1-bookworm AS builder

RUN apt-get update && apt-get install -y \
    build-essential \
    clang \
    libclang-dev \
    llvm-dev \
    pkg-config \
    libssl-dev \
    liburing-dev \
    cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY Cargo.toml Cargo.lock ./
RUN cargo fetch --locked
COPY src ./src
COPY benches ./benches
RUN cargo build --release --bin lila-openingexplorer

FROM golang:1.23-bookworm AS go-builder
WORKDIR /src
COPY stockfish-wrapper/go.mod stockfish-wrapper/go.sum ./
RUN go mod download
COPY stockfish-wrapper/main.go ./
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o /stockfish-http-wrapper .

FROM debian:bookworm-slim

ARG STOCKFISH_RELEASE_TAG=sf_18
ARG STOCKFISH_OFFICIAL_ASSET=stockfish-ubuntu-x86-64-avx2
ARG CADDY_VERSION=2.8.4

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    liburing2 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL \
    "https://github.com/official-stockfish/Stockfish/releases/download/${STOCKFISH_RELEASE_TAG}/${STOCKFISH_OFFICIAL_ASSET}.tar" \
    -o /tmp/sf.tar \
    && tar -xf /tmp/sf.tar -C /tmp \
    && install -m 755 "/tmp/stockfish/${STOCKFISH_OFFICIAL_ASSET}" /usr/local/bin/stockfish \
    && rm -rf /tmp/sf.tar /tmp/stockfish \
    && curl -fsSL \
    "https://github.com/caddyserver/caddy/releases/download/v${CADDY_VERSION}/caddy_${CADDY_VERSION}_linux_amd64.tar.gz" \
    -o /tmp/caddy.tar.gz \
    && tar -xf /tmp/caddy.tar.gz -C /tmp caddy \
    && install -m 755 /tmp/caddy /usr/local/bin/caddy \
    && rm -f /tmp/caddy.tar.gz

COPY --from=builder /app/target/release/lila-openingexplorer /usr/local/bin/lila-openingexplorer
COPY --from=go-builder /stockfish-http-wrapper /usr/local/bin/stockfish-http-wrapper
COPY Caddyfile /etc/Caddyfile
COPY start-all.sh /start-all.sh
RUN chmod +x /start-all.sh /usr/local/bin/stockfish-http-wrapper /usr/local/bin/lila-openingexplorer

EXPOSE 8080
ENV DISABLE_BLACKLIST_UPDATE=1

ENTRYPOINT ["/start-all.sh"]
