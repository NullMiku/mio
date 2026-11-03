#!/usr/bin/env python3
"""Fresh main-checkout E3 then complete E6; serial native work, no old PASS reuse."""
from pathlib import Path
import argparse,fcntl,hashlib,json,os,signal,subprocess,sys,time,traceback
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--out',required=True,type=Path)
p.add_argument('--compiler',required=True,type=Path)
p.add_argument('--compiler-sha256',required=True)
p.add_argument('--historical-e3',required=True,type=Path)
p.add_argument('--los-before-builder',required=True,type=Path)
a=p.parse_args();r=Path(__file__).resolve().parents[3];os.chdir(r)
out=a.out.resolve();compiler=a.compiler.resolve()
assert out.is_relative_to(r/'build/m19ef-evidence')
assert hashlib.sha256(compiler.read_bytes()).hexdigest()==a.compiler_sha256
assert subprocess.check_output(['git','branch','--show-current'],text=True).strip()=='Mio-2.1'
(r/'build').mkdir(exist_ok=True);lock=os.fdopen(os.dup(int(os.environ['MIO_E5_TEST_LOCK_FD'])),'a+') if 'MIO_E5_TEST_LOCK_FD' in os.environ else (r/'build/.m19ef-native-test.lock').open('a+')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);out.mkdir(parents=True)
env=dict(os.environ,MIO_NATIVE_COMPILER=str(compiler),MIO_NATIVE_COMPILER_SHA256=a.compiler_sha256,MIO_E5_TEST_LOCK_FD=str(lock.fileno()))
rows=[]
def save(name,obj):(out/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def run(label,args,deadline):
 start=time.monotonic();print(label,'START',flush=True)
 with (out/(label+'.stdout')).open('xb') as so,(out/(label+'.stderr')).open('xb') as se:
  child=subprocess.Popen(list(map(str,args)),cwd=r,env=env,stdout=so,stderr=se,start_new_session=True,pass_fds=(lock.fileno(),))
  save('active-process.json',dict(label=label,pid=child.pid,argv=list(map(str,args))))
  try:code=child.wait(timeout=deadline);timed=False
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);code=child.wait();timed=True
 rows.append(dict(label=label,argv=list(map(str,args)),cwd=str(r),exit=code,expected_exit=0,timed_out=timed,wall_seconds=time.monotonic()-start))
 save('commands.json',rows);print(label,code,flush=True);assert code==0 and not timed,rows[-1]
try:
 save('plan.json',dict(status='RUNNING',E6='IN_PROGRESS',M19e='NOT_ACCEPTED',compiler=str(compiler),compiler_sha256=a.compiler_sha256,worktree=str(r),stages=['fresh complete E3','complete E6 including E4, E5 fixed32 and NEW ABCD'],retries=0))
 e3=out/('E3-'+out.name);run('E3',[sys.executable,r/'tests/m19ef/user-workers/run.py',e3],14400)
 e6=out/('accept-'+out.name);run('E6',[sys.executable,r/'tests/m19ef/e6/accept.py',e6,e3,'--compiler',compiler,'--compiler-sha256',a.compiler_sha256,'--historical-e3',a.historical_e3.resolve(),'--los-before-builder',a.los_before_builder.resolve()],43200)
 save('summary.json',dict(status='SUITES_FINISHED_PENDING_G6_REVIEW',E6='IN_PROGRESS_PENDING_GATE_REVIEW',M19e='NOT_ACCEPTED'))
except BaseException as exc:
 save('FAIL.json',dict(status='CANDIDATE_ENDED_REPAIR_REQUIRED',error=repr(exc),traceback=traceback.format_exc(),E6='IN_PROGRESS',M19e='NOT_ACCEPTED'));raise
