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

# ==================== FINAL STAGE ====================
FROM debian:bookworm-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    liburing2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the compiled binary
COPY --from=builder /app/target/release/lila-openingexplorer /usr/local/bin/lila-openingexplorer

WORKDIR /data
EXPOSE 8080

# Masters-only operational default
ENV DISABLE_BLACKLIST_UPDATE=1

# === Stockfish wrapper (defensive version) ===
COPY start-with-stockfish.sh /start-with-stockfish.sh
RUN chmod +x /start-with-stockfish.sh

ENTRYPOINT ["/start-with-stockfish.sh"]