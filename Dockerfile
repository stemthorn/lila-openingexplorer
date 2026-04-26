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
COPY . .
RUN cargo build --release --bin lila-openingexplorer

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    ca-certificates \
    liburing2 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/target/release/lila-openingexplorer /usr/local/bin/lila-openingexplorer

WORKDIR /data
EXPOSE 8080

# Masters-only operational default; can be overridden per environment.
ENV DISABLE_BLACKLIST_UPDATE=1

# Render should pass PORT, with fallback for local container runs.
CMD ["/bin/sh", "-lc", "lila-openingexplorer --db /data --bind 0.0.0.0:${PORT:-8080}"]
