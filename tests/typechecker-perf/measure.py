#!/usr/bin/env python3
"""Interleaved native runs; preserve stdout/stderr and kernel peak RSS."""
import argparse, hashlib, json, os, pathlib, statistics, subprocess, time
p=argparse.ArgumentParser();p.add_argument('evidence',type=pathlib.Path);p.add_argument('--repeats',type=int,default=5);a=p.parse_args();e=a.evidence.resolve();out=e/'measurements';out.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(label,tag):
 image=e/(label+'-observed.native');stdout=out/(tag+'.stdout');stderr=out/(tag+'.stderr')
 with stdout.open('xb') as so,stderr.open('xb') as se:
  start=time.monotonic();child=subprocess.Popen([str(image)],stdout=so,stderr=se)
  _,status,usage=os.wait4(child.pid,0);child.returncode=os.waitstatus_to_exitcode(status)
  elapsed=time.monotonic()-start
 assert child.returncode==0,(tag,child.returncode)
 lines=stdout.read_text().splitlines();assert lines[:2]==['0','0'],(tag,lines[:2]);assert lines[-1]=='0',(tag,'type errors')
 metrics={}
 for line in stderr.read_text().splitlines():
  if line.startswith('mio-gc '):k,v=line[7:].split('=',1);metrics[k]=int(v)
 assert 'gc_total_ticks' in metrics and metrics['timer_frequency_hz']>0,(tag,'missing GC telemetry')
 semantic='\n'.join(lines[:2]+lines[3:]).encode()
 return dict(label=label,tag=tag,exit=child.returncode,typecheck_ms=int(lines[2]),elapsed_seconds=elapsed,user_seconds=usage.ru_utime,system_seconds=usage.ru_stime,peak_rss_bytes=usage.ru_maxrss,gc_ms=1000*metrics['gc_total_ticks']/metrics['timer_frequency_hz'],telemetry=metrics,semantic_sha256=hashlib.sha256(semantic).hexdigest(),stdout_sha256=sha(stdout),stderr_sha256=sha(stderr))
rows=[]
for label in ['baseline','after']:rows.append(run(label,label+'-warmup'))
for i in range(a.repeats):
 for label in (['baseline','after'] if i%2==0 else ['after','baseline']):
  row=run(label,label+'-'+str(i));rows.append(row);(out/'runs.json').write_text(json.dumps(rows,indent=2))
assert len({r['semantic_sha256'] for r in rows})==1,'semantic output differs'
summary={}
for label in ['baseline','after']:
 data=[r for r in rows if r['label']==label and 'warmup' not in r['tag']]
 summary[label]={k:statistics.median(r[k] for r in data) for k in ['typecheck_ms','elapsed_seconds','peak_rss_bytes','gc_ms']}
 summary[label]['gc_count']=statistics.median(r['telemetry']['gc_count'] for r in data)
 summary[label]['typecheck_range_ms']=[min(r['typecheck_ms'] for r in data),max(r['typecheck_ms'] for r in data)]
summary['speedup']=summary['baseline']['typecheck_ms']/summary['after']['typecheck_ms']
summary['semantic_sha256']=rows[0]['semantic_sha256']
summary['provenance']={name:sha(e/name) for name in ['input.mio','baseline-observed.native','after-observed.native']}
(out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
