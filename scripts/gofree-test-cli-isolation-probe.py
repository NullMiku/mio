#!/usr/bin/env python3
"""Isolated single-installed-binary native test CLI and locale audit."""
import argparse,json,hashlib,shutil,subprocess,tempfile,time,signal,os
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(exist_ok=False,parents=True);sandbox=Path(tempfile.mkdtemp(prefix='mio-test-offline-')).resolve();install=sandbox/'install';install.mkdir();cli=install/'mio';shutil.copy2(a.candidate,cli);project=sandbox/'工程 空格';project.mkdir();pkg=project/'pkg';pkg.mkdir();(pkg/'a_test.mio').write_text('yobu "kiso/testing"; waza test_language() -> unit { testing.expect(hai,"ok"); }\n');empty=project/'empty';empty.mkdir();bad=project/'invalid';bad.mkdir();(bad/'a_test.mio').write_text('waza test_bad(value: int64) -> unit {}\n')
policy=sandbox/'runtime.sb';policy.write_text('(version 1)(allow default)(deny network*)(deny process-exec)(allow process-exec (literal '+json.dumps(str(cli))+'))(allow process-exec (regex #"^(/private)?/tmp/mio-test-[0-9]+/test-[0-9]+[.]native$"))(deny file-read* (subpath "/Users/hatsunemiku/.codex/worktrees"))(deny file-read* (subpath "/Volumes/Sector0/AppData/Mio"))\n');commands=[];results=[]
(out/'isolation.json').write_text(json.dumps({'installation':str(install),'installed_files':[x.name for x in install.iterdir()],'candidate_sha256':hashlib.sha256(cli.read_bytes()).hexdigest(),'sandbox':str(sandbox),'policy':policy.read_text(),'source_root':str(root),'scope':'test command and locale selection only; complete GF3 remains pending'},indent=2)+'\n')
def run(name,target,args,env):
 argv=['/usr/bin/sandbox-exec','-f',str(policy),str(cli),'test',str(target),*args];start=time.monotonic();proc=subprocess.Popen(argv,cwd=project,env={'PATH':'',**env},stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
 try:stdout,stderr=proc.communicate(timeout=120);code=proc.returncode
 except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);stdout,stderr=proc.communicate();code=None
 (out/(name+'.stdout')).write_bytes(stdout);(out/(name+'.stderr')).write_bytes(stderr);commands.append({'name':name,'argv':argv,'cwd':str(project),'environment':{'PATH':'',**env},'exit':code,'wall_seconds':time.monotonic()-start});(out/'commands.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2)+'\n');return code,stdout,stderr
def record(name,ok,code):
 results.append({'case':name,'status':'PASS' if ok else 'FAIL','exit':code});(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(name,results[-1]['status'],flush=True)
for name,env,args,label in [('default',{},[],'PASS'),('mio-lang',{'MIO_LANG':'zh-CN'},[],'通过'),('lc-all',{'LC_ALL':'ja_JP.UTF-8'},[],'成功'),('lc-messages',{'LC_MESSAGES':'zh_TW.UTF-8'},[],'通过'),('lang',{'LANG':'ja.UTF8'},[],'成功'),('explicit',{'MIO_LANG':'ja-JP'},['--lang=zh.UTF-8'],'通过'),('unknown-priority',{'MIO_LANG':'unknown','LC_ALL':'zh-CN'},[],'PASS'),('empty-fallback',{'MIO_LANG':'','LC_ALL':'','LC_MESSAGES':'ja'},[],'成功'),('unicode-trim',{},['--lang= ja　'],'成功'),('priority-all',{'LC_ALL':'zh','LC_MESSAGES':'ja','LANG':'en'},[],'通过')]:
 code,stdout,stderr=run(name,pkg,args,env);record(name,code==0 and label.encode() in stdout and not stderr,code)
for name,target,args,expected in [('json-embedded',pkg,['--format=json'],0),('filter',pkg,['--format=json','--run=^test_language$'],0),('no-match',pkg,['--format=json','--run=^NEVER$'],0),('empty',empty,['--format=json'],0),('invalid-before-filter',bad,['--format=json','--run=^NEVER$'],1)]:
 code,stdout,stderr=run(name,target,args,{'MIO_LANG':'zh'});report=None
 try:report=json.loads(stdout)
 except Exception:pass
 ok=code==expected and report is not None
 if report:
  if name in ('json-embedded','filter'):ok=ok and report['summary']['passed']==1
  elif name in ('no-match','empty'):ok=ok and report['summary']['status']=='no_tests'
  else:ok=ok and report['packages'][0]['status']=='compile_failed'
 record(name,ok,code)
code,stdout,stderr=run('bad-regexp',pkg,['--run=['],{});record('bad-regexp',code==1 and not stdout and b'E_OPTIONS' in stderr,code)
(out/'source-manifest.json').write_text(json.dumps([{'path':str(x.relative_to(root)),'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in sorted(set(root.glob('bunko/**/*.mio'))|set(root.glob('selfhost/**/*.mio')))],indent=2)+'\n');raise SystemExit(0 if all(x['status']=='PASS' for x in results) else 1)
