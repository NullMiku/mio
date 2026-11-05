#!/usr/bin/env python3
"""Build every case with the pure-Mio lowering (reference-VM hosted), verify the PE structure independently and,
on Windows, execute each image comparing exit code, stdout and stderr exactly."""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_pe
import cases
import verify_pe


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mio", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--execute", action="store_true", help="require real Windows execution")
    p.add_argument("--backend", default="lowerwin", choices=("lowerwin", "lowerwinrt"))
    o = p.parse_args()
    out = o.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    report = dict(generation="NOT_RUN", structure="NOT_RUN", windows_execution="NOT_RUN", reject="NOT_RUN", cases=[], rejects=[])
    path = out / "cases-report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    failures = []
    can_run = platform.system() == "Windows"
    if o.execute and not can_run:
        print("--execute requires Windows", file=sys.stderr)
        sys.exit(2)
    gen_ok = struct_ok = True
    exec_ok = True if o.execute else None
    for name, source, code, stdout, stderr in cases.RUN + (cases.RUN_HEAP if o.backend == "lowerwinrt" else []):
        src = out / (name + ".mio")
        src.write_text(source, encoding="utf-8")
        exe = out / (name + ".exe")
        entry = dict(name=name, source_sha256=hashlib.sha256(source.encode()).hexdigest())
        ok, message = build_pe.build(o.mio, src, exe, o.backend)
        if not ok:
            gen_ok = False
            entry.update(status="FAIL", error=message)
            failures.append(name + ": generation: " + message)
            report["cases"].append(entry)
            continue
        entry["pe_sha256"] = hashlib.sha256(exe.read_bytes()).hexdigest()
        try:
            entry["structure"] = verify_pe.verify(exe.read_bytes(), expect_relocations=o.backend == "lowerwin")
        except Exception as error:
            struct_ok = False
            entry.update(status="FAIL", error="structure: %s" % error)
            failures.append(name + ": structure: %s" % error)
            report["cases"].append(entry)
            continue
        entry["status"] = "GENERATED"
        if o.execute:
            r = subprocess.run([str(exe)], capture_output=True, timeout=60, cwd=out)
            entry.update(exit_code=r.returncode, stdout_hex=r.stdout.hex(), stderr_hex=r.stderr.hex())
            if (r.returncode, r.stdout, r.stderr) == (code, stdout, stderr):
                entry["status"] = "PASS"
            else:
                exec_ok = False
                entry["status"] = "FAIL"
                failures.append("%s: expected %r got %r" % (name, (code, stdout, stderr), (r.returncode, r.stdout, r.stderr)))
        report["cases"].append(entry)
    rej_ok = True
    # The reject list describes the scalar backend; lowerwinrt supports those constructs, so it is not applicable.
    for name, source, needle in (cases.REJECT if o.backend == "lowerwin" else []):
        src = out / ("reject-" + name + ".mio")
        src.write_text(source, encoding="utf-8")
        exe = out / ("reject-" + name + ".exe")
        ok, message = build_pe.build(o.mio, src, exe, o.backend)
        good = (not ok) and needle in message and not exe.exists()
        report["rejects"].append(dict(name=name, rejected=good, message=message[:300]))
        if not good:
            rej_ok = False
            failures.append("reject %s: ok=%s message=%s" % (name, ok, message[:200]))
    report["generation"] = "PASS" if gen_ok else "FAIL"
    report["structure"] = "PASS" if gen_ok and struct_ok else ("FAIL" if not struct_ok else "NOT_RUN")
    report["reject"] = ("PASS" if rej_ok else "FAIL") if o.backend == "lowerwin" else "NOT_RUN"
    report["backend"] = o.backend
    report["windows_execution"] = ("PASS" if exec_ok else "FAIL") if o.execute else "NOT_RUN"
    report["failures"] = failures
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("cases", "rejects")}, indent=2))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
