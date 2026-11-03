#!/usr/bin/env python3
"""Isolated audit of Mio-generated Darwin process syscalls."""
import argparse,json,os,shutil,signal,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--compiler',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);compiler=a.compiler.resolve();commands=[]
def run(label,argv,stdin=None,timeout=120):
 with (out/(label+'.stdout')).open('wb') as stdout,(out/(label+'.stderr')).open('wb') as stderr:
  start=time.monotonic();proc=subprocess.Popen(['/usr/bin/time','-l',*map(str,argv)],cwd=out,env={'PATH':''},stdin=subprocess.PIPE,stdout=stdout,stderr=stderr,start_new_session=True)
  try:proc.communicate(stdin,timeout=timeout);code=proc.returncode
  except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.communicate();code=None
 commands.append({'label':label,'argv':list(map(str,argv)),'cwd':str(out),'environment':{'PATH':''},'exit_code':code,'wall_seconds':time.monotonic()-start});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');return code,(out/(label+'.stdout')).read_bytes()
def build(name,source):
 src=out/(name+'.mio');src.write_text(source);target=out/(name+'.unsigned');data=('\n'.join(map(str,[root,src,root/'bunko',target]))+'\n8388608\nstress\n').encode();(out/(name+'.stdin')).write_bytes(data)
 policy=out/'compiler.sb';policy.write_text('(version 1)(allow default)(deny process-fork)(deny process-exec)(allow process-exec (literal '+json.dumps(str(compiler))+'))\n');code,_=run(name+'-build',['/usr/bin/sandbox-exec','-f',policy,compiler],data);assert code==0
 signed=out/(name+'.native');shutil.copy2(target,signed);signed.chmod(0o755);assert run(name+'-seed-sign',['/usr/bin/codesign','--force','--sign','-',signed])[0]==0;assert run(name+'-verify',['/usr/bin/codesign','--verify','--strict',signed])[0]==0;return signed
child=build('child','''yobu "kiso/os"; kaku args = os.arguments(); chant(len(args)); kaku at = 1; aida (at < len(args)) { chant(args[at]); at = at + 1; } os.exit(7);''')
# Source literals are JSON/Mio compatible for these UTF8 paths.
path=json.dumps(str(child));parent=build('parent','''yobu "kiso/os"; yobu "kiso/fs";
chant(os.pid() > 0);
kaku status = os.spawn('''+path+''', ['''+path+''', "alpha", "中文 空格", ""]); chant(status);
chant(os.exec("/no-such-mio-executable", ["missing"]) < 0);
chant(os.spawn("/no-such-mio-executable", ["missing"]));
kaku created = fs.write_all("remove-me", []); chant(os.remove("remove-me")); chant(!fs.exists("remove-me"));
''')
policy=out/'runtime.sb';policy.write_text('(version 1)(allow default)(deny process-exec)(allow process-exec (literal '+json.dumps(str(parent))+'))(allow process-exec (literal '+json.dumps(str(child))+'))\n');code,actual=run('parent-run',['/usr/bin/sandbox-exec','-f',policy,parent]);expected=b'hai\n4\nalpha\n'+'中文 空格\n'.encode()+b'\n7\nhai\n127\n0\nhai\n';results=[{'case':'spawn-wait-args-exec-error-pid-remove','status':'PASS' if code==0 and actual==expected else 'FAIL','exit':code,'stdout':actual.decode(errors='replace')}];(out/'results.json').write_text(json.dumps(results,indent=2,ensure_ascii=False)+'\n');print(results[-1],flush=True)
replacement=build('replacement','yobu "kiso/os"; os.exec('+path+',['+path+',"replacement"]); chant("unreachable");')
policy=out/'replacement.sb';policy.write_text('(version 1)(allow default)(deny process-fork)(deny process-exec)(allow process-exec (literal '+json.dumps(str(replacement))+'))(allow process-exec (literal '+json.dumps(str(child))+'))\n');code,actual=run('replacement-run',['/usr/bin/sandbox-exec','-f',policy,replacement]);results.append({'case':'exec-replacement-preserves-child-exit','status':'PASS' if code==7 and actual==b'2\nreplacement\n' else 'FAIL','exit':code,'stdout':actual.decode(errors='replace')});(out/'results.json').write_text(json.dumps(results,indent=2,ensure_ascii=False)+'\n');print(results[-1],flush=True)
raise SystemExit(0 if all(x['status']=='PASS' for x in results) else 1)
