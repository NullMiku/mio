#!/usr/bin/env python3
"""Isolated native source/IR test of non-nil facts and captured-Cell mutation."""
import argparse,json,hashlib,os,signal,subprocess,time,struct
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--frontend',type=Path,required=True);p.add_argument('--driver',action='store_true');p.add_argument('--linker',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);frontend=a.frontend.resolve();linker=a.linker.resolve();commands=[];results=[]
def policy(path,program):path.write_text('(version 1)(allow default)(deny network*)(deny process-fork)(deny process-exec)(allow process-exec (literal '+json.dumps(str(program))+'))\n')
def run(name,argv,cwd,pass_fds=(),stdin=None):
 start=time.monotonic()
 with (out/(name+'.stdout')).open('wb') as stdout,(out/(name+'.stderr')).open('wb') as stderr:
  proc=subprocess.Popen(list(map(str,argv)),cwd=cwd,env={'PATH':''},stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,stdout=stdout,stderr=stderr,pass_fds=pass_fds,start_new_session=True)
  try:proc.communicate(stdin,timeout=120);code=proc.returncode
  except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait();code=None
 commands.append({'name':name,'argv':list(map(str,argv)),'cwd':str(cwd),'exit':code,'wall_seconds':time.monotonic()-start});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');return code
prefix='''yobu "kiso/testing"; kata Item { key: string; }
waza find(items: []Item) -> Item? { moshi(len(items)>0){kaesu items[0];}kaesu mu; }
waza touch() -> unit { testing.expect(hai,"unrelated call"); }
waza apply(callback: () -> unit) -> unit { callback(); }
'''
cases=[('uncaptured-optional-record',prefix+'''waza test_case() -> unit { kaku item=find([Item {key:"alive"}]);moshi(item==mu){testing.fail("missing");kaesu;}touch();testing.expect(item.key=="alive","record non-nil survives call");touch();testing.expect(item.key=="alive","record survives repeated calls"); }''',0,True),('captured-record-null-runtime',prefix+'''waza test_case() -> unit { kaku item: Item?=Item {key:"alive"};kaku clear=waza () -> unit {item=mu;};moshi(item==mu){testing.fail("missing");kaesu;}apply(clear);chant(item.key); }''',1,False),('captured-record-recheck',prefix+'''waza test_case() -> unit { kaku item: Item?=Item {key:"alive"};kaku clear=waza () -> unit {item=mu;};moshi(item==mu){testing.fail("missing");kaesu;}apply(clear);moshi(item==mu){testing.expect(hai,"rechecked nil");kaesu;}testing.fail("captured write lost"); }''',0,True),('captured-record-replace',prefix+'''waza test_case() -> unit { kaku item: Item?=Item {key:"alive"};kaku replace=waza () -> unit {item=Item {key:"changed"};};moshi(item==mu){testing.fail("missing");kaesu;}apply(replace);testing.expect(item.key=="changed","shared Cell value reloaded"); }''',0,True),('uncaptured-scalar-zero',prefix+'''waza maybe() -> int64? { kaesu 0; } waza test_case() -> unit {kaku value=maybe();moshi(value==mu){testing.fail("zero is not nil");kaesu;}touch();testing.expect(value+1==1,"unboxed zero survives direct call");}''',0,True),('captured-scalar-null-runtime',prefix+'''waza test_case() -> unit {kaku value:int64?=0;kaku clear=waza () -> unit {value=mu;};moshi(value==mu){testing.fail("zero is not nil");kaesu;}apply(clear);chant(value+1);}''',1,False)]
for i,(name,source,expected,expected_complete) in enumerate(cases):
 case=out/name;case.mkdir();src=case/'main.mio';src.write_text(source+'\n');ir=case/'input.mochi';image=case/'test.native';fp=case/'frontend.sb';lp=case/'linker.sb';policy(fp,frontend);policy(lp,linker)
 request=('\n'.join([str(case),str(src),'',str(ir)])+'\n').encode() if a.driver else None
 if request is not None:(case/'frontend.stdin').write_bytes(request)
 emitted=run(name+'-frontend',['/usr/bin/sandbox-exec','-f',fp,frontend,*([] if a.driver else ['build',src,'--emit=mochi','-o',ir])],case,stdin=request);linked=None;verified=None;status=None;complete=False;messages=[]
 if emitted==0 and ir.exists():
  (case/'input.config').write_text(str(ir));(case/'output.config').write_text(str(image));(case/'test.config').write_text('test_case');linked=run(name+'-link',['/usr/bin/sandbox-exec','-f',lp,linker],case)
 if linked==0 and image.exists():
  image.chmod(0o700);verified=run(name+'-verify',['/usr/bin/codesign','--verify','--strict',image],case);rp=case/'runtime.sb';policy(rp,image);fd=os.open(case/'records',os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600);assert fd==3
  try:status=run(name+'-run',['/usr/bin/sandbox-exec','-f',rp,image],case,(fd,))
  finally:os.close(fd)
  data=(case/'records').read_bytes();at=0
  while at+8<=len(data):
   length=struct.unpack_from('<Q',data,at)[0];at+=8
   if length==2**64-1:complete=at==len(data);break
   if length>len(data)-at:messages.append('INVALID');break
   messages.append(data[at:at+length].hex());at+=length
 ok=emitted==linked==verified==0 and status==expected and complete==expected_complete and not messages
 results.append({'case':name,'status':'PASS' if ok else 'FAIL','frontend':emitted,'linker':linked,'run_exit':status,'expected_exit':expected,'complete':complete,'expected_complete':expected_complete,'failures_hex':messages});(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(name,results[-1]['status'],flush=True)
(out/'provenance.json').write_text(json.dumps({'frontend':str(frontend),'frontend_sha256':hashlib.sha256(frontend.read_bytes()).hexdigest(),'linker':str(linker),'linker_sha256':hashlib.sha256(linker.read_bytes()).hexdigest(),'scope':'all source and backend stages are native Mio; developer transport only; unified CLI revalidation remains required'},indent=2)+'\n');raise SystemExit(0 if all(x['status']=='PASS' for x in results) else 1)
