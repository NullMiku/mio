#!/usr/bin/env python3
"""Isolated audit controller for an existing Mio-native embedded resource generator.
No Python-generated source enters the product. Preserve prior bundle and verify
all generated source bytes, lengths and hashes independently.
"""
import argparse,hashlib,json,re,shutil,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--generator',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
target=root/'selfhost/resources/bunko_data.mio';generator=a.generator.resolve()
shutil.copy2(target,out/'previous-bunko_data.mio')
(out/'input.config').write_text(str(root/'bunko'));(out/'output.config').write_text(str(target))
policy=out/'generator.sb';policy.write_text('(version 1)(allow default)(deny network*)(deny process-fork)(deny process-exec)(allow process-exec (literal '+json.dumps(str(generator))+'))\n')
argv=['/usr/bin/sandbox-exec','-f',str(policy),str(generator)];start=time.monotonic()
with (out/'stdout').open('wb') as stdout,(out/'stderr').open('wb') as stderr:
 result=subprocess.run(argv,cwd=out,env={'PATH':''},stdout=stdout,stderr=stderr,timeout=120)
(out/'provenance.json').write_text(json.dumps({'argv':argv,'generator_sha256':hashlib.sha256(generator.read_bytes()).hexdigest(),'exit':result.returncode,'wall_seconds':time.monotonic()-start,'environment':{'PATH':''},'scope':__doc__},indent=2)+'\n')
assert result.returncode==0
raw=target.read_bytes();records=[]
quoted=r'"(?:[^"\\]|\\.)*"'
pattern=r'File \{ path: ('+quoted+r'), version: ('+quoted+r'), length: ([0-9]+), sha256: ('+quoted+r'), source: ('+quoted+r') \}'
for m in re.finditer(pattern,raw.decode()):
 path,version,length,hash_value,source=m.groups();path=json.loads(path);source=json.loads(source).encode();expected=(root/'bunko'/path).read_bytes();sha=hashlib.sha256(source).hexdigest()
 ok=source==expected and len(source)==int(length) and sha==json.loads(hash_value)
 records.append({'path':path,'bytes':len(source),'sha256':sha,'status':'PASS' if ok else 'FAIL'})
expected_paths={str(x.relative_to(root/'bunko')) for x in (root/'bunko').rglob('*.mio') if not x.name.endswith('_test.mio')}
assert {x['path'] for x in records}==expected_paths, 'resource membership mismatch'
ok=all(x['status']=='PASS' for x in records)
report={'status':'PASS' if ok else 'FAIL','records':records,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
(out/'resource-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='records'}),flush=True)
raise SystemExit(0 if ok else 1)
