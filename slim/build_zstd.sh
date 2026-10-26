#!/bin/sh
# Build a static zstd for Linux x86_64 clients that have none (stock Debian slim,
# many minimal images). Linked statically against musl, so the same binary runs on
# glibc and musl. Published beside the bundles; install.sh fetches it only when
# the host lacks zstd. Needs build-base (Alpine).
#
#   sh slim/build_zstd.sh OUT_DIR
set -eu
out="$1"
version=1.5.7
sha256=eb33e51f49a15e023950cd7825ca74a4a2b43db8354825ac24fc1b7ee09e6fa3
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
curl -fsSL -o "$work/zstd.tar.gz" "https://github.com/facebook/zstd/releases/download/v$version/zstd-$version.tar.gz"
echo "$sha256  $work/zstd.tar.gz" | sha256sum -c -
tar -xzf "$work/zstd.tar.gz" -C "$work"
make -C "$work/zstd-$version/programs" -j"$(nproc)" zstd-decompress LDFLAGS=-static >/dev/null
mkdir -p "$out"
strip -o "$out/zstd-linux-x64" "$work/zstd-$version/programs/zstd-decompress"
(cd "$out" && sha256sum zstd-linux-x64 > zstd-linux-x64.sha256)
"$out/zstd-linux-x64" -V
