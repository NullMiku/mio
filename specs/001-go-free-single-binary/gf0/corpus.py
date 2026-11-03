#!/usr/bin/env python3
"""Freeze the existing differential corpus; compare Go VM with archived pure Mio AOT."""
import argparse, hashlib, json, os, pathlib, re, shutil, signal, subprocess, time
p=argparse.ArgumentParser(); p.add_argument('--freeze',type=pathlib.Path,required=True); p.add_argument('--output',type=pathlib.Path,required=True); a=p.parse_args(); f=a.freeze.resolve(); out=a.output.resolve(); out.mkdir(parents=True,exist_ok=False)
text=(f/'source/selfhost/codegen/codegen_diff_test.go').read_text().split('func TestCodegenExecutionDifferential')[1].split('for index, source := range cases')[0]
cases=re.findall(r'`([^`]*)`',text); assert len(cases)==16
commands=[]; results=[]; mio=f/'probes/mio'; native=f/'historical/build/m19c-20261026-fixed-point/stage4.native'
def run(label,args,cwd,env=None):
 t=time.monotonic(); argv=[str(x) for x in args]
 with (out/(label+'.stdout')).open('wb') as stdout,(out/(label+'.stderr')).open('wb') as stderr:
  proc=subprocess.Popen(['/usr/bin/time','-l',*argv],cwd=cwd,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
  try: code=proc.wait(timeout=60)
  except subprocess.TimeoutExpired: os.killpg(proc.pid,signal.SIGKILL); proc.wait(); code=None
 commands.append({'label':label,'argv':argv,'cwd':str(cwd),'environment':env,'exit_code':code,'wall_seconds':time.monotonic()-t,'source_manifest_sha256':hashlib.sha256((f/'source-manifest.json').read_bytes()).hexdigest()}); (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 return code,(out/(label+'.stdout')).read_bytes()
for i,source in enumerate(cases):
 d=out/str(i); d.mkdir(); src=d/'case.mio'; src.write_text(source+'\n'); env=os.environ.copy(); env['MIO_BUNKO']=str(f/'work/bunko'); result={'case':i,'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest()}
 code,_=run(f'{i}-build',[mio,'build',src],d,env)
 if code!=0: result['status']='BLOCKED_REFERENCE'
 else:
  vmcode,vmout=run(f'{i}-vm',[mio,'exec',d/'case.mochi'],d,env)
  (d/'input.config').write_text(str(d/'case.mochi')); (d/'output.config').write_text(str(d/'image.unsigned'))
  policy=d/'sandbox.sb'; policy.write_text('(version 1)(allow default)(deny process-fork)(deny process-exec)(allow process-exec (literal '+json.dumps(str(native))+'))\n')
  ncode,nout=run(f'{i}-lower',['/usr/bin/sandbox-exec','-f',policy,native],d,{'PATH':''})
  result.update(vm_exit=vmcode,lower_exit=ncode,lower_stdout=nout.decode())
  if ncode!=0 or not nout.startswith(b'native-aot: ok\n') or not (d/'image.unsigned').exists(): result['status']='BLOCKED_NATIVE'
  else:
   image=d/'image.native'; shutil.copy2(d/'image.unsigned',image); image.chmod(0o755)
   scode,_=run(f'{i}-sign',['/usr/bin/codesign','--force','--sign','-',image],d)
   vcode,_=run(f'{i}-verify',['/usr/bin/codesign','--verify','--strict',image],d)
   rcode,rout=run(f'{i}-native',[image],d,{'PATH':''})
   result.update(native_exit=rcode,stdout_equal=rout==vmout)
   result['status']='PASS' if scode==vcode==vmcode==rcode==0 and rout==vmout else 'FAIL'
 results.append(result); (out/'results.json').write_text(json.dumps(results,indent=2)+'\n'); print(i,result['status'],flush=True)
# Repeated large source reference compilation, with retained raw measurements.
for i in range(3): run('selfhost-build-'+str(i),[mio,'build','-o',out/f'selfhost-{i}.mochi','selfhost/bootstrap'],f/'work',env)
