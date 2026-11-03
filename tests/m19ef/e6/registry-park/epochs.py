#!/usr/bin/env python3
"""Fixed32 actual eight-Epoch regression, with failure-only copied diagnostics."""
from pathlib import Path
import argparse,fcntl,hashlib,json,os,shutil,signal,struct,subprocess,time,traceback
from epoch_diagnostic import install
p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--compiler',required=True,type=Path);p.add_argument('--compiler-sha256',required=True);p.add_argument('--prior-builder-proof',type=Path);p.add_argument('--directed',action='store_true');a=p.parse_args()
r=Path.cwd();out=a.output.resolve();out.mkdir();assert out.is_relative_to(r/'build/m19ef-evidence');sha=lambda q:hashlib.sha256(q.read_bytes()).hexdigest();assert sha(a.compiler)==a.compiler_sha256
lock=(r/'build/.m19ef-native-test.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);snap=out/'source-snapshot';snap.mkdir();manifest={};rows=[]
def save(n,x):(out/n).write_text(json.dumps(x,sort_keys=True,indent=2)+'\n')
for top in ('bunko','selfhost','tests/m19ef'):
 for q in (r/top).rglob('*.mio'):
  rel=q.relative_to(r);d=snap/rel;d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(q,d);manifest[str(rel)]=sha(q)
save('canonical-manifest.json',manifest);install(snap);overlaid={str(q.relative_to(snap)):sha(q) for q in snap.rglob('*.mio')};save('diagnostic-manifest.json',overlaid)
repetitions=1 if a.directed else 32
save('plan.json',dict(repetitions=repetitions,epochs_per_program=8,retries=0,compiler_sha256=a.compiler_sha256,diagnostics='only failure paths; original actual Collector/Mutator work and exact Epoch oracle retained',scope='32 ungated natural8-Epoch programs; separate controlled cancellation required; not full E5/E6'))
def run(label,argv,timeout):
 start=time.monotonic();print(label,'START',flush=True);timed=False
 with (out/(label+'.stdout')).open('xb') as so,(out/(label+'.stderr')).open('xb') as se:
  c=subprocess.Popen(list(map(str,argv)),cwd=r,stdout=so,stderr=se,start_new_session=True)
  while True:
   got,status,u=os.wait4(c.pid,os.WNOHANG)
   if got:break
   if time.monotonic()-start>timeout:timed=True;os.killpg(c.pid,signal.SIGKILL);_,status,u=os.wait4(c.pid,0);break
   time.sleep(.05)
 row=dict(label=label,argv=list(map(str,argv)),exit=os.waitstatus_to_exitcode(status),expected_exit=0,timed_out=timed,wall_seconds=time.monotonic()-start,cpu_seconds=u.ru_utime+u.ru_stime,peak_rss_bytes_darwin=u.ru_maxrss,stdout_sha256=sha(out/(label+'.stdout')),stderr_sha256=sha(out/(label+'.stderr')));rows.append(row);save('commands.json',rows);print(label,row['exit'],flush=True)
 if row['exit'] or timed:
  b=(out/(label+'.stderr')).read_bytes();save('failed-packet.json',dict(label=label,stdout=(out/(label+'.stdout')).read_text(),bytes=len(b),words=list(struct.unpack('<'+str(len(b)//8)+'Q',b)) if len(b)%8==0 else [],diagnostic_tag_meanings={'7001':'registry_lock timeout: now,soft,hard,seen_before,seen_after,heartbeat_initial,heartbeat_after,epoch,owner,ctx','7002':'gc_begin abort: now,deadline,member,last_progress,last_error,mutex,trylock,epoch,owner,ctx'}));raise RuntimeError(row)
 assert all(sha(r/k)==v for k,v in manifest.items());return (out/(label+'.stdout')).read_bytes()
def verify(n,data):
 assert len(data)==808 and len(n)==121 and n[-1]==0
 sweep=struct.unpack('<32Q',data[:256]);old=struct.unpack('<24Q',data[256:448]);mut=struct.unpack('<45Q',data[448:])
 for cycle in range(8):
  v=n[cycle*15:cycle*15+15];cancel=False
  assert v[0]==0 and v[1]>=65 and v[3:6]==([4,0,0] if cancel else [3,0,0]) and v[8]>=1000 and v[9]>=1000 and v[12]==0,v
  if cancel:assert v[13]==2 and v[14]>0 and 0<=v[2]<400003,v
  else:assert v[2]>=400003 and v[7]>0 and v[10]+v[11]>0 and v[13] in (2,3) and v[14]==0,v
 assert sweep[:4]==(1330406979,3,3,0) and sweep[4]==sweep[5]>=100003 and sweep[6:8]==(0,0) and sweep[12:16]==(8,8,1,1) and sweep[20]==8 and sweep[25]==0,sweep
 assert old[12:17]==(8,8,0,1,1) and old[22]==8 and mut[24]==0 and mut[26]==0
 for off in (7,14):assert mut[off:off+6]==(8,8,8,8,24,24),mut
try:
 builder=out/'builder'
 if a.prior_builder_proof:
  prior=a.prior_builder_proof.resolve();relevant=lambda m:{k:v for k,v in m.items() if k.startswith(('bunko/','selfhost/')) or k=='tests/m19ef/old-sweep/builder.mio'}
  assert relevant(json.loads((prior/'canonical-manifest.json').read_text()))==relevant(manifest)
  assert relevant(json.loads((prior/'diagnostic-manifest.json').read_text()))==relevant(overlaid)
  assert json.loads((prior/'plan.json').read_text())['compiler_sha256']==a.compiler_sha256
  for row in json.loads((prior/'commands.json').read_text()):
   assert row['exit']==row['expected_exit'] and not row['timed_out']
   for stream in ('stdout','stderr'):assert sha(prior/(row['label']+'.'+stream))==row[stream+'_sha256']
  shutil.copy2(prior/'builder',builder);save('retained-builder.json',dict(path=str(prior),sha256=sha(builder),scope='identical compiler/Core/builder inputs; different fresh natural-Epoch user source; not prior workload acceptance'))
 else:run('build',[a.compiler.resolve(),'build',snap/'tests/m19ef/old-sweep/builder.mio','--bunko-root',snap/'bunko','-o',builder],1800)
 run('builder-signature',['codesign','--verify','--strict',builder],30)
 image=out/'epochs-native';common=[builder,snap,'tests/m19ef/old-sweep-v2/epochs-natural.mio',snap/'bunko'];run('generate',common+[image,67108864,32],300);run('signature',['codesign','--verify','--strict',image],30);copy=out/'epochs-repro';run('reproduce',common+[copy,67108864,32],300);assert image.read_bytes()==copy.read_bytes()
 for i in range(repetitions):
  label='epochs-'+str(i);n=list(map(int,run(label,[image],300).splitlines()));verify(n,(out/(label+'.stderr')).read_bytes())
 save('summary.json',dict(status='PASS_ACTUAL_NATURAL_EPOCH_DIRECTED' if a.directed else 'PASS_ACTUAL_EPOCHS32_DIRECTED',repetitions=repetitions,epochs=8*repetitions,source_unchanged=True,full_E5_E6='NEW_FROZEN_ROUND_REQUIRED'))
except BaseException as e:save('FAIL.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
