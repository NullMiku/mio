#!/usr/bin/env python3
"""Full pure-Mio compiler chain on Windows (selfhost/windows-compiler = parser + resolver + typecheck + codegen + lowerwinrt):

  A = windows-compiler PE produced by the reference-VM-hosted lowering (trusted start: reference VM, NOT a Native Seed)
  B = A(windows-compiler sources), C = B(...), D = C(...)  - each run natively. A's Mochi came from the Go frontend while B, C
  and D compile Mochi produced by the Mio frontend itself, so A != B is expected and recorded; the fixed point is B == C == D
  the last generation compiles sample applications, which are run and compared with the Go VM, and a broken application
  whose diagnostic and non-zero exit status are checked.

--execute runs on Windows (required for a Windows PASS); --emulate uses the unicorn model (development aid, not Windows).
Scope: selfhost/windows-compiler, which is NOT selfhost/cli (no argument/environment/spawn support yet)."""
import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_pe

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
COMPILER = ROOT / "selfhost" / "windows-compiler" / "main.mio"
ENTRY = "selfhost/windows-compiler"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_tree():
    files = {}
    for top in ("bunko", "selfhost", "tests/windows-amd64/apps"):
        for p in (ROOT / top).rglob("*.mio"):
            if not p.name.endswith("_test.mio"):
                files[p.relative_to(ROOT).as_posix()] = bytearray(p.read_bytes())
    return files


def compile_with(mode, exe_path, exe_bytes, entry, output_rel, workdir):
    """Run a compiler generation on `entry`; returns (record, produced bytes or b'')."""
    request = (entry + "\n" + output_rel + "\n").encode()
    started = time.monotonic()
    out_path = ROOT / output_rel
    if mode == "windows":
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.unlink(missing_ok=True)
        r = subprocess.run([str(exe_path)], cwd=ROOT, input=request, capture_output=True, timeout=7200)
        code, out, err, violations = r.returncode, r.stdout, r.stderr, []
        produced = out_path.read_bytes() if out_path.exists() else b""
    else:
        import emu
        files = source_tree()
        e = emu.Emu(exe_bytes, files=files, stack_size=64 * 1024 * 1024, max_instructions=2_000_000_000_000, stdin=request)
        code, out, err, violations = e.run()
        produced = bytes(files.get(output_rel, b""))
    return dict(entry=entry, runner=mode, exit_code=code, stdout=out.decode("utf-8", "replace"), stderr=err.decode("utf-8", "replace"),
                violations=violations, seconds=round(time.monotonic() - started, 1), executable_sha256=sha(exe_bytes),
                output_sha256=sha(produced) if produced else None, output_size=len(produced)), produced


