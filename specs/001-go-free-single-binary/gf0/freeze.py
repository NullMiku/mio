#!/usr/bin/env python3
"""GF0 non-mutating source/evidence freeze; output must be outside checkout and new."""
import argparse, hashlib, json, os, pathlib, shutil, stat, subprocess, datetime
p=argparse.ArgumentParser(); p.add_argument('--root',type=pathlib.Path,required=True); p.add_argument('--output',type=pathlib.Path,required=True); a=p.parse_args()
r=a.root.resolve(); out=a.output.resolve()
if out == r or r in out.parents: raise SystemExit('output must be outside source')
out.mkdir(parents=True,exist_ok=False)
def git(*args): return subprocess.check_output(['git','-C',str(r),*args])
def save(name,data): (out/name).write_bytes(data)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
for name,args in {'head.txt':['rev-parse','HEAD'],'branches.txt':['branch','-avv','--no-abbrev'],'worktrees.txt':['worktree','list','--porcelain'],'status.txt':['status','--porcelain=v1','--untracked-files=all'],'staged.patch':['diff','--cached','--binary'],'unstaged.patch':['diff','--binary'],'tracked.zlist':['ls-files','-z'],'untracked.zlist':['ls-files','--others','--exclude-standard','-z']}.items(): save(name,git(*args))
worktrees=[]
for line in (out/'worktrees.txt').read_text().splitlines():
 if line.startswith('worktree '):
  w=pathlib.Path(line[9:]); result=subprocess.run(['git','-C',str(w),'status','--porcelain=v1','--untracked-files=all'],capture_output=True)
  worktrees.append({'path':str(w),'exit_code':result.returncode,'status':result.stdout.decode(),'stderr':result.stderr.decode()})
save('worktree-status.json',(json.dumps(worktrees,indent=2)+'\n').encode())
paths=set(os.fsdecode(x) for x in git('ls-files','-z','--cached','--others','--exclude-standard').split(b'\0') if x)
# Ignored technical records are needed; local credentials, IDE state and caches are not source.
paths.update(str(x.relative_to(r)) for x in (r/'docs').rglob('*') if x.is_file() and x.name!='.DS_Store')
records=[]
for name in sorted(paths):
 src=r/name
 if not src.exists(): records.append({'path':name,'missing':True}); continue
 if src.is_symlink(): raise SystemExit('review symlink before snapshot: '+name)
 before=sha(src); dst=out/'source'/name; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
 if before!=sha(dst) or before!=sha(src): raise SystemExit('source changed during copy: '+name)
 records.append({'path':name,'bytes':src.stat().st_size,'mode':stat.S_IMODE(src.stat().st_mode),'sha256':before})
save('source-manifest.json',(json.dumps(records,ensure_ascii=False,indent=2)+'\n').encode())
history=[]
for name in ['build/m18-20261020-verified','build/m19c-20261026-fixed-point','build/m19c-20261026-report','build/m19c-20261026-full','build/m19c-20261026-full-race','build/m19c-20261026-specialized','build/m19c-20261026-race-targeted']:
 src=r/name
 if src.is_dir():
  for f in sorted(src.rglob('*')):
   if f.is_file() and not f.is_symlink():
    rel=f.relative_to(r); dst=out/'historical'/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(f,dst)
    digest=sha(dst)
    if digest!=sha(f): raise SystemExit('history changed during copy: '+str(rel))
    history.append({'path':str(rel),'bytes':f.stat().st_size,'sha256':digest})
save('historical-manifest.json',(json.dumps(history,indent=2)+'\n').encode())
meta={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'root':str(r),'output':str(out),'source_manifest_sha256':sha(out/'source-manifest.json'),'historical_manifest_sha256':sha(out/'historical-manifest.json'),'source_files':len(records),'historical_files':len(history),'excluded':'Git object/admin database, ignored build artifacts except named historical evidence directories, local .mio state (may contain credentials), IDE/cache/dist; ignored docs included. Other worktrees inventoried, never merged.'}
save('freeze.json',(json.dumps(meta,indent=2)+'\n').encode())
shutil.copytree(out/'source',out/'work')
for tree in [out/'source',out/'historical']:
 if tree.exists():
  for f in tree.rglob('*'):
   if f.is_file(): f.chmod(0o555 if os.access(f,os.X_OK) else 0o444)
  for d in sorted((x for x in tree.rglob('*') if x.is_dir()),reverse=True): d.chmod(0o555)
  tree.chmod(0o555)
print(json.dumps(meta,indent=2))
