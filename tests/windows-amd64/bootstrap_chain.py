#!/usr/bin/env python3
"""Stage 4 evidence: Windows bootstrap chain of selfhost/windows-compiler (parser + resolver + typecheck + codegen +
lowerwinrt), recorded generation by generation.

  A      produced by the reference-VM-hosted pure-Mio lowering (trusted start = Go reference VM; there is NO trusted Native
         Seed, so a seed bootstrap is NOT_RUN and A is only as trusted as the reference VM)
  B C D  B = A(sources), C = B(sources), D = C(sources), each run natively on the host given by --execute / --emulate
  A_gc   A rebuilt with a 64 KiB GC threshold (collection pressure); A_gc(sources) must equal B

Checks (none is relaxed on a mismatch):
  * B == C == D byte for byte (A != B is expected and only recorded: A's Mochi came from the Go frontend)
  * A_gc(sources) == B                      (collector pressure does not change the result)
  * every generation (A B C D A_gc) compiles every application; the produced images are byte-identical across generations,
    are run, and match the Go VM's stdout/exit status; diagnostics for a syntax error, a type error and a missing module
    have a non-zero exit, a message on stderr and no image
  * all runs use an empty PATH; the compile path imports no os/process package; produced images import only KERNEL32.dll
--execute = Windows (required for a Windows PASS); --emulate = unicorn model, a development aid that is never Windows."""
import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_pe
import verify_pe

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
COMPILER = ROOT / "selfhost" / "windows-compiler" / "main.mio"
ENTRY = "selfhost/windows-compiler"
APPS = ROOT / "tests" / "windows-amd64" / "apps"
APP_PREFIX = "tests/windows-amd64/apps/"
RUN_APPS = ["hello", "structs", "modules", "gcstress", "fsio"]
BAD_APPS = ["broken", "typeerror", "missingmodule"]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def tree_files():
    files = {}
    for top in ("bunko", "selfhost", "tests/windows-amd64/apps"):
        for p in sorted((ROOT / top).rglob("*.mio")):
            if not p.name.endswith("_test.mio"):
                files[p.relative_to(ROOT).as_posix()] = p.read_bytes()
    return files


def package_closure(entry):
    """Import closure of a package by reading `yobu "..."` lines (independent of the Mio frontend)."""
    seen, todo = {}, [entry]
    while todo:
        pkg = todo.pop()
        if pkg in seen:
            continue
        base = ROOT / ("bunko/" + pkg if pkg.startswith("kiso/") else pkg)
        files = [p for p in sorted(base.glob("*.mio")) if not p.name.endswith("_test.mio")]
        seen[pkg] = files
        for p in files:
            for m in re.finditer(r'^\s*yobu\s+"([^"]+)"', p.read_text(encoding="utf-8"), re.M):
                todo.append(m.group(1))
    return seen


def independence_scan():
    """The compile path must not import OS/process packages or call process-spawning natives."""
    closure = package_closure(ENTRY)
    findings = []
    for pkg, files in closure.items():
        if pkg == "kiso/os" or pkg.startswith("mio/os"):
            findings.append("imports %s" % pkg)  # mio/fs/runtime (file access) is expected and allowed
        for p in files:
            text = p.read_text(encoding="utf-8")
            if re.search(r"\bos\.(spawn|exec|spawn_test)\s*\(", text) or re.search(r"\bruntime\.(spawn|exec|spawn_test)\s*\(", text):
                findings.append("%s calls a process-spawning function" % p.relative_to(ROOT).as_posix())
    return dict(packages=len(closure), files=sum(len(f) for f in closure.values()), findings=findings)


