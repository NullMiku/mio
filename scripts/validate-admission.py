#!/usr/bin/env python3
"""Reproducible lightweight M19d checks. Heavy bootstrap is a separate resource window."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent
CHECKS = [
    ('differential', ['go', 'test', './internal/aot', '-run', '^TestM19d', '-count=1', '-v', '-timeout=5m']),
    ('targeted-race', ['go', 'test', '-race', '-p=1', './internal/aot/...', '-run', '^TestM19|^TestM17ePureMioHeap|^TestM17ePureMioReadAllCrossPage', '-count=1', '-v', '-timeout=10m']),
    ('generated-policy', ['go', 'run', './scripts/native-memory-policy', '--check']),
]


def source_hashes():
    names = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
    return {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
            for name in sorted(set(names)) if name and (ROOT/name).suffix in {'.go', '.mio', '.py'}}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence', type=Path, required=True)
    args = p.parse_args()
    evidence = args.evidence.resolve()
    evidence.mkdir(parents=True, exist_ok=False)
    results = []
    for name, argv in CHECKS:
        before = source_hashes()
        start = time.monotonic()
        log = evidence / (name + '.log')
        env = dict(os.environ, GOMAXPROCS='2', MIO_M19D_EVIDENCE_DIR=str(evidence/(name+'-native')))
        try:
            with log.open('xb') as out:
                r = subprocess.run(argv, cwd=ROOT, env=env, stdout=out, stderr=subprocess.STDOUT, timeout=660)
            code = r.returncode
        except subprocess.TimeoutExpired:
            code = 124  # Only this runner's owned child; never touch other processes.
        unchanged = before == source_hashes()
        if not unchanged:
            code = code or 125
        results.append(dict(name=name, argv=argv, environment={k:env[k] for k in ['GOMAXPROCS','MIO_M19D_EVIDENCE_DIR']},
                            sources_unchanged=unchanged,source_hashes=before,
                            exit_code=code, status='PASS' if code == 0 else 'FAIL',
                            wall_seconds=time.monotonic()-start, log=str(log.relative_to(ROOT)),
                            sha256=hashlib.sha256(log.read_bytes()).hexdigest()))
        (evidence/'test-results.json').write_text(json.dumps(results, indent=2)+'\n')
        print(name, results[-1]['status'], flush=True)
    return int(any(r['exit_code'] for r in results))


if __name__ == '__main__':
    raise SystemExit(main())
