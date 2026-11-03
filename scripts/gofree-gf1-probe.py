#!/usr/bin/env python3
"""GF1 backend differential probe; reference Go is allowed only during GF1.

This does NOT certify the native frontend or any complete GF phase. Each run
uses a new output directory and retains failed commands and original corpus.
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
p.add_argument('--gf0', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--gc-stress', action='store_true')
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=False)
gf0 = a.gf0.resolve()
reference = root / 'build/gofree-evidence/GF1/mio-reference'
seed = gf0 / 'historical/build/m19c-20261026-fixed-point/stage4.native'
commands = []

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

inputs = sorted(set(root.glob('bunko/**/*.mio')) | set(root.glob('selfhost/**/*.mio')))
(out / 'source-manifest.json').write_text(json.dumps([
    {'path': str(x.relative_to(root)), 'sha256': digest(x)} for x in inputs
], indent=2) + '\n')
(out / 'provenance.json').write_text(json.dumps({
    'seed': str(seed), 'seed_sha256': digest(seed),
    'reference': str(reference), 'reference_sha256': digest(reference),
    'scope': 'native backend only; frontend reference remains Go',
    'source_manifest_sha256': digest(out / 'source-manifest.json'),
}, indent=2) + '\n')

def run(label, argv, cwd=root, env=None, timeout=120):
    argv = list(map(str, argv))
    start = time.monotonic()
    with (out / (label + '.stdout')).open('wb') as stdout, (out / (label + '.stderr')).open('wb') as stderr:
        proc = subprocess.Popen(['/usr/bin/time', '-l', *argv], cwd=cwd,
                                env=env, stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            code = None
    commands.append({'label': label, 'argv': argv, 'cwd': str(cwd),
                     'environment': env, 'exit_code': code,
                     'wall_seconds': time.monotonic() - start})
    (out / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
    return code, (out / (label + '.stdout')).read_bytes()

def lower(label, compiler, mochi, directory):
    (directory / 'input.config').write_text(str(mochi))
    image = directory / 'image.unsigned'
    (directory / 'output.config').write_text(str(image))
    policy = directory / 'sandbox.sb'
    policy.write_text('(version 1)(allow default)(deny process-fork)(deny process-exec)'
                      '(allow process-exec (literal ' + json.dumps(str(compiler)) + '))\n')
    code, stdout = run(label, ['/usr/bin/sandbox-exec', '-f', policy, compiler], directory, {'PATH': ''})
    return code == 0 and stdout.startswith(b'native-aot: ok\n') and image.is_file(), image

def sign(label, unsigned):
    signed = unsigned.with_suffix('.native')
    shutil.copy2(unsigned, signed)
    signed.chmod(0o755)
    code, _ = run(label + '-sign', ['/usr/bin/codesign', '--force', '--sign', '-', signed])
    verify, _ = run(label + '-verify', ['/usr/bin/codesign', '--verify', '--strict', signed])
    assert code == verify == 0, label
    return signed

backend_dir = out / 'backend'
backend_dir.mkdir()
backend_mochi = backend_dir / 'backend.mochi'
driver = root / 'selfhost/native-aot'
if a.gc_stress:
    driver = backend_dir / 'driver.mio'
    driver.write_text((root / 'selfhost/native-aot/main.mio').read_text().replace(
        'lower.compile_with_heap(file, 1073741824, iie)',
        'lower.compile_with_heap(file, 1073741824, hai)'))
code, _ = run('build-backend-reference', [reference, 'build', driver, '-o', backend_mochi])
assert code == 0
ok, unsigned = lower('build-backend-native', seed, backend_mochi, backend_dir)
assert ok, 'historical native seed could not build modified backend'
backend = sign('backend', unsigned)

cases = [(str(i), (gf0 / f'corpus/{i}/case.mio').read_bytes()) for i in range(16)]
cases += [('map-empty', b'''
kaku values = Map[string, int64](); chant(values["absent"] == mu);
'''), ('map-empty-mixed', b'''
kaku empty = Map[string, int64](); kaku other = Map[string, string](); other["key"] = "mio";
chant(empty["absent"] == mu); chant(other["key"] != mu);
'''), ('map-values', b'''
kaku values = Map[string, int64]();
chant(values["absent"] == mu);
values["answer"] = 41;
kaku first = values["answer"]; moshi (first != mu) { chant(first + 1); }
values["answer"] = 7;
kaku second = values["answer"]; moshi (second != mu) { chant(second + 1); }
kaku texts = Map[int64, string](); texts[1] = "mio";
kaku text = texts[1]; moshi (text != mu) { chant(text == "mio"); } chant(texts[2] == mu);
kaku arrays = Map[string, []int64](); arrays["shared"] = [1, 2];
kaku found = arrays["shared"]; moshi (found != mu) { found[0] = 42; }
kaku again = arrays["shared"]; moshi (again != mu) { chant(again[0]); }
kaku index = 0; aida (index < 300) { values["answer"] = index; texts[index] = "retained"; index = index + 1; }
kaku last = values["answer"]; moshi (last != mu) { chant(last + 1); }
kaku retained = texts[1]; moshi (retained != mu) { chant(retained == "retained"); }
'''), ('map-containers', b'''
kata Box { value: int64; }
kaku values = Map[string, Box](); values["answer"] = Box { value: 42 };
kaku maps = [values]; kaku alias = maps[0];
kaku index = 0; aida (index < 100) { alias["answer"] = Box { value: index }; index = index + 1; }
kaku found = values["answer"]; moshi (found != mu) { chant(found.value); }
kaku flags = Map[bool, int64](); flags[hai] = 1; flags[iie] = 2;
kaku yes = flags[hai]; moshi (yes != mu) { chant(yes + 10); }
kaku no = flags[iie]; moshi (no != mu) { chant(no + 10); }
'''), ('map-then-call', b'''
waza next(value: int64) -> int64 { kaesu value + 1; }
kaku values = Map[string, int64](); values["answer"] = 42;
chant(next(4)); chant(values["answer"] != mu); chant(next(5));
'''), ('generic-numeric', b'''
waza twice<T: Number>(value: T) -> T { kaesu value + value; }
chant(twice[int64](7)); chant(twice[float32](float32(1.25)));
'''), ('generic-recursive', b'''
waza repeat<T: Number>(value: T, depth: int64) -> T {
    moshi (depth == 0) { kaesu value; }
    kaesu repeat[T](value + value, depth - 1);
}
chant(repeat[int64](3, 3)); chant(repeat[float32](float32(1.25), 2));
waza first<T>(values: []T) -> T { kaesu values[0]; }
chant(first[int64]([7])); chant(first[string](["mio"]));
'''), ('float-output', b'''
kaku zero: float64 = -0.0; chant(zero); chant(float32(zero));
kaku a: float32 = 16777216.0; chant(a + float32(1.0));
chant(float64(a)); chant(float32(1.25)); chant(3.141592653589793);
kaku tiny: float64 = 0.0000001; chant(tiny); chant(-tiny);
'''), ('nullable-operands', b'''
kaku flag: bool = iie; kaku maybe: bool? = flag; maybe = mu;
chant(flag); chant(!flag); moshi (flag) { chant("wrong"); } sore { chant("false branch"); }
kaku number: int64 = 7; kaku nullable: int64? = number; nullable = mu;
chant(number); chant(int8(number)); chant(float64(number));
'''), ('array-scalar-storage', b'''
yobu "kiso/array";
kaku value: int64 = 7; kaku nullable: int64? = value; nullable = mu;
kaku count: int64 = 2; kaku maybe_count: int64? = count; maybe_count = mu;
kaku values = array.make[int64](count, value); chant(values[0]);
array.push(values, value); values[1] = value; chant(values[1]); chant(values[2]);
kaku index: int64 = 1; kaku maybe_index: int64? = index; maybe_index = mu; chant(values[index]);
array.reserve(values, count + 10); array.truncate(values, count); chant(len(values));
kaku read = values[0]; kaku maybe_read: int64? = read; maybe_read = mu; chant(read);
kaku nullable_values: []int64? = [value, mu]; kaku first = nullable_values[0]; moshi (first != mu) { chant(first); } chant(nullable_values[1] == mu);
array.push(nullable_values, value); nullable_values[1] = value; kaku second = nullable_values[1]; kaku third = nullable_values[2]; moshi (second != mu) { chant(second); } moshi (third != mu) { chant(third); }
'''), ('math-primitives', b'''
yobu "kiso/math";
chant(math.min(7, 9)); chant(math.max(7, 9)); chant(math.clamp(12, 3, 9));
chant(math.abs(int8(-127))); chant(math.checked_abs(int8(-128)) == mu);
chant(math.abs(-7)); chant(math.gcd(54, -24)); chant(math.lcm(6, 15));
chant(math.sqrt(float32(9.0))); chant(math.sqrt(2.0));
chant(math.floor(float32(-1.5))); chant(math.ceil(-1.5)); chant(math.trunc(-1.5));
chant(math.round(2.5)); chant(math.round(3.5)); chant(math.round(float32(-2.5)));
kaku zero: float64 = -0.0; chant(math.min(zero, 0.0)); chant(math.max(zero, 0.0));
kaku nan = math.sqrt(-1.0); chant(math.is_nan(nan)); chant(math.is_finite(nan));
chant(math.is_inf(1.0 / 0.0)); chant(math.is_finite(1.0));
'''), ('last-string-gc', b'''
yobu "kiso/string"; yobu "kiso/array";
waza text() -> string { kaesu string.concat("alive", "-value"); }
text(); kaku index = 0;
aida (index < 200) { kaku junk = array.make[int64](64, index); index = index + 1; }
chant("done");
'''), ('last-bool', b'''hai;'''), ('last-float', b'''float32(1.25);'''), ('last-nil', b'''mu;'''), ('last-nullable', b'''
yobu "kiso/array";
waza maybe(flag: bool) -> int64? { moshi (flag) { kaesu 7; } kaesu mu; }
maybe(hai); kaku at = 0; aida (at < 200) { kaku junk = array.make[int64](64, at); at = at + 1; } chant("done");
'''), ('last-nullable-nil', b'''
waza maybe(flag: bool) -> int64? { moshi (flag) { kaesu 7; } kaesu mu; } maybe(iie);
'''), ('last-composite', b'''
kata Value { item: int64; } Value { item: 7 }; chant("done");
'''), ('integer-boundaries', b'''
waza step(value: int8) -> int8 { kaesu value + int8(1); }
kaku a: int8 = -128; chant(a - int8(1)); chant(-a);
kaku b: int16 = 32767; chant(b + int16(1));
kaku c: int32 = 2147483647; chant(c + int32(1));
kaku d: uint8 = 255; chant(d + uint8(1));
kaku e: uint16 = 65535; chant(e + uint16(1));
kaku f: uint32 = 0; chant(f - uint32(1));
kaku g: int8 = 64; chant(g * int8(2));
kaku h: int8 = -128; chant(h / int8(-1));
chant(step(int8(127))); kaku values: []int8 = [int8(127)]; chant(values[0] + int8(1));
''')]
results = []
for name, source in cases:
    directory = out / name
    directory.mkdir()
    src = directory / 'case.mio'
    src.write_bytes(source)
    mochi = directory / 'case.mochi'
    code, _ = run(name + '-build', [reference, 'build', src, '-o', mochi])
    result = {'case': name, 'source_sha256': digest(src), 'status': 'BLOCKED_REFERENCE'}
    if code == 0:
        vmcode, vmout = run(name + '-vm', [reference, 'exec', mochi])
        ok, unsigned = lower(name + '-lower', backend, mochi, directory)
        result.update(mochi_sha256=digest(mochi), vm_exit=vmcode)
        result['status'] = 'BLOCKED_NATIVE'
        if ok:
            signed = sign(name, unsigned)
            nativecode, nativeout = run(name + '-native', [signed], directory, {'PATH': ''})
            result.update(native_exit=nativecode, stdout_equal=vmout == nativeout,
                          unsigned_sha256=digest(unsigned), signed_sha256=digest(signed))
            expected_exit = 1 if name == 'last-composite' else 0
            diagnostic_ok = expected_exit == 0 or b'cannot display' in (out / (name + '-native.stderr')).read_bytes()
            result['status'] = 'PASS' if vmcode == nativecode == expected_exit and vmout == nativeout and diagnostic_ok else 'FAIL'
    results.append(result)
    (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(name, result['status'], flush=True)

print('GF1 phase remains IN_PROGRESS: native frontend and other gates required.', flush=True)

for name, config in [('missing-config', None), ('invalid-config', b'\xff'), ('bad-mochi', b'bad')]:
    directory = out / name
    directory.mkdir()
    target = directory / 'should-not-exist'
    if config is not None:
        (directory / 'input.config').write_bytes(config if name == 'invalid-config' else str(directory / 'bad.mochi').encode())
        (directory / 'output.config').write_text(str(target))
        (directory / 'bad.mochi').write_bytes(b'bad')
    code, stdout = run(name, [backend], directory, {'PATH': ''})
    stderr = (out / (name + '.stderr')).read_bytes()
    result = {'case': name, 'exit': code, 'status': 'PASS' if code not in (None, 0) and not stdout and b'E_' in stderr and not target.exists() else 'FAIL'}
    results.append(result)
    (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(name, result['status'], flush=True)

raise SystemExit(0 if all(x['status'] == 'PASS' for x in results) else 1)
