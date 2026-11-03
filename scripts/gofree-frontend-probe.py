#!/usr/bin/env python3
"""Run the GF1 source frontend natively, with process execution denied.

GF1 development uses the Go reference to build the initial driver IR. This
probe records that provenance and never presents it as GF4 source bootstrap.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--backend', type=Path, required=True)
p.add_argument('--gf0', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--all-bunko', action='store_true')
p.add_argument('--extra-corpus', type=Path)
p.add_argument('--stress-target-backend', type=Path)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
backend = a.backend.resolve()
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=False)
reference = root / 'build/gofree-evidence/GF1/mio-reference'
commands = []

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(label, argv, cwd=root, stdin=None, env=None, timeout=120):
    argv = list(map(str, argv))
    started = time.monotonic()
    if stdin is not None:
        (out / (label + '.stdin')).write_bytes(stdin)
    with (out / (label + '.stdout')).open('wb') as stdout, (out / (label + '.stderr')).open('wb') as stderr:
        proc = subprocess.Popen(['/usr/bin/time', '-l', *argv], cwd=cwd, env=env,
                                stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                                stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            proc.communicate(input=stdin, timeout=timeout)
            code = proc.returncode
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
            code = None
    commands.append({'label': label, 'argv': argv, 'cwd': str(cwd), 'exit_code': code,
                     'wall_seconds': time.monotonic() - started,
                     'stdin': label + '.stdin' if stdin is not None else None,
                     'environment': env})
    (out / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
    return code, (out / (label + '.stdout')).read_bytes()

def sandbox(compiler, directory):
    policy = directory / 'sandbox.sb'
    policy.write_text('(version 1)(allow default)(deny process-fork)(deny process-exec)'
                      '(allow process-exec (literal ' + json.dumps(str(compiler)) + '))\n')
    return ['/usr/bin/sandbox-exec', '-f', policy, compiler]

def lower(label, mochi, directory, stress_target=False):
    image = directory / 'image.unsigned'
    (directory / 'input.config').write_text(str(mochi))
    (directory / 'output.config').write_text(str(image))
    compiler = a.stress_target_backend.resolve() if stress_target and a.stress_target_backend else backend
    code, stdout = run(label + '-lower', sandbox(compiler, directory), directory, env={'PATH': ''})
    if code != 0 or not stdout.startswith(b'native-aot: ok\n') or not image.exists():
        return None
    signed = directory / 'image.native'
    shutil.copy2(image, signed)
    signed.chmod(0o755)
    code, _ = run(label + '-sign', ['/usr/bin/codesign', '--force', '--sign', '-', signed])
    verify, _ = run(label + '-verify', ['/usr/bin/codesign', '--verify', '--strict', signed])
    assert code == verify == 0
    return signed

manifest = [{'path': str(x.relative_to(root)), 'sha256': digest(x)}
            for x in sorted(set(root.glob('bunko/**/*.mio')) | set(root.glob('selfhost/**/*.mio')))]
(out / 'source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
driver_dir = out / 'driver'
driver_dir.mkdir()
driver_ir = driver_dir / 'driver.mochi'
code, _ = run('driver-reference-build', [reference, 'build', root / 'selfhost/frontend-driver', '-o', driver_ir])
assert code == 0
driver = lower('driver', driver_ir, driver_dir)
assert driver is not None, 'driver lowering failed'
(out / 'provenance.json').write_text(json.dumps({
    'backend': str(backend), 'backend_sha256': digest(backend),
    'driver_reference_ir_sha256': digest(driver_ir), 'driver_native_sha256': digest(driver),
    'source_manifest_sha256': digest(out / 'source-manifest.json'),
    'scope': 'GF1 native frontend probe, not GF4 source bootstrap',
}, indent=2) + '\n')
results = []

def compile_source(label, entry, destination, cwd, project_root=root, bunko_root=None):
    request = '\n'.join([str(project_root), str(entry), str(bunko_root or project_root / 'bunko'), str(destination), '']).encode()
    return run(label, sandbox(driver, cwd), cwd, stdin=request, env={'PATH': ''})

cases = [(i, a.gf0 / f'corpus/{i}/case.mio', a.gf0 / f'corpus/{i}/case.mochi') for i in range(16)]
if a.extra_corpus:
    for name in ['map-empty', 'map-empty-mixed', 'map-values', 'map-containers', 'map-then-call',
                 'generic-numeric', 'generic-recursive', 'float-output', 'nullable-operands', 'array-scalar-storage', 'math-primitives', 'last-string-gc', 'last-bool', 'last-float', 'last-nil', 'last-nullable', 'last-nullable-nil', 'last-composite', 'integer-boundaries']:
        cases.append((name, a.extra_corpus / name / 'case.mio', a.extra_corpus / name / 'case.mochi'))
for i, input_source, reference_ir in cases:
    name = str(i)
    directory = out / name
    directory.mkdir()
    src = directory / 'case.mio'
    src.write_bytes(input_source.read_bytes())
    mochi = directory / 'pure.mochi'
    code, stdout = compile_source(name + '-frontend', src, mochi, directory)
    result = {'case': i, 'frontend_exit': code, 'status': 'FAIL_FRONTEND', 'stdout': stdout.decode(errors='replace')}
    if code == 0 and mochi.is_file():
        result['mochi_sha256'] = digest(mochi)
        vmcode, vmout = run(name + '-pure-vm', [reference, 'exec', mochi])
        refcode, refout = run(name + '-reference-vm', [reference, 'exec', reference_ir.resolve()])
        native = lower(name, mochi, directory, stress_target=True)
        result.update(pure_vm_exit=vmcode, reference_vm_exit=refcode, vm_stdout_equal=vmout == refout)
        result['status'] = 'FAIL_NATIVE'
        if native is not None:
            ncode, nout = run(name + '-native', [native], directory, env={'PATH': ''})
            result.update(native_exit=ncode, native_stdout_equal=nout == refout)
            expected_exit = 1 if name == 'last-composite' else 0
            diagnostic_ok = expected_exit == 0 or b'cannot display' in (out / (name + '-native.stderr')).read_bytes()
            result['status'] = 'PASS' if code == 0 and vmcode == refcode == ncode == expected_exit and stdout == b'' and vmout == nout == refout and diagnostic_ok else 'FAIL'
    results.append(result)
    (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(i, result['status'], flush=True)

for name, source in [('syntax-error', b'kaku = ;'), ('type-error', b'kaku x: int64 = "bad";'),
                     ('resolve-error', b'chant(unknown);')]:
    directory = out / name
    directory.mkdir()
    src = directory / 'case.mio'
    src.write_bytes(source)
    mochi = directory / 'pure.mochi'
    code, stdout = compile_source(name, src, mochi, directory)
    stderr = (out / (name + '.stderr')).read_text()
    result = {'case': name, 'exit': code, 'output_exists': mochi.exists(),
              'status': 'PASS' if code not in (None, 0) and not stdout and not mochi.exists() and str(src) in stderr else 'FAIL'}
    results.append(result)
    print(name, result['status'], flush=True)
    (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')

directory = out / 'bootstrap'
directory.mkdir()
mochi = directory / 'compiler.mochi'
code, stdout = compile_source('bootstrap', 'selfhost/bootstrap', mochi, directory, a.gf0.resolve() / 'source')
golden = 'b44a55bf3f9020e6b0ff83ad137b25774814a32dfe8acaf070abcd167bfd1465'
result = {'case': 'historical-bootstrap', 'exit': code, 'sha256': digest(mochi) if mochi.exists() else None}
result['status'] = 'PASS' if code == 0 and not stdout and result['sha256'] == golden else 'FAIL'
results.append(result)
(out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
print('historical-bootstrap', result['status'], flush=True)

for entry in ['selfhost/frontend-driver', 'selfhost/native-aot']:
    label = entry.rsplit('/', 1)[-1]
    directory = out / label
    directory.mkdir()
    mochi = directory / 'pure.mochi'
    code, stdout = compile_source(label + '-source', entry, mochi, directory)
    native = lower(label, mochi, directory) if code == 0 and mochi.exists() else None
    result = {'case': entry, 'exit': code, 'status': 'PASS' if native is not None and not stdout else 'FAIL',
              'mochi_sha256': digest(mochi) if mochi.exists() else None,
              'native_sha256': digest(native) if native else None}
    results.append(result)
    (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(entry, result['status'], flush=True)

directory = out / 'multi'
(directory / 'sample/lib').mkdir(parents=True)
(directory / 'sample/app').mkdir()
(directory / 'sample/lib/one.mio').write_text('koukai teisu amount = 6; koukai kata Result { value: string; } koukai waza twice(value: int64) -> int64 { kaesu value * 2; }\n')
(directory / 'sample/app/one.mio').write_text('yobu "sample/lib"; kata Result { value: int64?; } kaku empty = Result { value: mu }; chant(empty.value == mu); chant(lib.twice(lib.amount));\n')
(directory / 'sample/app/two.mio').write_text('waza unused() -> unit {}\n')
mochi = directory / 'pure.mochi'
code, stdout = compile_source('multi', 'sample/app', mochi, directory, directory, root / 'bunko')
native = lower('multi', mochi, directory, stress_target=True) if code == 0 and mochi.exists() else None
ncode, nout = run('multi-native', [native], directory, env={'PATH': ''}) if native else (None, b'')
result = {'case': 'multi-file-module', 'exit': code, 'native_exit': ncode,
          'status': 'PASS' if code == ncode == 0 and not stdout and nout == b'hai\n12\n' else 'FAIL'}
results.append(result)
(out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
print('multi-file-module', result['status'], flush=True)
for label, assertions, expected_code, expected_stderr in [
    ('testing-pass', 'testing.expect(hai, "unused");', 0, b''),
    ('testing-fail', 'testing.expect(iie, "first failure"); testing.fail("second failure");', 1,
     b'first failure\nsecond failure\n'),
]:
    directory = out / label
    directory.mkdir()
    src = directory / 'case.mio'
    src.write_text('yobu "kiso/testing"; ' + assertions + ' chant("continued");\n')
    mochi = directory / 'pure.mochi'
    code, stdout = compile_source(label + '-frontend', src, mochi, directory)
    native = lower(label, mochi, directory, stress_target=True) if code == 0 and mochi.exists() else None
    ncode, nout = run(label + '-native', [native], directory, env={'PATH': ''}) if native else (None, b'')
    stderr = (out / (label + '-native.stderr')).read_bytes() if native else b''
    # /usr/bin/time appends resource statistics after the program stderr.
    stderr_ok = stderr.startswith(expected_stderr) if expected_stderr else b'failure' not in stderr
    result = {'case': label, 'exit': code, 'native_exit': ncode,
              'status': 'PASS' if code == 0 and not stdout and ncode == expected_code and nout == b'continued\n' and stderr_ok else 'FAIL'}
    results.append(result)
    (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(label, result['status'], flush=True)
if a.all_bunko:
    modules = sorted({x.parent.relative_to(root / 'bunko').as_posix()
                      for x in (root / 'bunko').rglob('*.mio') if not x.name.endswith('_test.mio')})
    for index, entry in enumerate(modules):
        directory = out / ('bunko-' + str(index))
        directory.mkdir()
        mochi = directory / 'pure.mochi'
        code, stdout = compile_source('bunko-' + str(index), entry, mochi, directory)
        result = {'case': entry, 'exit': code,
                  'status': 'PASS' if code == 0 and not stdout and mochi.exists() else 'FAIL',
                  'mochi_sha256': digest(mochi) if mochi.exists() else None}
        results.append(result)
        (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
        print(entry, result['status'], flush=True)
raise SystemExit(0 if all(x['status'] == 'PASS' for x in results) else 1)
