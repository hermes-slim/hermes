#!/usr/bin/env python3
"""List Windows binaries (.exe/.dll/.pyd) under a directory and whether each carries an
Authenticode signature (a non-empty PE certificate table).

    python slim/pe_signatures.py DIR [--fail-unsigned]

Presence only, stdlib only, runs anywhere. Windows CI checks that each signature is
valid with Get-AuthenticodeSignature. Smart App Control blocks unsigned binaries.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

PE_SUFFIXES = {".exe", ".dll", ".pyd"}


def has_signature(path: Path) -> bool:
    data = path.read_bytes()
    if data[:2] != b"MZ":
        return False
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        return False
    opt = pe + 24
    magic = struct.unpack_from("<H", data, opt)[0]
    dirs = opt + (96 if magic == 0x10B else 112)  # PE32 / PE32+
    _, size = struct.unpack_from("<II", data, dirs + 4 * 8)  # entry 4: certificate table
    return size > 0


def scan(root: Path) -> tuple[list[Path], list[Path]]:
    signed, unsigned = [], []
    for p in sorted(root.rglob("*")):
        if p.suffix.lower() in PE_SUFFIXES and p.is_file():
            (signed if has_signature(p) else unsigned).append(p)
    return signed, unsigned


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", type=Path)
    ap.add_argument("--fail-unsigned", action="store_true")
    args = ap.parse_args()
    signed, unsigned = scan(args.root)
    for p in unsigned:
        print(f"unsigned  {p.relative_to(args.root)}")
    print(f"{len(signed)} signed, {len(unsigned)} unsigned")
    return 1 if args.fail_unsigned and unsigned else 0


if __name__ == "__main__":
    sys.exit(main())
