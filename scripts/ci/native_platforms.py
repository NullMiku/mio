#!/usr/bin/env python3
"""Native verification of the pure-Mio toolchain on darwin-arm64, linux-amd64 and windows-amd64.

Engines are never mixed: every check records whether it ran a native Mio image ("native"), the Go reference VM
("reference") or the Go-hosted bootstrap host ("go-hosted"). Statuses are PASS, FAIL, SKIP, NOT_RUN and NOT_APPLICABLE
(a check that does not exist on that platform, with the reason); only PASS counts as passed.

  linux    Stage A of the native compiler is lowered by the pure-Mio backend running in the Go reference VM (go-hosted,
           NOT a trusted Native Seed). Native A->B->C->D compiler and CLI fixed points, native `mio test`, Runtime ABI
           contract (default and --gc-stress) with the VM differential, then the darwin-arm64 and windows-amd64 Stage A
           CLIs are cross-built by the native Linux CLI (twice, by two generations, which must agree).
  darwin   On macos-15. Stage A = the cross-built CLI (SHA-256 checked against the Linux manifest). Native B->C->D,
  windows  native `mio test` (darwin only), Runtime ABI contract. A == B (cross build equals native build) is required.
  summary  Combines the platform reports; fails unless every required check is PASS.

The trusted GF4 Native Seed is not available to hosted runners; its verification is always reported NOT_RUN.
Python only starts processes, compares bytes and writes JSON; it generates no code.
"""
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STARTED = time.monotonic()
# Wall-clock budget for one platform (below the job timeout) so a slow host still uploads a complete report.
BUDGET_SECONDS = int(os.environ.get("MIO_NATIVE_BUDGET_SECONDS", "6600"))
GF4_SEED_SHA256 = "4c3f7dcbea536d756c3c4a93c18a999412625184bd5c90123f1c16a0cd9e36da"
TARGETS = {"linux": "linux-amd64", "darwin": "darwin-arm64", "windows": "windows-amd64"}
EXPECTED_HOST = {"linux-amd64": ("Linux", ("x86_64", "amd64")), "darwin-arm64": ("Darwin", ("arm64", "aarch64")),
                 "windows-amd64": ("Windows", ("amd64", "x86_64"))}
EXE = {"windows-amd64": ".exe"}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Report:
    def __init__(self, target, output):
        self.target, self.output = target, Path(output).resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        self.logs = self.output / "logs"
        self.logs.mkdir(exist_ok=True)
        self.checks, self.hashes = [], {}
        self.data = dict(schema_version=1, suite="native-platforms", target=target,
                         source_sha=os.environ.get("GITHUB_SHA") or git("rev-parse", "HEAD"),
                         runner=dict(os=os.environ.get("RUNNER_OS", ""), arch=os.environ.get("RUNNER_ARCH", ""),
                                     name=os.environ.get("RUNNER_NAME", ""), image=os.environ.get("ImageOS", ""),
                                     image_version=os.environ.get("ImageVersion", ""),
                                     system=platform.system(), machine=platform.machine(), platform=platform.platform()),
                         run=dict(id=os.environ.get("GITHUB_RUN_ID", ""), attempt=os.environ.get("GITHUB_RUN_ATTEMPT", ""),
                                  url="%s/%s/actions/runs/%s" % (os.environ.get("GITHUB_SERVER_URL", ""),
                                                                 os.environ.get("GITHUB_REPOSITORY", ""),
                                                                 os.environ.get("GITHUB_RUN_ID", ""))),
                         seed=dict(status="NOT_RUN", sha256=GF4_SEED_SHA256,
                                   reason="the trusted GF4 Native Seed is not available to GitHub-hosted runners; "
                                          "Stage A comes from the Go-hosted reference VM and is not seed-verified"),
                         checks=self.checks, hashes=self.hashes)

    def check(self, name, status, engine, reason="", required=True, **extra):
        item = dict(name=name, status=status, engine=engine, required=required, reason=reason)
        item.update(extra)
        self.checks.append(item)
        print("%-15s %-34s %-10s %s" % (status, name, engine, reason), flush=True)
        self.save()
        return status == "PASS"

    def save(self):
        failed = [c["name"] for c in self.checks if c["required"] and c["status"] != "PASS"]
        self.data["status"] = "FAIL" if failed else "PASS"
        self.data["failed_required"] = failed
        (self.output / "report.json").write_text(json.dumps(self.data, indent=2) + "\n")


