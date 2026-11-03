#!/usr/bin/env python3
"""Run a VM investigation command and retain exit status, wait4 CPU/RSS and ps samples."""
import argparse
import datetime
import json
import os
import pathlib
import subprocess
import sys
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=pathlib.Path, required=True)
parser.add_argument('command', nargs=argparse.REMAINDER)
args = parser.parse_args()
command = args.command
if command[:1] == ['--']:
    command = command[1:]
if not command:
    parser.error('command required')
args.output.mkdir(parents=True, exist_ok=False)
started = time.monotonic()
result = {'command': command, 'cwd': os.getcwd(),
          'started': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'environment': {k: v for k, v in os.environ.items() if k.startswith('MIO_CODEGEN_')},
          'status': 'RUNNING'}
result_path = args.output / 'result.json'
result_path.write_text(json.dumps(result, indent=2) + '\n')
with (args.output / 'output.log').open('w') as log, (args.output / 'processes.log').open('w') as samples:
    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
    next_sample = 0.0
    while True:
        pid, status, usage = os.wait4(process.pid, os.WNOHANG)
        if pid:
            break
        elapsed = time.monotonic() - started
        if elapsed >= next_sample:
            samples.write(f'elapsed={elapsed:.3f}\n')
            subprocess.run(['ps', '-Ao', 'pid,ppid,etime,time,pcpu,rss,args'], stdout=samples, check=True)
            samples.flush()
            next_sample = elapsed + 10
        time.sleep(0.1)
    code = os.waitstatus_to_exitcode(status)
    process.returncode = code
result.update(status='PASS' if code == 0 else 'FAIL', exit_code=code,
              elapsed_seconds=time.monotonic()-started, cpu_user_seconds=usage.ru_utime,
              cpu_system_seconds=usage.ru_stime,
              peak_rss_bytes=usage.ru_maxrss if sys.platform == 'darwin' else usage.ru_maxrss*1024,
              rusage_scope='wait4 command and its waited descendants; process samples retain per-process CPU/RSS')
result_path.write_text(json.dumps(result, indent=2) + '\n')
sys.exit(code if code >= 0 else 128-code)
