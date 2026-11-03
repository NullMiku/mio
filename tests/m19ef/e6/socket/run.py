#!/usr/bin/env python3
"""Native Mio socket repair proof; actual loopback peers, no retries or sleeps in Mio."""
from pathlib import Path
import argparse,fcntl,hashlib,json,os,signal,socket,struct,subprocess,sys,threading,time,traceback
p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--compiler',type=Path,required=True);p.add_argument('--compiler-sha256',required=True);a=p.parse_args()
r=Path.cwd();out=a.output.resolve();assert out.is_relative_to(r/'build/m19ef-evidence');out.mkdir()
lock=os.fdopen(os.dup(int(os.environ['MIO_E5_TEST_LOCK_FD'])),'a+') if 'MIO_E5_TEST_LOCK_FD' in os.environ else (r/'build/.m19ef-native-test.lock').open('a+')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest();compiler=a.compiler.resolve();assert sha(compiler)==a.compiler_sha256
rows=[];manifest={str(q.relative_to(r)):sha(q) for folder in ('bunko','selfhost','tests/m19ef') for q in sorted((r/folder).rglob('*')) if q.is_file() and q.suffix in ('.mio','.py')}
def save(name,data):(out/name).write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')
save('source-manifest.json',manifest);save('plan.json',dict(scope='real Darwin ARM64 TCP library/native ABI, exact buffer validation, stale/foreign resource, zero-read/EOF and actual reset/SIGPIPE',native_cases=['lifecycle','bounds','client0','client1','server0','server1','reset0','reset1'],retries=0,E6='IN_PROGRESS',M19e='NOT_ACCEPTED'))
def run(label,args,timeout=1200,peer=None):
 args=list(map(str,args));print(label,'START',flush=True);start=time.monotonic();errors=[]
 with (out/(label+'.stdout')).open('xb') as so,(out/(label+'.stderr')).open('xb') as se:
  child=subprocess.Popen(args,cwd=r,stdout=so,stderr=se,start_new_session=True)
  save('active-process.json',dict(label=label,pid=child.pid,argv=args))
  def connect_peer():
   try:peer(child)
   except BaseException as exc:errors.append(repr(exc))
  thread=threading.Thread(target=connect_peer,daemon=True) if peer else None
  if thread:thread.start()
  timed=False
  while True:
   got,status,usage=os.wait4(child.pid,os.WNOHANG)
   if got:break
   if time.monotonic()-start>timeout:
    timed=True;os.killpg(child.pid,signal.SIGKILL);_,status,usage=os.wait4(child.pid,0);break
   time.sleep(.025)
  if thread:thread.join(25)
  row=dict(label=label,argv=args,cwd=str(r),exit=os.waitstatus_to_exitcode(status),expected_exit=0,timed_out=timed,wall_seconds=time.monotonic()-start,cpu_seconds=usage.ru_utime+usage.ru_stime,peak_rss_bytes_darwin=usage.ru_maxrss,peer_errors=errors,peer_finished=not thread or not thread.is_alive(),stdout_sha256=sha(out/(label+'.stdout')),stderr_sha256=sha(out/(label+'.stderr')))
 rows.append(row);save('commands.json',rows);print(label,row['exit'],flush=True);assert row['exit']==0 and not timed and not errors and row['peer_finished'],row
 return (out/(label+'.stdout')).read_bytes()
def exact(peer,count):
 data=b''
 while len(data)<count:
  block=peer.recv(count-len(data));assert block,'unexpected EOF';data+=block
 return data
payload=bytes([0,1,127,128,255])
try:
 run('compiler-signature',['codesign','--verify','--strict',compiler])
 unit=json.loads(run('typecheck-signatures',[compiler,'test','selfhost/typecheck','--run=test_native_(socket_signatures|boundary_argument_types)','--bunko-root',r/'bunko','--format=json']))
 assert unit['summary']['passed']==2 and unit['summary']['failed']==0,unit
 builder=out/'socket-builder';run('builder-build',[compiler,'build',r/'tests/m19ef/e6/socket/builder.mio','--bunko-root',r/'bunko','-o',builder]);run('builder-signature',['codesign','--verify','--strict',builder])
 image=out/'socket-native';generate=[builder,r,'tests/m19ef/e6/socket/main.mio',r/'bunko'];run('generate',generate+[image]);run('signature',['codesign','--verify','--strict',image]);copy=out/'socket-reproduced-native';run('reproduce',generate+[copy]);assert image.read_bytes()==copy.read_bytes()
 for case in ('lifecycle','bounds'):assert run(case,[image,case,'0'],30)==b'OK\n'
 for case in ('client','reset'):
  for repeat in range(2):
   label=case+str(repeat)
   with socket.socket() as listener:
    listener.settimeout(20);listener.bind(('127.0.0.1',0));listener.listen(1);port=listener.getsockname()[1]
    def peer(child):
     conn,_=listener.accept()
     with conn:
      conn.settimeout(10)
      if case=='reset':conn.setsockopt(socket.SOL_SOCKET,socket.SO_LINGER,struct.pack('ii',1,0));return
      assert exact(conn,5)==payload;conn.sendall(payload[:2]);conn.sendall(payload[2:]);conn.shutdown(socket.SHUT_WR);assert conn.recv(1)==b''
    assert run(label,[image,case,port],30,peer)==b'OK\n'
 for repeat in range(2):
  label='server'+str(repeat)
  with socket.socket() as reservation:reservation.bind(('127.0.0.1',0));port=reservation.getsockname()[1]
  def peer(child):
   deadline=time.monotonic()+20
   while (out/(label+'.stdout')).read_bytes()!=b'READY\n':
    assert time.monotonic()<deadline,'native listen readiness deadline';time.sleep(.01)
   with socket.create_connection(('127.0.0.1',port),timeout=10) as conn:
    conn.sendall(payload[:1]);conn.sendall(payload[1:]);assert exact(conn,5)==payload;assert conn.recv(1)==b''
  assert run(label,[image,'server',port],30,peer)==b'READY\nOK\n'
 assert all(sha(r/name)==digest for name,digest in manifest.items()),'frozen source changed'
 save('summary.json',dict(status='PASS_NATIVE_MIO_SOCKET_REPAIR',native_cases=8,native_typecheck_tests=2,source_unchanged=True,native_image_sha256=sha(image),compiler_sha256=sha(compiler),E6='IN_PROGRESS',M19e='NOT_ACCEPTED'))
except BaseException as exc:
 save('FAIL.json',dict(error=repr(exc),traceback=traceback.format_exc(),E6='IN_PROGRESS',M19e='NOT_ACCEPTED'));raise
