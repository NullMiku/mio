#!/usr/bin/env python3
"""Conservative Quick scheduling; modules retain all test business logic."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys

import runner


def git(*args):
    return subprocess.check_output(["git", *args], cwd=runner.ROOT, timeout=30)


def documentation(path):
    return path in ("README.md", "CONTRIBUTING.md") or (path.startswith("docs/") and path.endswith(".md"))


DEFERRED_REASON = ("Native Verification is deferred: no trusted Native Seed is available to GitHub-hosted runners; "
                   "NOT_RUN, never PASS")


def native_verification_state(value=None):
    """Only the exact value `enabled` turns Native Verification on; anything else is the deferred state."""
    value = os.environ.get("MIO_NATIVE_VERIFICATION", "") if value is None else value
    return "enabled" if value == "enabled" else "deferred"


def select(paths, modules, fallback="", native_verification="enabled"):
    quick = {name: m for name, m in modules.items() if "quick" in m["suites"]}
    baseline = {"core", "quality", "go-reference"}
    if not baseline <= quick.keys():
        raise ValueError("required Quick baseline module missing")
    mode, reason = "full-quick", fallback or "unknown or cross-module impact"
    selected = set(quick)
    if not fallback and paths and all(documentation(p) for p in paths):
        mode, reason, selected = "documentation", "only documentation changed; language tests are not requested", {"quality"}
    elif not fallback and paths:
        affected = set()
        for name in paths:
            if documentation(name):
                continue
            path = PurePosixPath(name)
            # Only ordinary package test changes can be localized without a
            # compiler-complete dependency analysis. Implementations, manifests,
            # removed files, Core, ABI, GC and AOT always use full Quick.
            if (not name.startswith("bunko/") or not name.endswith("_test.mio") or
                    name.startswith(("bunko/kiso/aot/", "bunko/kiso/runtime/")) or
                    not (runner.ROOT / name).is_file()):
                break
            owners = [m for m in quick.values() if path.parent ==
                      PurePosixPath(Path(m["script"]).parent.relative_to(runner.ROOT).as_posix())]
            if len(owners) != 1:
                break
            affected.add(owners[0]["module"])
        else:
            if affected:
                mode, reason, selected = "module-tests", "ordinary package tests only; keep Core and supplementary baseline", baseline | affected

    linux, native = [], []
    for name, module in quick.items():
        if name not in selected or name == "quality":
            continue
        if "linux-amd64" in module["targets"]:
            linux.append(name)
        if "macos-arm64" in module["targets"] and (module.get("engine", "native") == "native" or "linux-amd64" not in module["targets"]):
            native.append(name)
    # Deferred Native Verification: modules that need the trusted Native Seed are recorded NOT_RUN and are not
    # started; the executable supplementary modules still run, on hosted macOS as well.
    deferred, macos = [], []
    if native_verification == "deferred":
        deferred, native = native, []
        macos = [name for name, module in quick.items() if name in selected and name != "quality" and
                 "macos-arm64" in module["targets"] and module.get("engine", "native") != "native"]
    scheduled = set(linux) | set(native) | set(macos) | set(deferred) | {"quality"}
    if selected - scheduled:
        raise ValueError("selected Quick modules have no execution platform: " + ",".join(sorted(selected - scheduled)))
    def reason_for(name):
        if name in deferred:
            return DEFERRED_REASON
        if name in scheduled:
            return "scheduled; execution evidence required"
        return "not selected by Quick scope" if name in quick else "not a Quick suite module"
    return dict(schema_version=1, suite="quick", mode=mode, reason=reason, changed_files=paths,
                native_verification=native_verification,
                native_needs_go=any(quick[name].get("engine", "native") == "reference" or
                                    "go" in quick[name].get("requires", []) for name in native),
                native_modules=native, deferred_native_modules=deferred, macos_modules=macos,
                reference_modules=linux, infrastructure_modules=["quality"],
                modules=[dict(module=name, status="NOT_RUN" if name in scheduled else "SKIP", reason=reason_for(name))
                         for name in modules])


def make_plan(base, head, native_verification=None):
    modules = runner.discover()  # Invalid registration is an error, never a docs-only success.
    actual = git("rev-parse", "HEAD").decode().strip()
    fallback, paths = "", []
    try:
        if git("rev-parse", "--verify", head + "^{commit}").decode().strip() != actual:
            raise ValueError("head does not match checkout")
        git("merge-base", "--is-ancestor", base, head)
        paths = [p.decode("utf-8") for p in git("diff", "--name-only", "--no-renames", "-z", base, head).split(b"\0") if p]
        if not paths:
            fallback = "empty diff; cannot infer impact"
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        fallback = "diff unavailable or unreliable; complete Quick required: " + str(error)
    plan = select(paths, modules, fallback, native_verification_state(native_verification))
    plan.update(base=base, head=head, source_sha=actual)
    return plan


def combine(checks):
    return "FAIL" if any(c["status"] == "FAIL" for c in checks) else \
        "NOT_RUN" if any(c["status"] == "NOT_RUN" for c in checks) else "PASS"


def gate(plan, infrastructure, native, reference, macos=""):
    """Supplementary gate plus Native Verification, reported separately.

    With Native Verification deferred the gate can pass on the supplementary checks alone, but the report keeps
    `native_verification` as NOT_RUN: a green gate never means that native tests passed.
    """
    if plan.get("schema_version") != 1 or plan.get("suite") != "quick":
        raise ValueError("invalid Quick plan")
    for field in ("native_modules", "reference_modules"):
        if not isinstance(plan.get(field), list):
            raise ValueError("missing plan field: " + field)
    state = plan.get("native_verification", "enabled")
    if state not in ("enabled", "deferred"):
        raise ValueError("invalid native_verification state")

    def judge(name, required, result):
        status = ("PASS" if result == "success" else "FAIL" if result == "failure" else "NOT_RUN") if required else "SKIP"
        return dict(name=name, required=required, status=status, job_result=result,
                    reason="" if status == "PASS" else "not requested by scope" if not required else
                    "required job did not succeed; a missing runner or Native Seed is NOT_RUN")
    supplementary = [judge("infrastructure", True, infrastructure),
                     judge("reference", bool(plan["reference_modules"]), reference)]
    if plan.get("macos_modules"):
        supplementary.append(judge("macos-supplementary", True, macos))
    native_checks = [judge("native", bool(plan["native_modules"]), native)]
    if state == "deferred":
        verification = dict(status="NOT_RUN", state="deferred", reason=DEFERRED_REASON,
                            modules=list(plan.get("deferred_native_modules", [])))
        checks = supplementary
        status = combine(supplementary)
    else:
        verification = dict(status=combine(native_checks) if plan["native_modules"] else "SKIP", state="enabled",
                            reason="", modules=list(plan["native_modules"]))
        checks = supplementary + native_checks
        status = combine(checks)
    return dict(status=status, scope=plan["mode"], source_sha=plan.get("source_sha"), checks=checks,
                native_verification=verification,
                note="Supplementary checks passing does not mean Mio native tests passed." if state == "deferred" else "")


def evidence(directory, expected, target, source_sha):
    """A successful job must also supply this commit's exact module report."""
    try:
        reports = list(directory.rglob("report.json")) if directory else []
        if len(reports) != 1:
            raise ValueError("expected exactly one execution report")
        report = json.loads(reports[0].read_text(encoding="utf-8"))
        if (report.get("status") != "PASS" or report.get("exit_code") != 0 or
                report.get("target") != target or report.get("suite") != "quick" or
                report.get("source_revision") != source_sha or
                sorted(report.get("selected_modules", [])) != sorted(expected) or
                sorted(m["module"] for m in report["checks"]) != sorted(expected)):
            raise ValueError("execution report does not match required scope, result or revision")
        modules = runner.discover()
        for item in report["checks"]:
            if item["status"] == "SKIP" and item["module"] in modules:
                module = modules[item["module"]]
                if module.get("covered_by") in expected and runner.delegated(module, modules, target, "quick"):
                    continue
            if item["status"] != "PASS":
                raise ValueError("required module did not pass: " + item["module"])
        return dict(status="PASS", reason="scope and source verified", report=str(reports[0]))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        return dict(status="NOT_RUN", reason=str(error))