def base_env(tmp):
    env = {"PATH": str(tmp)}
    for key in ("SystemRoot", "SYSTEMROOT", "TEMP", "TMP", "windir"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


FROZEN = {}


def compile_with(mode, exe_path, exe_bytes, entry, output_rel, logdir, label, env):
    request = (entry + "\n" + output_rel + "\n").encode()
    started = time.monotonic()
    out_path = ROOT / output_rel
    if mode == "windows":
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.unlink(missing_ok=True)
        r = subprocess.run([str(exe_path)], cwd=ROOT, input=request, capture_output=True, timeout=7200, env=env)
        code, out, err, violations = r.returncode, r.stdout, r.stderr, []
        produced = out_path.read_bytes() if out_path.exists() else b""
    else:
        import emu
        files = {k: bytearray(v) for k, v in FROZEN.items()}
        e = emu.Emu(exe_bytes, files=files, stack_size=64 * 1024 * 1024, max_instructions=2_000_000_000_000, stdin=request)
        code, out, err, violations = e.run()
        produced = bytes(files.get(output_rel, b""))
    logdir.mkdir(parents=True, exist_ok=True)
    stem = "%s--%s" % (label, entry.replace("/", "_"))
    (logdir / (stem + ".stdout.log")).write_bytes(out)
    (logdir / (stem + ".stderr.log")).write_bytes(err)
    return dict(label=label, entry=entry, command=[str(exe_path.name)], stdin=request.decode(), cwd="repository root", runner=mode,
                exit_code=code, stdout=out.decode("utf-8", "replace"), stderr=err.decode("utf-8", "replace"), violations=violations,
                seconds=round(time.monotonic() - started, 1), compiler_sha256=sha(exe_bytes),
                output_sha256=sha(produced) if produced else None, output_size=len(produced),
                logs=[stem + ".stdout.log", stem + ".stderr.log"]), produced


def run_image(mode, data, path, cwd, env):
    if mode == "windows":
        r = subprocess.run([str(path)], capture_output=True, timeout=300, cwd=cwd, env=env)
        return r.returncode, r.stdout, r.stderr, []
    import emu
    return emu.Emu(data).run()


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
    try:
        rel = out.relative_to(ROOT).as_posix()
    except ValueError:
        rel = "build/bootstrap-chain"
        out = ROOT / rel
        out.mkdir(parents=True, exist_ok=True)
    logs = out / "logs"
    tmp_path = tempfile.mkdtemp(prefix="empty-path-")
    env = base_env(Path(tmp_path))
    files = tree_files()
    FROZEN.update(files)
    report = dict(
        mode=mode, stage="4: bootstrap evidence for selfhost/windows-compiler (NOT selfhost/cli)",
        trusted_start="Go reference VM hosting the pure-Mio lowering; NO trusted Native Seed: seed bootstrap NOT_RUN",
        selfhost_cli="NOT_RUN", seed_bootstrap="NOT_RUN",
        host=dict(system=platform.system(), release=platform.release(), machine=platform.machine(), python=platform.python_version()),
        git_head=subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
        refvm_sha256=sha(o.refvm.read_bytes()) if o.refvm.exists() else None,
        source_tree=dict(files=len(files), sha256=sha(b"".join(k.encode() + b"\0" + sha(v).encode() + b"\n" for k, v in sorted(files.items())))),
        compiler_source_sha256=sha(COMPILER.read_bytes()), env_path="empty directory (no external tool can be found)",
        generations=[], applications={}, checks={}, failures=[])
    path = out / "bootstrap-report.json"
    try:
        scan = independence_scan()
        report["checks"]["compile_path_independence"] = scan
        if scan["findings"]:
            report["failures"].append("compile path is not independent of OS/process packages: %s" % scan["findings"][:5])
        gens = {}
        exe_a = out / "A.exe"
        ok, message = build_pe.build(o.refvm, COMPILER, exe_a, "lowerwinrt")
        if not ok:
            raise RuntimeError("A: " + message[:300])
        gens["A"] = (exe_a.read_bytes(), exe_a)
        report["generations"].append(dict(label="A", producer="reference VM + pure-Mio lowerwinrt (threshold 32 MiB)", output_sha256=sha(gens["A"][0]), output_size=len(gens["A"][0]),
                                          command="build_pe.py --backend lowerwinrt selfhost/windows-compiler/main.mio", input_source_sha256=report["compiler_source_sha256"]))
        exe_g = out / "A_gc.exe"
        ok, message = build_pe.build(o.refvm, COMPILER, exe_g, "lowerwinrt", gc_threshold=65536)
        if not ok:
            raise RuntimeError("A_gc: " + message[:300])
        gens["A_gc"] = (exe_g.read_bytes(), exe_g)
        report["generations"].append(dict(label="A_gc", producer="reference VM + pure-Mio lowerwinrt (GC threshold 64 KiB)", output_sha256=sha(gens["A_gc"][0]), output_size=len(gens["A_gc"][0])))
        chain = ["A"]
        for label in ("B", "C", "D"):
            previous = chain[-1]
            record, produced = compile_with(mode, gens[previous][1], gens[previous][0], ENTRY, "%s/%s.exe" % (rel, label), logs, "%s-from-%s" % (label, previous), env)
            record.update(label=label, producer=previous, input_source_sha256=report["source_tree"]["sha256"])
            report["generations"].append(record)
            if not (record["exit_code"] == 0 and record["stdout"] == "windows-compiler: ok\n" and record["stderr"] == "" and not record["violations"] and produced):
                report["failures"].append("%s: generation failed (exit %s, stderr %r)" % (label, record["exit_code"], record["stderr"][:300]))
                break
            (out / (label + ".exe")).write_bytes(produced)
            gens[label] = (produced, out / (label + ".exe"))
            chain.append(label)
        record, produced = compile_with(mode, exe_g, gens["A_gc"][0], ENTRY, "%s/Bgc.exe" % rel, logs, "Bgc-from-A_gc", env)
        record.update(label="Bgc", producer="A_gc")
        report["generations"].append(record)
        report["checks"]["gc_pressure_compiler_output_equals_B"] = bool(produced) and "B" in gens and produced == gens["B"][0]
        if not report["checks"]["gc_pressure_compiler_output_equals_B"]:
            report["failures"].append("A_gc (64 KiB GC threshold) output differs from B or failed: exit %s" % record["exit_code"])
        hashes = {k: sha(v[0]) for k, v in gens.items()}
        report["checks"]["generation_hashes"] = hashes
        report["checks"]["A_equals_B"] = hashes.get("A") == hashes.get("B")
        report["checks"]["B_C_D_identical"] = all(k in hashes for k in "BCD") and len({hashes["B"], hashes["C"], hashes["D"]}) == 1
        if not report["checks"]["B_C_D_identical"]:
            report["failures"].append("fixed point not reached: %s" % hashes)
        # every generation compiles and runs every application
        expected = {}
        for app in RUN_APPS:
            with tempfile.TemporaryDirectory() as vm_cwd:  # the VM oracle must not leave files in the checkout
                r = subprocess.run(build_pe.frontend_command(o.refvm, "run", APPS / app / "main.mio"), cwd=vm_cwd, capture_output=True, timeout=900)
            expected[app] = (0 if r.returncode == 0 else 1, r.stdout)
        images = {app: {} for app in RUN_APPS}
        for label in [g for g in ("A", "B", "C", "D", "A_gc") if g in gens]:
            exe_bytes, exe_path = gens[label]
            for app in RUN_APPS + BAD_APPS:
                output_rel = "%s/apps-%s/%s.exe" % (rel, label, app)
                record, produced = compile_with(mode, exe_path, exe_bytes, APP_PREFIX + app, output_rel, logs, "%s-app" % label, env)
                entry = report["applications"].setdefault(app, {})
                entry[label] = dict(compile_exit=record["exit_code"], compile_stderr=record["stderr"][:300], pe_sha256=sha(produced) if produced else None)
                if app in BAD_APPS:
                    good = record["exit_code"] != 0 and "windows-compiler" in record["stderr"] and not produced
                    entry[label]["diagnostic_ok"] = good
                    if not good:
                        report["failures"].append("%s compiling %s: expected a diagnostic, non-zero exit and no image (exit %s)" % (label, app, record["exit_code"]))
                    continue
                if not produced:
                    report["failures"].append("%s compiling %s: no image (exit %s, %r)" % (label, app, record["exit_code"], record["stderr"][:200]))
                    continue
                img = out / ("apps-%s-%s.exe" % (label, app))
                img.write_bytes(produced)
                try:
                    verify_pe.verify(produced, expect_relocations=False)
                    imports_ok = b"KERNEL32.dll" in produced and not any(x in produced.lower() for x in (b"msvcrt", b"ucrtbase", b"vcruntime", b"user32", b"ntdll"))
                except Exception as error:
                    report["failures"].append("%s %s: PE structure: %s" % (label, app, error))
                    imports_ok = False
                if not imports_ok:
                    report["failures"].append("%s %s: image imports something besides KERNEL32.dll" % (label, app))
                code, so, se, viol = run_image(mode, produced, img, out, env)
                want = expected[app]
                ran_ok = code == want[0] and so == want[1] and not viol and (se == b"")
                entry[label].update(exit_code=code, stdout_matches_vm=so == want[1], stderr=se.decode("utf-8", "replace")[:200], run_ok=ran_ok)
                if not ran_ok:
                    report["failures"].append("%s %s: run mismatch (exit %s, stdout_ok=%s, stderr=%r)" % (label, app, code, so == want[1], se[:100]))
                images[app][label] = sha(produced)
        for app, by in images.items():
            same = len(set(by.values())) == 1 and len(by) == len([g for g in gens])
            report["applications"][app]["identical_across_generations"] = same
            if not same:
                report["failures"].append("app %s: images differ between generations: %s" % (app, by))
    except Exception as error:
        report["failures"].append("%s: %s" % (type(error).__name__, error))
    now = tree_files()
    if sha(b"".join(k.encode() + b"\0" + sha(v).encode() + b"\n" for k, v in sorted(now.items()))) != report["source_tree"]["sha256"]:
        report["failures"].append("the source tree changed while the chain was running: the evidence is void")
    report["result"] = "PASS" if not report["failures"] and report["checks"].get("B_C_D_identical") else "FAIL"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("mode", "stage", "result", "failures", "selfhost_cli", "seed_bootstrap")}, indent=2))
    print(json.dumps(report["checks"].get("generation_hashes", {}), indent=2))
    sys.exit(0 if report["result"] == "PASS" else 1)


if __name__ == "__main__":
    main()
