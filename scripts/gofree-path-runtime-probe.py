#!/usr/bin/env python3
"""Isolated native OS path/stat ABI audit; not a production build dependency."""
import argparse,hashlib,json,os,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--compiler',type=Path,required=True);p.add_argument('--signer',type=Path,required=True);p.add_argument('--cli',action='store_true');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);compiler=a.compiler.resolve();signer=a.signer.resolve();commands=[]
(out/'物理 目录').mkdir();(out/'fixture-link').symlink_to('物理 目录',target_is_directory=True);(out/'regular').write_text('fixture')
source='''yobu "kiso/os";yobu "kiso/fs";yobu "kiso/array";yobu "kiso/string";yobu "mio/os/runtime";yobu "./stat";
waza run() -> unit {
 kaku physical=os.canonical_path("fixture-link");moshi(physical!=mu){chant(physical);}sore{chant("missing");}
 chant(os.canonical_path("definitely-missing")==mu);
 chant(fs.is_character_device("/dev/null"));chant(fs.is_character_device("regular"));chant(fs.is_character_device("/dev/stdin"));
 kaku small: []uint8=[0];chant(runtime.real_path(".",small));
 stat.check();
 kaku before=fs.read_dir("/dev/fd");kaku at=0;kaku completed=0;aida(at<1000){kaku resolved=os.canonical_path("fixture-link");moshi(resolved!=mu){completed=completed+1;}at=at+1;}chant(completed);kaku after=fs.read_dir("/dev/fd");chant(before.error==mu && after.error==mu && len(before.entries)==len(after.entries));
}run();
'''
(out/'stat').mkdir();(out/'stat/main.mio').write_text('yobu \"mio/fs/runtime\";koukai waza check() -> unit {'+' kaku two: []uint8=[0,0];runtime.stat("/dev/null",two);chant(two[0]);chant(two[1]);\n kaku three: []uint8=[0,0,77];runtime.stat("/dev/null",three);chant(three[2]);runtime.stat("regular",three);chant(three[2]);runtime.stat("definitely-missing",three);chant(three[2]);'+'}\n')
entry=out/'main.mio';entry.write_text(source)
def policy(label,executable):
 path=out/(label+'.sb');path.write_text('(version 1)(allow default)(deny network*)(deny process-fork)(deny process-exec)(allow process-exec (literal '+json.dumps(str(executable))+'))\n');return ['/usr/bin/sandbox-exec','-f',str(path),str(executable)]
def run(label,argv,data=None):
 start=time.monotonic();r=subprocess.run(argv,input=data,cwd=out,env={'PATH':''},capture_output=True,timeout=180)
 (out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr);commands.append({'label':label,'argv':argv,'exit':r.returncode,'seconds':time.monotonic()-start});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');return r
request=('\n'.join(map(str,[root,entry,root/'bunko',out/'input.bin']))+'\n').encode();(out/'compile.stdin').write_bytes(request)
argv=policy('compile',compiler)
if a.cli:argv+=['build',str(entry),'-o',str(out/'input.bin')]
r=run('compile',argv,None if a.cli else request);assert r.returncode==0,r.stderr
if a.cli:
 import shutil
 shutil.copy2(out/'input.bin',out/'signed.bin')
else:
 r=run('sign',policy('sign',signer));assert r.returncode==0,r.stderr
app=out/'signed.bin';app.chmod(0o755);r=run('verify',['/usr/bin/codesign','--verify','--strict',str(app)]);assert r.returncode==0
r=run('execute',policy('runtime',app),b'');expected=(str((out/'物理 目录').resolve())+'\nhai\nhai\niie\niie\n-22\n1\n0\n1\n0\n0\n1000\nhai\n').encode()
result={'status':'PASS' if r.returncode==0 and r.stdout==expected else 'FAIL','exit':r.returncode,'actual':r.stdout.decode(),'expected':expected.decode(),'compiler_sha256':hashlib.sha256(compiler.read_bytes()).hexdigest(),'scope':'Normal unified CLI source build/sign with native stat/path/descriptor-count checks' if a.cli else __doc__,'checks':['physical symlink/Unicode/space path identity','missing path','char/regular/pipe classification','undersized output buffer -EINVAL','legacy stat packet preserved','optional char byte clears on regular/missing','1000 successful repeated calls without descriptor leak']}
(out/'results.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n');print(json.dumps(result,indent=2,ensure_ascii=False),flush=True);raise SystemExit(0 if result['status']=='PASS' else 1)