def git(*args):
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def run(report, label, argv, cwd=ROOT, stdin=None, timeout=1800, env=None):
    """Runs a process, keeps its output in logs/<label>.log; returns (exit code or None on timeout, stdout, stderr)."""
    started = time.monotonic()
    environment = dict(os.environ, MIO_BUNKO=str(ROOT / "bunko"))
    environment.update(env or {})
    try:
        proc = subprocess.run([str(a) for a in argv], cwd=cwd, input=stdin, capture_output=True, timeout=timeout, env=environment)
        code, out, err = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as error:
        code, out, err = None, error.stdout or b"", (error.stderr or b"") + b"\n[timed out]"
    seconds = time.monotonic() - started
    with open(report.logs / (label + ".log"), "wb") as stream:
        stream.write(("$ %s\n[cwd %s] [exit %s] [%.1fs]\n" % (" ".join(str(a) for a in argv), cwd, code, seconds)).encode())
        stream.write(b"--- stdout\n" + out + b"\n--- stderr\n" + err)
    return code, out.decode(errors="replace"), err.decode(errors="replace"), seconds


def brief(text, limit=300):
    text = " ".join(text.split())
    return text[-limit:]


def verify_host(report):
    system, machines = EXPECTED_HOST[report.target]
    actual = (platform.system(), platform.machine().lower())
    ok = actual[0] == system and actual[1] in machines
    return report.check("runner-os-arch", "PASS" if ok else "FAIL", "host",
                        "" if ok else "expected %s/%s, runner is %s/%s" % (system, machines[0], actual[0], actual[1]),
                        detected="%s/%s" % actual)


CLI_BUILD_TIMEOUT = 1500  # a self-build that needs longer is reported FAIL (with its log), never left to hang the job


def peak_rss_mib(err):
    """Peak RSS from macOS `/usr/bin/time -l` (bytes) or GNU `time -v` (KiB); 0 when absent."""
    match = re.search(r"(\d+)\s+maximum resident set size", err)
    if match:
        return int(match.group(1)) // (1024 * 1024)
    match = re.search(r"Maximum resident set size \(kbytes\): (\d+)", err)
    return int(match.group(1)) // 1024 if match else 0


def cli_build(report, label, cli, entry, target, output, extra=()):
    argv = [cli, "build", entry, "--target=" + target, "-o", output, *extra]
    if platform.system() == "Darwin" and Path("/usr/bin/time").exists():
        argv = ["/usr/bin/time", "-l", *argv]  # resource usage only; the build itself is unchanged
    code, out, err, seconds = run(report, label, argv, timeout=CLI_BUILD_TIMEOUT)
    ok = code == 0 and Path(output).is_file()
    if ok and target != "windows-amd64":
        os.chmod(output, 0o755)
    reason = "timed out after %ds" % CLI_BUILD_TIMEOUT if code is None else "exit %s: %s" % (code, brief(err or out))
    rss = peak_rss_mib(err)
    if rss:
        reason += " (peak RSS %d MiB)" % rss
    print("    %s: %.1fs%s" % (label, seconds, ", peak RSS %d MiB" % rss if rss else ""), flush=True)
    return ok, reason, seconds


