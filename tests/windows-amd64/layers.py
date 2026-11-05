#!/usr/bin/env python3
"""Development-only: combine per-layer evidence into one report.json with SHA256s.

Layers are reported separately. A layer that did not run is NOT_RUN, never PASS.
"""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--sha", required=True)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    o = p.parse_args()
    run = {}
    rp = o.evidence / "report.json"
    if rp.exists():
        run = json.loads(rp.read_text(encoding="utf-8"))

    def layer(*keys):
        vals = [run.get(k, "NOT_RUN") for k in keys]
        if any(v == "FAIL" for v in vals):
            return "FAIL"
        return "PASS" if all(v == "PASS" for v in vals) else "NOT_RUN"

    layers = {
        "reference_vm_tests": layer("reference_tests", "reference_console_tests"),
        "reference_vm_generation": layer("generation"),
        "pe_structure_independent": layer("structure", "console_structure", "console_oracle_negative"),
        "windows_native_execution": layer("windows_execution", "console_windows_execution", "console_write_failure"),
        # No approved trusted Native Seed is available: never substituted.
        "mio_native_generation": "NOT_RUN",
        "mio_native_module_tests": "NOT_RUN",
        "source_to_pe_reference_hosted": "NOT_RUN",
        "source_to_pe_windows_execution": "NOT_RUN",
        "source_to_pe_pure_mio_frontend": "NOT_RUN",
        "source_to_pe_reject_cases": "NOT_RUN",
        "selfhost_bootstrap": "NOT_RUN",
    }
    cases_path = o.evidence / "cases" / "cases-report.json"
    if cases_path.exists():
        c = json.loads(cases_path.read_text(encoding="utf-8"))
        layers["source_to_pe_reference_hosted"] = "PASS" if c["generation"] == "PASS" and c["structure"] == "PASS" else ("FAIL" if "FAIL" in (c["generation"], c["structure"]) else "NOT_RUN")
        layers["source_to_pe_windows_execution"] = c["windows_execution"]
        layers["source_to_pe_reject_cases"] = c["reject"]
    files = {}
    for f in sorted(list(o.evidence.glob("*.exe")) + list((o.evidence / "cases").glob("*.exe"))):
        files["pe/" + f.parent.name + "/" + f.name] = sha(f)
    for rel in ("bunko/kiso/aot/pe/pe.mio", "bunko/kiso/aot/x86_64/x86_64.mio",
                "bunko/kiso/aot/winconsole/winconsole.mio", "bunko/kiso/aot/lowerwin/lowerwin.mio", "tests/windows-amd64/build_pe.py", "tests/windows-amd64/cases.py", "tests/pe-writer/builder.mio",
                "tests/pe-writer/run.py", "tests/pe-writer/verify.py"):
        files["src/" + rel] = sha(o.root / rel)
    for f in o.evidence.glob("mio-reference*"):
        files["tool/" + f.name] = sha(f)
    out = dict(commit_sha=o.sha, runner="windows-x64", layers=layers, sha256=files,
               note="Workflow success alone is not evidence of a complete Windows AOT.")
    o.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(layers, indent=2))
    bad = [k for k, v in layers.items() if v == "FAIL"]
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
