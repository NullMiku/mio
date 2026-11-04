#!/usr/bin/env python3
"""Development-only driver; native and reference generation never fall back."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from verify import require, verify

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mio", type=Path, required=True)
    parser.add_argument("--mode", choices=("native", "reference"), required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "build/pe-writer")
    parser.add_argument("--execute", action="store_true", help="require real Windows AMD64 execution")
    options = parser.parse_args()
    mio, output = options.mio.resolve(), options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Only remove our six known output files; stale images must not stand in
    # for a builder that accidentally stops producing one of the fixtures.
    for name in ("exit42.exe", "relocated43.exe", "bss44.exe", "paged45.exe", "leaf.exe", "large-unwind.exe"):
        (output / name).unlink(missing_ok=True)
    report_path = output / "report.json"
    # Replace any old success before starting. An interrupted run is NOT_RUN.
    report = dict(generation="NOT_RUN", structure="NOT_RUN", windows_execution="NOT_RUN",
                  mio_native_tests="NOT_RUN", reference_tests="NOT_RUN", mode=options.mode,
                  compiler_sha256=hashlib.sha256(mio.read_bytes()).hexdigest(),
                  writer_sha256=hashlib.sha256((ROOT / "bunko/kiso/aot/pe/pe.mio").read_bytes()).hexdigest())
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    env = dict(os.environ, MIO_BUNKO=str(ROOT / "bunko"))
    commands = []

    def run(label, command, cwd=ROOT):
        started = time.monotonic()
        process = subprocess.run(list(map(str, command)), cwd=cwd, env=env, capture_output=True, timeout=600)
        (output / (label + ".stdout.log")).write_bytes(process.stdout)
        (output / (label + ".stderr.log")).write_bytes(process.stderr)
        commands.append(dict(command=list(map(str, command)), exit_code=process.returncode,
                             duration_ms=int((time.monotonic() - started) * 1000)))
        require(process.returncode == 0, label + " failed; see " + str(output))
        return process

    stage = "generation"
    try:
        if options.mode == "reference":
            stage = "reference_tests"
            tested = run("reference-tests", [mio, "test", "bunko/kiso/aot/pe", "--format=json", "--lang=en-US"])
            summary = json.loads(tested.stdout)["summary"]
            require(summary["status"] == "passed" and summary["passed"] > 0 and summary["failed"] == 0, "nonempty reference tests")
            report.update(reference_tests="PASS", reference_test_count=summary["passed"])
            stage = "generation"
            run("reference-builder", [mio, "run", ROOT / "tests/pe-writer/builder.mio"], cwd=output)
        else:
            # Native primary tests are run by the existing module test entry;
            # this driver is only the separate independent artifact check.
            builder = output / "builder.native"
            run("native-build", [mio, "build", "tests/pe-writer/builder.mio", "--bunko-root", ROOT / "bunko", "-o", builder])
            run("native-builder", [builder], cwd=output)
        report["generation"] = "PASS"
        stage = "structure"
        report.update(verify(output))
        if options.execute:
            stage = "windows_execution"
            report.update(verify(output, execute=True))
    except Exception as error:
        report[stage] = "FAIL"
        report["error"] = str(error)
        raise
    finally:
        report["commands"] = commands
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