def cli_chain(report, first, target, work, engine="native"):
    """first builds selfhost/cli -> B, B -> C, C -> D for `target`; requires B == C == D. Returns the path of B."""
    suffix = EXE.get(target, "")
    paths = {"A": Path(first)}
    for previous, name in (("A", "B"), ("B", "C"), ("C", "D")):
        output = work / ("mio-%s%s" % (name, suffix))
        ok, reason, seconds = cli_build(report, "cli-" + name, paths[previous], "selfhost/cli", target, output)
        if not report.check("cli-stage-" + name, "PASS" if ok else "FAIL", engine,
                            "" if ok else "%s could not build stage %s: %s" % (previous, name, reason),
                            seconds=round(seconds, 1), built_by=previous, detail=reason if ok else ""):
            return None
        paths[name] = output
        report.hashes["cli-" + name] = sha256(output)
    same = sha256(paths["B"]) == sha256(paths["C"]) == sha256(paths["D"])
    report.check("cli-fixed-point", "PASS" if same else "FAIL", engine, "" if same else "B, C and D differ",
                 B=report.hashes["cli-B"], C=report.hashes["cli-C"], D=report.hashes["cli-D"])
    return paths["B"] if same else None


def smoke(report, cli, target, work, label_prefix=""):
    Path(work).mkdir(parents=True, exist_ok=True)
    code, out, err, _ = run(report, label_prefix + "cli-version", [cli, "--version"])
    report.check(label_prefix + "cli-version", "PASS" if code == 0 and out.startswith("mio ") else "FAIL", "native",
                 "" if code == 0 else "exit %s: %s" % (code, brief(err)), output=out.strip())
    project = work / "hello"
    project.mkdir(exist_ok=True)
    (project / "main.mio").write_text('chant("hello from the native Mio CLI");\nkaku n = 0; kaku i = 1;\n'
                                      'aida (i <= 100) { n = n + i; i = i + 1; }\nchant(n);\n')
    image = work / ("hello-image" + EXE.get(target, ""))
    ok, reason, _ = cli_build(report, label_prefix + "hello-build", cli, str(project / "main.mio"), target, image)
    if not ok:
        return report.check(label_prefix + "cli-hello", "FAIL", "native", "build " + reason)
    code, out, err, _ = run(report, label_prefix + "hello-run", [image], cwd=work)
    want = "hello from the native Mio CLI\n5050\n"
    ok = code == 0 and out == want
    return report.check(label_prefix + "cli-hello", "PASS" if ok else "FAIL", "native", "" if ok else "exit %s, stdout %r" % (code, out[:200]))


def test_packages():
    found = set()
    for top in ("bunko", "selfhost"):
        for path in (ROOT / top).rglob("*_test.mio"):
            found.add(path.parent.relative_to(ROOT).as_posix())
    return sorted(found)


def count(pattern, text):
    match = re.search(pattern, text)
    return int(match.group(1)) if match else 0


def native_mio_test(report, cli, skips_allowed):
    """Every package with *_test.mio. A skipped test is never a pass: skips are reported separately (SKIP, with the
    test's own reason). Where every test must run (darwin-arm64, the primary target) a skip is a required failure."""
    failures = []
    for package in test_packages():
        label = "mio-test-" + package.replace("/", "_")
        if time.monotonic() - STARTED > BUDGET_SECONDS:
            report.check("mio-test " + package, "NOT_RUN", "native", "platform time budget (%ds) exhausted" % BUDGET_SECONDS)
            failures.append(package)
            continue
        code, out, err, seconds = run(report, label, [cli, "test", package], timeout=900)
        text = out + err
        passed = count(r"Tests complete: (\d+) passed", text)
        failed = count(r"Tests complete: \d+ passed, (\d+) failed", text)
        skipped = count(r"Tests skipped: (\d+)", text)
        reasons = sorted({line.strip() for line in text.splitlines() if line.strip().startswith("skipped:")})
        complete = "Tests complete:" in text
        ok = code == 0 and complete and failed == 0 and (passed > 0 or skipped > 0)  # nothing executed is a failure
        status = "PASS" if ok and passed > 0 and skipped == 0 else "FAIL" if not ok else "SKIP"
        report.check("mio-test " + package, "PASS" if status == "PASS" else "FAIL" if status == "FAIL" else
                     ("SKIP" if skips_allowed else "FAIL"), "native",
                     "" if status == "PASS" else ("exit %s: %s" % (code, brief(text)) if status == "FAIL" else
                                                  "%d skipped: %s" % (skipped, "; ".join(reasons)[:300])),
                     required=status != "SKIP" or not skips_allowed, seconds=round(seconds, 1),
                     passed=passed, failed=failed, skipped=skipped)
        if status == "SKIP" and skips_allowed and passed > 0:
            report.check("mio-test " + package + " (non-skipped)", "PASS", "native", "", passed=passed)
        if status == "FAIL":
            failures.append(package)
    return not failures


