#!/usr/bin/env python3
"""Compile unchanged production policy plus explicit native input/clock probe."""
from pathlib import Path
import fcntl,hashlib,json,os,shutil,signal,struct,subprocess,sys,time
r=Path.cwd();out=(r/sys.argv[1]).resolve();compiler=Path(sys.argv[2]).resolve();pin=sys.argv[3]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();assert sha(compiler)==pin
assert out.is_relative_to(r/'build/m19ef-evidence');out.mkdir()
lock=os.fdopen(os.dup(int(os.environ['MIO_E5_TEST_LOCK_FD'])),'a+') if 'MIO_E5_TEST_LOCK_FD' in os.environ else (r/'build/.m19ef-native-test.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
snap=out/'source-snapshot';snap.mkdir();manifest={}
for folder in ('bunko','selfhost','tests/m19ef'):
 for p in sorted((r/folder).rglob('*.mio')):
  rel=p.relative_to(r);dest=snap/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);manifest[str(rel)]=sha(p)
def save(name,data):(out/name).write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')
save('source-manifest.json',manifest);shutil.copyfile(__file__,out/'controller.py')
private=out/'policy-source';private.mkdir();inputs={}
for p in (snap/'bunko/kiso/aot/lower').glob('*.mio'):
 if not p.name.endswith('_test.mio'):
  shutil.copyfile(p,private/p.name);inputs[p.name]=sha(p)
shutil.copyfile(snap/'tests/m19ef/e6/memory/audit.mio',private/'audit.mio')
save('private-factory-inputs.json',inputs)
save('provenance.json',dict(compiler=str(compiler),compiler_sha256=pin,scope='policy component/legacy snapshot ABI only; real GC, ownership snapshots and OS Unknown separately validated',clock='one MRS replaced by native Mio assembler load from probe-private metadata+3072; deterministic 1MHz ticks, no sleeps',production_tree_modified=False))
rows=[]
def run(label,args,timeout=600):
 args=list(map(str,args));start=time.monotonic();print(label,'START',flush=True)
 with (out/(label+'.stdout')).open('xb') as so,(out/(label+'.stderr')).open('xb') as se:
  child=subprocess.Popen(args,cwd=snap,stdout=so,stderr=se,start_new_session=True);timed=False
  while True:
   got,status,u=os.wait4(child.pid,os.WNOHANG)
   if got:break
   if time.monotonic()-start>timeout:
    timed=True;os.killpg(child.pid,signal.SIGKILL);_,status,u=os.wait4(child.pid,0);break
   time.sleep(.05)
 row=dict(label=label,argv=args,exit=os.waitstatus_to_exitcode(status),timed_out=timed,wall_seconds=time.monotonic()-start,cpu_seconds=u.ru_utime+u.ru_stime,peak_rss_bytes_darwin=u.ru_maxrss,stdout_sha256=sha(out/(label+'.stdout')),stderr_sha256=sha(out/(label+'.stderr')))
 rows.append(row);save('commands.json',rows);assert row['exit']==0 and not timed,row
 return (out/(label+'.stdout')).read_bytes()
run('compiler-signature',['codesign','--verify','--strict',compiler])
builder=out/'policy-builder';run('build',[compiler,'build',private,'--bunko-root',snap/'bunko','-o',builder]);run('builder-signature',['codesign','--verify','--strict',builder])
image=out/'policy-native';checks=int(run('generate',[builder,image]).strip());assert checks>=25
run('image-signature',['codesign','--verify','--strict',image]);copy=out/'policy-reproduced-native';assert int(run('reproduce',[builder,copy]).strip())==checks and image.read_bytes()==copy.read_bytes()
for repeat in range(8):assert run('policy-'+str(repeat),[image],30)==struct.pack('<Q',checks)
assert all(sha(r/k)==v and sha(snap/k)==v for k,v in manifest.items())
save('summary.json',dict(status='PASS_NATIVE_M19C_POLICY_COMPONENT',runs=8,checks_per_run=checks,levels=[0,1,2,3],reason_bits=[1,2,4,8,16],recovery_distinct_samples=3,unknown_ignored_system=True,signed_reproduction=True,scope='component only; not concurrent GC or timing measurement',source_manifest_sha256=sha(out/'source-manifest.json')))
