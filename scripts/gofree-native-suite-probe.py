#!/usr/bin/env python3
"""Isolated audit of the native Mio test command; never a formal build step."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--candidate', type=Path, required=True)
p.add_argument('--suite', required=True)
p.add_argument('--run')
p.add_argument('--timeout', type=int, default=600)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=False)
cli = a.candidate.resolve()

def manifest():
    return [{'path': str(x.relative_to(root)), 'sha256': hashlib.sha256(x.read_bytes()).hexdigest()}
            for x in sorted(set(root.glob('bunko/**/*.mio')) | set(root.glob('selfhost/**/*.mio')))]

before = manifest()
(out / 'source-before.json').write_text(json.dumps(before, indent=2) + '\n')
policy = out / 'native.sb'
policy.write_text('(version 1)(allow default)(deny network*)(deny process-exec)'
                  '(allow process-exec (literal ' + json.dumps(str(cli)) + '))'
                  '(allow process-exec (regex #"^(/private)?/tmp/mio-test-[0-9]+/test-[0-9]+[.]native$"))'
                  '(allow process-exec (regex #"^(/private)?/tmp/mio-globals-[0-9]+/program$"))\n')
argv = ['/usr/bin/sandbox-exec', '-f', str(policy), str(cli), 'test', a.suite,
        '--bunko-root', str(root / 'bunko'), '--format=json', '--lang=en-US']
if a.run:
    argv.append('--run=' + a.run)
start = time.monotonic()
with (out / 'report.json').open('wb') as stdout, (out / 'stderr').open('wb') as stderr:
    proc = subprocess.Popen(argv, cwd=root, env={'PATH': ''}, stdout=stdout,
                            stderr=stderr, start_new_session=True)
    try:
        code = proc.wait(timeout=a.timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        code = None
after = manifest()
(out / 'source-after.json').write_text(json.dumps(after, indent=2) + '\n')
changed = [x['path'] for x in before if x not in after] + [x['path'] for x in after if x not in before]
summary = None
try:
    summary = json.loads((out / 'report.json').read_text())['summary']
except (ValueError, KeyError):
    pass
ok = code == 0 and summary is not None and summary['status'] == 'passed' and not changed
result = {'status': 'PASS' if ok else 'FAIL', 'argv': argv, 'exit': code,
          'wall_seconds': time.monotonic() - start, 'summary': summary,
          'source_changes': sorted(set(changed)), 'candidate': str(cli),
          'candidate_sha256': hashlib.sha256(cli.read_bytes()).hexdigest(),
          'scope': 'native unified CLI with explicit current Bunko source; embedded/offline acceptance is separate'}
(out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2), flush=True)
raise SystemExit(0 if ok else 1)
