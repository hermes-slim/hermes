# Local builder for the glibc linux-x64 bundle.
FROM debian:bookworm-slim@sha256:7ff6ba31527b9e336162fa061746c366c4b2032f4d2cff2078bea43f78efe3f8
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates python3 git zstd \
    && rm -rf /var/lib/apt/lists/* && git config --global --add safe.directory /repo
