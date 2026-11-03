#!/usr/bin/env python3
"""Offline native CLI path/override/discovery regression; audit controller only."""
import argparse,hashlib,json,os,shutil,subprocess,tempfile,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);work=Path(tempfile.mkdtemp(prefix='mio-path-final-',dir='/tmp')).resolve();cli=work/'mio';shutil.copy2(a.candidate,cli);commands=[];results=[]
def policy(name,program,test=False):
 f=work/(name+'.sb');s='(version 1)(allow default)(deny network*)(deny process-exec)(allow process-exec (literal '+json.dumps(str(program))+'))'
 if test:s+='(allow process-exec (regex #"^(/private)?/tmp/mio-test-[0-9]+/test-[0-9]+[.]native$"))'
 else:s+='(deny process-fork)'
 s+='(deny file-read* (subpath '+json.dumps(str(root))+'))(deny file-read* (subpath "/Volumes/Sector0/AppData/Mio/mio"))';f.write_text(s+'\n');return ['/usr/bin/sandbox-exec','-f',str(f),str(program)]
def run(label,argv,cwd=None,env=None):
 start=time.monotonic();environment={'PATH':'','MIO_BUNKO':''};environment.update(env or {});r=subprocess.run(list(map(str,argv)),cwd=cwd or work,env=environment,capture_output=True,timeout=120);(out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr);commands.append({'label':label,'argv':list(map(str,argv)),'cwd':str(cwd or work),'environment':environment,'exit':r.returncode,'seconds':time.monotonic()-start});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');return r

def record(name,ok,**details):
 results.append({'case':name,'status':'PASS' if ok else 'FAIL',**details});(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(name,results[-1]['status'],flush=True)
def build(name,entry,expected,args=(),env=None,cwd=None):
 app=work/(name+'.native');r=run(name+'-build',policy(name+'-compiler',cli)+['build',str(entry),'-o',str(app),*map(str,args)],cwd,env);executed=None;verify=None
 if r.returncode==0 and app.exists():
  verify=run(name+'-verify',['/usr/bin/codesign','--verify','--strict',app]);executed=run(name+'-native',policy(name+'-runtime',app))
 record(name,r.returncode==0 and verify is not None and verify.returncode==0 and executed is not None and executed.returncode==0 and executed.stdout==expected,build_exit=r.returncode)
project=work/'工程 空格';(project/'dep').mkdir(parents=True);(project/'dep/main.mio').write_text('koukai waza value() -> int64 {kaesu 99;}');(project/'depAlias').symlink_to('dep',target_is_directory=True);main=project/'main.mio';main.write_text('yobu "./depAlias";chant(depAlias.value());')
link=work/'project-alias';link.symlink_to(project,target_is_directory=True)
build('absolute-unicode-entry-relative-symlink-import',main,b'99\n')
build('symlink-project-entry-from-other-cwd',link/'main.mio',b'99\n')
build('relative-entry-keeps-import-alias',Path('工程 空格/main.mio'),b'99\n')
for name,value in [('rootA',11),('rootB',22)]:
 d=work/name/'kiso/custom';d.mkdir(parents=True);(d/'main.mio').write_text(f'koukai waza value() -> int64 {{kaesu {value};}}')
custom=work/'custom.mio';custom.write_text('yobu "kiso/custom";chant(custom.value());')
build('environment-bunko-root',custom,b'11\n',env={'MIO_BUNKO':str(work/'rootA')})
build('explicit-root-over-environment',custom,b'22\n',args=['--bunko-root',work/'rootB'],env={'MIO_BUNKO':str(work/'rootA')})
(work/'root-alias').symlink_to('rootA',target_is_directory=True);build('symlink-bunko-root',custom,b'11\n',args=['--bunko-root',work/'root-alias'])
(work/'rootA/kiso/escape').symlink_to(work/'rootB/kiso/custom',target_is_directory=True);escape=work/'escape.mio';escape.write_text('yobu "kiso/escape";chant(escape.value());');target=work/'escape.native';r=run('escape',policy('escape-compiler',cli)+['build',str(escape),'--bunko-root',str(work/'rootA'),'-o',str(target)]);record('explicit-bunko-symlink-escape-rejected',r.returncode==1 and not target.exists() and b'escapes explicit root' in r.stderr)
spoof=work/'bunko/kiso/math';spoof.mkdir(parents=True);(spoof/'math.mio').write_text('koukai waza max(a: int64,b: int64) -> int64 {kaesu -999;}');standard=work/'standard.mio';standard.write_text('yobu "kiso/math";chant(math.max(1,2));');build('embedded-does-not-search-cwd-bunko',standard,b'2\n')
target=work/'invalid-env.native';r=run('invalid-env',policy('invalid-env-compiler',cli)+['build',str(standard),'-o',str(target)],env={'MIO_BUNKO':str(work/'missing')});record('invalid-environment-root-does-not-fallback',r.returncode==1 and not target.exists())
tests=work/'tests';(tests/'sub').mkdir(parents=True)
for d,name in [(tests,'test_parent'),(tests/'sub','test_child')]:
 (d/'main_test.mio').write_text(f'yobu "kiso/testing";waza {name}() -> unit {{testing.expect(hai,"native path test");}}')
(tests/'loop').symlink_to('.',target_is_directory=True);r=run('recursive-test',policy('tests-compiler',cli,test=True)+['test','./...','--format=json','--lang=en-US'],cwd=tests);summary=None
try:summary=json.loads(r.stdout)['summary']
except (ValueError,KeyError):pass
record('relative-recursive-test-registry-and-symlink-cycle',r.returncode==0 and summary is not None and summary.get('passed')==2 and summary.get('failed')==0,summary=summary)
(out/'provenance.json').write_text(json.dumps({'candidate':str(a.candidate.resolve()),'candidate_sha256':hashlib.sha256(cli.read_bytes()).hexdigest(),'work':str(work),'scope':__doc__},indent=2)+'\n');raise SystemExit(0 if all(x['status']=='PASS' for x in results) else 1)
