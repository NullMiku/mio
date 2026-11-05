#!/usr/bin/env python3
"""Independent CLI oracles: never call Mio's test assertion implementation."""
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import sys


def require_output(result, expected, expected_code=0):
    if result.returncode != expected_code or result.stdout != expected or result.stderr:
        raise RuntimeError(f"exit={result.returncode}, stdout={result.stdout!r}, stderr={result.stderr!r}; expected={expected!r}")


def main(mode):
    tools = Path(os.environ["MIO_CI_TOOLS"])
    work = Path(os.environ["MIO_CI_MODULE_DIR"])
    suffix = ".exe" if os.name == "nt" else ""
    mio = tools / ("mio" + suffix)

    def run(argv):
        result = subprocess.run(list(map(str, argv)), capture_output=True, timeout=120)
        with (work / "independent-commands.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(dict(command=list(map(str, argv)), exit_code=result.returncode,
                                         stdout=result.stdout.decode(errors="replace"), stderr=result.stderr.decode(errors="replace"))) + "\n")
        return result

    # Nine parameters exercise both register and stack argument slots in the native ABI.
    source = work / "oracle.mio"
    source.write_text('''waza sum(a: int64, b: int64, c: int64, d: int64, e: int64, f: int64, g: int64, h: int64, i: int64) -> int64 {
    kaesu a + b + c + d + e + f + g + h + i;
}
kaku n = 0;
kaku total = 0;
aida (n < 5) { total = total + n; n = n + 1; }
chant(total);
chant(sum(1, 2, 3, 4, 5, 6, 7, 8, 9));
kaku values = [7, 8, 9];
chant(values[1]);
chant("Mio");
''', encoding="utf-8")
    expected = b"10\n45\n8\nMio\n"
    if mode == "vm":
        mochi = work / "oracle.mochi"
        built = run([mio, "build", "-o", mochi, source])
        if built.returncode or built.stderr or not mochi.is_file() or mochi.stat().st_size == 0:
            raise RuntimeError("Mochi build failed: " + repr(built))
        require_output(run([mio, "run", source]), expected)
        require_output(run([mio, "exec", mochi]), expected)
        invalid = work / "invalid.mio"
        invalid.write_text('kaku age = 18; age = "Mio";\n')
        negative = run([mio, "check", invalid])
        if negative.returncode == 0 or not negative.stderr:
            raise RuntimeError("invalid type assignment accepted without diagnostics")
        # A real wrong assertion must fail; the independent output oracle above
        # remains effective even if the assertion framework lies about this case.
        package = work / "negative-assertion"
        package.mkdir()
        (package / "bad_test.mio").write_text('yobu "kiso/testing";\nwaza test_bad() -> unit { testing.expect(iie, "intentional failure"); }\n')
        negative = run([mio, "test", package, "--format=json"])
        report = json.loads(negative.stdout)
        if negative.returncode == 0 or report["summary"]["failed"] != 1:
            raise RuntimeError("false assertion was not rejected")
    elif mode == "native":
        if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
            raise RuntimeError("native oracle requires macOS ARM64")
        # The current-source native CLI (built from the verified seed by the runner) compiles the oracle; the image is
        # written and ad-hoc signed by Mio itself. No Go program generates code here.
        binary = work / "oracle.native"
        result = run([os.environ["MIO_CI_MIO"], "build", source, "--target=darwin-arm64", "-o", binary])
        if result.returncode or result.stderr:
            raise RuntimeError("native compilation failed: " + repr(result))
        header = struct.unpack_from("<4I", binary.read_bytes())
        if header[0] != 0xFEEDFACF or header[1] != 0x100000C or header[3] != 2:
            raise RuntimeError("expected ARM64 Mach-O executable")
        result = run(["codesign", "--verify", "--strict", binary])
        if result.returncode:
            raise RuntimeError("Mio ad-hoc signature does not verify")
        require_output(run([binary]), expected)
    else:
        raise ValueError("unknown verification mode")
    print(mode + " independent oracle PASS")


if __name__ == "__main__":
    main(sys.argv[1])
