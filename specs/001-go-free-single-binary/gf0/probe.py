#!/usr/bin/env python3
"""GF0 read-only-input probes. Uses frozen work copy; never runs release/bootstrap scripts."""
import argparse, hashlib, json, os, pathlib, platform, shutil, signal, subprocess, time
p=argparse.ArgumentParser(); p.add_argument('--freeze',type=pathlib.Path,required=True); p.add_argument('--output',type=pathlib.Path,required=True); a=p.parse_args()
f=a.freeze.resolve(); root=f/'work'; out=a.output.resolve(); out.mkdir(parents=True,exist_ok=False)
manifest=f/'source-manifest.json'; manifest_hash=hashlib.sha256(manifest.read_bytes()).hexdigest(); records=[]
env=os.environ.copy(); env.update(MIO_BUNKO=str(root/'bunko'),GOMAXPROCS='2',GOFLAGS='-p=2',CGO_ENABLED='0')
def run(label,argv,cwd=root,timeout=90,expected=0,override=None):
 e=env.copy(); e.update(override or {}); start=time.monotonic()
 rec={'label':label,'argv':[str(x) for x in argv],'cwd':str(cwd),'source_manifest_sha256':manifest_hash,'environment':{k:e[k] for k in ['MIO_BUNKO','GOMAXPROCS','GOFLAGS','CGO_ENABLED']},'overrides':override or {},'expected_exit':expected,'timeout_seconds':timeout}
 with (out/(label+'.stdout')).open('wb') as stdout, (out/(label+'.stderr')).open('wb') as stderr:
  try:
   proc=subprocess.Popen(['/usr/bin/time','-l',*rec['argv']],cwd=cwd,env=e,stdout=stdout,stderr=stderr,start_new_session=True); rec['exit_code']=proc.wait(timeout=timeout)
  except subprocess.TimeoutExpired:
   os.killpg(proc.pid,signal.SIGKILL); proc.wait(); rec['exit_code']=None; rec['status']='TIMEOUT'
 rec['wall_seconds']=time.monotonic()-start
 rec.setdefault('status','PASS' if rec['exit_code']==expected else 'FAIL')
 records.append(rec); (out/'commands.json').write_text(json.dumps(records,indent=2)+'\n'); print(label,rec['exit_code'],rec['status'],flush=True)
 return rec['exit_code']
for label,argv in [('host',['uname','-a']),('os',['sw_vers']),('cpu',['sysctl','-n','machdep.cpu.brand_string','hw.memsize']),('go-version',['go','version']),('go-env',['go','env','GOVERSION','GOOS','GOARCH','GOROOT','GOTOOLCHAIN']),('python',['python3','--version']),('processes',['ps','-axo','pid,ppid,etime,%cpu,rss,command']),('go-modules',['go','list','-m','all']),('go-dependencies',['go','list','-deps','-json','./...']),('static-calls',['rg','-n',r'exec\.|subprocess|go build|go test|go run|codesign|clang|sandbox-exec|lldb|go:embed','cmd','internal','selfhost','scripts','.github']),('imports',['rg','-n','^yobu |mio/fs/runtime|binding_key','bunko','selfhost']),('test-inventory',['rg','-n','^func (Test|Benchmark)|t.Skip|MIO_M18|MIO_STRESS','cmd','internal','selfhost']),('pure-errors',['rg','-n','unsupported|Unsupported|not supported|TODO|conflict|unknown','bunko/kiso/aot/lower','selfhost'])]: run(label,argv)
mio=out/'mio'; aot=out/'mochi-aot'
if run('build-cli',['go','build','-buildvcs=false','-o',mio,'./cmd/mio'])!=0: raise SystemExit('CLI blocked')
run('build-aot',['go','build','-buildvcs=false','-o',aot,'./cmd/mochi-aot'])
for name,binary in [('cli',mio),('aot',aot)]:
 run(name+'-buildinfo',['go','version','-m',binary]); run(name+'-file',['file',binary]); run(name+'-libraries',['otool','-L',binary])
