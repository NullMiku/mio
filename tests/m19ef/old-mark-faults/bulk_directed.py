#!/usr/bin/env python3
"""Eight fixed controlled bulk runs; unchanged failed packet still rejected."""
from pathlib import Path
import fcntl,hashlib,json,os,shutil,signal,subprocess,sys,time
from bulk_overlay import install
from bulk_trace import verify_bulk
r=Path.cwd();out=(r/sys.argv[1]).resolve();assert out.is_relative_to(r/'build/m19ef-evidence');out.mkdir()
lock=(r/'build/.m19ef-native-test.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,value):(out/name).write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')
snap=out/'source-snapshot';snap.mkdir();manifest={}
for folder in ('bunko','selfhost','tests/m19ef'):
 for p in sorted((r/folder).rglob('*')):
  if p.is_file() and p.suffix in ('.mio','.py'):
   rel=p.relative_to(r);dest=snap/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);manifest[str(rel)]=sha(p)
save('canonical-manifest.json',manifest);install(snap)
overlay={str(p.relative_to(snap)):sha(p) for p in snap.rglob('*.mio')}
save('overlay-manifest.json',overlay)
changes=[k for k,v in overlay.items() if v!=manifest[k]];assert changes==['bunko/kiso/runtime/gc/old_mark.mio']
save('contract.json',dict(scope='controlled white-before-scan bulk only; independent ungated E4 overlap still mandatory',changed_source=changes,gate='real acquire counter440 before work_take; production pause gate and deadline retained',repetitions=8,retries=0,canonical_gc_change=False))
compiler=r/'build/m19ef-evidence/E6-LSP-policy-repair-20261103-01/mio-current';assert sha(compiler)=='0225cb1296f08af147e491ae1f5f17e31d2ed79b3ad0208737f86cb039c3bad8'
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
   time.sleep(.03)
 row=dict(label=label,argv=args,exit=os.waitstatus_to_exitcode(status),timed_out=timed,wall_seconds=time.monotonic()-start,cpu_seconds=u.ru_utime+u.ru_stime,peak_rss_bytes_darwin=u.ru_maxrss,stdout_sha256=sha(out/(label+'.stdout')),stderr_sha256=sha(out/(label+'.stderr')))
 rows.append(row);save('commands.json',rows);assert row['exit']==0 and not timed,row
 return (out/(label+'.stdout')).read_bytes()
run('compiler-signature',['codesign','--verify','--strict',compiler])
builder=out/'bulk-builder';run('build',[compiler,'build','tests/m19ef/old-mark-proto/builder.mio','--bunko-root',snap/'bunko','-o',builder]);run('builder-signature',['codesign','--verify','--strict',builder])
image=out/'bulk-native';args=[builder,snap,'tests/m19ef/old-mark-bulk/ordinary/main.mio',snap/'bunko'];run('generate',args+[image,'16777216']);run('signature',['codesign','--verify','--strict',image]);copy=out/'bulk-reproduced-native';run('reproduce',args+[copy,'16777216']);assert image.read_bytes()==copy.read_bytes()
observations=[]
for repeat in range(8):
 label='bulk-'+str(repeat);stdout=run(label,[image],60);observations.append(verify_bulk(stdout,(out/(label+'.stderr')).read_bytes()))
save('observations.json',observations)
failed=r/'build/m19ef-evidence/E4-faults-E6-accept-20261103-01'
try:verify_bulk((failed/'bulk-21.stdout').read_bytes(),(failed/'bulk-21.stderr').read_bytes())
except AssertionError as exc:save('historical-failure-rejection.json',dict(status='REJECTED_UNCHANGED',predicate=repr(exc)))
else:raise AssertionError('old zero-white packet must remain rejected')
for replacement in (b'0',b'-1'):
 lines=stdout.splitlines();lines[4]=replacement
 try:verify_bulk(b'\n'.join(lines)+b'\n',(out/'bulk-7.stderr').read_bytes())
 except AssertionError:pass
 else:raise AssertionError('nonpositive white count falsely accepted')
assert all(sha(r/k)==v for k,v in manifest.items())
save('summary.json',dict(status='PASS_DIRECTED_SAME_EPOCH_BULK_WHITE_HANDSHAKE',native_runs=8,minimum_real_prewhite=min(x['prewhite'] for x in observations),canonical_unchanged=True,E6='IN_PROGRESS'))
