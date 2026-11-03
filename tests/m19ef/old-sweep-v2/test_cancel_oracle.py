#!/usr/bin/env python3
"""Host-oracle regression over authentic packets; no generated GC evidence."""
from pathlib import Path
import argparse,json,struct,hashlib
from workload_oracle import verify_cancel_gate,verify_workload
p=argparse.ArgumentParser();p.add_argument('positive',type=Path);p.add_argument('output',type=Path);a=p.parse_args();rows=json.loads((a.positive/'observations.json').read_text());assert {x['case'] for x in rows}=={'epochs-cancel','reenter','shutdown','oom','oom-bound'}
rejected=[]
for row in rows:
 gate=tuple(row['gate_words']);verify_cancel_gate(row['case'],gate)
 for index,value in [(0,0),(2,0),(3,0),(4,0),(5,0),(6,0),(7,0),(8,0),(9,0),(11,1),(12,0),(13,0),(14,0),(15,0)]:
  bad=list(gate);bad[index]=value
  try:verify_cancel_gate(row['case'],tuple(bad))
  except AssertionError:rejected.append([row['case'],index]);continue
  raise AssertionError(('accepted corrupt gate',row['case'],index))
folder=Path(__file__).resolve().parent;pins=json.loads((folder/'old-unscheduled-epochs.json').read_text())['sha256'];old_stdout=(folder/'old-unscheduled-epochs.stdout.fixture').read_bytes();old_stderr=(folder/'old-unscheduled-epochs.stderr.fixture').read_bytes();assert hashlib.sha256(old_stdout).hexdigest()==pins['stdout'] and hashlib.sha256(old_stderr).hexdigest()==pins['stderr']
try:verify_workload('epochs',old_stdout,old_stderr,'historical-failure-not-accepted')
except AssertionError:old_rejected=True
else:raise AssertionError('historical unscheduled cancellation failure was accepted')
a.output.write_text(json.dumps(dict(status='PASS_CANCEL_ORACLE_NEGATIVES',corrupt_gate_rejections=len(rejected),historical_failure_remains_rejected=old_rejected,scope='authentic packet validation only; no native GC execution',positive_packets_sha256=hashlib.sha256((a.positive/'observations.json').read_bytes()).hexdigest()),indent=2)+'\n')
print(a.output)
