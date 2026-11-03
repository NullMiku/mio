#!/usr/bin/env python3
"""Isolated audit transport for the two nullable-flow frontend regressions.

The executable under test is Mio Native AOT. Python only supplies source and
records its response; it never implements a production compilation stage.
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
p.add_argument('--cli', action='store_true', help='use the normal native CLI build --emit=mochi command')
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
frontend = a.frontend.resolve()
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=False)
cases = [
    ('repeated-null-check', True, None,
     'waza main(value: int64?) -> int64 { moshi(value==mu){kaesu 0;} '
     'moshi(value==mu){kaesu 0;} kaesu value; }'),
    ('nonnullable-null-comparison', False, b'E0301 ',
     'kaku value: int64=1; chant(value==mu);'),
    ('unexecuted-closure-fact', False, b'E0302 ',
     'kaku value: int64?=mu; kaku setter=waza () -> unit { value=1; }; chant(value+1);'),
    ('unexecuted-function-fact', False, b'E0302 ',
     'kaku value: int64?=mu; waza setter() -> unit { value=1; } chant(value+1);'),
    ('closure-preserves-outer-proof', True, None,
     'waza f(value: int64?) -> int64 { moshi(value==mu){kaesu 0;} '
     'kaku setter=waza () -> unit {value=mu;}; kaesu value+1; }'),
    ('function-preserves-outer-proof', True, None,
     'kaku value: int64?=mu; value=1; '
     'waza setter() -> unit {value=mu;} chant(value+1);'),
    ('delayed-closure-requires-own-proof', False, b'E0302 ',
     'kaku value: int64?=mu; value=1; '
     'kaku getter=waza () -> int64 {kaesu value+1;};'),
    ('function-requires-own-proof', False, b'E0302 ',
     'kaku value: int64?=mu; value=1; '
     'waza getter() -> int64 {kaesu value+1;}'),
    ('guarded-closure-accepted', True, None,
     'kaku value: int64?=mu; value=1; '
     'kaku getter=waza () -> int64 {moshi(value==mu){kaesu 0;}kaesu value+1;};'),
]
results = []
for name, accept, diagnostic, source in cases:
    case = out / name
    case.mkdir()
    src = case / 'main.mio'
    src.write_text(source + '\n')
    ir = case / 'output.mochi'
    request = ('\n'.join(map(str, [case, src, '', ir])) + '\n').encode()
    (case / 'request.stdin').write_bytes(request)
    policy = case / 'frontend.sb'
    policy.write_text('(version 1)(allow default)(deny network*)(deny process-fork)'
                      '(deny process-exec)(allow process-exec (literal '
                      + json.dumps(str(frontend)) + '))\n')
    argv = ['/usr/bin/sandbox-exec', '-f', str(policy), str(frontend)]
    if a.cli:
        argv += ['build', str(src), '--emit=mochi', '-o', str(ir), '--format=json']
    start = time.monotonic()
    with (case / 'stdout').open('wb') as stdout, (case / 'stderr').open('wb') as stderr:
        proc = subprocess.Popen(argv, cwd=case, env={'PATH': ''}, stdin=subprocess.PIPE if not a.cli else subprocess.DEVNULL,
                                stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            proc.communicate(None if a.cli else request, timeout=60)
            code = proc.returncode
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            code = None
    # A crash, timeout or missing module is never a valid source rejection.
    diagnostics = (case / 'stdout').read_bytes() + (case / 'stderr').read_bytes()
    observed_code = None
    if a.cli and not accept:
        try: observed_code = json.loads((case/'stderr').read_text()).get('code')
        except (ValueError, AttributeError): pass
    expected_code = diagnostic.decode().strip() if diagnostic is not None else None
    rejected_with_code = observed_code == expected_code if a.cli else diagnostics.startswith(diagnostic) if diagnostic is not None else False
    ok = (code == 0 and ir.is_file()) if accept else (code == 1 and not ir.exists() and rejected_with_code)
    results.append({'case': name, 'status': 'PASS' if ok else 'FAIL',
                    'expected_accept': accept, 'exit': code, 'module_exists': ir.exists(),
                    'argv': argv, 'wall_seconds': time.monotonic() - start})
    (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(name, results[-1]['status'], flush=True)
(out / 'provenance.json').write_text(json.dumps({
    'frontend': str(frontend),
    'frontend_sha256': hashlib.sha256(frontend.read_bytes()).hexdigest(),
    'transport': 'native CLI' if a.cli else 'native developer stdin driver',
    'scope': 'native Mio frontend source acceptance/rejection; isolated audit transport only',
}, indent=2) + '\n')
raise SystemExit(0 if all(r['status'] == 'PASS' for r in results) else 1)
