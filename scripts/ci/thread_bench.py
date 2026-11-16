#!/usr/bin/env python3
"""Independently runnable thread benchmark phases (benchmarks/threads/efficiency.mio) for darwin-arm64 and linux-amd64.

Every phase is built as its own program (the final `run();` line of efficiency.mio is replaced by one phase call, so workloads are byte-for-byte the
ones of the combined program) and run as its own process with its own budget: an unfinished phase cannot hide the others. A phase is COMPLETE only
if the process exited 0, was not killed by the budget, printed exactly the expected measurement line(s) and the work count matches. Partial output of a
timed-out phase is kept as partial evidence and never counted as a measurement.

  phases:   start_join fan_join pingpong mpmc alloc_1 alloc_2 alloc_4 mpmc_probe   (and `all`: the original combined program, original 240 s budget)
  examples: scripts/ci/thread_bench.py --mio build/mio --target darwin-arm64 --repeat 5 --output build/bench/candidate
            scripts/ci/thread_bench.py --mio build/mio-candidate --baseline-mio build/mio-baseline --phase mpmc --phase pingpong --repeat 5

--baseline-mio builds the same phases with a second compiler and ALTERNATES baseline and candidate runs (B C B C ...). The image is only executed when the
host can run it (darwin-arm64 on macOS ARM64, linux-amd64 on Linux x86-64); otherwise the phase is reported NOT_RUN after a successful build.
Exit status: 0 when every requested phase was COMPLETE (or NOT_RUN because of the host), 1 otherwise.
"""
import argparse
import hashlib
import json
import os
import platform
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "benchmarks/threads/efficiency.mio"
# phase -> (source call, expected output name, expected work count, per-phase budget in seconds)
PHASES = {
    "start_join": ("start_join();", "start_join", 20000, 120),
    "fan_join": ("fan_join();", "fan_join", 6400, 120),
    "pingpong": ("pingpong();", "pingpong", 20000, 120),
    "mpmc": ("mpmc();", "mpmc", 400000, 240),          # 200000 sends + 200000 receives
    "alloc_1": ("alloc_scale(1);", "alloc_1", 2000000, 120),   # weak scaling: 2000000 loop iterations PER WORKER
    "alloc_2": ("alloc_scale(2);", "alloc_2", 4000000, 120),
    "alloc_4": ("alloc_scale(4);", "alloc_4", 8000000, 120),
    "mpmc_probe": ("mpmc_probe();", "mpmc_probe", None, 120),
}
ORDER = ["start_join", "fan_join", "pingpong", "mpmc", "alloc_1", "alloc_2", "alloc_4"]
ALL_EXPECTED = {name: PHASES[name][2] for name in ORDER}
ALL_BUDGET = 240   # the budget of the original darwin-thread-bench run


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def host_target():
    system, machine = platform.system(), platform.machine().lower()
    if system == "Darwin" and machine in ("arm64", "aarch64"):
        return "darwin-arm64"
    if system == "Linux" and machine in ("x86_64", "amd64"):
        return "linux-amd64"
    return None


def build(mio, call, target, work, label, bunko_root):
    text = SOURCE.read_text()
    marker = "\nrun();\n"
    if not text.endswith(marker):
        raise SystemExit("efficiency.mio must end with a bare `run();` line")
    source = work / (label + ".mio")
    source.write_text(text[:-len(marker)] + "\n" + call + "\n")
    image = work / label
    argv = [str(mio), "build", str(source), "--target=" + target, "-o", str(image)]
    if bunko_root:
        argv += ["--bunko-root", str(bunko_root)]
    done = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
    if done.returncode != 0 or not image.is_file():
        return None, (done.stderr or done.stdout)[-300:]
    os.chmod(image, 0o755)
    return image, ""


def run_once(image, budget):
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.monotonic()
    timed_out = False
    try:
        done = subprocess.run([str(image)], capture_output=True, text=True, timeout=budget)
        code, out, err = done.returncode, done.stdout, done.stderr
    except subprocess.TimeoutExpired as expired:
        timed_out, code = True, None
        out = (expired.stdout.decode() if isinstance(expired.stdout, bytes) else expired.stdout) or ""
        err = (expired.stderr.decode() if isinstance(expired.stderr, bytes) else expired.stderr) or ""
    wall = time.monotonic() - start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    return dict(exit=code, timed_out=timed_out, wall_s=round(wall, 3), user_s=round(after.ru_utime - before.ru_utime, 3),
                system_s=round(after.ru_stime - before.ru_stime, 3), stdout=out, stderr=err[-300:])


def parse(out):
    rows = {}
    for line in out.splitlines():
        parts = line.split(",")
        if len(parts) != 3:
            return None
        try:
            rows[parts[0]] = (int(parts[1]), int(parts[2]))
        except ValueError:
            return None
    return rows


