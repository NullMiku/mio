#!/usr/bin/env python3
"""One fixed32 matrix, canonical freeze, separate ungated and scheduled images."""
from pathlib import Path
import subprocess,sys,json,hashlib,shutil,fcntl,os
r=Path.cwd();out=(r/sys.argv[1]).resolve();assert out.is_relative_to(r/'build/m19ef-evidence');out.mkdir()
lock=os.fdopen(os.dup(int(os.environ['MIO_E5_TEST_LOCK_FD'])),'a+') if 'MIO_E5_TEST_LOCK_FD' in os.environ else (r/'build/.m19ef-native-test.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
env=dict(os.environ,MIO_E5_TEST_LOCK_FD=str(lock.fileno()))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest={str(p.relative_to(r)):sha(p) for folder in ('bunko','selfhost','tests/m19ef','specs/002-m19ef-portable-pure-mio') for p in sorted((r/folder).rglob('*')) if p.is_file() and p.suffix in ('.mio','.py','.md','.json','.sh','.txt')}
(out/'freeze.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n');shutil.copyfile(__file__,out/'controller.py')
plan=dict(contract='E5-lifecycle-v2.1.1',repetitions=32,canonical_manifest_sha256=sha(out/'freeze.json'),historical_full30='FAIL_PERMANENT',status='RUNNING',parts=['ungated_fixed32','lifecycle_fixed32'],E5='IN_PROGRESS',E6='NOT_RUN')
(out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
prior=None
for candidate in sorted((r/'build/m19ef-evidence').glob('E5-v2*-directed-*'),reverse=True):
 try:
  base=json.loads((candidate/'canonical-manifest.json').read_text())
  relevant=lambda m:{k:v for k,v in m.items() if k.startswith(('bunko/','selfhost/')) or k in ('tests/m19ef/old-sweep/builder.mio','tests/m19ef/old-sweep-v2/overlay.py')}
  if relevant(base)==relevant(manifest) and json.loads((candidate/'summary.json').read_text())['status']=='PASS_DIRECTED':prior=candidate;break
 except (OSError,KeyError,ValueError):pass
life=[sys.executable,'tests/m19ef/old-sweep-v2/run.py',str(out/'lifecycle'),'full']
if len(sys.argv)>3:life.append(sys.argv[3])
elif prior:life.append(str(prior))
for name,args in [('ungated',[sys.executable,'tests/m19ef/old-sweep-v2/ungated_matrix.py',str(out/'ungated'),sys.argv[2]]),('lifecycle',life)]:
 with (out/(name+'.stdout')).open('xb') as so,(out/(name+'.stderr')).open('xb') as se:
  result=subprocess.run(args,stdout=so,stderr=se,env=env,pass_fds=(lock.fileno(),))
 assert result.returncode==0,(name,result.returncode)
 assert all(sha(r/k)==h for k,h in manifest.items()),'frozen source changed'
plan.update(status='PASS_FIXED32_PENDING_AFFECTED_REGRESSION');(out/'summary.json').write_text(json.dumps(plan,indent=2)+'\n')
