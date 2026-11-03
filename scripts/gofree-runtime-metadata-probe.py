#!/usr/bin/env python3
"""Native-only runtime emitter audit. Copy the frozen actual Mio runtime package
unchanged for package-private access, add a separately identified Mio test fixture,
and use the selected unified compiler to build/sign the native audit generator.
No foreign compiler/VM/code generator or replacement collector is involved.
"""
import argparse,json,hashlib,shutil,subprocess,tempfile,time,signal,os
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);work=Path(tempfile.mkdtemp(prefix='mio-runtime-native-',dir='/tmp')).resolve();package=work/'runtime';package.mkdir();candidate=work/'mio';shutil.copy2(a.candidate,candidate);original=[];commands=[];results=[]
for source in sorted((root/'bunko/kiso/aot/lower').glob('*.mio')):
 if source.name.endswith('_test.mio'):continue
 shutil.copy2(source,package/source.name);original.append({'path':str(source.relative_to(root)),'sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
fixture=root/'tests/gofree/runtime_metadata.mio.fixture';shutil.copy2(fixture,package/'audit.mio');(out/'core-manifest.json').write_text(json.dumps(original,indent=2)+'\n')
(out/'provenance.json').write_text(json.dumps({'scope':__doc__,'candidate':str(a.candidate.resolve()),'candidate_sha256':hashlib.sha256(candidate.read_bytes()).hexdigest(),'fixture':str(fixture),'fixture_sha256':hashlib.sha256(fixture.read_bytes()).hexdigest(),'work':str(work),'reference':'Existing internal/aot/m19b_generational_test.go ten metadata cases, ported to native Mio audit plus actual emit_shadow_pop/major reclamation case. Historical Go reference never executed by this controller.'},indent=2)+'\n')
def run(label,program,args,timeout=300):
 policy=out/(label+'.sb');policy.write_text('(version 1)(allow default)(deny network*)(deny process-fork)(deny process-exec)(allow process-exec (literal '+json.dumps(str(program))+'))(deny file-read* (subpath '+json.dumps(str(root))+'))(deny file-read* (subpath "/Volumes/Sector0/AppData/Mio"))\n');argv=['/usr/bin/sandbox-exec','-f',str(policy),str(program),*map(str,args)];start=time.monotonic()
 with (out/(label+'.stdout')).open('wb') as stdout,(out/(label+'.stderr')).open('wb') as stderr:
  process=subprocess.Popen(argv,cwd=work,env={'PATH':'','MIO_BUNKO':''},stdout=stdout,stderr=stderr,start_new_session=True)
  try:code=process.wait(timeout=timeout)
  except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait();code=None
 commands.append({'label':label,'argv':argv,'exit':code,'seconds':time.monotonic()-start});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');return code
builder=work/'builder.native';code=run('build',candidate,['build',package,'-o',builder],timeout=900)
if code!=0:raise SystemExit(1)
shutil.copy2(builder,out/'builder.native')
programs=work/'programs';programs.mkdir();code=run('generate',builder,[programs]);assert code==0
for name in ['ages','remembered','promotion-edge','major','precision','adaptive','cross-graph','alternating','minor-scan','precision-storage','shadow-frame-pop']:
 program=programs/name;shutil.copy2(program,out/(name+'.native'));code=run(name,program,[],timeout=60);ok=code==0 and not (out/(name+'.stdout')).read_bytes() and not (out/(name+'.stderr')).read_bytes();results.append({'case':name,'status':'PASS' if ok else 'FAIL','exit':code,'native_sha256':hashlib.sha256(program.read_bytes()).hexdigest()});(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(name,results[-1]['status'],flush=True)
assert all(hashlib.sha256((root/x['path']).read_bytes()).hexdigest()==x['sha256'] for x in original)
raise SystemExit(0 if all(x['status']=='PASS' for x in results) else 1)
