#!/usr/bin/env python3
"""Bootstrap a Mio component with an audited native seed, retaining all evidence.
External signing here prepares a development seed only, not formal build output.
"""
import argparse,hashlib,json,os,shutil,signal,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--compiler',type=Path,required=True);p.add_argument('--entry',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--timeout',type=int,default=600);p.add_argument('--config-input',type=Path);p.add_argument('--config-output',type=Path);a=p.parse_args()
root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);compiler=a.compiler.resolve();commands=[]
def run(label,argv,stdin=None):
 with (out/(label+'.stdout')).open('wb') as stdout,(out/(label+'.stderr')).open('wb') as stderr:
  start=time.monotonic();proc=subprocess.Popen(['/usr/bin/time','-l',*map(str,argv)],cwd=out,env={'PATH':''},stdin=subprocess.PIPE,stdout=stdout,stderr=stderr,start_new_session=True)
  try:proc.communicate(stdin,timeout=a.timeout);code=proc.returncode
  except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.communicate();code=None
 commands.append({'label':label,'argv':list(map(str,argv)),'cwd':str(out),'environment':{'PATH':''},'exit_code':code,'wall_seconds':time.monotonic()-start});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');return code
manifest=[{'path':str(x.relative_to(root)),'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in sorted(set(root.glob('bunko/**/*.mio'))|set(root.glob('selfhost/**/*.mio')))];(out/'source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
def policy(name,executable):
 p=out/(name+'.sb');p.write_text('(version 1)(allow default)(deny process-fork)(deny process-exec)(allow process-exec (literal '+json.dumps(str(executable))+'))\n');return ['/usr/bin/sandbox-exec','-f',p,executable]
unsigned=out/'component.unsigned';request=('\n'.join(map(str,[root,a.entry,root/'bunko',unsigned]))+'\n').encode();(out/'compile.stdin').write_bytes(request);code=run('compile',policy('compiler',compiler),request)
assert code==0 and unsigned.exists(),'native component compilation failed'
program=out/'component.native';shutil.copy2(unsigned,program);program.chmod(0o755);assert run('seed-sign',['/usr/bin/codesign','--force','--sign','-',program])==0;assert run('seed-verify',['/usr/bin/codesign','--verify','--strict',program])==0
if a.config_input and a.config_output:
 (out/'input.config').write_text(str(a.config_input.resolve()));(out/'output.config').write_text(str(a.config_output.resolve()));assert run('component-execute',policy('component',program))==0
 assert a.config_output.is_file();(out/'generated.json').write_text(json.dumps({'path':str(a.config_output.resolve()),'bytes':a.config_output.stat().st_size,'sha256':hashlib.sha256(a.config_output.read_bytes()).hexdigest()},indent=2)+'\n')
(out/'provenance.json').write_text(json.dumps({'compiler':str(compiler),'compiler_sha256':hashlib.sha256(compiler.read_bytes()).hexdigest(),'unsigned_sha256':hashlib.sha256(unsigned.read_bytes()).hexdigest(),'scope':'development component audit; external signing prepares the initial component only'},indent=2)+'\n');print(program,flush=True)
