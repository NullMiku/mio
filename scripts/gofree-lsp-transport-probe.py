#!/usr/bin/env python3
"""Isolated native LSP framed-I/O audit, including response before stdin EOF."""
import argparse,json,os,selectors,signal,subprocess,time,hashlib
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--program',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(exist_ok=False,parents=True);program=a.program.resolve();policy=out/'runtime.sb';policy.write_text('(version 1)(allow default)(deny network*)(deny process-fork)(deny process-exec)(allow process-exec (literal '+json.dumps(str(program))+'))\n');argv=['/usr/bin/sandbox-exec','-f',str(policy),str(program)];results=[]
def frame(body):return b'Content-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body
def run(name,data,expected,code):
 start=time.monotonic();proc=subprocess.Popen(argv,env={'PATH':''},stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
 try:stdout,stderr=proc.communicate(data,timeout=5);status=proc.returncode
 except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);stdout,stderr=proc.communicate();status=None
 (out/(name+'.stdout')).write_bytes(stdout);(out/(name+'.stderr')).write_bytes(stderr);results.append({'case':name,'status':'PASS' if status==code and stdout==expected else 'FAIL','exit':status,'input_hex':data.hex(),'wall_seconds':time.monotonic()-start})
bodies=[b'{}','{"id":12345678901234567890,"text":"中文😀"}'.encode(),b'',b'a\0b',b'x'*20000]
run('pipeline',b''.join(map(frame,bodies)),b''.join(map(frame,bodies)),0)
run('unknown-case-duplicate',b'Other: x\r\ncOnTeNt-LeNgTh: 9\nContent-Length: +2\r\n\r\n{}',frame(b'{}'),0)
run('unicode-whitespace',' Content-Length : 2 \n\n{}'.encode(),frame(b'{}'),0)
run('missing',b'Other: x\n\n{}',b'',1)
run('negative',b'Content-Length: -1\n\n',b'',1)
run('overflow',b'Content-Length: 9223372036854775808\n\n',b'',1)
run('oversize',b'Content-Length: 67108865\n\n',b'',1)
run('truncated',b'Content-Length: 4\n\n{}',b'',1)
run('bad-header',b'no-colon\n\n',b'',1)
run('nul',b'Content-Length: \x002\n\n{}',b'',1)
run('header-section-limit',b'X:'+b'a'*65536+b'\n\n',b'',1)
# Feed fragments through a live pipe and require each response before closing it.
proc=subprocess.Popen(argv,env={'PATH':''},stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True);sel=selectors.DefaultSelector();sel.register(proc.stdout,selectors.EVENT_READ);captured=b'';ok=True;start=time.monotonic()
try:
 for i,body in enumerate([b'{}','{"id":"😀"}'.encode(),b'x'*9000]):
  wire=frame(body)
  for at in range(0,len(wire),7):proc.stdin.write(wire[at:at+7]);proc.stdin.flush()
  expected=frame(body);received=b'';deadline=time.monotonic()+3
  while len(received)<len(expected):
   remaining=deadline-time.monotonic()
   if remaining<=0 or not sel.select(remaining):ok=False;break
   chunk=os.read(proc.stdout.fileno(),min(65536,len(expected)-len(received)))
   if not chunk:ok=False;break
   received+=chunk
  captured+=received;ok=ok and received==expected
  if not ok:break
 proc.stdin.close();proc.wait(timeout=5);stderr=proc.stderr.read();ok=ok and proc.returncode==0
except Exception as e:
 ok=False;stderr=str(e).encode();os.killpg(proc.pid,signal.SIGKILL);proc.wait()
finally:sel.close()
(out/'live.stdout').write_bytes(captured);(out/'live.stderr').write_bytes(stderr);results.append({'case':'fragmented-live-response-before-eof','status':'PASS' if ok else 'FAIL','exit':proc.returncode,'wall_seconds':time.monotonic()-start})
(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');(out/'provenance.json').write_text(json.dumps({'argv':argv,'program_sha256':hashlib.sha256(program.read_bytes()).hexdigest(),'scope':'framing only, not full language-server acceptance'},indent=2)+'\n');print(json.dumps({'passed':sum(x['status']=='PASS' for x in results),'total':len(results)},indent=2),flush=True);raise SystemExit(0 if all(x['status']=='PASS' for x in results) else 1)
