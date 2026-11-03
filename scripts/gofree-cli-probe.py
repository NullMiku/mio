#!/usr/bin/env python3
"""Isolated GF3 CLI vertical slice; incomplete commands remain NOT_ACCEPTED."""
import argparse,hashlib,json,os,shutil,signal,subprocess,tempfile,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--legacy-ir',type=Path);p.add_argument('--typed-v15-ir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);sandbox=Path(tempfile.mkdtemp(prefix='mio-gf3-offline-')).resolve();mio=sandbox/'mio';shutil.copy2(a.candidate,mio);project=sandbox/'工程 空格';project.mkdir();commands=[];results=[]
(out/'isolation.json').write_text(json.dumps({'directory':str(sandbox),'installed_files':['mio'],'candidate_sha256':hashlib.sha256(mio.read_bytes()).hexdigest(),'forbidden_reads':[str(root),'/Volumes/Sector0/AppData/Mio'],'environment':{'PATH':'','MIO_BUNKO':''},'scope':'GF3 candidate check/build/run/exec/disasm/emit-mochi; test and LSP have separate audits'},indent=2)+'\n')
policy=sandbox/'compiler.sb';policy.write_text('(version 1)(allow default)(deny network*)(deny process-fork)(deny process-exec)(allow process-exec (literal '+json.dumps(str(mio))+'))(deny file-read* (subpath '+json.dumps(str(root))+'))(deny file-read* (subpath "/Users/hatsunemiku/.codex/worktrees"))(deny file-read* (subpath "/Volumes/Sector0/AppData/Mio"))\n')
run_policy=sandbox/'run.sb';run_policy.write_text('(version 1)(allow default)(deny network*)(deny process-exec)(allow process-exec (literal '+json.dumps(str(mio))+'))(allow process-exec (regex #"^/private/tmp/mio-run-[0-9]+/program$"))(deny file-read* (subpath '+json.dumps(str(root))+'))(deny file-read* (subpath "/Users/hatsunemiku/.codex/worktrees"))(deny file-read* (subpath "/Volumes/Sector0/AppData/Mio"))\n')
def run(label,argv,compiler=False):
 argv=list(map(str,argv));start=time.monotonic()
 with (out/(label+'.stdout')).open('wb') as stdout,(out/(label+'.stderr')).open('wb') as stderr:
  proc=subprocess.Popen(['/usr/bin/time','-l',*(['/usr/bin/sandbox-exec','-f',str(run_policy if compiler == 'run' else policy)] if compiler else []),*argv],cwd=project,env={'PATH':'','MIO_BUNKO':''},stdout=stdout,stderr=stderr,start_new_session=True)
  try:code=proc.wait(timeout=180)
  except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait();code=None
 commands.append({'label':label,'argv':argv,'sandbox_policy':str(run_policy if compiler == 'run' else policy) if compiler else None,'cwd':str(project),'exit_code':code,'wall_seconds':time.monotonic()-start});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');return code,(out/(label+'.stdout')).read_bytes()
