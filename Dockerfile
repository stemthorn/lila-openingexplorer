FROM rust:1-slim-bookworm AS builder

RUN apt-get update && apt-get install -y \
    clang \
    libclang-dev \
    llvm-dev \
    pkg-config \
    libssl-dev \
    make \
    build-essential \
    liburing-dev \
    && rm -rf /var/lib/apt/lists/* \
    && rustup component add rustfmt

# Reduce build memory usage
ENV CARGO_INCREMENTAL=0
ENV RUSTFLAGS="-C link-arg=-s"

WORKDIR /app
COPY . .

# Build with fewer parallel jobs to lower peak memory
RUN cargo build --release --jobs 2

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/target/release/lila-openingexplorer /usr/local/bin/

EXPOSE 8080
WORKDIR /data
CMD ["lila-openingexplorer", "--db-path", "/data", "--port", "8080"]
