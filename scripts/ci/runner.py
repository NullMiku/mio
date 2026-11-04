#!/usr/bin/env python3
"""Local CI dispatcher and check protocol, using only Python's standard library."""
import json
import hashlib
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
TARGETS = {"linux-amd64": ("Linux", "x86_64"), "macos-arm64": ("Darwin", "arm64")}
SEED_SHA256 = "4c3f7dcbea536d756c3c4a93c18a999412625184bd5c90123f1c16a0cd9e36da"


def execute(argv, timeout, env=None):
    """Capture both streams and kill the entire process group on POSIX timeout."""
    started = time.monotonic()
    try:
        proc = subprocess.Popen(list(map(str, argv)), cwd=ROOT, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                start_new_session=os.name != "nt")
    except OSError as error:
        return 2, b"", str(error).encode(), "NOT_RUN", str(error), 0
    reason = ""
    try:
        out, err = proc.communicate(timeout=timeout)
        code = proc.returncode
        status = "PASS" if code == 0 else "FAIL"
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
        out, err = proc.communicate()
        code, status, reason = 1, "FAIL", "timeout"
    return code, out, err, status, reason, round((time.monotonic() - started) * 1000)


def assess(kind, code, out, status, reason):
    details = []
    if status != "PASS":
        return status, reason, details
    try:
        if kind == "go":
            events = [json.loads(line) for line in out.splitlines() if line.strip()]
            details = [{"name": e["Package"] + "/" + e["Test"],
                        "status": {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}[e["Action"]],
                        "reason": "Go test skip; see log" if e["Action"] == "skip" else ""}
                       for e in events if e.get("Test") and e.get("Action") in ("pass", "fail", "skip")]
            if any(e.get("Action") == "fail" for e in events):
                return "FAIL", "Go reported a failed test", details
            if not any(d["status"] == "PASS" for d in details):
                return "NOT_RUN", "no Go test executed and passed", details
        elif kind == "mio":
            report = json.loads(out)
            tests = [t for p in report["packages"] for t in p["tests"]]
            if report["summary"]["failed"] or any(t["status"] != "passed" for t in tests):
                return "FAIL", "Mio reported failure", details
            if not tests or report["summary"]["passed"] != len(tests):
                return "NOT_RUN", "no tests or inconsistent Mio count", details
        elif kind != "command":
            return "NOT_RUN", "unknown check kind", details
    except (ValueError, KeyError, TypeError) as error:
        return "NOT_RUN", "invalid test report: " + str(error), details
    return "PASS", reason, details


def check(args):
    if len(args) < 3 or not os.environ.get("MIO_CI_CHECKS"):
        print("check requires an active module, kind, name and command", file=sys.stderr)
        return 2
    kind, name, *argv = args
    directory = Path(os.environ["MIO_CI_MODULE_DIR"])
    stem = uuid.uuid4().hex[:10]
    code, out, err, status, reason, duration = execute(argv, float(os.environ.get("MIO_CI_CHECK_TIMEOUT", "2400")))
    status, reason, details = assess(kind, code, out, status, reason)
    stdout, stderr = directory / (stem + ".stdout.log"), directory / (stem + ".stderr.log")
    stdout.write_bytes(out)
    stderr.write_bytes(err)
    record = dict(name=name, layer={"mio": "native", "go": "supplementary"}.get(kind, "independent"), status=status, reason=reason, duration_ms=duration,
                  exit_code=code, command=argv, tests=details,
                  artifacts=[str(stdout), str(stderr)])
    with open(os.environ["MIO_CI_CHECKS"], "a", encoding="utf-8") as stream:
        stream.write(json.dumps(record) + "\n")
    print(f"{status}: {name} ({duration} ms)", flush=True)
    if status != "PASS":
        print((out + err).decode(errors="replace")[-12000:], file=sys.stderr)
    return 0 if status == "PASS" else (2 if status == "NOT_RUN" else 1)


def discover():
    modules = {}
    for base in (ROOT / "internal", ROOT / "bunko", ROOT / "selfhost", ROOT / "tools", ROOT / "scripts/ci"):
        for manifest in sorted(base.rglob("ci-module.json")):
            data = json.loads(manifest.read_text(encoding="utf-8"))
            name = data["module"]
            if name in modules or not (manifest.parent / "test.sh").is_file():
                raise ValueError("duplicate module or missing test.sh: " + name)
            data["script"] = str(manifest.parent / "test.sh")
            modules[name] = data
    return dict(sorted(modules.items(), key=lambda pair: (pair[1].get("engine", "native") != "native", pair[0])))


