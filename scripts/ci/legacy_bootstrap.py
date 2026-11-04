#!/usr/bin/env python3
"""Run the historical BCD fixture gate in a private source snapshot.

The historical compiler writes bootstrap.config and fixed output paths. Never
let a timeout or interruption change the developer's checkout.
"""
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    destination = Path(os.environ["MIO_CI_MODULE_DIR"]) / "bcd-source"
    destination.mkdir()  # Refuse reuse of historical evidence.
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    names.append("scripts/check-native-bootstrap.sh")
    for name in set(names) - {""}:
        source = ROOT / name
        if not source.is_file():
            continue  # Tracked deletions are absent in the current source tree.
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return subprocess.call(["bash", str(destination / "scripts/check-native-bootstrap.sh")], cwd=destination)


if __name__ == "__main__":
    raise SystemExit(main())
