#!/usr/bin/env python3
"""Native-only resource refresh/current CLI build, directed checks, then fresh E3/E6."""
from pathlib import Path
import argparse,fcntl,hashlib,json,os,re,shutil,signal,subprocess,sys,time,traceback
p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--compiler',required=True,type=Path);p.add_argument('--compiler-sha256',required=True);p.add_argument('--e6-output',type=Path);p.add_argument('--historical-e3',type=Path);p.add_argument('--los-before-builder',type=Path);a=p.parse_args()
r=Path.cwd();out=a.output.resolve();assert out.is_relative_to(r/'build/m19ef-evidence');out.mkdir()
lock=(r/'build/.m19ef-native-test.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest();compiler=a.compiler.resolve();assert sha(compiler)==a.compiler_sha256
rows=[];manifest={};snap=out/'source-snapshot'
def save(name,data):(out/name).write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')
def unchanged():assert all(sha(r/name)==digest and sha(snap/name)==digest for name,digest in manifest.items()),'frozen source changed'
def run(label,args,timeout=1800,expected=0,cwd=None):
 args=list(map(str,args));cwd=cwd or r;start=time.monotonic();print(label,'START',flush=True)
 with (out/(label+'.stdout')).open('xb') as so,(out/(label+'.stderr')).open('xb') as se:
  child=subprocess.Popen(args,cwd=cwd,stdout=so,stderr=se,start_new_session=True,env=dict(os.environ,MIO_E5_TEST_LOCK_FD=str(lock.fileno())),pass_fds=(lock.fileno(),));timed=False
  save('active-process.json',dict(label=label,pid=child.pid,argv=args,cwd=str(cwd)))
  while True:
   got,status,u=os.wait4(child.pid,os.WNOHANG)
   if got:break
   if time.monotonic()-start>timeout:
    timed=True;os.killpg(child.pid,signal.SIGKILL);_,status,u=os.wait4(child.pid,0);break
   time.sleep(.1)
 row=dict(label=label,argv=args,cwd=str(cwd),exit=os.waitstatus_to_exitcode(status),expected_exit=expected,timed_out=timed,wall_seconds=time.monotonic()-start,cpu_seconds=u.ru_utime+u.ru_stime,peak_rss_bytes_darwin=u.ru_maxrss,stdout_sha256=sha(out/(label+'.stdout')),stderr_sha256=sha(out/(label+'.stderr')))
 rows.append(row);save('commands.json',rows);print(label,row['exit'],flush=True);assert row['exit']==expected and not timed,row
 if manifest:unchanged()
 return (out/(label+'.stdout')).read_bytes()
try:
 run('compiler-signature',['codesign','--verify','--strict',compiler])
 full=json.loads(run('all-typecheck-tests',[compiler,'test','selfhost/typecheck','--bunko-root',r/'bunko','--format=json']))
 assert full['summary']['failed']==0 and full['summary']['passed']>=2
 bundle=r/'selfhost/resources/bunko_data.mio';shutil.copyfile(bundle,out/'pre-resource-bunko_data.mio')
 generator=out/'resource-generator';run('resource-generator-build',[compiler,'build','selfhost/embed-bunko/main.mio','--bunko-root',r/'bunko','-o',generator]);run('resource-generator-signature',['codesign','--verify','--strict',generator])
 config=out/'resource-config';config.mkdir();(config/'input.config').write_text(str(r/'bunko'));(config/'output.config').write_text(str(bundle));run('resource-refresh',[generator],cwd=config)
 pattern=r'path: ("(?:[^"\\]|\\.)*"), version: "[^"\n]+", length: (\d+), sha256: "([0-9a-f]+)", source: ("(?:[^"\\]|\\.)*")'
 entries={}
 for path,length,digest,source in re.findall(pattern,bundle.read_text()):
  name=json.loads(path);data=json.loads(source).encode();assert name not in entries and len(data)==int(length) and hashlib.sha256(data).hexdigest()==digest;entries[name]=digest
 expected={str(q.relative_to(r/'bunko')):sha(q) for q in (r/'bunko/kiso').rglob('*.mio') if not q.name.endswith('_test.mio')};assert entries==expected,(len(entries),len(expected))
 save('resource-verification.json',dict(status='PASS_EXACT_NATIVE_GENERATED_BUNDLE',count=len(entries),entries=entries,source_sha256=sha(bundle),prior_bundle_sha256=sha(out/'pre-resource-bunko_data.mio')))
 snap.mkdir()
 for folder in ('bunko','selfhost','tests','specs','tools'):
  for source in sorted((r/folder).rglob('*')):
   if source.is_file() and source.suffix in ('.mio','.py','.sh','.md','.json','.txt','.fixture'):
    rel=source.relative_to(r);dest=snap/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest);manifest[str(rel)]=sha(source)
 shutil.copyfile(r/'VERSION',snap/'VERSION');manifest['VERSION']=sha(r/'VERSION');save('source-manifest.json',manifest)
 # The prior compiler emits its own embedded Runtime. First compile the new
 # emitter, then use it to emit a CLI that actually runs the repaired Runtime.
 # A single source rebuild would leave this candidate executing the old GC.
 generation_a=out/'mio-A';run('new-emitter-full-CLI-build',[compiler,'build','selfhost/cli','--bunko-root',snap/'bunko','-o',generation_a],cwd=snap);run('new-emitter-signature',['codesign','--verify','--strict',generation_a])
 current=out/'mio-current';run('current-full-CLI-build',[generation_a,'build','selfhost/cli','--bunko-root',snap/'bunko','-o',current],cwd=snap);run('current-signature',['codesign','--verify','--strict',current]);run('current-version',[current,'version'])
 fixture=snap/'tests/m19ef/e6/socket/main.mio';run('current-TCP-check',[current,'check',fixture,'--bunko-root',snap/'bunko'],cwd=snap);run('current-embedded-TCP-check',[current,'check',fixture],cwd=snap)
 for name in ('bad-fs','bad-socket'):
  run('reject-'+name,[current,'check',snap/'tests/m19ef/e6/socket'/name/'main.mio','--bunko-root',snap/'bunko'],expected=1,cwd=snap)
  assert b'E0301' in (out/('reject-'+name+'.stderr')).read_bytes()
 run('real-current-CLI-LSP',[sys.executable,snap/'tests/m19ef/e6/lsp_session.py',current,out/'current-LSP',snap/'bunko'],180)
 unchanged();save('summary.json',dict(status='PASS_NEW_CURRENT_CLI_DIRECTED',compiler=str(current),compiler_sha256=sha(current),source_manifest_sha256=sha(out/'source-manifest.json'),typecheck_tests=full['summary']['passed'],source_unchanged=True,ABCD='NEW_REQUIRED_NOT_SUBSTITUTED',E6='IN_PROGRESS',M19e='NOT_ACCEPTED'))
 if a.e6_output:
  assert a.historical_e3 is not None and a.los_before_builder is not None,'explicit historical E3 and LOS before-builder references are required for E6'
  run('fresh-E3-then-E6',[sys.executable,r/'tests/m19ef/e6/resume.py','--out',a.e6_output,'--compiler',current,'--compiler-sha256',sha(current),'--historical-e3',a.historical_e3.resolve(),'--los-before-builder',a.los_before_builder.resolve()],57600)
except BaseException as exc:
 save('FAIL.json',dict(error=repr(exc),traceback=traceback.format_exc(),E6='IN_PROGRESS',M19e='NOT_ACCEPTED'));raise
