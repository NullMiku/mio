#!/usr/bin/env python3
"""Isolated unified CLI diagnostics/color gates, including a real pseudoterminal."""
import argparse,errno,hashlib,json,os,pty,selectors,shutil,subprocess,tempfile,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
work=Path(tempfile.mkdtemp(prefix='mio-diagnostics-',dir='/tmp')).resolve();cli=work/'mio';shutil.copy2(a.candidate,cli)
policy=work/'native.sb';policy.write_text('(version 1)(allow default)(deny network*)(deny process-fork)(deny process-exec)(allow process-exec (literal '+json.dumps(str(cli))+'))(deny file-read* (subpath '+json.dumps(str(root))+'))(deny file-read* (subpath "/Volumes/Sector0/AppData/Mio/mio"))\n')
(work/'错误.mio').write_text('kaku 値 = 1;\r\n');(work/'syntax.mio').write_text('kaku n = 1');(work/'type.mio').write_text('kaku n: int64="wrong";');(work/'valid.mio').write_text('kaku n: int64=1;')
results=[];commands=[]
def run(label,args,env=None,terminal=False):
 argv=['/usr/bin/sandbox-exec','-f',str(policy),str(cli),*args];environment={'PATH':'','TERM':'xterm-256color'};environment.update(env or {});start=time.monotonic()
 if not terminal:
  r=subprocess.run(argv,cwd=work,env=environment,capture_output=True,timeout=30);code=r.returncode;stdout=r.stdout;stderr=r.stderr
 else:
  master,slave=pty.openpty();proc=subprocess.Popen(argv,cwd=work,env=environment,stdout=subprocess.PIPE,stderr=slave);os.close(slave);selector=selectors.DefaultSelector();selector.register(master,selectors.EVENT_READ);data=bytearray();deadline=time.monotonic()+30
  while True:
   assert selector.select(max(0,deadline-time.monotonic())),'pseudoterminal deadline'
   try:block=os.read(master,65536)
   except OSError as exc:
    if exc.errno==errno.EIO:break
    raise
   if not block:break
   data.extend(block)
  os.close(master);selector.close();code=proc.wait(timeout=5);stdout=proc.stdout.read();stderr=bytes(data)
 (out/(label+'.stdout')).write_bytes(stdout);(out/(label+'.stderr')).write_bytes(stderr);commands.append({'label':label,'argv':argv,'cwd':str(work),'environment':environment,'terminal':terminal,'exit':code,'seconds':time.monotonic()-start});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');return code,stdout,stderr

def record(label,ok,**details):
 results.append({'case':label,'status':'PASS' if ok else 'FAIL',**details});(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(label,results[-1]['status'],flush=True)
c,o,e=run('short',['check','错误.mio','--format=short','--color=never']);record('short-source-code-path-no-ansi',c==1 and not o and b'error[E0001]' in e and b'\x1b' not in e and '错误.mio:1:6:'.encode() in e)
c,o,e=run('json',['check','--format=json',str(work/'错误.mio')]);d=None
try:d=json.loads(e)
except ValueError:pass
record('json-structured-source-span',c==1 and not o and isinstance(d,dict) and d.get('code')=='E0001' and d.get('path')==str(work/'错误.mio') and d.get('severity')=='error' and d.get('location',{}).get('offset')==5 and d.get('labels',[{}])[0].get('primary') is True)
c,o,e=run('syntax',['check','syntax.mio']);record('human-syntax-location-caret',c==1 and not o and b'error[E0101]' in e and b'syntax.mio:1:11' in e and b'^' in e and b'\x1b' not in e)
c,o,e=run('always',['check','type.mio','--color=always']);record('explicit-always-color',c==1 and not o and b'\x1b[1;31merror[E0301]' in e)
c,o,e=run('no-color',['check','type.mio','--color=always'],{'NO_COLOR':'1'});record('no-color-overrides-always',c==1 and b'\x1b' not in e)
c,o,e=run('json-color',['check','type.mio','--format=json','--color=always']);d=None
try:d=json.loads(e)
except ValueError:pass
record('json-never-colored',c==1 and not o and isinstance(d,dict) and d.get('code')=='E0301' and b'\x1b' not in e)
c,o,e=run('verbose',['build','syntax.mio','--verbose','-o','failed']);record('verbose-cause-no-artifact',c==1 and not o and b'= cause:' in e and b'E_PARSE' in e and not (work/'failed').exists())
c,o,e=run('auto-tty',['check','type.mio','--color=auto'],terminal=True);record('auto-real-tty-color',c==1 and not o and b'\x1b[1;31m' in e)
c,o,e=run('auto-ci',['check','type.mio','--color=auto'],{'CI':'1'},terminal=True);record('auto-ci-suppresses-color',c==1 and b'\x1b' not in e)
c,o,e=run('valid',['check','--format=json','valid.mio','--verbose']);record('successful-check-has-no-diagnostic-stream',c==0 and not o and not e)
c,o,e=run('bad-format',['check','valid.mio','--format=bad']);record('invalid-format-is-usage-error',c==2 and not o)
c,o,e=run('test-color',['test','.', '--run=(', '--color=always']);record('test-diagnostic-honors-color',c==1 and not o and b'\x1b' in e)
(out/'provenance.json').write_text(json.dumps({'candidate':str(a.candidate.resolve()),'candidate_sha256':hashlib.sha256(cli.read_bytes()).hexdigest(),'work':str(work),'scope':__doc__,'policy':policy.read_text()},indent=2)+'\n');raise SystemExit(0 if all(x['status']=='PASS' for x in results) else 1)
