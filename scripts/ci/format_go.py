#!/usr/bin/env python3
"""Check Go formatting without changing sources or treating CRLF as a defect."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    names = subprocess.check_output(["git", "ls-files", "-z", "--", "*.go"], cwd=ROOT).decode().split("\0")
    names = [name for name in names if name and (ROOT / name).is_file()]
    if not names:
        raise RuntimeError("no tracked Go sources to check")
    failed = False
    with tempfile.TemporaryDirectory(prefix="mio-gofmt-") as directory:
        temporary = Path(directory)
        for name in names:
            copy = temporary / name
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_bytes((ROOT / name).read_bytes().replace(b"\r\n", b"\n"))
        for offset in range(0, len(names), 100):
            result = subprocess.run(["gofmt", "-l", *[str(temporary / name) for name in names[offset:offset + 100]]],
                                    capture_output=True, check=True)
            for line in result.stdout.decode().splitlines():
                print(Path(line).relative_to(temporary).as_posix())
                failed = True
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