def judge(phase, result):
    """COMPLETE / PARTIAL / FAIL plus the measurement (ms, work) of a complete run."""
    rows = parse(result["stdout"])
    if result["timed_out"]:
        return "PARTIAL", None, "budget exceeded; partial output %r" % result["stdout"][:200]
    if result["exit"] != 0:
        return "FAIL", None, "exit %s stderr %r" % (result["exit"], result["stderr"][:120])
    if rows is None:
        return "FAIL", None, "unparsable output %r" % result["stdout"][:120]
    if phase == "all":
        if rows.keys() != ALL_EXPECTED.keys() or any(rows[n][1] != w for n, w in ALL_EXPECTED.items()):
            return "FAIL", None, "wrong phase set or work counts %r" % rows
        return "COMPLETE", rows, ""
    _, name, work, _ = PHASES[phase]
    if phase == "mpmc_probe":
        probe = rows.get("mpmc_probe")
        workers = sorted(n for n in rows if n != "mpmc_probe")
        if probe is None or len(workers) != 8:
            return "FAIL", None, "probe lines missing: %r" % list(rows)
        sent = sum(rows[n][0] for n in workers if n.startswith("probe_producer"))
        if sent != probe[1]:
            return "FAIL", None, "delivered %d != sent %d" % (probe[1], sent)
        return "COMPLETE", rows, ""
    if set(rows) != {name} or rows[name][1] != work or rows[name][0] < 0:
        return "FAIL", None, "wrong output %r (expected one line %s with work %d)" % (rows, name, work)
    return "COMPLETE", rows, ""


def summarize(values):
    if not values:
        return {}
    return dict(n=len(values), values=values, median=statistics.median(values), min=min(values), max=max(values),
                spread_pct=round(100.0 * (max(values) - min(values)) / statistics.median(values), 1) if statistics.median(values) else 0.0)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mio", required=True, help="compiler under test")
    parser.add_argument("--baseline-mio", help="second compiler; baseline and candidate runs alternate")
    parser.add_argument("--target", default=host_target(), choices=("darwin-arm64", "linux-amd64"))
    parser.add_argument("--phase", action="append", choices=list(PHASES) + ["all"], help="repeatable; default: the seven benchmark phases")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--budget", type=int, help="override every phase budget (seconds); recorded in the report")
    parser.add_argument("--bunko-root", help="Bunko root for BOTH compilers (omit to use each compiler's embedded Bunko)")
    parser.add_argument("--output", default=str(ROOT / "build/thread-bench"))
    args = parser.parse_args()
    if args.target is None:
        raise SystemExit("--target is required on this host")
    phases = args.phase or ORDER
    work = Path(args.output)
    work.mkdir(parents=True, exist_ok=True)
    runnable = host_target() == args.target
    contenders = [("candidate", args.mio)] + ([("baseline", args.baseline_mio)] if args.baseline_mio else [])
    report = dict(host=dict(system=platform.system(), machine=platform.machine(), release=platform.release(), cpus=os.cpu_count()),
                  target=args.target, executed=runnable, repeat=args.repeat,
                  compilers={label: dict(path=str(path), sha256=sha256(path)) for label, path in contenders}, phases={})
    failed = False
    for phase in phases:
        call = "run();" if phase == "all" else PHASES[phase][0]
        budget = args.budget or (ALL_BUDGET if phase == "all" else PHASES[phase][3])
        entry = dict(budget_s=budget, expected_work=ALL_EXPECTED if phase == "all" else PHASES[phase][2], contenders={})
        images = {}
        for label, path in contenders:
            if phase == "all":   # the original combined program, unmodified
                image = work / ("all-" + label)
                done = subprocess.run([str(path), "build", str(SOURCE), "--target=" + args.target, "-o", str(image)] +
                                      (["--bunko-root", args.bunko_root] if args.bunko_root else []), cwd=ROOT, capture_output=True, text=True)
                image, why = (image, "") if done.returncode == 0 and image.is_file() else (None, (done.stderr or done.stdout)[-300:])
                if image:
                    os.chmod(image, 0o755)
            else:
                image, why = build(path, call, args.target, work, "%s-%s" % (phase, label), args.bunko_root)
            if image is None:
                entry["contenders"][label] = dict(status="FAIL", reason="build failed: " + why)
                failed = True
                continue
            images[label] = image
            entry["contenders"][label] = dict(image_sha256=sha256(image), runs=[])
        if not runnable:
            for label in images:
                entry["contenders"][label]["status"] = "NOT_RUN"
                entry["contenders"][label]["reason"] = "host %s cannot execute a %s image" % (host_target(), args.target)
        else:
            for repeat in range(args.repeat):
                for label, _ in contenders:      # alternate: candidate, baseline, candidate, baseline ...
                    if label not in images:
                        continue
                    result = run_once(images[label], budget)
                    status, rows, why = judge(phase, result)
                    entry["contenders"][label]["runs"].append(dict(status=status, reason=why, rows=rows, **{k: v for k, v in result.items() if k != "stdout"}))
                    print("%-10s %-9s run %d: %-8s exit %s %.1fs %s" % (phase, label, repeat, status, result["exit"], result["wall_s"], why), flush=True)
            for label in images:
                runs = entry["contenders"][label]["runs"]
                complete = [r for r in runs if r["status"] == "COMPLETE"]
                entry["contenders"][label]["status"] = "COMPLETE" if len(complete) == len(runs) and runs else ("PARTIAL" if any(r["status"] == "PARTIAL" for r in runs) else "FAIL")
                if phase not in ("all", "mpmc_probe") and complete:
                    entry["contenders"][label]["elapsed_ms"] = summarize([r["rows"][PHASES[phase][1]][0] for r in complete])
                entry["contenders"][label]["wall_s"] = summarize([r["wall_s"] for r in runs])
                entry["contenders"][label]["cpu_s"] = summarize([round(r["user_s"] + r["system_s"], 3) for r in runs])
                if entry["contenders"][label]["status"] != "COMPLETE" and phase != "mpmc_probe":
                    failed = True
        report["phases"][phase] = entry
        (work / "report.json").write_text(json.dumps(report, indent=1))
    print("report: %s" % (work / "report.json"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
