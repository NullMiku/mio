#!/usr/bin/env python3
"""Seal GF0 evidence hashes; never changes source or historical inputs."""
import argparse, collections, hashlib, json, pathlib, shutil, subprocess
p=argparse.ArgumentParser(); p.add_argument('--root',type=pathlib.Path,required=True); p.add_argument('--freeze',type=pathlib.Path,required=True); a=p.parse_args(); root=a.root.resolve(); f=a.freeze.resolve()
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for b in iter(lambda:stream.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
report={}
for label,manifest,base in [('snapshot','source-manifest.json',f/'source'),('original','source-manifest.json',root),('history-copy','historical-manifest.json',f/'historical'),('history-original','historical-manifest.json',root)]:
 differences=[]
 for item in json.loads((f/manifest).read_text()):
  if item.get('missing'): continue
  path=base/item['path']
  if not path.exists() or sha(path)!=item['sha256']: differences.append(item['path'])
 expected=['specs/001-go-free-single-binary/tasks.md'] if label=='original' else []
 report[label]={'status':'PASS' if not (set(differences)-set(expected)) else 'FAIL','differences':differences,'allowed_audit_only_changes':expected}
assert all(x['status']=='PASS' for x in report.values()), report
for name,args in [('final-status.txt',['git','status','--porcelain=v1','--untracked-files=all']),('final-tracked.diff',['git','diff','HEAD','--binary']),('final-worktrees.txt',['git','worktree','list','--porcelain'])]:
 proc=subprocess.run(args,cwd=root,capture_output=True); assert proc.returncode==0; (f/name).write_bytes(proc.stdout)
assert not (f/'final-tracked.diff').read_bytes(),'tracked code changed'
(f/'final-integrity.json').write_text(json.dumps(report,indent=2)+'\n')
tools=f/'tools'; tools.mkdir(exist_ok=False)
for file in (root/'specs/001-go-free-single-binary/gf0').iterdir():
 if file.is_file(): shutil.copy2(file,tools/file.name)
# Preserve exact r1 runner, whose expected negative exit and timeout handling were corrected for r2.
s=(tools/'probe.py').read_text().replace('shutil, signal, subprocess','shutil, subprocess').replace("r'exec\\.|subprocess","'exec\\.|subprocess").replace("run('native-buildinfo',['go','version','-m',native],expected=1)","run('native-buildinfo',['go','version','-m',native])")
s=s.replace("proc=subprocess.Popen(['/usr/bin/time','-l',*rec['argv']],cwd=cwd,env=e,stdout=stdout,stderr=stderr,start_new_session=True); rec['exit_code']=proc.wait(timeout=timeout)","proc=subprocess.run(['/usr/bin/time','-l',*rec['argv']],cwd=cwd,env=e,stdout=stdout,stderr=stderr,timeout=timeout); rec['exit_code']=proc.returncode")
s=s.replace("except subprocess.TimeoutExpired:\n   os.killpg(proc.pid,signal.SIGKILL); proc.wait(); rec['exit_code']=None; rec['status']='TIMEOUT'","except subprocess.TimeoutExpired: rec['exit_code']=None; rec['status']='TIMEOUT'")
(tools/'probe-r1.py').write_text(s)
(tools/'VERSIONS.md').write_text('freeze.py ran at initial snapshot. probe-r1.py reconstructs the initial runner exactly (negative Go buildinfo expected exit was wrong; no timeout occurred). probe.py is corrected r2; both outputs retained. verify.py / corpus.py / dependencies.py match their executed versions. finalize.py seals this evidence. All tools operate on the declared frozen work copy. AUDIT.md references current results.\n')
results=json.loads((f/'corpus/results.json').read_text())
summary={'gf0_status':'PASS','scope':'dependency audit and source baseline freeze only','go_free_single_binary':'NOT_ACCEPTED','head':(f/'head.txt').read_text().strip(),'source_manifest_sha256':sha(f/'source-manifest.json'),'historical_manifest_sha256':sha(f/'historical-manifest.json'),'corpus_status_counts':dict(collections.Counter(x['status'] for x in results)),'native_frontend_probe':json.loads((f/'verification/frontend-output.json').read_text()),'historical_full_race':'NOT_ACCEPTED','heavy_full_validation':'NOT RUN: M19 concurrent Race workload','next_phase':'GF1 only; see AUDIT.md blockers and plan','evidence_root':str(f)}
(f/'summary.json').write_text(json.dumps(summary,indent=2)+'\n'); (root/'specs/001-go-free-single-binary/gf0/summary.json').write_text(json.dumps(summary,indent=2)+'\n')
# The final index excludes itself to avoid self-reference. All source/history files included.
files=[]
for path in sorted(f.rglob('*')):
 if path.is_file() and path.name!='evidence-index.json': files.append({'path':str(path.relative_to(f)),'bytes':path.stat().st_size,'sha256':sha(path)})
(f/'evidence-index.json').write_text(json.dumps(files,indent=2)+'\n')
print(json.dumps(summary,indent=2)); print('evidence-index SHA256',sha(f/'evidence-index.json'))
