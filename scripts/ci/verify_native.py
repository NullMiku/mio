#!/usr/bin/env python3
"""Independent native behavior and real GC telemetry, outside Mio assertions."""
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main(mode):
    mio = Path(os.environ["MIO_CI_MIO"])
    work = Path(os.environ["MIO_CI_MODULE_DIR"])

    def run(argv, expected=None, code=0, stderr=None):
        result = subprocess.run(list(map(str, argv)), cwd=ROOT, capture_output=True, timeout=600)
        with (work / "native-commands.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(dict(command=list(map(str, argv)), exit_code=result.returncode,
                                         stdout_hex=result.stdout.hex(), stderr_hex=result.stderr.hex())) + "\n")
        if result.returncode != code or (expected is not None and result.stdout != expected) or (stderr is not None and result.stderr != stderr):
            raise RuntimeError(f"native command failed: {argv}; exit={result.returncode}, stdout={result.stdout!r}, stderr={result.stderr!r}")
        return result

    if mode == "core":
        source = work / "oracle.mio"
        source.write_text('''waza sum(a: int64, b: int64, c: int64, d: int64, e: int64, f: int64, g: int64, h: int64, i: int64) -> int64 {
    kaesu a+b+c+d+e+f+g+h+i;
}
chant(sum(1,2,3,4,5,6,7,8,9));
kaku values = [7,8,9]; chant(values[1]); chant("Mio");
''')
        binary = work / "oracle.native"
        run([mio, "build", source, "--bunko-root", ROOT / "bunko", "-o", binary])
        magic, cpu, _, kind = struct.unpack_from("<4I", binary.read_bytes())
        if (magic, cpu, kind) != (0xFEEDFACF, 0x100000C, 2):
            raise RuntimeError("expected native ARM64 Mach-O executable")
        run(["codesign", "--verify", "--strict", binary])
        # No external test dependency is available to the generated program.
        env = dict(os.environ, PATH="", MIO_BUNKO="")
        result = subprocess.run([str(binary)], env=env, capture_output=True, timeout=30)
        if (result.returncode, result.stdout, result.stderr) != (0, b"45\n8\nMio\n", b""):
            raise RuntimeError("independent ABI/output mismatch: " + repr(result))
        package = work / "negative"
        package.mkdir()
        (package / "bad_test.mio").write_text('yobu "kiso/testing";\nwaza test_bad() -> unit { testing.expect(iie, "intentional failure"); }\n')
        negative = subprocess.run([str(mio), "test", str(package), "--bunko-root", str(ROOT / "bunko"), "--format=json"], capture_output=True, timeout=120)
        (work / "false-assertion.json").write_bytes(negative.stdout)
        (work / "false-assertion.stderr.log").write_bytes(negative.stderr)
        if negative.returncode == 0 or json.loads(negative.stdout)["summary"]["failed"] != 1:
            raise RuntimeError("Mio native framework falsely accepted a wrong assertion")
    elif mode == "gc":
        builder = work / "automatic-builder"
        binary = work / "containers.native"
        run([mio, "build", "tests/m19ef/automatic-roots/builder.mio", "--bunko-root", ROOT / "bunko", "-o", builder])
        run(["codesign", "--verify", "--strict", builder])
        # Existing pure Mio builder requests a 1 MiB heap and GC telemetry.
        run([builder, ROOT, "tests/m19ef/automatic-roots/containers/main.mio", ROOT / "bunko", binary])
        run(["codesign", "--verify", "--strict", binary])
        result = run([binary], b"4797\n")
        if len(result.stderr) != 64:
            raise RuntimeError("missing real GC telemetry")
        polls, publications, depth, registrations, exits, acquired, released, minor = struct.unpack("<8Q", result.stderr)
        if not (polls > 0 and publications > polls and depth > 0 and (registrations, exits, acquired, released) == (1, 1, 3, 3) and minor > 0):
            raise RuntimeError("GC/root lifecycle witness mismatch")
        (work / "gc-witness.json").write_text(json.dumps(dict(minor_collections=minor, polls=polls, publications=publications, max_shadow_frames=depth)) + "\n")
    else:
        raise ValueError("unknown native oracle")
    print(mode + " independent native oracle PASS")


if __name__ == "__main__":
    main(sys.argv[1])
