#!/usr/bin/env python3
"""Native observed LOS pressure regression; preserves before/after artifacts."""
from pathlib import Path
import argparse,fcntl,hashlib,json,os,signal,subprocess,time,traceback,shutil
p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--compiler',required=True,type=Path);p.add_argument('--compiler-sha256',required=True);p.add_argument('--before-builder',required=True,type=Path);p.add_argument('--prior-current-builder-proof',type=Path);a=p.parse_args()
r=Path.cwd();out=a.output.resolve();assert out.is_relative_to(r/'build/m19ef-evidence');out.mkdir()
lock=os.fdopen(os.dup(int(os.environ['MIO_E5_TEST_LOCK_FD'])),'a+') if 'MIO_E5_TEST_LOCK_FD' in os.environ else (r/'build/.m19ef-native-test.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
sha=lambda q:hashlib.sha256(q.read_bytes()).hexdigest();compiler=a.compiler.resolve();assert sha(compiler)==a.compiler_sha256
rows=[];manifest={str(q.relative_to(r)):sha(q) for top in ('bunko','selfhost','tests/m19ef') for q in (r/top).rglob('*.mio')}
def save(name,data):(out/name).write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')
save('source-manifest.json',manifest);save('plan.json',dict(compiler=str(compiler),compiler_sha256=sha(compiler),before_builder=str(a.before_builder.resolve()),before_builder_sha256=sha(a.before_builder),heap_capacity=8388608,retries=0))
def run(label,argv,expected=0,timeout=1800):
 argv=list(map(str,argv));start=time.monotonic();print(label,'START',flush=True);timed=False
 with (out/(label+'.stdout')).open('xb') as so,(out/(label+'.stderr')).open('xb') as se:
  child=subprocess.Popen(argv,cwd=r,stdout=so,stderr=se,start_new_session=True)
  while True:
   got,status,u=os.wait4(child.pid,os.WNOHANG)
   if got:break
   if time.monotonic()-start>timeout:
    timed=True;os.killpg(child.pid,signal.SIGKILL);_,status,u=os.wait4(child.pid,0);break
   time.sleep(.05)
 row=dict(label=label,argv=argv,cwd=str(r),exit=os.waitstatus_to_exitcode(status),expected_exit=expected,timed_out=timed,wall_seconds=time.monotonic()-start,cpu_seconds=u.ru_utime+u.ru_stime,peak_rss_bytes_darwin=u.ru_maxrss,stdout_sha256=sha(out/(label+'.stdout')),stderr_sha256=sha(out/(label+'.stderr')));rows.append(row);save('commands.json',rows);print(label,row['exit'],flush=True);assert row['exit']==expected and not timed,row
 assert all(sha(r/k)==v for k,v in manifest.items())
 return (out/(label+'.stdout')).read_bytes()
def metrics(label):
 result={}
 for line in (out/(label+'.stderr')).read_text().splitlines():
  assert line.startswith('mio-gc '),line;k,v=line[7:].split('=');assert k not in result;result[k]=int(v)
 return result
try:
 fixture=r/'tests/m19ef/e6/los-pressure/main.mio';bunko=r/'bunko'
 old=out/'before-native';run('before-generate',[a.before_builder.resolve(),r,fixture,bunko,old,8388608]);run('before-signature',['codesign','--verify','--strict',old])
 assert run('before-control',[old,'control'],timeout=30)==b'7000000\n'
 assert run('before-churn',[old,'garbage'],2,30)==b'40\n'*50
 before=metrics('before-churn');assert before['heap_capacity']==8388608 and before['los_objects']==0 and before['heap_live_bytes']<1024 and before['oom_request_bytes']==7000048
 assert before['heap_committed']+before['oom_request_bytes']>before['heap_limit']
 builder=out/'builder'
 if a.prior_current_builder_proof:
  prior=a.prior_current_builder_proof.resolve();proof=json.loads((prior/'summary.json').read_text())
  assert proof['status']=='PASS_LOS_PRESSURE_DIRECTED' and proof['source_unchanged']
  assert json.loads((prior/'source-manifest.json').read_text())==manifest
  plan=json.loads((prior/'plan.json').read_text());assert plan['compiler_sha256']==sha(compiler)
  logs=json.loads((prior/'commands.json').read_text())
  for row in logs:
   assert row['exit']==row['expected_exit'] and not row['timed_out']
   for stream in ('stdout','stderr'):assert sha(prior/(row['label']+'.'+stream))==row[stream+'_sha256']
  shutil.copy2(prior/'builder',builder);save('retained-builder.json',dict(path=str(prior),sha256=sha(builder),source_manifest_sha256=sha(prior/'source-manifest.json'),scope='exact native generator retained, not a new build'))
 else:run('current-builder-build',[compiler,'build',r/'tests/m19ef/e6/los-pressure/builder.mio','--bunko-root',bunko,'-o',builder])
 run('current-builder-signature',['codesign','--verify','--strict',builder])
 native=out/'native';run('current-generate',[builder,r,fixture,bunko,native,8388608]);run('current-signature',['codesign','--verify','--strict',native])
 copy=out/'native-copy';run('current-reproduce',[builder,r,fixture,bunko,copy,8388608]);assert native.read_bytes()==copy.read_bytes()
 for mode,expected_output,code in [('control',b'7000000\n',0),('garbage',b'40\n'*50+b'7000000\n',0),('preserved',b'40\n'*50+b'7000000\n128\n255\n41\n',0),('overlimit',b'',2)]:
  label='current-'+mode;assert run(label,[native,mode],code,30)==expected_output
  m=metrics(label);assert m['heap_capacity']==8388608 and m['heap_limit']==before['heap_limit'];assert m['heap_live_bytes']<=8388608
  if code==0:assert m['oom_request_bytes']==0
  if mode=='garbage':assert m['los_reclaimed_bytes']>=262240000 and m['los_objects']==1
  if mode=='preserved':assert m['los_objects']==2
 # Test-only adapter copy: every pressure-pass munmap gets an unaligned
 # address and must fail through the real public kernel ABI. Production source
 # is untouched; retained dead mappings must remain charged and OOM bounded.
 overlay=out/'unmap-failure-bunko';shutil.copytree(bunko,overlay)
 source=overlay/'kiso/aot/lower/large_objects.mio';text=source.read_text()
 old='move_x(code,0,20); emit(code,arm64.movz_x(16,73,0));'
 assert text.count(old)==1
 source.write_text(text.replace(old,'move_x(code,0,20); moshi(pressure){emit(code,arm64.add_imm_x(0,0,1,iie));} emit(code,arm64.movz_x(16,73,0));'))
 failed_builder=out/'unmap-failure-builder';run('failure-builder-build',[compiler,'build',r/'tests/m19ef/e6/los-pressure/builder.mio','--bunko-root',overlay,'-o',failed_builder]);run('failure-builder-signature',['codesign','--verify','--strict',failed_builder])
 failed_native=out/'unmap-failure-native';run('failure-generate',[failed_builder,r,fixture,bunko,failed_native,8388608]);run('failure-signature',['codesign','--verify','--strict',failed_native])
 assert run('failure-churn',[failed_native,'garbage'],2,30)==b'40\n'*50
 failed=metrics('failure-churn');assert failed['los_objects']==0 and failed['heap_live_bytes']<1024 and failed['oom_request_bytes']==7000048
 assert failed['heap_limit']==before['heap_limit'] and failed['heap_committed']+failed['oom_request_bytes']>failed['heap_limit']
 save('summary.json',dict(status='PASS_LOS_PRESSURE_DIRECTED',before_false_oom=before,failed_unmap_retains_charge=failed,native_sha256=sha(native),source_unchanged=True,scope='same 8 MiB heap, real LOS/GC/unmap; existing true over-capacity OOM retained',E6='IN_PROGRESS_NEW_FULL_REGRESSION_AND_ABCD_REQUIRED'))
except BaseException as e:save('FAIL.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