def record(label,ok,**kwargs):
 results.append({'case':label,'status':'PASS' if ok else 'FAIL',**kwargs});(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(label,results[-1]['status'],flush=True)
code,stdout=run('version',[mio,'version'],True);record('version',code==0 and b'pure Mio Native AOT' in stdout)
code,stdout=run('help',[mio,'help','build'],True);record('help',code==0 and b'mio build' in stdout)
(project/'hello.mio').write_text('yobu "kiso/math"; yobu "kiso/array"; kaku values = array.make[int64](2, 7); chant(math.max(values[1], 9));\n')
code,stdout=run('check',[mio,'check','hello.mio'],True);record('check-embedded',code==0 and not stdout)
code,stdout=run('build',[mio,'build','hello.mio','-o','hello'],True);app=project/'hello';record('build-embedded-native-sign-and-mode',code==0 and not stdout and app.is_file() and os.access(app,os.X_OK))
if code==0 and app.exists():
 verify,_=run('verify',['/usr/bin/codesign','--verify','--strict',app]);execute,actual=run('execute',[app]);record('native-signature-and-independent-application',verify==execute==0 and actual==b'9\n',signature_source='Mio only; system codesign used exclusively with --verify')
code,stdout=run('emit-mochi',[mio,'build','hello.mio','--emit=mochi','-o','hello.mochi'],True);ir=project/'hello.mochi';record('explicit-mochi-export',code==0 and ir.exists() and ir.read_bytes()[:5]==b'MOCHI')
(project/'broken.mio').write_text('kaku = ;');code,stdout=run('syntax',[mio,'build','broken.mio','-o','broken'],True);stderr=(out/'syntax.stderr').read_bytes();record('syntax',code not in (0,None) and not stdout and b'error[E0101]' in stderr and b'broken.mio' in stderr and not (project/'broken').exists())
code,stdout=run('missing-override',[mio,'build','hello.mio','--bunko-root',str(sandbox/'missing-bunko'),'-o','missing'],True);record('explicit-override-no-fallback',code not in (0,None) and not (project/'missing').exists())
code,_=run('missing-option',[mio,'build','hello.mio','-o'],True);record('missing-option',code==2)
code,_=run('unknown-command',[mio,'unknown'],True);record('unknown-command',code==2)
before=set(Path('/private/tmp').glob('mio-run-*'))
code,actual=run('run-hello',[mio,'run','hello.mio'],'run');record('run-shared-core',code==0 and actual==b'9\n')
(project/'args.mio').write_text('yobu "kiso/os"; kaku args = os.arguments(); chant(len(args)); kaku at = 1; aida (at < len(args)) { chant(args[at]); at = at + 1; } os.exit(7);\n')
code,actual=run('run-arguments',[mio,'run','args.mio','--','alpha','中文 空格','','--flag'],'run');expected=b'5\nalpha\n'+'中文 空格\n'.encode()+b'\n--flag\n';record('run-args-and-exit',code==7 and actual==expected)
after=set(Path('/private/tmp').glob('mio-run-*'));record('run-temporary-cleanup',not (after-before),new_directories=[str(x) for x in after-before])
code,actual=run('exec-hello',[mio,'exec','hello.mochi'],'run');record('exec-native-aot',code==0 and actual==b'9\n')
code,_=run('emit-args',[mio,'build','args.mio','--emit=mochi','-o','args.mochi'],True);record('emit-os-mochi',code==0)
code,actual=run('exec-arguments',[mio,'exec','args.mochi','--','alpha','中文 空格','','--flag'],'run');record('exec-args-and-exit',code==7 and actual==expected)
code,actual=run('disasm-hello',[mio,'disasm','hello.mochi'],True);record('disasm-native-decoder',code==0 and b'Globals:' in actual and b'OpMath' in actual and b'Function ' in actual)
reference=root/'build/gofree-evidence/GF1/mio-reference'
if a.legacy_ir:
 legacy=a.legacy_ir.resolve().read_bytes();assert legacy[:7]==b'MOCHI\x00\x0e';legacy_path=project/'legacy-v14.mochi';legacy_path.write_bytes(legacy)
 nc,native_text=run('native-legacy-disasm',[mio,'disasm',legacy_path],True);rc,reference_text=run('reference-disasm',[reference,'disasm',legacy_path]);record('disasm-core-format-compatibility',nc==rc==0 and native_text==reference_text,fixture_sha256=hashlib.sha256(legacy).hexdigest(),scope='frozen v14 module; reference cannot consume v15/v16')
else:record('disasm-core-format-compatibility',False,reason='supply --legacy-ir with a frozen native v14 fixture; historical reference cannot decode v15/v16')
(project/'typed.mio').write_text('kata Record { value: int64; } kaku record=Record {value:5}; chant(record.value);\n')
code,_=run('emit-typed',[mio,'build','typed.mio','--emit=mochi','-o','typed.mochi'],True);typed=project/'typed.mochi';record('emit-v16-declared-field',code==0 and typed.is_file() and typed.read_bytes()[:7]==b'MOCHI\x00\x10')
code,text=run('disasm-typed',[mio,'disasm','typed.mochi'],True);record('disasm-type-constraint',code==0 and b'OpTypeConstraint 1' in text)
code,text=run('exec-typed',[mio,'exec','typed.mochi'],'run');record('exec-v16-declared-field',code==0 and text==b'5\n')
v15=a.typed_v15_ir.resolve().read_bytes();assert v15[:7]==b'MOCHI\x00\x0f';(project/'legacy-v15.mochi').write_bytes(v15)
code,text=run('exec-frozen-v15',[mio,'exec','legacy-v15.mochi'],'run');record('exec-frozen-v15',code==0 and text==b'5\n',fixture_sha256=hashlib.sha256(v15).hexdigest())
code,text=run('disasm-frozen-v15',[mio,'disasm','legacy-v15.mochi'],True);record('disasm-frozen-v15',code==0 and b'OpTypeConstraint 1' in text)
(project/'bad.mochi').write_bytes(b'bad')
for command in ['exec','disasm']:
 code,actual=run(command+'-invalid',[mio,command,'bad.mochi'],'run' if command=='exec' else True);record(command+'-invalid-input',code==1 and not actual and b'E_IR' in (out/(command+'-invalid.stderr')).read_bytes())
raise SystemExit(0 if all(x['status']=='PASS' for x in results) else 1)
