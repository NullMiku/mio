#!/usr/bin/env python3
"""Verify frozen bytes, historical provenance, and existing native frontend execution."""
import argparse, hashlib, importlib.util, json, os, pathlib, re, shutil, signal, subprocess, time
p=argparse.ArgumentParser(); p.add_argument('--freeze',type=pathlib.Path,required=True); p.add_argument('--output',type=pathlib.Path,required=True); a=p.parse_args()
f=a.freeze.resolve(); out=a.output.resolve(); out.mkdir(parents=True,exist_ok=False); records=[]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def run(label,args,cwd,timeout=60,expected=0,env=None):
 start=time.monotonic(); argv=[str(x) for x in args]
 rec={'label':label,'argv':argv,'cwd':str(cwd),'expected_exit':expected,'environment':env,'source_manifest_sha256':sha(f/'source-manifest.json')}
 with (out/(label+'.stdout')).open('wb') as stdout,(out/(label+'.stderr')).open('wb') as stderr:
  child=subprocess.Popen(['/usr/bin/time','-l',*argv],cwd=cwd,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
  try: rec['exit_code']=child.wait(timeout=timeout)
  except subprocess.TimeoutExpired:
   os.killpg(child.pid,signal.SIGKILL); child.wait(); rec['exit_code']=None
 rec['wall_seconds']=time.monotonic()-start; rec['status']='PASS' if rec['exit_code']==expected else ('TIMEOUT' if rec['exit_code'] is None else 'FAIL'); records.append(rec)
 (out/'commands.json').write_text(json.dumps(records,indent=2)+'\n'); print(label,rec['exit_code'],flush=True)
 return rec
# Validate both the immutable source copy and untouched original source subset.
checks={}
for label,base in [('snapshot',f/'source'),('original',pathlib.Path(json.loads((f/'freeze.json').read_text())['root']))]:
 differences=[]
 for item in json.loads((f/'source-manifest.json').read_text()):
  if item.get('missing'): continue
  path=base/item['path']
  if not path.is_file() or sha(path)!=item['sha256']: differences.append(item['path'])
 checks[label]={'status':'PASS' if not differences else 'FAIL','differences':differences}
history=[]
spec=importlib.util.spec_from_file_location('m18',f/'source/scripts/check-native-aot-fixed-point.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
for directory in ['m18-20261020-verified','m19c-20261026-fixed-point']:
 d=f/'historical/build'/directory; provenance=json.loads((d/'provenance.json').read_text()); stages=[]
 for i in range(1,6):
  path=d/f'stage{i}.unsigned'; expected=provenance['artifacts'][f'stage{i}']['sha256']; actual=sha(path); assert actual==expected
  mod.validate_macho(path); stages.append({'stage':i,'sha256':actual,'bytes':path.stat().st_size})
 assert all((d/f'stage{i}.unsigned').read_bytes()==(d/'stage2.unsigned').read_bytes() for i in range(1,6))
 inputs=[]
 for item in json.loads((d/'source-manifest.json').read_text()):
  path=pathlib.Path(item['path']); rel=path.relative_to(pathlib.Path(provenance['root'])); frozen=f/'source'/rel
  inputs.append({'path':str(rel),'matches_current':frozen.exists() and sha(frozen)==item['sha256']})
 history.append({'directory':directory,'status':'PASS','claim':'Archived backend fixed point bytes and recorded execution; not a fresh chain or GF4 source bootstrap','recorded_status':provenance['status'],'recorded_stage4_executed':provenance.get('stage4_executed'),'recorded_stage5_continuation':provenance.get('stage5_continuation'),'stages':stages,'source_match':all(x['matches_current'] for x in inputs),'source_differences':[x for x in inputs if not x['matches_current']]})
(out/'integrity.json').write_text(json.dumps(checks,indent=2)+'\n'); (out/'history.json').write_text(json.dumps(history,indent=2)+'\n')
# Native frontend is only an unchanged bootstrap driver; config modified solely in throwaway work copy.
work=f/'work'; config=work/'selfhost/bootstrap/bootstrap.config'; original=config.read_bytes()
image=out/'frontend.native'; shutil.copy2(f/'probes/native-frontend/image.unsigned',image); image.chmod(0o755)
run('sign',['/usr/bin/codesign','--force','--sign','-',image],out); run('verify',['/usr/bin/codesign','--verify','--strict',image],out)
policy=out/'sandbox.sb'; policy.write_text('(version 1)(allow default)(deny process-fork)(deny process-exec)(allow process-exec (literal '+json.dumps(str(image))+'))\n')
try:
 config.write_text(str(out/'compiler-B.mochi'))
 run('frontend-execute',['/usr/bin/sandbox-exec','-f',policy,image],work,env={'PATH':''})
finally: config.write_bytes(original)
# Negative probe demonstrates exit-zero error behavior without implementing anything.
run('frontend-no-config',['/usr/bin/sandbox-exec','-f',policy,image],out,env={'PATH':''})
run('sandbox-denial',['/usr/bin/sandbox-exec','-f',policy,'/bin/sh','-c','exec /usr/bin/true'],out,expected=71,env={'PATH':''})
result=out/'compiler-B.mochi'
if result.exists():
 (out/'frontend-output.json').write_text(json.dumps({'sha256':sha(result),'bytes':result.stat().st_size,'historical_golden':'b44a55bf3f9020e6b0ff83ad137b25774814a32dfe8acaf070abcd167bfd1465','matches_historical_golden':sha(result)=='b44a55bf3f9020e6b0ff83ad137b25774814a32dfe8acaf070abcd167bfd1465'},indent=2)+'\n')
# Binary inventory includes pre-existing on-disk CLI and previous v1 distributions.
origin=pathlib.Path(json.loads((f/'freeze.json').read_text())['root'])
for i,path in enumerate([origin/'mio',origin/'build/mio',origin/'build/m19c-20261026-mio',origin/'.mio/v1.0.0/mio']):
 if path.is_file():
  run('existing-version-'+str(i),[path,'version'],out)
  run('existing-help-'+str(i),[path,'help'],out)
  run('existing-buildinfo-'+str(i),['go','version','-m',path],out)
  (out/('existing-'+str(i)+'.json')).write_text(json.dumps({'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size},indent=2)+'\n')