def full_plan(modules, native_verification):
    """Module selection for Full. Deferred: only modules that do not need the trusted Native Seed run, and the
    skipped native modules are listed as NOT_RUN. Enabled: every module, exactly as before. Standalone long-running
    modules are never part of these lists: the Full workflow runs each of them in its own job."""
    def usable(module, target):
        return target in module["targets"] and "full" in module["suites"]
    result = dict(schema_version=1, suite="full", native_verification=native_verification,
                  standalone_modules={target: sorted(name for name, m in modules.items() if usable(m, target) and m.get("standalone"))
                                      for target in ("linux-amd64", "macos-arm64")})
    native_modules = sorted(name for name, m in modules.items() if usable(m, "macos-arm64") and m.get("engine", "native") == "native")
    if native_verification == "enabled":
        result.update(linux_modules="all", macos_modules="all", executed_native_modules=native_modules, deferred_native_modules=[])
        result["native_verification"] = dict(status="PENDING", state="enabled", modules=native_modules,
                                             reason="executed by the macos-arm64 job; requires the trusted Native Seed")
    else:
        for target, field in (("linux-amd64", "linux_modules"), ("macos-arm64", "macos_modules")):
            names = [name for name, m in modules.items()
                     if usable(m, target) and m.get("engine", "native") != "native" and not m.get("standalone")]
            if not names:
                raise ValueError("no executable supplementary module for " + target)
            result[field] = ",".join(names)
        result.update(executed_native_modules=[], deferred_native_modules=native_modules)
        result["native_verification"] = dict(status="NOT_RUN", state="deferred", reason=DEFERRED_REASON, modules=native_modules)
    return result


