#!/usr/bin/env python3
"""Isolated native SHA256 differential audit; not a production dependency."""
import argparse,hashlib,json,os,shutil,signal,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--compiler',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);compiler=a.compiler.resolve();commands=[]
def run(label,argv,stdin=None,timeout=180):
 with (out/(label+'.stdout')).open('wb') as stdout,(out/(label+'.stderr')).open('wb') as stderr:
  start=time.monotonic();proc=subprocess.Popen(['/usr/bin/time','-l',*map(str,argv)],cwd=out,env={'PATH':''},stdin=subprocess.PIPE,stdout=stdout,stderr=stderr,start_new_session=True)
  try:proc.communicate(stdin,timeout=timeout);code=proc.returncode
  except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.communicate();code=None
 commands.append({'label':label,'argv':list(map(str,argv)),'cwd':str(out),'environment':{'PATH':''},'exit_code':code,'wall_seconds':time.monotonic()-start});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');return code
src=out/'case.mio';src.write_text('''yobu "kiso/crypto/sha256"; yobu "kiso/fs"; yobu "kiso/math";
kaku input = fs.read_all("input.bin"); moshi (input.error != mu) { math.fail("input"); }
kaku digest = sha256.sum(input.data); kaku result = fs.write_all("digest.bin", digest);
moshi (result.error != mu) { math.fail("output"); }
''')
policy=out/'compiler.sb';policy.write_text('(version 1)(allow default)(deny process-fork)(deny process-exec)(allow process-exec (literal '+json.dumps(str(compiler))+'))\n')
unsigned=out/'image.unsigned';request=('\n'.join(map(str,[root,src,root/'bunko',unsigned]))+'\n').encode();(out/'compile.stdin').write_bytes(request)
assert run('compile',['/usr/bin/sandbox-exec','-f',policy,compiler],request)==0
signed=out/'image.native';shutil.copy2(unsigned,signed);signed.chmod(0o755);assert run('sign',['/usr/bin/codesign','--force','--sign','-',signed])==0;assert run('verify',['/usr/bin/codesign','--verify','--strict',signed])==0
policy=out/'runtime.sb';policy.write_text('(version 1)(allow default)(deny process-fork)(deny process-exec)(allow process-exec (literal '+json.dumps(str(signed))+'))\n')
cases=[('empty',b''),('abc',b'abc')]+[(str(n),bytes((i*73+19)%256 for i in range(n))) for n in [1,55,56,63,64,65,119,120,127,128,255,4095,4096,4097,8193]]+[('million-a',b'a'*1000000)]
results=[]
for name,data in cases:
 (out/'input.bin').write_bytes(data);target=out/'digest.bin';target.unlink(missing_ok=True)
 code=run(name,['/usr/bin/sandbox-exec','-f',policy,signed]);actual=target.read_bytes().hex() if target.exists() else None;expected=hashlib.sha256(data).hexdigest()
 results.append({'case':name,'input_bytes':len(data),'input_sha256':expected,'actual':actual,'exit':code,'status':'PASS' if code==0 and actual==expected else 'FAIL'});(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(name,results[-1]['status'],flush=True)
manifest=[{'path':str(x.relative_to(root)),'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in sorted(set(root.glob('bunko/**/*.mio'))|set(root.glob('selfhost/**/*.mio')))];(out/'source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
raise SystemExit(0 if all(x['status']=='PASS' for x in results) else 1)
