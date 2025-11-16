# syntax=docker/dockerfile:1.6

##########################
# Build Stage            #
##########################
FROM rust:1.84-bullseye AS builder

WORKDIR /app

# Install build dependencies for crates that need OpenSSL / pkg-config.
RUN apt-get update \
    && apt-get install -y --no-install-recommends pkg-config libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Cache dependencies
COPY Cargo.toml Cargo.lock ./
RUN mkdir src && echo "fn main() {}" > src/main.rs \
    && cargo build --release \
    && rm -rf src

# Copy project sources
COPY . .
RUN cargo build --release

##########################
# Runtime Stage          #
##########################
FROM debian:bullseye-slim AS runtime

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl libgcc-s1 libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/target/release/loglumen-server /usr/local/bin/loglumen-server

ENV LOGLUMEN_BIND_ADDRESS=0.0.0.0:8080
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s CMD curl -fsS http://localhost:8080/api/stats || exit 1

ENTRYPOINT ["/usr/local/bin/loglumen-server"]