def announce(result):
    """Make the Native Verification state impossible to miss next to a green supplementary gate."""
    verification = result.get("native_verification", {})
    lines = ["### Mio CI gate: " + result["status"], "",
             "| Check | Status |", "|---|---|"]
    lines += ["| %s | %s |" % (c["name"], c["status"]) for c in result["checks"]]
    lines += ["| **Native Verification** | **%s** |" % verification.get("status", "?"), ""]
    if result.get("note"):
        lines.append(result["note"])
    if verification.get("status") == "NOT_RUN":
        lines.append("Native Verification is NOT_RUN: " + verification.get("reason", ""))
        print("::warning title=Native Verification NOT_RUN::" + verification.get("reason", ""))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "gate", "full"))
    parser.add_argument("--base")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--infrastructure", default="")
    parser.add_argument("--native", default="")
    parser.add_argument("--reference", default="")
    parser.add_argument("--macos", default="")
    parser.add_argument("--native-verification", choices=("enabled", "deferred"))
    parser.add_argument("--infrastructure-results", type=Path)
    parser.add_argument("--native-results", type=Path)
    parser.add_argument("--reference-results", type=Path)
    parser.add_argument("--macos-results", type=Path)
    args = parser.parse_args()
    code = 0
    try:
        if args.command == "plan":
            if not args.base:
                raise ValueError("--base is required")
            result = make_plan(args.base, args.head, args.native_verification)
            if os.environ.get("GITHUB_OUTPUT"):
                with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
                    for field in ("native_modules", "reference_modules"):
                        stream.write(field + "=" + ",".join(result[field]) + "\n")
                    stream.write("macos_modules=" + ",".join(result["macos_modules"]) + "\n")
                    stream.write("native_verification=" + result["native_verification"] + "\n")
                    stream.write("native_needs_go=" + str(result["native_needs_go"]).lower() + "\n")
        elif args.command == "full":
            result = full_plan(runner.discover(), native_verification_state(args.native_verification))
            if os.environ.get("GITHUB_OUTPUT"):
                with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
                    for field in ("linux_modules", "macos_modules"):
                        stream.write(field + "=" + result[field] + "\n")
        else:
            plan = json.loads(args.plan.read_text(encoding="utf-8"))
            if plan["source_sha"] != git("rev-parse", "HEAD").decode().strip():
                raise ValueError("plan belongs to another source revision")
            result = gate(plan, args.infrastructure, args.native, args.reference, args.macos)
            for name, directory, expected, target in (
                    ("infrastructure", args.infrastructure_results, ["quality"], "linux-amd64"),
                    ("native", args.native_results, plan["native_modules"], "macos-arm64"),
                    ("reference", args.reference_results, plan["reference_modules"], "linux-amd64"),
                    ("macos", args.macos_results, plan.get("macos_modules", []), "macos-arm64")):
                if expected and getattr(args, name) == "success":
                    result["checks"].append(dict(name=name + "-evidence", **evidence(directory, expected, target, plan["source_sha"])))
            result["status"] = combine(result["checks"])
            code = {"PASS": 0, "FAIL": 1, "NOT_RUN": 2}[result["status"]]
            announce(result)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as error:
        result, code = dict(status="NOT_RUN", reason=str(error)), 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