def run_program(mode, data, path):
    if mode == "windows":
        r = subprocess.run([str(path)], capture_output=True, timeout=120)
        return r.returncode, r.stdout, r.stderr, []
    import emu
    return emu.Emu(data).run()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--refvm", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True, help="directory (inside the repository checkout for --execute)")
    m = p.add_mutually_exclusive_group(required=True)
    m.add_argument("--execute", action="store_true")
    m.add_argument("--emulate", action="store_true")
    o = p.parse_args()
    mode = "windows" if o.execute else "emulator"
    if o.execute and platform.system() != "Windows":
        print("--execute requires Windows", file=sys.stderr)
        sys.exit(2)
    out = o.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    try:
        rel = out.relative_to(ROOT).as_posix()
    except ValueError:
        rel = "build/compiler-chain"
        out = ROOT / rel
        out.mkdir(parents=True, exist_ok=True)
    report = dict(mode=mode, scope="selfhost/windows-compiler (parser+resolver+typecheck+codegen+lowerwinrt), not selfhost/cli",
                  start="reference-VM-hosted pure-Mio lowering; no trusted Native Seed (seed bootstrap is NOT_RUN)",
                  compiler_source_sha256=sha(COMPILER.read_bytes()), generations=[], checks={}, failures=[])
    report_path = out / "compiler-chain-report.json"
    try:
        exe_a = out / "A.exe"
        ok, message = build_pe.build(o.refvm, COMPILER, exe_a, "lowerwinrt")
        if not ok:
            raise RuntimeError("A: " + message[:300])
        executables = {"A": (exe_a.read_bytes(), exe_a)}
        report["generations"].append(dict(label="A", producer="reference VM + pure-Mio lowerwinrt", output_sha256=sha(executables["A"][0]), output_size=len(executables["A"][0])))
        for label in ("B", "C", "D"):
            previous = list(executables)[-1]
            data, path = executables[previous]
            output_rel = "%s/%s.exe" % (rel, label)
            record, produced = compile_with(mode, path, data, ENTRY, output_rel, out)
            record.update(label=label, producer=previous)
            report["generations"].append(record)
            if not (record["exit_code"] == 0 and record["stdout"] == "windows-compiler: ok\n" and record["stderr"] == "" and not record["violations"] and produced):
                report["failures"].append("%s: generation failed (exit %s, stderr %r)" % (label, record["exit_code"], record["stderr"][:300]))
                break
            (out / (label + ".exe")).write_bytes(produced)
            executables[label] = (produced, out / (label + ".exe"))
        hashes = {k: sha(v[0]) for k, v in executables.items()}
        report["checks"]["generation_hashes"] = hashes
        report["checks"]["A_equals_B"] = hashes.get("A") == hashes.get("B")  # informational: different frontends produced their Mochi
        report["checks"]["B_C_D_identical"] = len(hashes) == 4 and len({hashes["B"], hashes["C"], hashes["D"]}) == 1
        if not report["checks"]["B_C_D_identical"]:
            report["failures"].append("fixed point not reached, generations: %s" % hashes)
        data, path = executables[list(executables)[-1]]
        apps = []
        for app, expected_args in (("hello", None), ("structs", None)):
            entry = "tests/windows-amd64/apps/" + app
            output_rel = "%s/app-%s.exe" % (rel, app)
            record, produced = compile_with(mode, path, data, entry, output_rel, out)
            result = dict(app=app, compile_exit=record["exit_code"], compile_stderr=record["stderr"][:300])
            expected = subprocess.run(build_pe.frontend_command(o.refvm, "run", ROOT / entry / "main.mio"), cwd=ROOT, capture_output=True, timeout=600)
            if produced:
                exe = out / ("app-" + app + ".exe")
                exe.write_bytes(produced)
                code, so, se, viol = run_program(mode, produced, exe)
                result.update(exit_code=code, stdout_matches_vm=so == expected.stdout, stderr=se.decode("utf-8", "replace"), violations=viol, pe_sha256=sha(produced))
                if not (code == 0 and so == expected.stdout and not se and not viol):
                    report["failures"].append("app %s: output differs from the Go VM" % app)
            else:
                report["failures"].append("app %s: no executable produced (%s)" % (app, record["stderr"][:200]))
            apps.append(result)
        report["checks"]["applications"] = apps
        record, produced = compile_with(mode, path, data, "tests/windows-amd64/apps/broken", "%s/app-broken.exe" % rel, out)
        diag = dict(exit_code=record["exit_code"], stderr=record["stderr"][:400], produced_image=bool(produced))
        report["checks"]["diagnostics"] = diag
        if not (record["exit_code"] != 0 and "windows-compiler" in record["stderr"] and not produced):
            report["failures"].append("broken source: expected a diagnostic, a non-zero exit and no image, got %r" % diag)
    except Exception as error:
        report["failures"].append("%s: %s" % (type(error).__name__, error))
    report["result"] = "PASS" if not report["failures"] and report["checks"].get("B_C_D_identical") else "FAIL"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("mode", "scope", "result", "failures")}, indent=2))
    print(json.dumps(report["checks"].get("generation_hashes", {}), indent=2))
    sys.exit(0 if report["result"] == "PASS" else 1)


if __name__ == "__main__":
    main()
