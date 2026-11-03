#!/usr/bin/env python3
"""Isolated controlled-pipe audit of Mio's syscall-only stdin readiness primitive.

Compiler and signer are Mio-native development components; no output is signed
by an external signer. This is not the GF4 unified CLI bootstrap chain.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import shutil
import subprocess
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--compiler', type=Path, required=True)
p.add_argument('--signer', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--cli', action='store_true', help='Compile and sign using the normal unified CLI source build command')
p.add_argument('--wait', action='store_true', help='Also verify native timed/indefinite waits and invalid timeout bounds')
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
compiler, signer, out = a.compiler.resolve(), a.signer.resolve(), a.output.resolve()
out.mkdir(parents=True, exist_ok=False)

def policy(folder, label, executable):
    path = folder / (label + '.sb')
    path.write_text('(version 1)(allow default)(deny network*)(deny process-fork)(deny process-exec)'
                    '(allow process-exec (literal ' + json.dumps(str(executable)) + '))\n')
    return ['/usr/bin/sandbox-exec', '-f', str(path), str(executable)]

commands = []
def run(folder, label, argv, data=None):
    start = time.monotonic()
    result = subprocess.run(argv, input=data, cwd=folder, env={'PATH': ''}, capture_output=True, timeout=120)
    (folder / (label + '.stdout')).write_bytes(result.stdout)
    (folder / (label + '.stderr')).write_bytes(result.stderr)
    commands.append({'label': label, 'argv': list(map(str, argv)), 'cwd': str(folder),
                     'exit': result.returncode, 'wall_seconds': time.monotonic() - start})
    (out / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
    assert result.returncode == 0, (label, result.stderr.decode())

programs = {}
initial_source = 'yobu "kiso/os"; chant(os.stdin_ready());'
handshake_source = 'yobu "kiso/os"; yobu "kiso/fs"; kaku input=fs.open_read("/dev/stdin").file; moshi(input!=mu){kaku data: []uint8=[0];kaku received=fs.read(input,data,0,1);chant(os.stdin_ready());}'
sources = [('initial', initial_source), ('handshake', handshake_source)]
if a.wait:
    initial_source = ('yobu "kiso/os"; kaku started=os.monotonic_ms();kaku ready=os.stdin_wait(50);'
                      'kaku elapsed=os.monotonic_ms()-started;chant(ready);'
                      'moshi(ready==0 && (elapsed<40 || elapsed>5000)){os.exit(2);}')
    sources = [('initial', initial_source),
               ('handshake', handshake_source.replace('os.stdin_ready()', 'os.stdin_wait(2000)')),
               ('infinite', handshake_source.replace('os.stdin_ready()', 'os.stdin_wait(-1)')),
               ('maximum', handshake_source.replace('os.stdin_ready()', 'os.stdin_wait(2147483647)')),
               ('invalid-timeouts', 'yobu "kiso/os";chant(os.stdin_wait(-2));chant(os.stdin_wait(2147483648));')]
for name, source in sources:
    folder = out / name
    folder.mkdir()
    entry = folder / 'main.mio'
    entry.write_text(source + '\n')
    request = ('\n'.join(map(str, [folder, entry, root / 'bunko', folder / 'input.bin'])) + '\n').encode()
    (folder / 'compile.stdin').write_bytes(request)
    compile_argv = policy(folder, 'compile', compiler)
    if a.cli:
        compile_argv += ['build', str(entry), '-o', str(folder / 'input.bin')]
    run(folder, 'compile', compile_argv, None if a.cli else request)
    if a.cli:
        shutil.copy2(folder / 'input.bin', folder / 'signed.bin')
    else:
        run(folder, 'sign', policy(folder, 'sign', signer))
    program = folder / 'signed.bin'
    program.chmod(0o755)
    run(folder, 'verify', ['/usr/bin/codesign', '--verify', '--strict', str(program)])
    programs[name] = (folder, program)

results = []
cases = [
    ('idle-open-pipe', 'initial', None, False, b'0\n'),
    ('queued-pipe-data', 'handshake', b'xy', False, b'1\n'),
    ('pipe-eof', 'handshake', b'x', True, b'1\n'),
    ('invalid-stdin', 'initial', None, False, b'-9\n')]
if a.wait:
    cases += [('indefinite-ready-pipe', 'infinite', b'xy', False, b'1\n'),
              ('maximum-timeout-ready-pipe', 'maximum', b'xy', False, b'1\n'),
              ('invalid-timeout-bounds', 'invalid-timeouts', None, False, b'-22\n-22\n')]
for name, kind, data, close, expected in cases:
    folder, program = programs[kind]
    argv = policy(folder, name, program)
    stderr = (out / (name + '.stderr')).open('wb')
    proc = subprocess.Popen(argv, cwd=folder, env={'PATH': ''}, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=stderr, start_new_session=True,
                            preexec_fn=(lambda: os.close(0)) if name == 'invalid-stdin' else None)
    actual = bytearray()
    code = None
    error = None
    try:
        if data is not None:
            proc.stdin.write(data)
            proc.stdin.flush()
        if close:
            proc.stdin.close()
        selector = selectors.DefaultSelector()
        selector.register(proc.stdout, selectors.EVENT_READ)
        deadline = time.monotonic() + 15
        while b'\n' not in actual:
            remaining = deadline - time.monotonic()
            assert remaining > 0 and selector.select(remaining), 'nonblocking poll audit timed out'
            block = os.read(proc.stdout.fileno(), 4096)
            assert block, 'unexpected EOF'
            actual.extend(block)
        code = proc.wait(timeout=15)
        actual.extend(proc.stdout.read())
        selector.close()
    except Exception as exc:
        error = repr(exc)
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
    finally:
        if not proc.stdin.closed:
            proc.stdin.close()
        stderr.close()
    (out / (name + '.stdout')).write_bytes(actual)
    results.append({'case': name, 'argv': argv, 'exit': code, 'error': error,
                    'stdout': actual.decode(), 'expected': expected.decode(),
                    'status': 'PASS' if error is None and code == 0 and actual == expected else 'FAIL'})
    (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
(out / 'provenance.json').write_text(json.dumps({
    'scope': 'normal unified CLI source compile/sign and independent controlled-pipe native execution' if a.cli else __doc__, 'compiler': str(compiler), 'compiler_sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(),
    'signer': str(signer), 'signer_sha256': hashlib.sha256(signer.read_bytes()).hexdigest(),
    'environment': {'PATH': ''}}, indent=2) + '\n')
print(json.dumps(results, indent=2), flush=True)
raise SystemExit(0 if all(x['status'] == 'PASS' for x in results) else 1)
