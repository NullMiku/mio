#!/usr/bin/env python3
"""Isolated native frontend-plan / updated native test-image linker audit."""
import argparse,json,os,subprocess,signal,time,hashlib,struct
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--linker',type=Path,required=True);p.add_argument('--plan',type=Path,required=True);p.add_argument('--test',action='append',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);linker=a.linker.resolve();plan=a.plan.resolve();commands=[];results=[]
def run(name,argv,cwd,pass_fds=()):
 start=time.monotonic()
 with (out/(name+'.stdout')).open('wb') as stdout,(out/(name+'.stderr')).open('wb') as stderr:
  proc=subprocess.Popen(list(map(str,argv)),cwd=cwd,env={'PATH':''},stdout=stdout,stderr=stderr,pass_fds=pass_fds,start_new_session=True)
  try:code=proc.wait(timeout=180)
  except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait();code=None
 commands.append({'name':name,'argv':list(map(str,argv)),'cwd':str(cwd),'exit':code,'wall_seconds':time.monotonic()-start});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');return code
for i,name in enumerate(a.test):
 case=out/str(i);case.mkdir();image=case/'test.native';(case/'input.config').write_text(str(plan));(case/'output.config').write_text(str(image));(case/'test.config').write_text(name)
 policy=case/'linker.sb';policy.write_text('(version 1)(allow default)(deny network*)(deny process-fork)(deny process-exec)(allow process-exec (literal '+json.dumps(str(linker))+'))\n');code=run(str(i)+'-link',['/usr/bin/sandbox-exec','-f',policy,linker],case);ok=code==0 and image.is_file();status=None;complete=False;messages=[]
 if ok:
  image.chmod(0o700);verified=run(str(i)+'-verify',['/usr/bin/codesign','--verify','--strict',image],case);runtime=case/'runtime.sb';runtime.write_text('(version 1)(allow default)(deny network*)(deny process-fork)(deny process-exec)(allow process-exec (literal '+json.dumps(str(image))+'))\n');fd=os.open(case/'records',os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
  assert fd==3,'private audit expected fd3 available'
  try:status=run(str(i)+'-test',['/usr/bin/sandbox-exec','-f',runtime,image],case,(fd,))
  finally:os.close(fd)
  records=(case/'records').read_bytes();at=0;valid=True
  while at<len(records):
   if len(records)-at<8:valid=False;break
   length=struct.unpack_from('<Q',records,at)[0];at+=8
   if length==2**64-1:complete=at==len(records);break
   if length>len(records)-at:valid=False;break
   messages.append(records[at:at+length].hex());at+=length
  ok=verified==status==0 and valid and complete and not messages
 results.append({'test':name,'status':'PASS' if ok else 'FAIL','link_exit':code,'test_exit':status,'complete':complete,'failure_messages_hex':messages,'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest() if image.is_file() else None});(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(name,results[-1]['status'],flush=True)
(out/'provenance.json').write_text(json.dumps({'linker':str(linker),'linker_sha256':hashlib.sha256(linker.read_bytes()).hexdigest(),'plan':str(plan),'plan_sha256':hashlib.sha256(plan.read_bytes()).hexdigest(),'scope':'native developer linker evidence; unified CLI must still be rebuilt and revalidated'},indent=2)+'\n');raise SystemExit(0 if all(x['status']=='PASS' for x in results) else 1)
