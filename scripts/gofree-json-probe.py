#!/usr/bin/env python3
"""Native JSON codec differential audit against independent JSON values."""
import argparse,json,os,shutil,signal,subprocess,time,hashlib,random
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--compiler',type=Path,required=True);p.add_argument('--cli',action='store_true');p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);compiler=a.compiler.resolve();commands=[]
def run(label,argv,stdin=None,timeout=180):
 with (out/(label+'.stdout')).open('wb') as stdout,(out/(label+'.stderr')).open('wb') as stderr:
  start=time.monotonic();proc=subprocess.Popen(['/usr/bin/time','-l',*map(str,argv)],cwd=out,env={'PATH':''},stdin=subprocess.PIPE,stdout=stdout,stderr=stderr,start_new_session=True)
  try:proc.communicate(stdin,timeout=timeout);code=proc.returncode
  except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.communicate();code=None
 commands.append({'label':label,'argv':list(map(str,argv)),'exit_code':code,'wall_seconds':time.monotonic()-start});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');return code
src=out/'driver.mio';src.write_text('''yobu "kiso/encoding/json"; yobu "kiso/fs"; yobu "kiso/string"; yobu "kiso/math";
waza run() -> unit {
 kaku input = fs.read_all("input.json"); moshi (input.error != mu) { math.fail("input"); kaesu; }
 kaku parsed = json.parse(input.data); moshi (parsed.error != "") { fs.write_all("/dev/stderr", string.to_bytes(parsed.error)); math.fail("invalid JSON"); kaesu; }
 kaku written = fs.write_all("output.json", string.to_bytes(json.render(parsed, parsed.root))); moshi (written.error != mu) { math.fail("output"); }
} run();
''')
policy=out/'compiler.sb';policy.write_text('(version 1)(allow default)(deny network*)(deny process-fork)(deny process-exec)(allow process-exec (literal '+json.dumps(str(compiler))+'))\n')
program=out/'driver.native'
if a.cli:
 assert run('compile',['/usr/bin/sandbox-exec','-f',policy,compiler,'build',src,'-o',program])==0
else:
 unsigned=out/'driver.unsigned';data=('\n'.join(map(str,[root,src,root/'bunko',unsigned]))+'\n').encode();(out/'compile.stdin').write_bytes(data);assert run('compile',['/usr/bin/sandbox-exec','-f',policy,compiler],data)==0
 shutil.copy2(unsigned,program);program.chmod(0o755);assert run('development-sign',['/usr/bin/codesign','--force','--sign','-',program])==0
assert run('verify',['/usr/bin/codesign','--verify','--strict',program])==0
(out/'provenance.json').write_text(json.dumps({'compiler':str(compiler),'candidate_sha256':hashlib.sha256(compiler.read_bytes()).hexdigest(),'mode':'unified CLI embedded Bunko / native signing' if a.cli else 'development driver / external initial signing'},indent=2)+'\n')
runtime=out/'runtime.sb';runtime.write_text('(version 1)(allow default)(deny network*)(deny process-fork)(deny process-exec)(allow process-exec (literal '+json.dumps(str(program))+'))\n')
values=[None,True,False,0,-1,9223372036854775807,[],{},'中文😀\0\n\t\\"',{'id':'request-1','params':{'position':{'line':1,'character':2}}},[1,2,{'a':[False,None]}]]
rng=random.Random(20261026)
for i in range(30):values.append({'id':i,'text':''.join(rng.choice('abc中文😀\0\n') for _ in range(i)),'values':[rng.randint(-100000000000,100000000000),bool(i%2),None]})
cases=[(str(i),json.dumps(x,ensure_ascii=i%2==0,separators=(',',':')).encode(),True) for i,x in enumerate(values)]
cases += [('surrogate-high',b'"\\ud800"',True),('surrogate-low',b'"\\udc00"',True),('duplicate',b'{"x":1,"x":2}',True),('number-lexemes',b'[-0,1e+30,0.125,-1.25E-3]',True)]
cases += [('bad-'+str(i),x,False) for i,x in enumerate([b'',b' ',b'01',b'-',b'1e+',b'1.',b'[1,]',b'{"x":1,}',b'{"x" 1}',b'{:1}',b'true false',b'"\x00"',b'"\\x00"',b'"\\u000x"',b'"\xff"',b'[',b'{',b'NaN'])]
def normalized(value):
 if isinstance(value,str):return ''.join('\ufffd' if 0xd800<=ord(c)<=0xdfff else c for c in value)
 if isinstance(value,list):return [normalized(x) for x in value]
 if isinstance(value,dict):return {normalized(k):normalized(v) for k,v in value.items()}
 return value
results=[]
for name,data,valid in cases:
 (out/'input.json').write_bytes(data);target=out/'output.json';target.unlink(missing_ok=True);code=run(name,['/usr/bin/sandbox-exec','-f',runtime,program]);actual=target.read_bytes() if target.exists() else None
 ok=code not in (None,0) and actual is None if not valid else False
 if valid and code==0 and actual is not None:
  try:ok=json.loads(actual)==normalized(json.loads(data))
  except Exception:ok=False
 results.append({'case':name,'expected_valid':valid,'exit':code,'status':'PASS' if ok else 'FAIL','input_hex':data.hex(),'output_hex':actual.hex() if actual is not None else None});(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(name,results[-1]['status'],flush=True)
manifest=[{'path':str(x.relative_to(root)),'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in sorted(set(root.glob('bunko/**/*.mio'))|set(root.glob('selfhost/**/*.mio')))];(out/'source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');raise SystemExit(0 if all(x['status']=='PASS' for x in results) else 1)
