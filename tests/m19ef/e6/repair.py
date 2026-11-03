#!/usr/bin/env python3
"""Bounded native LSP/policy directed validation, then current full CLI build."""
from pathlib import Path
import fcntl,hashlib,json,os,shutil,signal,subprocess,sys,time,traceback
r=Path.cwd();out=(r/sys.argv[1]).resolve();assert out.is_relative_to(r/'build/m19ef-evidence');out.mkdir()
lock=(r/'build/.m19ef-native-test.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
compiler=r/'build/m19ef-evidence/ABCD-20261102-183902/mio-D'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();assert sha(compiler)=='19c61aacf4580a97979764325037e808bda06d523579626449b51c276e344e4c'
def save(name,data):(out/name).write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')
snap=out/'source-snapshot';snap.mkdir();manifest={};rows=[]
for folder in ('bunko','selfhost','tests/m19ef'):
 for p in sorted((r/folder).rglob('*')):
  if p.is_file() and p.suffix in ('.mio','.py','.sh'):
   rel=p.relative_to(r);dest=snap/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);manifest[str(rel)]=sha(p)
save('source-manifest.json',manifest);shutil.copyfile(__file__,out/'controller.py')
def run(label,args,timeout=1800,cwd=None):
 args=list(map(str,args));start=time.monotonic();print(label,'START',flush=True)
 with (out/(label+'.stdout')).open('xb') as so,(out/(label+'.stderr')).open('xb') as se:
  child=subprocess.Popen(args,cwd=cwd or snap,stdout=so,stderr=se,start_new_session=True,env=dict(os.environ,MIO_E5_TEST_LOCK_FD=str(lock.fileno())),pass_fds=(lock.fileno(),));timed=False
  while True:
   got,status,u=os.wait4(child.pid,os.WNOHANG)
   if got:break
   if time.monotonic()-start>timeout:
    timed=True;os.killpg(child.pid,signal.SIGKILL);_,status,u=os.wait4(child.pid,0);break
   time.sleep(.05)
 row=dict(label=label,argv=args,exit=os.waitstatus_to_exitcode(status),timed_out=timed,wall_seconds=time.monotonic()-start,cpu_seconds=u.ru_utime+u.ru_stime,peak_rss_bytes_darwin=u.ru_maxrss,stdout_sha256=sha(out/(label+'.stdout')),stderr_sha256=sha(out/(label+'.stderr')))
 rows.append(row);save('commands.json',rows);print(label,row['exit'],flush=True);assert row['exit']==0 and not timed,row
 return (out/(label+'.stdout')).read_bytes()
try:
 run('compiler-signature',['codesign','--verify','--strict',compiler])
 tests=json.loads(run('queued-cancel-tests',[compiler,'test','selfhost/lsp/rpc','--run=test_rpc_(same_read_pending_cancel|pending_cancel_request)','--bunko-root',snap/'bunko','--format=json']))
 assert tests['summary']['failed']==0 and tests['summary']['passed']==2
 server=out/'lsp-native';run('minimal-server-build',[compiler,'build','tests/m19ef/e6/lsp_native.mio','--bunko-root',snap/'bunko','-o',server]);run('minimal-server-signature',['codesign','--verify','--strict',server])
 run('real-stdio',[sys.executable,snap/'tests/m19ef/e6/lsp_session.py',server,out/'stdio-proof',snap/'bunko'],180,cwd=r)
 run('memory-policy',[sys.executable,snap/'tests/m19ef/e6/memory/run.py',out/'memory-proof',compiler,sha(compiler)],1800,cwd=r)
 current=out/'mio-current';run('current-full-CLI-build',[compiler,'build','selfhost/cli','--bunko-root',snap/'bunko','-o',current]);run('current-signature',['codesign','--verify','--strict',current])
 run('real-current-CLI-stdio',[sys.executable,snap/'tests/m19ef/e6/lsp_session.py',current,out/'current-CLI-stdio-proof',snap/'bunko'],180,cwd=r)
 assert all(sha(r/k)==v and sha(snap/k)==v for k,v in manifest.items())
 save('summary.json',dict(status='PASS_DIRECTED_LSP_POLICY_CURRENT_CLI',compiler=str(current),compiler_sha256=sha(current),source_manifest_sha256=sha(out/'source-manifest.json'),new_source_ABCD='REQUIRED_NOT_REUSED',E6='IN_PROGRESS'))
except BaseException as exc:
 save('FAIL.json',dict(status='FAIL_REPAIR_REQUIRED',error=repr(exc),traceback=traceback.format_exc()));raise
