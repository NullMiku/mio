#!/usr/bin/env python3
"""Native protocol-component regression; controlled inputs, never GC acceptance."""
from pathlib import Path
import argparse,fcntl,hashlib,json,os,shutil,signal,struct,subprocess,time,traceback
p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--compiler',required=True,type=Path);p.add_argument('--compiler-sha256',required=True);a=p.parse_args();r=Path.cwd();out=a.output.resolve();assert out.is_relative_to(r/'build/m19ef-evidence');out.mkdir();sha=lambda q:hashlib.sha256(q.read_bytes()).hexdigest();assert sha(a.compiler)==a.compiler_sha256
lock=os.fdopen(os.dup(int(os.environ['MIO_E5_TEST_LOCK_FD'])),'a+') if 'MIO_E5_TEST_LOCK_FD' in os.environ else (r/'build/.m19ef-native-test.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
rows=[];manifest={str(q.relative_to(r)):sha(q) for top in ('bunko','selfhost','tests/m19ef') for q in (r/top).rglob('*.mio')};folder=r/'tests/m19ef/e6/registry-park';pins=json.loads((folder/'before-pins.json').read_text());assert sha(folder/'before-registry-lock.mio.fixture')==pins['factory_sha256'];assert sha(folder/'before-gc-park.mio.fixture')==pins['park_factory_sha256']
def save(n,x):(out/n).write_text(json.dumps(x,sort_keys=True,indent=2)+'\n')
save('source-manifest.json',manifest);save('plan.json',dict(compiler_sha256=a.compiler_sha256,before_pins=pins,scope='actual registry_lock native instructions with controlled clock/completed-park inputs; not concurrent GC',soft_seconds=1,hard_seconds=30,retries=0))
def run(label,argv,timeout=240):
 start=time.monotonic();print(label,'START',flush=True);timed=False
 with (out/(label+'.stdout')).open('xb') as so,(out/(label+'.stderr')).open('xb') as se:
  c=subprocess.Popen(list(map(str,argv)),cwd=r,stdout=so,stderr=se,start_new_session=True)
  while True:
   got,status,u=os.wait4(c.pid,os.WNOHANG)
   if got:break
   if time.monotonic()-start>timeout:timed=True;os.killpg(c.pid,signal.SIGKILL);_,status,u=os.wait4(c.pid,0);break
   time.sleep(.05)
 row=dict(label=label,argv=list(map(str,argv)),exit=os.waitstatus_to_exitcode(status),expected_exit=0,timed_out=timed,wall_seconds=time.monotonic()-start,cpu_seconds=u.ru_utime+u.ru_stime,peak_rss_bytes_darwin=u.ru_maxrss,stdout_sha256=sha(out/(label+'.stdout')),stderr_sha256=sha(out/(label+'.stderr')));rows.append(row);save('commands.json',rows);print(label,row['exit'],flush=True);assert row['exit']==0 and not timed;assert all(sha(r/k)==v for k,v in manifest.items());return (out/(label+'.stdout')).read_bytes()
try:
 old=out/'before-bunko';shutil.copytree(r/'bunko',old);path=old/'kiso/runtime/gc/threads.mio';text=path.read_text();start=text.index('waza registry_lock_program(');end=text.index('\nwaza ',start+5);path.write_text(text[:start]+(folder/'before-registry-lock.mio.fixture').read_text().rstrip()+'\n'+text[end:])
 expected_before=[(2,3000000000,2,0,9,1),(2,3000000000,1,1,9,1),(2,3000000000,2,1,9,1),(0,3000000000,1,1,10,1)]
 expected_after=[(0,3000000000,2,1,9,1),(2,3000000000,1,1,9,1),(2,31000000000,16,1,9,15),(0,3000000000,1,1,10,1)]
 for label,bunko,expected in [('before',old,expected_before),('current',r/'bunko',expected_after)]:
  builder=out/(label+'-builder');run(label+'-build',[a.compiler.resolve(),'build',folder/'main.mio','--bunko-root',bunko,'-o',builder]);run(label+'-builder-signature',['codesign','--verify','--strict',builder]);prefix=out/(label+'-native');run(label+'-generate',[builder,prefix]);copy=out/(label+'-repro');run(label+'-reproduce',[builder,copy])
  for i in range(4):
   native=out/(label+'-native-'+str(i));assert native.read_bytes()==(out/(label+'-repro-'+str(i))).read_bytes();run(label+'-signature-'+str(i),['codesign','--verify','--strict',native]);got=struct.unpack('<6Q',run(label+'-mode-'+str(i),[native]));assert got==expected[i],(label,i,got)
   if label=='before':assert sha(native)==pins['native_signed_sha256'][str(i)]
 old_park=out/'before-park-bunko';shutil.copytree(r/'bunko',old_park);path=old_park/'kiso/runtime/gc/safepoints.mio';text=path.read_text();start=text.index('waza gc_park_locked_program()');end=text.index('\nwaza ',start+5);path.write_text(text[:start]+(folder/'before-gc-park.mio.fixture').read_text().rstrip()+'\n'+text[end:])
 for label,bunko,expected in [('resume-before',old_park,(0,7,8,8,8192,0,1)),('resume-current',r/'bunko',(0,7,7,8,8192,0,1))]:
  builder=out/(label+'-builder');run(label+'-build',[a.compiler.resolve(),'build',folder/'resume.mio','--bunko-root',bunko,'-o',builder]);run(label+'-builder-signature',['codesign','--verify','--strict',builder]);native=out/(label+'-native');run(label+'-generate',[builder,native]);copy=out/(label+'-repro');run(label+'-reproduce',[builder,copy]);assert native.read_bytes()==copy.read_bytes();run(label+'-signature',['codesign','--verify','--strict',native]);got=struct.unpack('<7Q',run(label,[native]));assert got==expected,(label,got)
  if label=='resume-before':assert sha(native)==pins['resume_native_signed_sha256']
 save('summary.json',dict(status='PASS_REGISTRY_PARK_PROTOCOL_COMPONENT',before_false_timeout_reproduced=True,completion_epoch_publication='actual acknowledged Epoch; future request rejected',real_gc='NOT_CLAIMED; independent actual Epoch32/full E3-E6 required',soft_seconds=1,hard_seconds=30,source_unchanged=True))
except BaseException as e:save('FAIL.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
