#!/usr/bin/env python3
"""Independent read-only archive/installer audit; product packaging/install logic
runs only in the native Mio program. Python never creates the product archive.
"""
import argparse,json,hashlib,subprocess,tempfile,shutil,tarfile,io,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--builder',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);work=Path(tempfile.mkdtemp(prefix='mio-native-package-',dir='/tmp')).resolve();builder=work/'native-ci';candidate=work/'mio';license=work/'LICENSE';shutil.copy2(a.builder,builder);shutil.copy2(a.candidate,candidate);shutil.copy2(root/'LICENSE',license);results=[];commands=[]
def run(label,args,install=False):
 policy=work/(label+'.sb');s='(version 1)(allow default)(deny network*)(deny process-exec)(allow process-exec (literal '+json.dumps(str(builder))+'))(deny file-read* (subpath '+json.dumps(str(root))+'))(deny file-read* (subpath "/Volumes/Sector0/AppData/Mio"))'
 if install:s+='(allow process-exec (literal '+json.dumps(str(work/'install/mio'))+'))'
 else:s+='(deny process-fork)'
 policy.write_text(s+'\n');argv=['/usr/bin/sandbox-exec','-f',str(policy),str(builder),*map(str,args)];start=time.monotonic();r=subprocess.run(argv,cwd=work,env={'PATH':'','MIO_BUNKO':''},capture_output=True,timeout=600);(out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr);commands.append({'label':label,'argv':argv,'exit':r.returncode,'seconds':time.monotonic()-start,'policy':s});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');return r
packed=work/'package';r=run('package',['package',candidate,license,packed]);assert r.returncode==0,r.stderr
archive=packed/'mio-2.0.0-dev-darwin-arm64.tar.gz';data=archive.read_bytes();members=[]
with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as tar:
 for member in tar.getmembers():members.append({'name':member.name,'mode':member.mode,'mtime':member.mtime,'uid':member.uid,'gid':member.gid,'data_sha256':hashlib.sha256(tar.extractfile(member).read()).hexdigest(),'size':member.size})
sha=hashlib.sha256(candidate.read_bytes()).hexdigest();ok=[x['name'] for x in members]==['mio','LICENSE','README.txt'] and members[0]['data_sha256']==sha and members[0]['mode']==0o755 and all(x['mtime']==x['uid']==x['gid']==0 for x in members);results.append({'case':'independent-standard-gzip-ustar-read','status':'PASS' if ok else 'FAIL','members':members,'native_archive_sha256':hashlib.sha256(data).hexdigest()});assert ok
r=run('install',['install',archive,work/'install',sha],install=True);results.append({'case':'native-offline-installer-and-version','status':'PASS' if r.returncode==0 and (work/'install/mio').read_bytes()==candidate.read_bytes() else 'FAIL'})
r=run('preserve-existing-install',['install',archive,work/'install',sha],install=True);results.append({'case':'preserve-existing-install','status':'PASS' if r.returncode!=0 and (work/'install/mio').read_bytes()==candidate.read_bytes() else 'FAIL'})
corrupt=bytearray(data);corrupt[-8]^=1;(work/'bad.gz').write_bytes(corrupt);r=run('reject-corrupt',['install',work/'bad.gz',work/'bad-install',sha],install=True);results.append({'case':'reject-corrupt-before-install','status':'PASS' if r.returncode!=0 and not (work/'bad-install').exists() else 'FAIL'})
r=run('repackage',['package',candidate,license,work/'package-again']);results.append({'case':'byte-reproducible-native-archive','status':'PASS' if r.returncode==0 and (work/'package-again'/archive.name).read_bytes()==data else 'FAIL'})
(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');(out/'provenance.json').write_text(json.dumps({'scope':__doc__,'work':str(work),'candidate_sha256':sha,'builder_sha256':hashlib.sha256(builder.read_bytes()).hexdigest(),'archive_sha256':hashlib.sha256(data).hexdigest()},indent=2)+'\n');shutil.copy2(archive,out/archive.name);shutil.copy2(packed/'SHA256SUMS',out/'SHA256SUMS');print(json.dumps(results,indent=2),flush=True);raise SystemExit(0 if all(x['status']=='PASS' for x in results) else 1)
