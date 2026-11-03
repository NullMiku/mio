#!/usr/bin/env python3
"""Bounded directed repair check; positive8, original negative1, strict oracle."""
from pathlib import Path
import fcntl,hashlib,json,os,shutil,signal,struct,subprocess,sys,time
r=Path.cwd();out=(r/sys.argv[1]).resolve()
assert out.is_relative_to(r/'build/m19ef-evidence');out.mkdir()
lock=(r/'build/.m19ef-native-test.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,data):(out/name).write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')
snap=out/'source-snapshot';snap.mkdir();manifest={}
for folder in ('bunko','selfhost','tests/m19ef'):
 for p in sorted((r/folder).rglob('*')):
  if p.is_file() and p.suffix in ('.mio','.py','.sh'):
   rel=p.relative_to(r);target=snap/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target);manifest[str(rel)]=sha(p)
save('source-manifest.json',manifest);shutil.copyfile(__file__,out/'controller.py')
sys.path.insert(0,str(snap/'tests/m19ef/user-workers'))
from worker_trace import verify_worker_trace
prior=(r/sys.argv[2]).resolve() if len(sys.argv)>2 else r/'build/m19ef-evidence/E3-workers-E6-20261031-01'
previous=json.loads((prior/'source-manifest.json').read_text())
relevant=lambda m:{k:v for k,v in m.items() if k.startswith(('bunko/','selfhost/')) or k=='tests/m19ef/user-workers/builder.mio'}
assert relevant(previous)==relevant(manifest),'native builder source inputs differ'
build=next(x for x in json.loads((prior/'commands.json').read_text()) if x['label']=='worker-build')
assert build['exit']==0 and not build['timed_out']
builder=prior/'worker-builder'
save('builder-reuse.json',dict(scope='byte-identical compiler/runtime/builder inputs; repaired user image freshly generated',builder=str(builder),sha256=sha(builder),original_build=build))
rows=[]
def run(label,args,timeout=60):
 args=list(map(str,args));start=time.monotonic();print(label,'START',flush=True)
 with (out/(label+'.stdout')).open('xb') as so,(out/(label+'.stderr')).open('xb') as se:
  child=subprocess.Popen(args,cwd=r if len(args)==1 else snap,stdout=so,stderr=se,start_new_session=True);timed=False
  while True:
   got,status,u=os.wait4(child.pid,os.WNOHANG)
   if got:break
   if time.monotonic()-start>timeout:
    timed=True;os.killpg(child.pid,signal.SIGKILL);_,status,u=os.wait4(child.pid,0);break
   time.sleep(.02)
 row=dict(label=label,argv=args,exit=os.waitstatus_to_exitcode(status),timed_out=timed,wall_seconds=time.monotonic()-start,cpu_seconds=u.ru_utime+u.ru_stime,peak_rss_bytes_darwin=u.ru_maxrss,stdout_sha256=sha(out/(label+'.stdout')),stderr_sha256=sha(out/(label+'.stderr')))
 rows.append(row);save('commands.json',rows);assert row['exit']==0 and not timed,row
 return (out/(label+'.stdout')).read_bytes()
run('builder-signature',['codesign','--verify','--strict',builder])
case='tests/m19ef/user-workers/global-snapshot/main.mio';image=out/'fixed-native'
run('fixed-build',[builder,snap,case,snap/'bunko',image],600);run('fixed-signature',['codesign','--verify','--strict',image])
copy=out/'fixed-reproduced-native';run('fixed-reproduce',[builder,snap,case,snap/'bunko',copy],600);assert image.read_bytes()==copy.read_bytes()
fifo=r/'build/m19ef-worker-fifo';assert not fifo.exists();observations=[]
for i in range(8):
 os.mkfifo(fifo,0o600)
 try:
  stdout=run('fixed-'+str(i),[image],30);assert stdout==b'hai\n1\n1\n0\n'
  raw=(out/('fixed-'+str(i)+'.stderr')).read_bytes();v=verify_worker_trace('global-snapshot',raw)
  observations.append(dict(repeat=i,native_entries=v[30:32],snapshot_roots_epochs=v[36:42],overlap_ns=min(v[33],v[35])-max(v[32],v[34]),los_reclaimed=v[25],final_heap=v[26]))
 finally:fifo.unlink()
save('observations.json',observations)
# The historical fixture must still fail the SAME strict oracle, even though
# its native exit/output can be correct and the two callback intervals overlap.
historical=r/'build/m19ef-evidence/E3-workers-E6-20261031-01'
original=historical/'source-snapshot'/case
assert sha(original)==json.loads((historical/'source-manifest.json').read_text())[case]
negative=snap/'original-global-snapshot.mio'
# Relocate only test IO paths; preserve the historical missing-work/readiness bug.
legacy='/Users/hatsunemiku/.codex/worktrees/m19ef-portable-gc/mio/'
negative.write_text(original.read_text().replace(legacy,''))
old=out/'original-native';run('original-build',[builder,snap,negative.name,snap/'bunko',old],600);run('original-signature',['codesign','--verify','--strict',old])
os.mkfifo(fifo,0o600)
try:
 assert run('original-0',[old],30)==b'hai\n1\n1\n0\n'
 raw_old=(out/'original-0.stderr').read_bytes()
 try:verify_worker_trace('global-snapshot',raw_old)
 except AssertionError as e:save('original-rejection.json',dict(status='REJECTED',predicate=repr(e),source_sha256=sha(original),relocated_fixture_sha256=sha(negative),relocation='test IO paths only; original retained unchanged'))
 else:raise AssertionError('original fixture unexpectedly satisfies NativeFS/snapshot contract')
finally:fifo.unlink()
negatives={}
for name,index,value in [('missing_native_boundary',31,0),('missing_snapshot',40,0),('missing_epoch',41,0),('no_worker_overlap',34,v[33]+1),('los_leaked',24,1),('heap_leaked',26,16),('join_missing',17,0)]:
 damaged=bytearray(raw);struct.pack_into('<Q',damaged,index*8,value)
 try:verify_worker_trace('global-snapshot',bytes(damaged))
 except AssertionError:negatives[name]='REJECTED'
 else:raise AssertionError('false acceptance: '+name)
save('oracle-negatives.json',negatives)
assert all(sha(r/k)==h and sha(snap/k)==h for k,h in manifest.items())
save('summary.json',dict(status='PASS_DIRECTED_GLOBAL_SNAPSHOT_REPAIR',positive_native_runs=8,original_fixture_native_negative=1,oracle_negative_cases=len(negatives),source_manifest_sha256=sha(out/'source-manifest.json'),runtime_change='NONE; missing NativeFS/snapshot workload and readiness handshake repaired',E6='IN_PROGRESS',M19e='NOT_ACCEPTED'))