def contract(report, cli, target, reference="", suite="contract"):
    """tests/runtime-abi/run.py --suite contract (RA-1 cases) or differential (former pureLowerPrograms corpus)."""
    output = report.output / ("runtime-abi" if suite == "contract" else "native-differential")
    argv = [sys.executable, ROOT / "tests/runtime-abi/run.py", "--suite", suite, "--mio", cli, "--target", target, "--output", output]
    if reference:
        argv += ["--reference", reference]
    code, out, err, seconds = run(report, "suite-" + suite, argv, timeout=5400)
    native_name = "runtime-abi-contract" if suite == "contract" else "native-differential"
    try:
        results = json.loads((output / "results.json").read_text())["results"]
    except (OSError, ValueError, KeyError):
        return report.check(native_name, "FAIL", "native", "runner produced no results: exit %s %s" % (code, brief(err)))
    ok_all = code == 0
    for engine in ("native", "reference"):
        if engine == "reference" and not reference:
            continue
        items = [r for r in results if r["engine"] in (engine, "contract")]
        bad = [r for r in items if r["status"] not in ("PASS", "NOT_APPLICABLE")]
        excluded = [r for r in items if r["status"] == "NOT_APPLICABLE"]
        name = native_name if engine == "native" else "vm-reference-" + suite
        report.check(name, "PASS" if items and not bad else "FAIL", engine,
                     "; ".join("%s/%s: %s" % (r["case"], r["mode"], r["reason"]) for r in bad)[:600],
                     cases=len({r["case"] for r in items}), passed=len([r for r in items if r["status"] == "PASS"]),
                     seconds=round(seconds, 1))
        if excluded:
            report.check(name + " (excluded)", "NOT_APPLICABLE", engine,
                         "; ".join("%s/%s: %s" % (r["case"], r["mode"], r["reason"]) for r in excluded)[:600], required=False)
        ok_all = ok_all and bool(items) and not bad
    return ok_all


# ---------------------------------------------------------------------------------------------------- linux

