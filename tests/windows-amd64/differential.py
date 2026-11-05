#!/usr/bin/env python3
"""Differential test: each program's expected stdout/exit status comes from the Go reference VM (independent oracle);
the actual result comes from the PE built by the pure-Mio lowering, run either on Windows (--execute) or, as a local
development aid only, in the unicorn emulator (--emulate; NOT Windows). programs.json is the corpus of
internal/aot/linux_purelower_test.go (pureLowerPrograms)."""
import argparse
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_pe
import verify_pe

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def vm_expected(mio, source):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "p.mio"
        path.write_text(source, encoding="utf-8")
        r = subprocess.run(build_pe.frontend_command(mio, "run", path), cwd=ROOT, capture_output=True, timeout=1800)
        return r.returncode, r.stdout


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mio", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--backend", default="lowerwinrt")
    p.add_argument("--only", default="")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--execute", action="store_true", help="run on Windows (required for a Windows PASS)")
    mode.add_argument("--emulate", action="store_true", help="unicorn emulator: development aid, not Windows")
    mode.add_argument("--build-only", action="store_true")
    o = p.parse_args()
    if o.execute and platform.system() != "Windows":
        print("--execute requires Windows", file=sys.stderr)
        sys.exit(2)
    out = o.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    programs = json.loads((HERE / "programs.json").read_text(encoding="utf-8"))
    skipped = {}
    if o.emulate:
        # Programs that need billions of instructions are NOT_RUN in the emulator; scaled variants run instead.
        for heavy in ("gc_garbage", "gc_keeps_live_data"):
            programs.pop(heavy)
            skipped[heavy] = "NOT_RUN in emulator (too many instructions); scaled variant runs instead"
        programs.update(json.loads((HERE / "programs_scaled.json").read_text(encoding="utf-8")))
    else:
        programs.update(json.loads((HERE / "programs_scaled.json").read_text(encoding="utf-8")))
    results, failures = [], []
    for name in sorted(programs):
        if o.only and name not in o.only.split(","):
            continue
        source = programs[name]
        entry = dict(name=name, source_sha256=hashlib.sha256(source.encode()).hexdigest())
        code, expected = vm_expected(o.mio, source)
        entry.update(vm_exit=code, vm_stdout_sha256=hashlib.sha256(expected).hexdigest())
        src = out / (name + ".mio")
        src.write_text(source, encoding="utf-8")
        exe = out / (name + ".exe")
        ok, message = build_pe.build(o.mio, src, exe, o.backend)
        if not ok:
            entry.update(status="FAIL", error=message[:500])
            failures.append("%s: build: %s" % (name, message[:300]))
            results.append(entry)
            continue
        entry["pe_sha256"] = hashlib.sha256(exe.read_bytes()).hexdigest()
        try:
            entry["structure"] = verify_pe.verify(exe.read_bytes(), expect_relocations=False)
        except Exception as error:
            entry.update(status="FAIL", error="structure: %s" % error)
            failures.append("%s: structure: %s" % (name, error))
            results.append(entry)
            continue
        entry["status"] = "BUILT"
        if o.execute or o.emulate:
            if o.execute:
                try:
                    r = subprocess.run([str(exe)], capture_output=True, timeout=120)
                except OSError as error:
                    entry.update(status="FAIL", error="cannot start: %s" % error)
                    failures.append("%s: cannot start the image: %s" % (name, error))
                    results.append(entry)
                    continue
                got = (r.returncode, r.stdout, r.stderr, [])
            else:
                import emu
                got = emu.Emu(exe.read_bytes()).run()
                got = (got[0], got[1], got[2], got[3])
            want_exit = 0 if code == 0 else 1
            entry.update(exit_code=got[0], stdout_sha256=hashlib.sha256(got[1]).hexdigest(), violations=got[3])
            if got[0] == want_exit and got[1] == expected and not got[3]:
                entry["status"] = "PASS" if o.execute else "EMU_PASS"
            else:
                entry["status"] = "FAIL"
                failures.append("%s: exit %s (want %s) stdout_match=%s stderr=%r violations=%s" % (
                    name, got[0], want_exit, got[1] == expected, got[2][:200], got[3][:3]))
        results.append(entry)
    report = dict(backend=o.backend, mode="windows" if o.execute else ("emulator" if o.emulate else "build-only"),
                  programs=results, failures=failures, not_run=skipped)
    (out / "differential-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(json.dumps(dict(mode=report["mode"], counts=counts, failures=failures), indent=2))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
