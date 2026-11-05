#!/usr/bin/env python3
"""Development driver: .mio -> (Go reference frontend) .mochi -> (pure-Mio kiso/aot/lowerwin in the reference VM) PE32+.

The lowering and PE writer are pure Mio; the Go reference VM only hosts them and the Go frontend produces Mochi.
The pure-Mio frontend path (selfhost/pipeline build_windows_source) is NOT_RUN without a trusted native seed."""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# The Go frontend cannot compile kiso/os (native-only runtime). Test programs therefore declare
# `waza windows_test_exit(code: int64) -> unit`; this DEVELOPMENT shim turns exactly that function into the
# body-less native os.exit function the pure-Mio frontend produces. Real kiso/os.exit is NOT_RUN here.
DRIVER = '''yobu "kiso/aot/BACKEND";
yobu "kiso/array";
yobu "kiso/encoding/mochi";
yobu "kiso/fs";
yobu "kiso/string";
waza shimmed(file: mochi.File) -> mochi.File {
    kaku name = "$mma::mio/os/runtime::exit::shim";
    kaku functions: []mochi.Function = []; kaku at = 0;
    aida (at < len(file.functions)) {
        kaku fn = file.functions[at];
        moshi (fn.name == "windows_test_exit") {
            fn = mochi.Function { id: fn.id, name: name, name_bytes: string.to_bytes(name), parameter_count: fn.parameter_count,
                local_count: fn.local_count, returns_value: fn.returns_value, captures: fn.captures, instructions: [] };
        }
        array.push(functions, fn); at = at + 1;
    }
    kaesu mochi.File { version: file.version, constants: file.constants, global_count: file.global_count,
        instructions: file.instructions, functions: functions };
}
waza build(file: mochi.File) -> unit {
    kaku lowered = BACKEND.compile(shimmed(file));
    moshi (lowered.error != "") { chant(lowered.error); kaesu; }
    kaku written = fs.write_all(%s, lowered.bytes);
    moshi (written.error != mu) { chant("write failed"); kaesu; }
    chant("ok");
}
kaku decoded = mochi.decode_file(%s);
kaku file = decoded.value;
moshi (decoded.error != mu) { chant("decode failed"); }
sore { moshi (file == mu) { chant("decode failed"); } sore { build(file); } }
'''


def frontend_command(host, command, source, output=None):
    """`host` is either the reference `mio` binary or tests/windows-amd64/refvm (large instruction budget)."""
    host = Path(host)
    if host.name.startswith("refvm"):
        return [str(host), str(ROOT / "bunko"), command, str(source)] + ([str(output)] if output else [])
    if command == "mochi":
        return [str(host), "build", "-o", str(output), str(source)]
    return [str(host), "run", str(source)]


def build(mio, source, output, backend="lowerwin", gc_threshold=None):
    """Returns (ok, message). A lowering error is reported verbatim, never turned into an image."""
    output = Path(output).resolve()
    output.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        mochi = tmp / "in.mochi"
        compiled = subprocess.run(frontend_command(mio, "mochi", Path(source).resolve(), mochi),
                                  cwd=ROOT, capture_output=True, text=True, timeout=300)
        if compiled.returncode != 0:
            return False, "frontend: " + compiled.stderr.strip()
        driver = tmp / "driver.mio"
        text = DRIVER.replace("BACKEND", backend)
        if gc_threshold:
            text = text.replace("%s.compile(shimmed(file))" % backend, "%s.compile_with_gc_threshold(shimmed(file), %d)" % (backend, gc_threshold))
        driver.write_text(text % ('"%s"' % output.as_posix(), '"%s"' % mochi.as_posix()), encoding="utf-8")
        ran = subprocess.run(frontend_command(mio, "run", driver), cwd=ROOT, capture_output=True, text=True, timeout=1800)
        out = ran.stdout.strip()
        if ran.returncode != 0:
            return False, "driver: " + (ran.stderr.strip() or out)
        if out != "ok":
            return False, out
        if not output.exists():
            return False, "driver reported ok but no image was written"
    return True, "ok"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mio", type=Path, required=True)
    p.add_argument("source", type=Path)
    p.add_argument("-o", "--output", type=Path, required=True)
    p.add_argument("--backend", default="lowerwin", choices=("lowerwin", "lowerwinrt"))
    o = p.parse_args()
    ok, message = build(o.mio, o.source, o.output, o.backend)
    print(message, file=sys.stdout if ok else sys.stderr)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
