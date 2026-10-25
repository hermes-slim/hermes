#!/bin/sh
# hermes-slim installer for macOS and Linux (musl).
#
#   sh install.sh [--version vX.Y.Z] [--dir ~/.hermes-slim] [-- <hermes-slim-setup args>]
#
# Downloads one prebuilt bundle from github.com/talos-hq/hermes-slim releases,
# verifies its sha256, unpacks it, and runs hermes-slim-setup. Nothing is
# compiled and no package manager runs.
set -eu

repo="talos-hq/hermes-slim"
version="latest"
dir="${HERMES_SLIM_DIR:-$HOME/.hermes-slim}"
while [ $# -gt 0 ]; do
  case "$1" in
    --version) version="$2"; shift 2 ;;
    --dir) dir="$2"; shift 2 ;;
    --) shift; break ;;
    *) break ;;
  esac
done

case "$(uname -s)-$(uname -m)" in
  Darwin-x86_64) target=darwin-x64 ;;
  Darwin-arm64) target=darwin-arm64 ;;
  Linux-x86_64) target=linux-x64-musl ;;
  *) echo "hermes-slim: unsupported platform $(uname -s)-$(uname -m)" >&2; exit 1 ;;
esac

if [ "$version" = latest ]; then
  base="https://github.com/$repo/releases/latest/download"
  version="$(curl -fsSLI -o /dev/null -w '%{url_effective}' "https://github.com/$repo/releases/latest" | sed 's#.*/##')"
else
  base="https://github.com/$repo/releases/download/$version"
fi
asset="$(curl -fsSL "https://api.github.com/repos/$repo/releases/tags/$version" |
  sed -n "s/.*\"name\": *\"\(hermes-slim-[^\"]*-$target\.tar\.gz\)\".*/\1/p" | head -1)"
[ -n "$asset" ] || { echo "hermes-slim: no $target bundle in release $version" >&2; exit 1; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
echo "→ downloading $asset"
curl -fSL --progress-bar -o "$tmp/$asset" "$base/$asset"
curl -fsSL -o "$tmp/$asset.sha256" "$base/$asset.sha256"
expected="$(cut -d' ' -f1 "$tmp/$asset.sha256")"
actual="$( (shasum -a 256 "$tmp/$asset" 2>/dev/null || sha256sum "$tmp/$asset") | cut -d' ' -f1)"
[ "$expected" = "$actual" ] || { echo "hermes-slim: sha256 mismatch" >&2; exit 1; }

echo "→ installing to $dir"
mkdir -p "$dir"
rm -rf "$dir/hermes-slim.new"
mkdir "$dir/hermes-slim.new"
tar -xzf "$tmp/$asset" -C "$dir/hermes-slim.new" --strip-components 1
rm -rf "$dir/hermes-slim.old"
[ -d "$dir/current" ] && mv "$dir/current" "$dir/hermes-slim.old"
mv "$dir/hermes-slim.new" "$dir/current"
# Unsigned bundle: clear the download quarantine so Gatekeeper does not block the interpreter.
[ "$(uname -s)" = Darwin ] && xattr -dr com.apple.quarantine "$dir/current" 2>/dev/null || true

mkdir -p "$HOME/.local/bin"
ln -sf "$dir/current/bin/hermes" "$HOME/.local/bin/hermes"
ln -sf "$dir/current/bin/hermes-slim-setup" "$HOME/.local/bin/hermes-slim-setup"
echo "✓ installed; 'hermes' is linked in ~/.local/bin"

exec "$dir/current/bin/hermes-slim-setup" --service "$@"
