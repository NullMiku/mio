#!/usr/bin/env python3
"""Independent isolated launcher for the exact native production CI program.
Copies frozen source bytes and starts Mio code; no Python build/test/package,
signature/provenance/archive generation logic participates in the product chain.
"""
import argparse,json,hashlib,shutil,subprocess,tempfile,os,signal,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--builder',type=Path,required=True);p.add_argument('--seed',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);work=Path(tempfile.mkdtemp(prefix='mio-native-ci-',dir='/tmp')).resolve();source=work/'source';source.mkdir();builder=work/'ci.native';seed=work/'seed';shutil.copy2(a.builder,builder);shutil.copy2(a.seed,seed);native_out=work/'native-output';copied=[]
manifest=json.loads((root/'build/gofree-evidence/GF3/final-r2/source-manifest.json').read_text());paths=[x['path'] for x in manifest]+[str(x.relative_to(root)) for x in sorted((root/'tools/native-ci').glob('*.mio'))]+['tests/gofree/runtime_metadata.mio.fixture','tests/gofree/unsigned_image_audit.mio.fixture','LICENSE','VERSION']
for name in paths:
 src=root/name;dst=source/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);dst.chmod(0o444);copied.append({'path':name,'sha256':hashlib.sha256(src.read_bytes()).hexdigest()})
policy=out/'native-ci.sb';policy.write_text('(version 1)(allow default)(deny network*)(deny process-exec)(allow process-exec (literal '+json.dumps(str(builder))+'))(allow process-exec (literal '+json.dumps(str(seed))+'))(allow process-exec (subpath '+json.dumps(str(native_out))+'))(allow process-exec (regex #"^(/private)?/tmp/mio-test-[0-9]+/test-[0-9]+[.]native$"))(allow process-exec (regex #"^(/private)?/tmp/mio-globals-[0-9]+/program$"))(deny file-read* (subpath '+json.dumps(str(root))+'))(deny file-read* (subpath "/Users/hatsunemiku/.codex/worktrees"))(deny file-read* (subpath "/Volumes/Sector0/AppData/Mio"))(deny file-write* (subpath '+json.dumps(str(source))+'))\n')
argv=['/usr/bin/sandbox-exec','-f',str(policy),str(builder),'ci',str(source),str(seed),str(native_out),'uncommitted-worktree-a96d83ca0ee30239026b9ba27d5a5d547349f647'];before={'scope':__doc__,'work':str(work),'source':str(source),'native_output':str(native_out),'builder_sha256':hashlib.sha256(builder.read_bytes()).hexdigest(),'trusted_seed_sha256':hashlib.sha256(seed.read_bytes()).hexdigest(),'argv':argv,'environment':{'PATH':'','MIO_BUNKO':''},'copied_sources':copied};(out/'launcher-provenance.json').write_text(json.dumps(before,indent=2)+'\n');start=time.monotonic()
with (out/'native-ci.stdout').open('wb') as stdout,(out/'native-ci.stderr').open('wb') as stderr:
 proc=subprocess.Popen(argv,cwd=source,env={'PATH':'','MIO_BUNKO':''},stdout=stdout,stderr=stderr,start_new_session=True);(out/'process.json').write_text(json.dumps({'pid':proc.pid,'argv':argv},indent=2)+'\n')
 try:code=proc.wait(timeout=10800)
 except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait();code=None
unchanged=all(hashlib.sha256((source/x['path']).read_bytes()).hexdigest()==x['sha256'] and hashlib.sha256((root/x['path']).read_bytes()).hexdigest()==x['sha256'] for x in copied);ok=code==0 and (native_out/'PASS').exists() and unchanged
if native_out.exists():shutil.copytree(native_out,out/'native-output')
result={'status':'PASS' if ok else 'FAIL','exit':code,'seconds':time.monotonic()-start,'source_unchanged':unchanged,'native_pass_marker':(native_out/'PASS').exists(),'scope':__doc__};(out/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True);raise SystemExit(0 if ok else 1)
