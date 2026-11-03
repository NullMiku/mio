#!/usr/bin/env python3
"""Isolated development audit: source-driven Mio generic codegen and native execution.

The frontend and linker are separately identified native development components.
This is not final unified CLI/bootstrap acceptance or a production build step.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--frontend', type=Path, required=True)
p.add_argument('--linker', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--cli', action='store_true', help='Use normal single-process CLI source build and run its standalone signed output')
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
front, linker, out = a.frontend.resolve(), a.linker.resolve(), a.output.resolve()
out.mkdir(parents=True, exist_ok=False)
cases = [
    ('reuse-and-distinct', 'waza empty<T>() -> []T {kaku values: []T=[];kaesu values;} kaku a=empty[int64](); kaku b=empty[string](); kaku c=empty[int64](); chant(len(a)+len(b)+len(c));', '0\n'),
    ('recursive-no-witness', 'waza size<T>(n: int64) -> int64 {kaku values: []T=[];moshi(n>0){kaesu size[T](n-1);}kaesu len(values);} chant(size[uint8](3));chant(size[string](2));', '0\n0\n'),
    ('nested-array', 'waza empty<T>() -> []T {kaku values: []T=[];kaesu values;} kaku values=empty[[]string]();chant(len(values));', '0\n'),
    ('nullable-element', 'waza empty<T>() -> []T {kaku values: []T=[];kaesu values;} kaku values=empty[int64?]();chant(len(values));', '0\n'),
    ('record-element', 'kata Item {value: string;} waza empty<T>() -> []T {kaku values: []T=[];kaesu values;} kaku values=empty[Item]();chant(len(values));', '0\n'),
    ('enum-element', 'sentaku Flag {On;Off;} waza empty<T>() -> []T {kaku values: []T=[];kaesu values;} kaku values=empty[Flag]();chant(len(values));', '0\n'),
    ('closure-body', 'waza make<T>(value: T) -> () -> T {kaesu waza () -> T {kaesu value;};} kaku number=make[int64](7); kaku text=make[string]("mio");chant(number());chant(text());', '7\nmio\n'),
    ('transitive-no-witness', 'waza inner<T>() -> []T {kaku values: []T=[];kaesu values;} waza outer<U>() -> []U {kaesu inner[U]();} chant(len(outer[uint32]()));chant(len(outer[bool]()));', '0\n0\n'),
    ('numeric-recursive', 'waza repeat<T: Number>(value: T, depth: int64) -> T {moshi(depth==0){kaesu value;}kaesu repeat[T](value+value,depth-1);} chant(repeat[int64](3,3));chant(repeat[float32](float32(1.25),2));', '24\n5\n'),
    ('concrete-mutable-arrays', 'yobu "kiso/array"; waza empty<T>() -> []T {kaku values: []T=[];kaesu values;} kaku numbers=empty[int64]();kaku texts=empty[string]();array.push(numbers,11);array.push(texts,"mio");numbers[0]=7;texts[0]="native";chant(numbers[0]);chant(texts[0]);', '7\nnative\n'),
    ('cross-package-record-enum', 'yobu "kiso/array"; yobu "./lib"; kata Item {value:string;} sentaku Flag {On;Off;} kaku records=lib.empty[Item]();kaku flags=lib.empty[Flag]();array.push(records,Item {value:"alive"});array.push(flags,Flag.On());chant(records[0].value);awase(flags[0]){baai On {chant(1);}baai Off {chant(0);}}', 'alive\n1\n', {'lib/main.mio': 'koukai waza empty<T>() -> []T {kaku values: []T=[];kaesu values;}'}),
    ('nested-mutable-array', 'yobu "kiso/array"; waza empty<T>() -> []T {kaku values: []T=[];kaesu values;} kaku values=empty[[]string]();array.push(values,["alive"]);values[0][0]="nested";chant(values[0][0]);', 'nested\n'),
]

def run(folder, label, argv, data=None):
    (folder / (label + '.argv.json')).write_text(json.dumps(list(map(str, argv)), indent=2) + '\n')
    start = time.monotonic()
    with (folder / (label + '.stdout')).open('wb') as stdout, (folder / (label + '.stderr')).open('wb') as stderr:
        proc = subprocess.Popen(list(map(str, argv)), cwd=folder, env={'PATH': ''}, stdin=subprocess.PIPE,
                                stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            proc.communicate(data, timeout=90)
            code = proc.returncode
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
            code = None
    return {'exit': code, 'wall_seconds': time.monotonic() - start}

results = []
for case in cases:
    name, source, expected = case[:3]
    folder = out / name
    folder.mkdir()
    if len(case) > 3:
        for relative, content in case[3].items():
            extra = folder / relative
            extra.parent.mkdir(parents=True, exist_ok=True)
            extra.write_text(content + '\n')
    entry = folder / 'main.mio'
    entry.write_text(source + '\n')
    ir = folder / ('program' if a.cli else 'input.mochi')
    request = ('\n'.join(map(str, [folder, entry, root / 'bunko', ir])) + '\n').encode()
    (folder / 'front.stdin').write_bytes(request)
    policy = folder / 'front.sb'
    policy.write_text('(version 1)(allow default)(deny network*)(deny process-fork)(deny process-exec)'
                      '(allow process-exec (literal ' + json.dumps(str(front)) + '))\n')
    compile_argv = ['/usr/bin/sandbox-exec', '-f', policy, front]
    if a.cli:
        compile_argv += ['build', entry, '-o', ir]
    compiled = run(folder, 'front', compile_argv, None if a.cli else request)
    executed = None
    if compiled['exit'] == 0 and ir.is_file():
        policy = folder / 'native.sb'
        if a.cli:
            policy.write_text('(version 1)(allow default)(deny network*)(deny process-fork)(deny process-exec)'
                              '(allow process-exec (literal ' + json.dumps(str(ir)) + '))\n')
            executed = run(folder, 'native', ['/usr/bin/sandbox-exec', '-f', policy, ir])
        else:
            policy.write_text('(version 1)(allow default)(deny network*)(deny process-exec)'
                              '(allow process-exec (literal ' + json.dumps(str(linker)) + '))'
                              '(allow process-exec (regex #"^(/private)?/tmp/mio-run-[0-9]+/program$"))\n')
            executed = run(folder, 'native', ['/usr/bin/sandbox-exec', '-f', policy, linker, 'exec', ir])
    actual = (folder / 'native.stdout').read_text() if executed is not None else None
    ok = compiled['exit'] == 0 and executed is not None and executed['exit'] == 0 and actual == expected
    results.append({'case': name, 'frontend': compiled, 'native': executed, 'expected': expected,
                    'actual': actual, 'status': 'PASS' if ok else 'FAIL'})
    (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
scope = 'normal unified CLI single-process source build and standalone native execution' if a.cli else 'two-component development audit, not final unified CLI or bootstrap acceptance'
provenance = {'scope': scope,
              'frontend': str(front), 'frontend_sha256': hashlib.sha256(front.read_bytes()).hexdigest(),
              'linker': str(linker), 'linker_sha256': hashlib.sha256(linker.read_bytes()).hexdigest()}
(out / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
print(json.dumps(results, indent=2), flush=True)
raise SystemExit(0 if all(x['status'] == 'PASS' for x in results) else 1)
