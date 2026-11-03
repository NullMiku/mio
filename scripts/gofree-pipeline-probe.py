#!/usr/bin/env python3
"""Isolated audit of the GF2 pure-Mio in-process pipeline; not a release builder."""
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
p.add_argument('--frontend', type=Path, required=True)
p.add_argument('--backend', type=Path, required=True)
p.add_argument('--corpus', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=False)
commands = []

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(label, argv, cwd=root, stdin=None, timeout=180, isolated=False):
    argv = list(map(str, argv))
    start = time.monotonic()
    if stdin is not None:
        (out / (label + '.stdin')).write_bytes(stdin)
    with (out / (label + '.stdout')).open('wb') as stdout, (out / (label + '.stderr')).open('wb') as stderr:
        proc = subprocess.Popen(['/usr/bin/time', '-l', *argv], cwd=cwd,
                                env={'PATH': ''} if isolated else None,
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
                     'wall_seconds': time.monotonic() - start,
                     'stdin': label + '.stdin' if stdin is not None else None,
                     'environment': {'PATH': ''} if isolated else 'inherited audit environment'})
    (out / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
    return code, (out / (label + '.stdout')).read_bytes()

def sandbox(executable, directory, output=None, diagnostic=None):
    policy = directory / ('sandbox-' + hashlib.sha256(str(executable).encode()).hexdigest()[:12] + '.sb')
    contents = '(version 1)(allow default)(deny process-fork)(deny process-exec)'
    contents += '(allow process-exec (literal ' + json.dumps(str(executable)) + '))'
    if output is not None:
        contents += '(deny file-write*)'
        for path in [output, diagnostic, Path('/dev/stderr'), Path('/dev/fd/2')]:
            if path is not None:
                contents += '(allow file-write* (literal ' + json.dumps(str(path)) + '))'
    policy.write_text(contents + '\n')
    return ['/usr/bin/sandbox-exec', '-f', policy, executable]

def request(entry, destination, heap=None, stress=False, project_root=root):
    fields = [str(project_root), str(entry), str(root / 'bunko'), str(destination)]
    if heap is not None:
        fields += [str(heap), 'stress' if stress else 'normal']
    return ('\n'.join(fields) + '\n').encode()

def sign(label, unsigned):
    signed = unsigned.with_suffix('.native')
    shutil.copy2(unsigned, signed)
    signed.chmod(0o755)
    code, _ = run(label + '-sign', ['/usr/bin/codesign', '--force', '--sign', '-', signed])
    verify, _ = run(label + '-verify', ['/usr/bin/codesign', '--verify', '--strict', signed])
    assert code == verify == 0
    return signed

inputs = sorted(set(root.glob('bunko/**/*.mio')) | set(root.glob('selfhost/**/*.mio')))
(out / 'source-manifest.json').write_text(json.dumps([
    {'path': str(x.relative_to(root)), 'sha256': digest(x)} for x in inputs
], indent=2) + '\n')
bootstrap = out / 'bootstrap'
bootstrap.mkdir()
ir = bootstrap / 'compiler.mochi'
frontend, backend = a.frontend.resolve(), a.backend.resolve()
code, stdout = run('bootstrap-frontend', sandbox(frontend, bootstrap), bootstrap,
                   stdin=request('selfhost/native-driver', ir), isolated=True)
assert code == 0 and not stdout and ir.exists(), 'native frontend could not compile the combined driver'
unsigned = bootstrap / 'compiler.unsigned'
(bootstrap / 'input.config').write_text(str(ir))
(bootstrap / 'output.config').write_text(str(unsigned))
code, stdout = run('bootstrap-backend', sandbox(backend, bootstrap), bootstrap, isolated=True)
assert code == 0 and stdout.startswith(b'native-aot: ok\n') and unsigned.exists()
compiler = sign('compiler', unsigned)
(out / 'provenance.json').write_text(json.dumps({
    'initial_frontend': str(frontend), 'initial_frontend_sha256': digest(frontend),
    'initial_backend': str(backend), 'initial_backend_sha256': digest(backend),
    'compiler_unsigned_sha256': digest(unsigned), 'compiler_signed_sha256': digest(compiler),
    'bootstrap_ir_sha256': digest(ir), 'source_manifest_sha256': digest(out / 'source-manifest.json'),
    'scope': 'GF2 development candidate; external signing is isolated audit, GF3 signer pending',
}, indent=2) + '\n')

results = []
corpus_results = json.loads((a.corpus / 'results.json').read_text())
names = [str(x['case']) for x in corpus_results if (a.corpus / str(x['case']) / 'case.mio').is_file()]
for name in names:
    for stress in [False, True]:
        label = name + ('-stress' if stress else '-normal')
        directory = out / label
        directory.mkdir()
        src = directory / 'case.mio'
        src.write_bytes((a.corpus / name / 'case.mio').read_bytes())
        target = directory / 'application.unsigned'
        before = sorted(x.name for x in directory.iterdir())
        code, stdout = run(label + '-build', sandbox(compiler, directory, target, out / (label + '-build.stderr')), directory,
                           stdin=request(src, target, 8 << 20, stress), isolated=True)
        produced_ir = list(directory.glob('*.mochi'))
        result = {'case': name, 'gc_stress': stress, 'build_exit': code,
                  'temporary_ir': [str(x) for x in produced_ir], 'files_before': before,
                  'files_after': sorted(x.name for x in directory.iterdir()), 'status': 'FAIL_BUILD'}
        if code == 0 and not stdout and target.exists() and not produced_ir:
            program = sign(label, target)
            ncode, nout = run(label + '-native', [program], directory, isolated=True)
            expected = (a.corpus / (name + '-vm.stdout')).read_bytes()
            result.update(native_exit=ncode, stdout_equal=nout == expected,
                          unsigned_sha256=digest(target), signed_sha256=digest(program))
            expected_exit = 1 if name == 'last-composite' else 0
            diagnostic_ok = expected_exit == 0 or b'cannot display' in (out / (label + '-native.stderr')).read_bytes()
            result['status'] = 'PASS' if ncode == expected_exit and nout == expected and diagnostic_ok else 'FAIL_EXECUTION'
        results.append(result)
        (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
        print(label, result['status'], flush=True)

for name, source in [('syntax', b'kaku = ;'), ('type', b'kaku x: int64 = "bad";'), ('resolve', b'chant(unknown);')]:
    directory = out / name
    directory.mkdir()
    src = directory / 'case.mio'
    src.write_bytes(source)
    target = directory / 'should-not-exist'
    code, stdout = run(name + '-build', sandbox(compiler, directory, target, out / (name + '-build.stderr')), directory,
                       stdin=request(src, target), isolated=True)
    stderr = (out / (name + '-build.stderr')).read_bytes()
    diagnostic_present = str(src).encode() in stderr and (b'E_' in stderr or b'E0301' in stderr)
    result = {'case': name, 'exit': code,
              'status': 'PASS' if code not in (None, 0) and not stdout and not target.exists() and diagnostic_present else 'FAIL'}
    results.append(result)
    (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(name, result['status'], flush=True)

fixtures = [
    ('nullable-array-make', '''yobu "kiso/array";
kaku value: int64 = 7; kaku nullable: int64? = value; nullable = mu;
kaku values = array.make[int64](2, value); chant(values[0]);
''', 8 << 20, True, 0, b'7\n'),
    ('native-fs-map-offset', '''yobu "kiso/fs"; yobu "kiso/string";
waza run() -> unit {
 kaku offsets = Map[string, int64](); offsets["start"] = 0;
 kaku offset = offsets["start"];
 moshi (offset != mu) {
  kaku opened = fs.open_write("mapped.txt"); kaku file = opened.file;
  moshi (file != mu) {
   kaku written = fs.write(file, string.to_bytes("ok"), offset, 2);
   chant(written.error == mu); chant(written.count); fs.close(file);
  }
 }
} run();
''', 8 << 20, True, 0, b'hai\n2\n'),
    ('native-fs', '''yobu "kiso/fs"; yobu "kiso/string";
kaku written = fs.write_all("payload.txt", string.to_bytes("payload")); chant(written.error == mu);
kaku loaded = fs.read_all("payload.txt"); chant(loaded.error == mu);
kaku text = string.from_utf8(loaded.data); moshi (text != mu) { chant(text == "payload"); }
''', 8 << 20, True, 0, b'hai\nhai\nhai\n'),
    ('los-alias', '''yobu "kiso/array";
kaku values = array.make[uint8](131072, uint8(211)); kaku alias = values;
kaku index = 0; aida (index < 24) {
    kaku churn = array.make[uint8](16384, uint8(index)); values[131071] = churn[0]; index = index + 1;
} chant(alias[0]); chant(alias[131071]);
''', 8 << 20, True, 0, b'211\n23\n'),
    ('oom', '''yobu "kiso/array"; kaku values = array.make[uint8](2097152, uint8(7)); chant(values[0]);
''', 65536, False, 2, b''),
]
for name, source, heap, stress, expected_code, expected_stdout in fixtures:
    directory = out / name
    directory.mkdir()
    src = directory / 'case.mio'
    src.write_text(source)
    target = directory / 'application.unsigned'
    code, stdout = run(name + '-build', sandbox(compiler, directory, target, out / (name + '-build.stderr')), directory,
                       stdin=request(src, target, heap, stress), isolated=True)
    result = {'case': name, 'build_exit': code, 'status': 'FAIL_BUILD'}
    if code == 0 and not stdout and target.exists() and not list(directory.glob('*.mochi')):
        program = sign(name, target)
        ncode, nout = run(name + '-native', [program], directory, isolated=True)
        result.update(native_exit=ncode, unsigned_sha256=digest(target))
        result['status'] = 'PASS' if ncode == expected_code and nout == expected_stdout else 'FAIL_EXECUTION'
    results.append(result)
    (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(name, result['status'], flush=True)

directory = out / 'multi'
(directory / 'sample/lib').mkdir(parents=True)
(directory / 'sample/app').mkdir()
(directory / 'sample/lib/one.mio').write_text('koukai teisu amount = 6; koukai waza twice(value: int64) -> int64 { kaesu value * 2; }\n')
(directory / 'sample/app/one.mio').write_text('yobu "sample/lib"; chant(lib.twice(lib.amount));\n')
(directory / 'sample/app/two.mio').write_text('waza unused() -> unit {}\n')
target = directory / 'application.unsigned'
code, stdout = run('multi-build', sandbox(compiler, directory, target, out / 'multi-build.stderr'), directory,
                   stdin=request('sample/app', target, 8 << 20, True, directory), isolated=True)
result = {'case': 'multi-module', 'build_exit': code, 'status': 'FAIL_BUILD'}
if code == 0 and not stdout and target.exists() and not list(directory.glob('*.mochi')):
    program = sign('multi', target)
    ncode, nout = run('multi-native', [program], directory, isolated=True)
    result.update(native_exit=ncode, unsigned_sha256=digest(target))
    result['status'] = 'PASS' if ncode == 0 and nout == b'12\n' else 'FAIL_EXECUTION'
results.append(result)
(out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
print('multi-module', result['status'], flush=True)
raise SystemExit(0 if all(x['status'] == 'PASS' for x in results) else 1)
