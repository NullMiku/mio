#!/usr/bin/env python3
"""Isolated GF2 large source audit, not a production/selfbootstrap builder."""
import argparse,hashlib,json,os,shutil,signal,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--compiler',type=Path,required=True)
p.add_argument('--compare-unsigned',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
compiler=a.compiler.resolve();commands=[]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(label,argv,stdin=None,timeout=180):
 (out/(label+'.stdin')).write_bytes(stdin or b'')
 with (out/(label+'.stdout')).open('wb') as stdout,(out/(label+'.stderr')).open('wb') as stderr:
  start=time.monotonic();proc=subprocess.Popen(['/usr/bin/time','-l',*map(str,argv)],cwd=out,env={'PATH':''},stdin=subprocess.PIPE,stdout=stdout,stderr=stderr,start_new_session=True)
  try:proc.communicate(stdin,timeout=timeout);code=proc.returncode
  except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.communicate();code=None
 commands.append({'label':label,'argv':list(map(str,argv)),'cwd':str(out),'environment':{'PATH':''},'exit_code':code,'wall_seconds':time.monotonic()-start,'stdin':label+'.stdin'})
 (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');return code

def build(label,builder,entry,dest):
 policy=out/(label+'.sb');policy.write_text('(version 1)(allow default)(deny process-fork)(deny process-exec)(allow process-exec (literal '+json.dumps(str(builder))+'))(deny file-write*)(allow file-write* (literal '+json.dumps(str(dest))+'))(allow file-write* (literal '+json.dumps(str(out/(label+'.stderr')))+'))(allow file-write* (literal "/dev/stderr"))(allow file-write* (literal "/dev/fd/2"))\n')
 data=('\n'.join(map(str,[root,entry,root/'bunko',dest]))+'\n').encode()
 return run(label,['/usr/bin/sandbox-exec','-f',policy,builder],data)
manifest=[{'path':str(x.relative_to(root)),'sha256':digest(x)} for x in sorted(set(root.glob('bunko/**/*.mio'))|set(root.glob('selfhost/**/*.mio')))];(out/'source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
target=out/'compiler.unsigned';code=build('self-source',compiler,'selfhost/native-driver',target)
results=[{'case':'large-self-source','exit':code,'status':'PASS' if code==0 and target.exists() else 'FAIL'}]
if results[-1]['status']=='PASS':
 identical=target.read_bytes()==a.compare_unsigned.read_bytes()
 results.append({'case':'development-candidate-fixed-point','status':'PASS' if identical else 'FAIL','sha256':digest(target),'comparison_sha256':digest(a.compare_unsigned)})
 signed=out/'compiler.native';shutil.copy2(target,signed);signed.chmod(0o755)
 sign=run('sign',['/usr/bin/codesign','--force','--sign','-',signed]);verify=run('verify',['/usr/bin/codesign','--verify','--strict',signed]);assert sign==verify==0
 src=out/'case.mio';src.write_text('yobu "kiso/array"; kaku values = array.make[int64](2, 7); chant(values[1]);\n')
 app=out/'app.unsigned';code=build('rebuilt-compiler-build',signed,src,app)
 if code==0 and app.exists():
  executable=out/'app.native';shutil.copy2(app,executable);executable.chmod(0o755)
  sign=run('app-sign',['/usr/bin/codesign','--force','--sign','-',executable]);verify=run('app-verify',['/usr/bin/codesign','--verify','--strict',executable]);assert sign==verify==0
  execution=run('app-execute',[executable]);actual=(out/'app-execute.stdout').read_bytes()
  results.append({'case':'rebuilt-compiler-application','exit':execution,'status':'PASS' if execution==0 and actual==b'7\n' else 'FAIL'})
 else:results.append({'case':'rebuilt-compiler-application','exit':code,'status':'FAIL_BUILD'})
(out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
(out/'provenance.json').write_text(json.dumps({'compiler':str(compiler),'compiler_sha256':digest(compiler),'source_manifest_sha256':digest(out/'source-manifest.json'),'scope':'GF2 developer candidate only; external audit signing; not final GF4 CLI seed chain'},indent=2)+'\n')
print(json.dumps(results,indent=2),flush=True)
raise SystemExit(0 if all(x['status']=='PASS' for x in results) else 1)
