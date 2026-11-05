#!/usr/bin/env python3
"""Backend-driver self-reconstruction chain (NOT the full selfhost/cli):

  A = driver PE produced by the pure-Mio lowering hosted in the Go reference VM (trusted start: reference VM, not a
      native seed - so this is NOT a Native Seed bootstrap)
  B = A(driver.mochi), C = B(driver.mochi), D = C(driver.mochi)   (each run natively, in a fresh directory)
  checks: A == B == C == D byte for byte, then C compiles sample programs whose PE must equal the VM-hosted PE and run.

--execute runs every generation on Windows. --emulate uses the unicorn model (development aid, not Windows)."""
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
DRIVER = ROOT / "selfhost" / "native-aot-windows" / "main.mio"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run_generation(mode, exe_bytes, exe_path, mochi, workdir, label):
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "input.config").write_bytes(b"in.mochi")
    (workdir / "output.config").write_bytes(b"out.exe")
    (workdir / "in.mochi").write_bytes(mochi)
    (workdir / "out.exe").unlink(missing_ok=True)
    started = time.monotonic()
    if mode == "windows":
        r = subprocess.run([str(exe_path)], cwd=workdir, capture_output=True, timeout=3600)
        code, out, err, violations = r.returncode, r.stdout, r.stderr, []
    else:
        import emu
        files = {"input.config": bytearray(b"in.mochi"), "output.config": bytearray(b"out.exe"), "in.mochi": bytearray(mochi)}
        e = emu.Emu(exe_bytes, files=files, stack_size=64 * 1024 * 1024, max_instructions=200_000_000_000)
        code, out, err, violations = e.run()
        if "out.exe" in files:
            (workdir / "out.exe").write_bytes(bytes(files["out.exe"]))
    produced = (workdir / "out.exe").read_bytes() if (workdir / "out.exe").exists() else b""
    return dict(label=label, runner=mode, exit_code=code, stdout=out.decode("utf-8", "replace"), stderr=err.decode("utf-8", "replace"),
                violations=violations, seconds=round(time.monotonic() - started, 1), input_sha256=sha(mochi),
                input_executable_sha256=sha(exe_bytes), output_sha256=sha(produced) if produced else None, output_size=len(produced)), produced


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--refvm", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
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
    report = dict(mode=mode, scope="backend driver (selfhost/native-aot-windows), not selfhost/cli", generations=[], checks={}, failures=[],
                  start="reference-VM-hosted pure-Mio lowering (no trusted Native Seed): A is not a seed-bootstrapped binary",
                  driver_source_sha256=sha(DRIVER.read_bytes()))
    path = out / "chain-report.json"
    try:
        mochi_path = out / "driver.mochi"
        r = subprocess.run(build_pe.frontend_command(o.refvm, "mochi", DRIVER, mochi_path), cwd=ROOT, capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            raise RuntimeError("driver frontend: " + r.stderr[:300])
        mochi = mochi_path.read_bytes()
        report["driver_mochi_sha256"] = sha(mochi)
        exe_a = out / "A.exe"
        ok, message = build_pe.build(o.refvm, DRIVER, exe_a, "lowerwinrt")
        if not ok:
            raise RuntimeError("A: " + message[:300])
        current = exe_a.read_bytes()
        report["generations"].append(dict(label="A", producer="reference VM + pure-Mio lowerwinrt", output_sha256=sha(current), output_size=len(current)))
        executables = {"A": (current, exe_a)}
        for label in ("B", "C", "D"):
            previous = list(executables)[-1]
            data, exe_path = executables[previous]
            record, produced = run_generation(mode, data, exe_path, mochi, out / ("gen-" + label), label)
            record["producer"] = previous
            report["generations"].append(record)
            good = record["exit_code"] == 0 and record["stdout"] == "native-aot-windows: ok\n" and record["stderr"] == "" and not record["violations"] and produced
            if not good:
                report["failures"].append("%s: generation failed (exit %s, stderr %r)" % (label, record["exit_code"], record["stderr"][:200]))
                break
            exe_label = out / (label + ".exe")
            exe_label.write_bytes(produced)
            executables[label] = (produced, exe_label)
        shas = {k: sha(v[0]) for k, v in executables.items()}
        report["checks"]["fixed_point_hashes"] = shas
        report["checks"]["A_B_C_D_identical"] = len(shas) == 4 and len(set(shas.values())) == 1
        if not report["checks"]["A_B_C_D_identical"]:
            report["failures"].append("generations differ: %s" % shas)
        # the last generation compiles sample programs; the result must equal the reference-VM-hosted PE and run correctly
        last = list(executables)[-1]
        data, exe_path = executables[last]
        samples = []
        for name, source in (("arrays", 'kaku a = [1, 2, 3]; chant(a[1]); chant(len(a));\n'),
                             ("recursion", 'waza fib(n: int64) -> int64 { moshi (n < 2) { kaesu n; } kaesu fib(n - 1) + fib(n - 2); }\nchant(fib(15));\n'),
                             ("strings", 'kaku s = "Mio"; chant(s); chant(s == "Mio");\n')):
            src = out / ("sample-" + name + ".mio")
            src.write_text(source, encoding="utf-8")
            ref = out / ("sample-" + name + ".ref.exe")
            ok, message = build_pe.build(o.refvm, src, ref, "lowerwinrt")
            sm = out / ("sample-" + name + ".mochi")
            subprocess.run(build_pe.frontend_command(o.refvm, "mochi", src, sm), cwd=ROOT, check=True, capture_output=True)
            record, produced = run_generation(mode, data, exe_path, sm.read_bytes(), out / ("sample-" + name), "sample:" + name)
            entry = dict(name=name, vm_hosted_sha256=sha(ref.read_bytes()) if ok else None, native_sha256=record["output_sha256"],
                         identical=bool(ok and produced == ref.read_bytes()), compile_exit=record["exit_code"])
            if mode == "windows" and produced:
                (out / ("sample-" + name + ".exe")).write_bytes(produced)
                run = subprocess.run([str(out / ("sample-" + name + ".exe"))], capture_output=True, timeout=120)
                entry["run"] = dict(exit_code=run.returncode, stdout=run.stdout.decode(), stderr=run.stderr.decode())
            samples.append(entry)
            if not entry["identical"]:
                report["failures"].append("sample %s: native-compiled PE differs from the VM-hosted PE" % name)
        report["checks"]["samples"] = samples
    except Exception as error:
        report["failures"].append("%s: %s" % (type(error).__name__, error))
    report["result"] = "PASS" if not report["failures"] and report["checks"].get("A_B_C_D_identical") else "FAIL"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("mode", "scope", "result", "failures")}, indent=2))
    print(json.dumps(report["checks"].get("fixed_point_hashes", {}), indent=2))
    sys.exit(0 if report["result"] == "PASS" else 1)


if __name__ == "__main__":
    main()