run('cli-symbols',['go','tool','nm',mio])
cases=out/'cases'; cases.mkdir()
(cases/'hello.mio').write_text('chant("GF0 hello");\n')
(cases/'import.mio').write_text('yobu "kiso/string";\nchant(string.concat("GF0", " import"));\n')
(cases/'bad.mio').write_text('kaku x: int64 = "bad";\n')
for label,argv,code in [('version',[mio,'version'],0),('help',[mio,'help'],0),('no-args',[mio],2),('check',[mio,'check',cases/'hello.mio'],0),('build-default',[mio,'build',cases/'hello.mio'],0),('run',[mio,'run',cases/'hello.mio'],0),('exec',[mio,'exec',cases/'hello.mochi'],0),('disasm',[mio,'disasm',cases/'hello.mochi'],0),('run-args',[mio,'run',cases/'hello.mio','--','x'],2),('bad-check',[mio,'check','--format=json',cases/'bad.mio'],1),('test',[mio,'test','bunko/kiso/path','--format=json'],0),('import',[mio,'run',cases/'import.mio'],0)]: run(label,argv,expected=code)
# Repeated compile runs are warm-cache process launches, not incremental compiler work.
for i in range(3):
 run('hello-build-'+str(i),[mio,'build','-o',cases/('hello-'+str(i)+'.mochi'),cases/'hello.mio'])
run('build-bootstrap-source',[mio,'build','-o',out/'bootstrap.mochi','selfhost/bootstrap'],timeout=120)
run('aot-bootstrap-probe',[aot,'-heap-mib','1024','-o',out/'bootstrap.unsigned',out/'bootstrap.mochi'],timeout=60)
run('aot-hello',[aot,'-o',out/'hello.unsigned',cases/'hello.mochi'])
# Exercise archived pure Mio backend on the same frontend IR without modifying it.
native=f/'historical/build/m19c-20261026-fixed-point/stage4.native'
if native.exists():
 run('native-buildinfo',['go','version','-m',native],expected=1)
 run('native-libraries',['otool','-L',native]); run('native-signature',['codesign','--verify','--strict',native])
 for name,input_file in [('hello',cases/'hello.mochi'),('frontend',out/'bootstrap.mochi')]:
  d=out/('native-'+name); d.mkdir(); (d/'input.config').write_text(str(input_file)); (d/'output.config').write_text(str(d/'image.unsigned'))
  policy=d/'sandbox.sb'; policy.write_text('(version 1)(allow default)(deny process-fork)(deny process-exec)(allow process-exec (literal '+json.dumps(str(native))+'))\n')
  run('native-'+name,[ '/usr/bin/sandbox-exec','-f',policy,native],cwd=d,timeout=60,override={'PATH':''})
  if (d/'image.unsigned').exists() and name=='hello':
   image=d/'image.native'; shutil.copy2(d/'image.unsigned',image); image.chmod(0o755)
   run('native-hello-sign',['codesign','--force','--sign','-',image]); run('native-hello-verify',['codesign','--verify','--strict',image]); run('native-hello-run',[image],cwd=d,override={'PATH':''})
clean=out/'clean'; clean.mkdir(); shutil.copy2(mio,clean/'mio'); shutil.copy2(cases/'import.mio',clean/'import.mio')
run('no-bunko',[clean/'mio','check','import.mio'],cwd=clean,expected=1,override={'PATH':'','MIO_BUNKO':str(clean/'absent')})
run('no-go-cli',[clean/'mio','check',cases/'hello.mio'],cwd=clean,override={'PATH':''})
# No cache flush, no full Race, no regeneration of heavy fixed-point chains while M19 is active.
summary={'platform':platform.platform(),'source_manifest_sha256':manifest_hash,'full_race':'NOT RUN: existing M19 Race process active; historical gate remains NOT_ACCEPTED','fresh_fixed_point':'NOT RUN: heavy validation window occupied; archived evidence independently inspected','cold_cache':'NOT RUN: no OS cache flush; sample 0 is first measured launch, not proven cold','incremental':'BLOCKED: no persistent incremental compiler API','process_trace':'NOT RUN: sandbox denial probes cover native backend child execution only; not full file-access tracing'}
(out/'scope.json').write_text(json.dumps(summary,indent=2)+'\n')
files=[]
for file in sorted(out.rglob('*')):
 if file.is_file(): files.append({'path':str(file.relative_to(out)),'bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
(out/'artifact-manifest.json').write_text(json.dumps(files,indent=2)+'\n')