def linux(args):
    report = Report("linux-amd64", args.output)
    verify_host(report)
    work = report.output / "work"
    work.mkdir(exist_ok=True)
    refvm = Path(args.refvm).resolve()
    # Stage A: Go reference frontend -> Mochi; pure-Mio lowerlinux running in the Go VM -> ELF. Explicitly go-hosted.
    mochi = work / "linux-compiler.mochi"
    code, out, err, seconds = run(report, "stage-a-mochi", [refvm, ROOT / "bunko", "mochi", ROOT / "selfhost/linux-compiler/main.mio", mochi])
    if not report.check("stage-a-frontend", "PASS" if code == 0 else "FAIL", "go-hosted",
                        "" if code == 0 else brief(err), seconds=round(seconds, 1),
                        note="Go reference frontend compiles selfhost/linux-compiler to Mochi"):
        return finish(report)
    lowering = work / "stage-a-lowering"
    lowering.mkdir(exist_ok=True)
    compiler_a = work / "compiler-A"
    (lowering / "input.config").write_text(str(mochi))
    (lowering / "output.config").write_text(str(compiler_a))
    code, out, err, seconds = run(report, "stage-a-lowering", [refvm, ROOT / "bunko", "run", ROOT / "selfhost/native-aot-linux/main.mio"], cwd=lowering, timeout=3600)
    ok = code == 0 and "native-aot-linux: ok" in out and compiler_a.is_file()
    if not report.check("stage-a-lowering", "PASS" if ok else "FAIL", "go-hosted", "" if ok else "exit %s: %s" % (code, brief(err or out)),
                        seconds=round(seconds, 1), note="pure-Mio lowerlinux executed by the Go reference VM; not a trusted seed"):
        return finish(report)
    os.chmod(compiler_a, 0o755)
    report.hashes["compiler-A"] = sha256(compiler_a)
    # Native compiler fixed point
    paths = {"A": compiler_a}
    for previous, name in (("A", "B"), ("B", "C"), ("C", "D")):
        output = work / ("compiler-" + name)
        code, out, err, seconds = run(report, "compiler-" + name, [paths[previous]], stdin=("selfhost/linux-compiler\n%s\n" % output).encode())
        ok = code == 0 and out == "linux-compiler: ok\n" and output.is_file()
        if not report.check("compiler-stage-" + name, "PASS" if ok else "FAIL", "native", "" if ok else "exit %s: %s" % (code, brief(err or out)),
                            seconds=round(seconds, 1), built_by=previous):
            return finish(report)
        os.chmod(output, 0o755)
        paths[name] = output
        report.hashes["compiler-" + name] = sha256(output)
    same = report.hashes["compiler-B"] == report.hashes["compiler-C"] == report.hashes["compiler-D"]
    report.check("compiler-fixed-point", "PASS" if same else "FAIL", "native", "" if same else "B, C and D differ")
    if not same:
        return finish(report)
    # CLI: compiler B builds selfhost/cli (CLI A); then the CLI builds itself A -> B -> C -> D
    cli_a = work / "mio-A"
    code, out, err, seconds = run(report, "cli-A", [paths["B"]], stdin=("selfhost/cli\n%s\n" % cli_a).encode())
    ok = code == 0 and out == "linux-compiler: ok\n" and cli_a.is_file()
    if not report.check("cli-stage-A", "PASS" if ok else "FAIL", "native", "" if ok else "exit %s: %s" % (code, brief(err or out)), built_by="compiler-B"):
        return finish(report)
    os.chmod(cli_a, 0o755)
    report.hashes["cli-A"] = sha256(cli_a)
    cli = cli_chain(report, cli_a, "linux-amd64", work)
    if cli is None:
        return finish(report)
    smoke(report, cli, "linux-amd64", work)
    native_mio_test(report, cli, skips_allowed=True)
    contract(report, cli, "linux-amd64", reference=str(refvm))
    contract(report, cli, "linux-amd64", reference=str(refvm), suite="differential")
    chain = work / "runtime-chain"
    chain.mkdir(exist_ok=True)
    code, out, err, seconds = run(report, "linux-runtime-chain", [sys.executable, ROOT / "bunko/kiso/runtime/os/linux/check_chain.py"],
                                  env=dict(MIO_CI_MIO=str(cli), MIO_CI_MODULE_DIR=str(chain)), timeout=1800)
    executed = "execution: NOT_RUN" not in out + err
    report.check("linux-runtime-chain", "PASS" if code == 0 and executed else "FAIL", "native",
                 "" if code == 0 and executed else "exit %s: %s" % (code, brief(err or out)), seconds=round(seconds, 1),
                 note="kiso/runtime/ir -> cpu/amd64 -> x86_64 -> elf image built by a native Mio program and executed")
    # Stage A of the other targets, cross-built by two native generations that must agree
    seeds = report.output / "stage-a"
    seeds.mkdir(exist_ok=True)
    manifest = {}
    for target in ("darwin-arm64", "windows-amd64"):
        name = "mio-%s%s" % (target, EXE.get(target, ""))
        first, second = seeds / name, work / ("again-" + name)
        ok1, reason1, _ = cli_build(report, "cross-" + target, cli, "selfhost/cli", target, first)
        ok2, reason2, _ = cli_build(report, "cross-again-" + target, work / "mio-C", "selfhost/cli", target, second)
        ok = ok1 and ok2 and sha256(first) == sha256(second)
        reason = "" if ok else (reason1 if not ok1 else reason2 if not ok2 else "generations B and C cross-build different images")
        if report.check("cross-stage-a " + target, "PASS" if ok else "FAIL", "native", reason, sha256=sha256(first) if ok1 else ""):
            manifest[target] = dict(file=name, sha256=sha256(first), built_by="linux-amd64 cli-B", source_sha=report.data["source_sha"])
            report.hashes["stage-a-" + target] = manifest[target]["sha256"]
    (seeds / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
            for target, item in manifest.items():
                stream.write("%s=%s\n" % (target.replace("-", "_"), item["sha256"]))
    return finish(report)


# ---------------------------------------------------------------------------------------------------- darwin / windows

def follower(args, target):
    report = Report(target, args.output)
    verify_host(report)
    work = report.output / "work"
    work.mkdir(exist_ok=True)
    stage_a = Path(args.stage_a).resolve()
    expected = args.expect_sha256
    manifest_sha = ""
    try:
        manifest_sha = json.loads((stage_a.parent / "manifest.json").read_text())[target]["sha256"]
    except (OSError, ValueError, KeyError):
        pass
    actual = sha256(stage_a) if stage_a.is_file() else ""
    ok = bool(actual) and actual == expected == manifest_sha
    if not report.check("stage-a-sha256", "PASS" if ok else "FAIL", "host",
                        "" if ok else "downloaded %s, job output %s, manifest %s" % (actual or "missing", expected, manifest_sha or "missing"),
                        sha256=actual, provenance="cross-built by the native linux-amd64 CLI of this run (go-hosted root)"):
        return finish(report)
    report.hashes["cli-A"] = actual
    first = work / stage_a.name
    shutil.copyfile(stage_a, first)
    if target != "windows-amd64":
        os.chmod(first, 0o755)
    # A quick signal that Stage A works on this host before the long self-builds.
    smoke(report, first, target, work / "smoke-A", label_prefix="stage-a-")
    cli = cli_chain(report, first, target, work)
    if cli is not None:
        same = report.hashes["cli-A"] == report.hashes["cli-B"]
        report.check("cross-equals-native", "PASS" if same else "FAIL", "native",
                     "" if same else "the Linux cross build (A) differs from this host's native build (B)")
        smoke(report, cli, target, work)
        if target == "darwin-arm64":
            darwin_profile(report, cli, work)
            native_mio_test(report, cli, skips_allowed=False)
        else:
            report.check("mio-test", "NOT_APPLICABLE", "native",
                         "`mio test` spawns test images; process spawn is not implemented by the Windows runtime "
                         "(kiso/aot/lowerwinrt). The same Mio package tests run natively on linux-amd64 and darwin-arm64.",
                         required=False)
        contract(report, cli, target)
        contract(report, cli, target, suite="differential")
    return finish(report)


def darwin_profile(report, cli, work):
    """Self-build of the CLI by an observation build of itself: the collector/memory counters and the time and peak RSS
    of a real compiler workload on this host. Observation must not change behaviour, so the output must equal B."""
    observed = work / "mio-observed"
    ok, reason, seconds = cli_build(report, "observed-build", cli, "selfhost/cli", "darwin-arm64", observed, extra=("--observe",))
    if not report.check("observed-cli-build", "PASS" if ok else "FAIL", "native", "" if ok else reason, seconds=round(seconds, 1)):
        return
    output = work / "mio-from-observed"
    argv = ["/usr/bin/time", "-l", observed, "build", "selfhost/cli", "--target=darwin-arm64", "-o", output]
    code, out, err, seconds = run(report, "observed-self-build", argv, timeout=CLI_BUILD_TIMEOUT)
    counters = dict(re.findall(r"mio-gc (\w+)=(\d+)", err))
    timing = dict((name, float(value)) for value, name in re.findall(r"([\d.]+) (real|user|sys)", err))
    same = code == 0 and output.is_file() and sha256(output) == report.hashes.get("cli-B")
    report.check("observed-self-build", "PASS" if same else "FAIL", "native",
                 "" if same else "exit %s or output differs from cli-B: %s" % (code, brief(err)),
                 seconds=round(seconds, 1), peak_rss_mib=peak_rss_mib(err), time=timing, gc=counters)
    print("    profile: time %s rss %d MiB counters %s" % (timing, peak_rss_mib(err), counters), flush=True)


def finish(report):
    report.save()
    print("%s: %s" % (report.target, report.data["status"]))
    if report.data["failed_required"]:
        print("failed required checks: " + ", ".join(report.data["failed_required"]))
    return 0 if report.data["status"] == "PASS" else 1


# ---------------------------------------------------------------------------------------------------- summary

def summary(args):
    rows, overall, combined = [], "PASS", {}
    found = {}
    for path in sorted(Path(args.reports).rglob("report.json")):
        try:
            data = json.loads(path.read_text())
        except ValueError:
            continue
        if data.get("suite") == "native-platforms":
            found[data.get("target")] = path
    for target in ("linux-amd64", "darwin-arm64", "windows-amd64"):
        path = found.get(target)
        if path is None:
            overall = "FAIL"
            rows.append("| %s | NOT_RUN | report missing (job failed before writing it or was not scheduled) |" % target)
            combined[target] = dict(status="NOT_RUN")
            continue
        data = json.loads(path.read_text())
        combined[target] = data
        counts = {}
        for item in data["checks"]:
            counts[item["status"]] = counts.get(item["status"], 0) + 1
        if data["status"] != "PASS":
            overall = "FAIL"
        rows.append("| %s | %s | %s | seed %s |" % (target, data["status"],
                    ", ".join("%s %d" % kv for kv in sorted(counts.items())), data["seed"]["status"]))
    text = ["## Native verification: %s" % overall, "",
            "Stage A is go-hosted (Go reference VM runs the pure-Mio Linux lowering); the trusted GF4 Native Seed is "
            "NOT_RUN. B/C/D fixed points and all tests below ran as native images on the named runner.", "",
            "| target | status | checks | seed |", "|---|---|---|---|", *rows, ""]
    for target, data in combined.items():
        for item in data.get("checks", []):
            if item["status"] != "PASS":
                text.append("- %s `%s` %s (%s): %s" % (target, item["name"], item["status"], item["engine"], item["reason"]))
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "native-summary.json").write_text(json.dumps(dict(status=overall, targets=combined), indent=2) + "\n")
    (output / "native-summary.md").write_text("\n".join(text) + "\n")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write("\n".join(text) + "\n")
    print("\n".join(text))
    return 0 if overall == "PASS" else 1


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("linux")
    p.add_argument("--refvm", required=True)
    p.add_argument("--output", required=True)
    for name in ("darwin", "windows"):
        p = sub.add_parser(name)
        p.add_argument("--stage-a", required=True)
        p.add_argument("--expect-sha256", required=True)
        p.add_argument("--output", required=True)
    p = sub.add_parser("summary")
    p.add_argument("--reports", required=True)
    p.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "linux":
        return linux(args)
    if args.command == "summary":
        return summary(args)
    return follower(args, TARGETS[args.command])


if __name__ == "__main__":
    sys.exit(main())
