#!/usr/bin/env python3
"""Native test planning, signed entry images, packet recording and child isolation audit."""
import argparse,json,os,shutil,signal,struct,subprocess,time,hashlib
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--compiler',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);compiler=a.compiler.resolve();commands=[]
def run(label,argv,stdin=None,timeout=180):
 with (out/(label+'.stdout')).open('wb') as stdout,(out/(label+'.stderr')).open('wb') as stderr:
  start=time.monotonic();proc=subprocess.Popen(['/usr/bin/time','-l',*map(str,argv)],cwd=out,env={'PATH':''},stdin=subprocess.PIPE,stdout=stdout,stderr=stderr,start_new_session=True)
  try:proc.communicate(stdin,timeout=timeout);code=proc.returncode
  except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.communicate();code=None
 commands.append({'label':label,'argv':list(map(str,argv)),'cwd':str(out),'environment':{'PATH':''},'exit_code':code,'wall_seconds':time.monotonic()-start});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');return code
pkg=out/'pkg';pkg.mkdir();(pkg/'dep').mkdir();(pkg/'dep/helper.mio').write_text('koukai waza test_pass() -> unit { chant("wrong dependency test"); }\n')
(pkg/'helper.mio').write_text('waza hidden() -> int64 { kaesu 42; }\n')
(pkg/'a_test.mio').write_text('''yobu "kiso/testing"; yobu "kiso/string"; yobu "kiso/fs"; yobu "./dep";
waza test_pass() { testing.expect(hidden() == 42, "private helper"); }
waza test_fail() -> unit {
 testing.fail("first\\nline"); kaku bytes: []uint8 = [uint8(97),uint8(0),uint8(98),uint8(10),uint8(99)];
 kaku text = string.from_utf8(bytes); moshi (text != mu) { testing.fail(text); }
}
waza test_bounds() -> unit { kaku values = [1]; values[2]; }
waza test_limit() -> unit { aida (hai) {} }
waza test_blocking() -> unit { kaku opened = fs.open_read("BLOCKING_FIFO_PATH"); }
waza test_after() -> unit { testing.expect(hai, "after failure"); }
''')
os.mkfifo(pkg/'blocking.pipe')
(pkg/'a_test.mio').write_text((pkg/'a_test.mio').read_text().replace('BLOCKING_FIFO_PATH',str(pkg/'blocking.pipe')))
invalid=out/'invalid';invalid.mkdir();(invalid/'bad_test.mio').write_text('waza test_bad(value: int64) -> unit {}\n')
empty=out/'empty';empty.mkdir()
# Only this audit driver embeds paths. Product/test APIs accept explicit roots.
lit=lambda x:json.dumps(str(x),ensure_ascii=False)
src=out/'driver.mio';src.write_text('''yobu "kiso/os"; yobu "kiso/fs"; yobu "kiso/string"; yobu "kiso/convert"; yobu "selfhost/tester";
waza fail(message: string) -> unit { fs.write_all("/dev/stderr", string.to_bytes(message)); os.exit(1); }
waza run() -> unit {
 kaku planned = tester.plan('''+lit(pkg)+''', ".", '''+lit(root/'bunko')+''');
 moshi (planned.error != "") { fail(planned.error); kaesu; }
 chant(len(planned.tests)); kaku at = 0;
 aida (at < len(planned.tests)) {
  kaku item = planned.tests[at]; kaku compiled = tester.image(planned, ".", item.name);
  moshi (compiled.error != "") { fail(compiled.error); kaesu; }
  kaku prefix = string.concat('''+lit(out/'test-')+''', convert.format_int(at));
  kaku program = string.concat(prefix, ".native"); kaku written = fs.write_all(program, compiled.bytes);
  moshi (written.error != mu || os.chmod(program, 493) != 0) { fail("write native test"); kaesu; }
  kaku status = os.spawn_test(program, [program], string.concat(prefix, ".stdout"), string.concat(prefix, ".stderr"), string.concat(prefix, ".records"), 1);
  chant(string.concat(item.name, string.concat("=", convert.format_int(status)))); at = at + 1;
 }
 kaku bad = tester.plan('''+lit(invalid)+''', ".", '''+lit(root/'bunko')+'''); chant(string.has_prefix(bad.error, "E0601"));
 kaku none = tester.plan('''+lit(empty)+''', ".", '''+lit(root/'bunko')+'''); chant(none.error == "" && len(none.tests) == 0);
}
run();
''')
policy=out/'compiler.sb';policy.write_text('(version 1)(allow default)(deny process-fork)(deny process-exec)(allow process-exec (literal '+lit(compiler)+'))\n');unsigned=out/'driver.unsigned';request=('\n'.join(map(str,[root,src,root/'bunko',unsigned]))+'\n').encode();(out/'compile.stdin').write_bytes(request);assert run('compile',['/usr/bin/sandbox-exec','-f',policy,compiler],request)==0
program=out/'driver.native';shutil.copy2(unsigned,program);program.chmod(0o755);assert run('development-seed-sign',['/usr/bin/codesign','--force','--sign','-',program])==0;assert run('development-seed-verify',['/usr/bin/codesign','--verify','--strict',program])==0
runtime=out/'runtime.sb';runtime.write_text('(version 1)(allow default)(deny network*)(deny process-exec)(allow process-exec (literal '+lit(program)+'))'+''.join('(allow process-exec (literal '+lit(out/f'test-{i}.native')+'))' for i in range(6))+'\n');exit=run('driver-run',['/usr/bin/sandbox-exec','-f',runtime,program],timeout=20);actual=(out/'driver-run.stdout').read_bytes();expected=b'6\ntest_pass=0\ntest_fail=1\ntest_bounds=1\ntest_limit=RESOURCE\ntest_blocking=142\ntest_after=0\nhai\nhai\n';normalized=actual
for resource_status in [137,142,152]:normalized=normalized.replace(('test_limit='+str(resource_status)+'\n').encode(),b'test_limit=RESOURCE\n')
results=[{'case':'native-test-plan-isolation-completion','status':'PASS' if exit==0 and normalized==expected else 'FAIL','exit':exit,'stdout':actual.decode(errors='replace')}]
for i in range(6):
 image=out/f'test-{i}.native'
 if not image.exists():continue
 verified=run(f'test-{i}-verify',['/usr/bin/codesign','--verify','--strict',image]);records=(out/f'test-{i}.records').read_bytes() if (out/f'test-{i}.records').exists() else b'';messages=[];done=False;at=0;valid=True
 while at<len(records):
  if at+8>len(records):valid=False;break
  length=struct.unpack_from('<Q',records,at)[0];at+=8
  if length==2**64-1:done=True;valid=at==len(records);break
  if length>len(records)-at:valid=False;break
  messages.append(records[at:at+length]);at+=length
 expected_messages=[b'first\nline',b'a\0b\nc'] if i==1 else []
 ok=verified==0 and valid and done==(i in (0,1,5)) and messages==expected_messages
 results.append({'case':f'test-{i}-signature-packets','status':'PASS' if ok else 'FAIL','completion':done,'messages_hex':[x.hex() for x in messages],'signed_by':'Mio only'})
(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2),flush=True)
manifest=[{'path':str(x.relative_to(root)),'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in sorted(set(root.glob('bunko/**/*.mio'))|set(root.glob('selfhost/**/*.mio')))];(out/'source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');raise SystemExit(0 if all(x['status']=='PASS' for x in results) else 1)
