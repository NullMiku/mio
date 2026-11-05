#!/usr/bin/env python3
"""Diagnostic only (never a pass/fail check): tries to start variants of a PE whose loading failed, to show which header
property the Windows loader objects to. Prints one line per variant."""
import struct
import subprocess
import sys
import tempfile
from pathlib import Path


def variants(data):
    pe = struct.unpack_from("<I", data, 60)[0]
    opt = pe + 24
    yield "original", data
    for mib in (1, 16):
        d = bytearray(data)
        struct.pack_into("<Q", d, opt + 72, mib * 1048576)
        yield "stack-reserve-%dMiB" % mib, bytes(d)
    d = bytearray(data)
    struct.pack_into("<H", d, opt + 70, 0x100)
    yield "dllcharacteristics-0x100", bytes(d)


def main():
    exe = Path(sys.argv[1])
    data = exe.read_bytes()
    with tempfile.TemporaryDirectory() as tmp:
        for name, variant in variants(data):
            path = Path(tmp) / (name + ".exe")
            path.write_bytes(variant)
            try:
                r = subprocess.run([str(path)], capture_output=True, timeout=30, stdin=subprocess.DEVNULL)
                print("%-28s starts, exit=%s stdout=%r" % (name, r.returncode, r.stdout[:40]))
            except OSError as error:
                print("%-28s cannot start: %s" % (name, error))
            except subprocess.TimeoutExpired:
                print("%-28s timeout" % name)


if __name__ == "__main__":
    main()
