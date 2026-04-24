FROM rust:1-slim-bookworm AS builder

# Install all required build dependencies
RUN apt-get update && apt-get install -y \
    clang \
    libclang-dev \
    llvm-dev \
    pkg-config \
    libssl-dev \
    make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

RUN cargo build --release

# Runtime stage
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/target/release/lila-openingexplorer /usr/local/bin/

EXPOSE 8080
WORKDIR /data
CMD ["lila-openingexplorer", "--db-path", "/data", "--port", "8080"]
