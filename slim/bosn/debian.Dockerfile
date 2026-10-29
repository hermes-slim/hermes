# A stock glibc desktop/server: no Python, no git, only what install.sh needs.
FROM debian:bookworm-slim@sha256:7ff6ba31527b9e336162fa061746c366c4b2032f4d2cff2078bea43f78efe3f8
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl zstd procps && rm -rf /var/lib/apt/lists/*
