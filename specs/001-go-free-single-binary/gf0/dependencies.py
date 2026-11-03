#!/usr/bin/env python3
"""Record full Go production/test import graph without executing tests."""
import argparse, hashlib, json, os, pathlib, subprocess, time
p=argparse.ArgumentParser(); p.add_argument('--freeze',type=pathlib.Path,required=True); a=p.parse_args(); f=a.freeze.resolve(); out=f/'dependencies'; out.mkdir(exist_ok=False); env=os.environ.copy(); env.update(GOMAXPROCS='2',GOFLAGS='-p=2')
argv=['go','list','-deps','-test','-json','./...']; t=time.monotonic(); proc=subprocess.run(argv,cwd=f/'work',env=env,capture_output=True,timeout=90)
(out/'go-list.jsonstream').write_bytes(proc.stdout); (out/'go-list.stderr').write_bytes(proc.stderr)
(out/'command.json').write_text(json.dumps({'argv':argv,'cwd':str(f/'work'),'environment':{'GOMAXPROCS':'2','GOFLAGS':'-p=2'},'exit_code':proc.returncode,'wall_seconds':time.monotonic()-t,'source_manifest_sha256':hashlib.sha256((f/'source-manifest.json').read_bytes()).hexdigest()},indent=2)+'\n'); assert proc.returncode==0
s=proc.stdout.decode(); decoder=json.JSONDecoder(); items=[]
while s.strip():
 s=s.lstrip(); obj,n=decoder.raw_decode(s); s=s[n:]; items.append({k:obj[k] for k in ['ImportPath','Standard','ForTest','Imports','TestImports','XTestImports','CgoFiles','GoFiles','TestGoFiles','XTestGoFiles','Module'] if k in obj})
(out/'graph.json').write_text(json.dumps(items,indent=2)+'\n')
(out/'mio-packages.json').write_text(json.dumps([x for x in items if x['ImportPath'].startswith('Mio')],indent=2)+'\n')
print('packages',len(items),'Mio packages',len([x for x in items if x['ImportPath'].startswith('Mio')]))