def run(args):
    started = time.monotonic()
    directory = Path(os.environ.get("MIO_CI_RESULTS", ROOT / "build/ci-results")).expanduser().resolve() / (time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
    try:
        directory.mkdir(parents=True)
    except OSError as error:
        print("cannot create result directory: " + str(error), file=sys.stderr)
        return 2
    report = dict(schema_version=1, target=args[0] if args else "", module=args[1] if len(args) > 1 else "",
                  suite=args[2] if len(args) > 2 else "", status="NOT_RUN", checks=[], artifacts=[str(directory)])
    exit_code = 2
    try:
        if len(args) != 3:
            raise ValueError("usage: bash scripts/ci/run.sh <linux-amd64|macos-arm64> <module|all> <quick|full|all|module-suite>")
        target, selected, suite = args
        suite = "full" if suite == "all" else suite
        if target not in TARGETS or TARGETS[target] != (platform.system(), platform.machine().lower()):
            raise ValueError("unsupported target or host mismatch: " + target)
        modules = discover()
        if selected != "all" and selected not in modules:
            raise ValueError("unknown module: " + selected)
        chosen = list(modules.values()) if selected == "all" else [modules[selected]]
        if selected == "all" and suite not in ("quick", "full"):
            raise ValueError("all modules require quick, full or all")
        for module in chosen:
            if target not in module["targets"] or suite not in module["suites"]:
                if selected != "all":
                    raise ValueError("unsupported target/module/suite combination")
        for tool in ("bash", "git"):
            if not shutil.which(tool):
                raise ValueError("required tool missing: " + tool)
        env = dict(os.environ, PYTHON=sys.executable, MIO_CI_ACTIVE="1", MIO_BUNKO=str(ROOT / "bunko"))
        env["MIO_CI_TOOLS"] = str(directory / "tools")
        # Reference binaries are development-only, never used to build a release.
        Path(env["MIO_CI_TOOLS"]).mkdir()
        reference_built = False
        exit_code = 0
        for module in chosen:
            item = dict(module=module["module"], status="NOT_RUN", checks=[], artifacts=[])
            report["checks"].append(item)
            if target not in module["targets"] or suite not in module["suites"]:
                item.update(status="SKIP", reason=module.get("skip_reason", "not supported for this target/suite; see testing.md"))
                continue
            parent = modules.get(module.get("covered_by", ""))
            if selected == "all" and parent and target in parent["targets"] and suite in parent["suites"]:
                item.update(status="SKIP", reason="native tests delegated to recursive package check: " + parent["module"])
                continue
            work = directory / module["module"].replace("/", "-")
            work.mkdir()
            checks = work / "checks.jsonl"
            module_env = dict(env, MIO_CI_MODULE_DIR=str(work), MIO_CI_CHECKS=str(checks))
            engine = module.get("engine", "native")
            if engine == "native":
                seed = Path(os.environ.get("MIO_NATIVE_SEED", ""))
                if not seed.is_file() or hashlib.sha256(seed.read_bytes()).hexdigest() != SEED_SHA256:
                    item.update(status="NOT_RUN", reason="verified MIO_NATIVE_SEED missing or GF4 SHA256 mismatch",
                                checks=[dict(name=name, status="NOT_RUN", reason="native compiler unavailable") for name in module.get("required_checks", ["native"])])
                    exit_code = 2
                    continue
                module_env["MIO_CI_MIO"] = str(seed.resolve())
                item["compiler"] = dict(path=str(seed.resolve()), sha256=SEED_SHA256)
            elif engine == "reference" and not reference_built:
                if not shutil.which("go"):
                    raise ValueError("development-only reference check requires Go")
                for tool in ("mio", "mochi-aot", "mochi-aot-audit"):
                    code, out, err, status, reason, duration = execute(["go", "build", "-o", Path(env["MIO_CI_TOOLS"]) / tool, "./cmd/" + tool], 300, env)
                    (directory / (tool + "-build.log")).write_bytes(out + err)
                    if code:
                        raise ValueError("reference tool build failed: " + tool + "; see " + str(directory))
                reference_built = True
            code, out, err, status, reason, duration = execute(["bash", module["script"], target, suite], float(os.environ.get("MIO_CI_MODULE_TIMEOUT", "7200")), module_env)
            (work / "module.log").write_bytes(out + err)
            print((out + err).decode(errors="replace"), end="", flush=True)
            records = [json.loads(line) for line in checks.read_text().splitlines()] if checks.exists() else []
            for name in module.get("required_checks", []):
                if not any(record["name"] == name for record in records):
                    records.append(dict(name=name, status="NOT_RUN", reason="required layer did not execute"))
            item.update(checks=records, duration_ms=duration, exit_code=code, artifacts=[str(work / "module.log")])
            if code or any(c["status"] == "FAIL" for c in records):
                item.update(status="NOT_RUN" if code == 2 else "FAIL", reason=reason)
                exit_code = max(exit_code, 2 if code == 2 else 1)
            elif not records or any(c["status"] != "PASS" for c in records):
                item.update(status="NOT_RUN", reason="module did not complete required checks")
                exit_code = 2
            else:
                item["status"] = "PASS"
        report["status"] = "PASS" if exit_code == 0 else ("NOT_RUN" if exit_code == 2 else "FAIL")
    except (ValueError, OSError, KeyError) as error:
        report.update(status="NOT_RUN", reason=str(error))
        print(str(error), file=sys.stderr)
        exit_code = 2
    finally:
        report["duration_ms"] = round((time.monotonic() - started) * 1000)
        (directory / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("Report: " + str(directory / "report.json"), flush=True)
    return exit_code


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("run", "check"):
        sys.exit(2)
    sys.exit(run(sys.argv[2:]) if sys.argv[1] == "run" else check(sys.argv[2:]))
