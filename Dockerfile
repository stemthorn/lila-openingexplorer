FROM debian:bookworm-slim

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy the binary you built locally
COPY target/release/lila-openingexplorer /usr/local/bin/

EXPOSE 8080
WORKDIR /data

# Run the explorer (masters-only by default)
CMD ["lila-openingexplorer", "--db-path", "/data", "--port", "8080"]
