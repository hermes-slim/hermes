#!/usr/bin/env python3
"""Build a self-contained hermes-slim bundle for one target.

    python slim/build_bundle.py --target darwin-x64 [--out dist] [--wheels DIR]

The bundle is a relocatable CPython (python-build-standalone, pinned with
sha256 in pm/lock.json) with every runtime dependency from uv.lock already
installed, the Hermes source tree, and launchers. The client machine only
unpacks it: no package resolution, no compilers, no downloads at install time.

Stdlib only, so it runs on any Python 3.11+.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TARGETS = ("darwin-x64", "darwin-arm64", "win32-x64", "linux-x64-musl", "linux-x64")
# Extras the slim bundle ships. Gateway + Telegram + MCP + free web search.
# `sms` is just aiohttp, which the gateway API server (/health) needs.
EXTRAS = ("telegram", "mcp", "ddgs", "sms")
# Source paths copied into app/. Everything else (desktop app, website, tests) stays out.
APP_EXCLUDE = {
    ".git", ".github", "apps", "website", "web", "tests", "tests-js", "evals", "ui-tui",
    "node_modules", "dist", "build", ".venv", "docker", "nix", "contributors", "assets",
}


def host_target() -> str:
    sysname = {"darwin": "darwin", "win32": "win32"}.get(sys.platform, "linux")
    arch = {"x86_64": "x64", "amd64": "x64", "arm64": "arm64", "aarch64": "arm64"}[platform.machine().lower()]
    t = f"{sysname}-{arch}"
    if sysname == "linux" and Path("/etc/alpine-release").exists():
        t += "-musl"
    return t


def pin(package: str, target: str) -> dict:
    lock = json.loads((REPO / "pm" / "lock.json").read_text())
    return lock["packages"][package]["artifacts"][target]


def fetch(url: str, sha256: str, dest_dir: Path) -> Path:
    dest = dest_dir / url.rsplit("/", 1)[-1]
    if not dest.exists():
        print(f"fetch {url}", flush=True)
        with urllib.request.urlopen(url) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    if digest != sha256:
        dest.unlink()
        raise SystemExit(f"sha256 mismatch for {url}: {digest} != {sha256}")
    return dest


def unpack(archive: Path, dest: Path) -> None:
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            z.extractall(dest)
    else:
        with tarfile.open(archive) as t:
            t.extractall(dest, filter="tar") if hasattr(tarfile, "data_filter") else t.extractall(dest)


def find_exe(root: Path, names: tuple[str, ...]) -> Path:
    for name in names:
        for p in sorted(root.rglob(name)):
            if p.is_file():
                return p
    raise SystemExit(f"no {names} under {root}")


def run(cmd: list, **kw) -> subprocess.CompletedProcess:
    print("+", " ".join(map(str, cmd)), flush=True)
    return subprocess.run([str(c) for c in cmd], check=True, **kw)


def write_launchers(bundle: Path, windows: bool) -> None:
    bindir = bundle / "bin"
    bindir.mkdir(exist_ok=True)
    if windows:
        for name, script in (("hermes", "app\\hermes"), ("hermes-slim-setup", "app\\slim\\setup.py")):
            (bindir / f"{name}.cmd").write_text(
                "@echo off\r\n"
                "set \"HS_ROOT=%~dp0..\"\r\n"
                "set \"PYTHONPATH=%HS_ROOT%\\app\"\r\n"
                "set \"HERMES_SLIM=1\"\r\n"
                f"\"%HS_ROOT%\\python\\python.exe\" \"%HS_ROOT%\\{script}\" %*\r\n",
                newline="",
            )
    else:
        for name, script in (("hermes", "app/hermes"), ("hermes-slim-setup", "app/slim/setup.py")):
            p = bindir / name
            p.write_text(
                "#!/bin/sh\n"
                # Resolve symlinks (install.sh links these into ~/.local/bin).
                'self="$0"\n'
                'while [ -L "$self" ]; do l="$(readlink "$self")"; case "$l" in /*) self="$l" ;; *) self="$(dirname "$self")/$l" ;; esac; done\n'
                'HS_ROOT="$(cd "$(dirname "$self")/.." && pwd)"\n'
                'export PYTHONPATH="$HS_ROOT/app"\n'
                "export HERMES_SLIM=1\n"
                f'exec "$HS_ROOT/python/bin/python3" "$HS_ROOT/{script}" "$@"\n'
            )
            p.chmod(0o755)


def build(target: str, out: Path, wheels: Path | None, work: Path) -> Path:
    windows = target.startswith("win32")
    bundle = work / "hermes-slim"
    if bundle.exists():
        shutil.rmtree(bundle)
    bundle.mkdir(parents=True)

    downloads = work / "downloads"
    downloads.mkdir(exist_ok=True)

    py_pin = pin("python", target)
    unpack(fetch(py_pin["url"], py_pin["sha256"], downloads), bundle)  # -> bundle/python/
    python = bundle / "python" / ("python.exe" if windows else "bin/python3")

    uv_dir = work / "uv"
    if not uv_dir.exists():
        uv_pin = pin("uv", host_target())
        unpack(fetch(uv_pin["url"], uv_pin["sha256"], downloads), uv_dir)
    uv = find_exe(uv_dir, ("uv.exe", "uv"))
    if not windows:
        uv.chmod(0o755)

    env = dict(os.environ, UV_NO_CONFIG="1", UV_PYTHON_DOWNLOADS="never")
    reqs = work / "requirements.txt"
    export = [uv, "export", "--frozen", "--no-dev", "--no-emit-project", "--no-hashes",
              "--format", "requirements.txt", "-o", reqs]
    for extra in EXTRAS:
        export += ["--extra", extra]
    run(export, cwd=REPO, env=env)

    install = [uv, "pip", "install", "--python", python, "--break-system-packages", "--no-deps", "--no-build", "-r", reqs]
    if wheels and wheels.is_dir():
        install += ["--find-links", wheels]
    log = work / "install.log"
    with open(log, "w") as f:
        proc = subprocess.run([str(c) for c in install], cwd=REPO, env=env, stdout=f, stderr=subprocess.STDOUT)
    text = log.read_text()
    print(text[-20000:])
    if proc.returncode:
        # --no-build: a package with no wheel for this target fails here instead of compiling.
        # Fix it by publishing a wheel to hermes-slim/wheels, not by compiling in the bundle.
        raise SystemExit(f"dependency install failed on {target} (see log above)")

    app = bundle / "app"
    shutil.copytree(REPO, app, ignore=lambda d, names: [n for n in names if Path(d) == REPO and n in APP_EXCLUDE]
                    + [n for n in names if n in ("__pycache__", ".pytest_cache", "node_modules")])
    write_launchers(bundle, windows)

    out.mkdir(parents=True, exist_ok=True)
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip() or "dev"
    (bundle / "BUNDLE.json").write_text(json.dumps({"target": target, "commit": rev, "extras": EXTRAS}, indent=2))
    name = f"hermes-slim-{rev}-{target}"
    if windows:
        archive = out / f"{name}.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            for p in bundle.rglob("*"):
                z.write(p, p.relative_to(work))
    else:
        archive = out / f"{name}.tar.gz"
        with tarfile.open(archive, "w:gz") as t:
            t.add(bundle, arcname="hermes-slim")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (out / f"{archive.name}.sha256").write_text(f"{digest}  {archive.name}\n")
    print(f"bundle: {archive} ({archive.stat().st_size // (1 << 20)} MiB) sha256={digest}")
    return archive


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default=host_target(), choices=TARGETS)
    ap.add_argument("--out", type=Path, default=REPO / "dist")
    ap.add_argument("--wheels", type=Path, help="directory of extra wheels (hermes-slim/wheels release assets)")
    ap.add_argument("--work", type=Path, help="scratch directory (default: a temp dir)")
    args = ap.parse_args()
    if args.target != host_target():
        raise SystemExit(f"bundles build natively: host is {host_target()}, asked for {args.target}")
    work = args.work or Path(tempfile.mkdtemp(prefix="hermes-slim-build-"))
    work.mkdir(parents=True, exist_ok=True)
    build(args.target, args.out.resolve(), args.wheels, work.resolve())


if __name__ == "__main__":
    main()
