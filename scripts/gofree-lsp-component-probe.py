#!/usr/bin/env python3
"""Build a development LSP-only Mio component with the normal native CLI.
This accelerates isolated service debugging; integrated CLI revalidation remains
mandatory. Python controls the audit only, never a formal compiler stage.
"""
import argparse,hashlib,json,os,signal,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--timeout',type=int,default=600);a=p.parse_args()
root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);cli=a.candidate.resolve()
source=out/'main.mio';source.write_text('yobu "kiso/os";yobu "selfhost/lsp/rpc";os.exit(rpc.command(os.arguments()));\n')
def manifest():
 return [{'path':str(x.relative_to(root)),'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in sorted([*root.glob('bunko/**/*.mio'),*root.glob('selfhost/**/*.mio')])]
before=manifest();(out/'source-before.json').write_text(json.dumps(before,indent=2)+'\n')
policy=out/'compiler.sb';policy.write_text('(version 1)(allow default)(deny network*)(deny process-fork)(deny process-exec)(allow process-exec (literal '+json.dumps(str(cli))+'))\n')
program=out/'lsp.native';argv=['/usr/bin/sandbox-exec','-f',str(policy),str(cli),'build',str(source),'--bunko-root',str(root/'bunko'),'-o',str(program)];(out/'argv.json').write_text(json.dumps(argv,indent=2)+'\n');start=time.monotonic()
with (out/'stdout').open('wb') as stdout,(out/'stderr').open('wb') as stderr:
 proc=subprocess.Popen(argv,cwd=root,env={'PATH':''},stdout=stdout,stderr=stderr,start_new_session=True)
 try:code=proc.wait(timeout=a.timeout)
 except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait();code=None
after=manifest();(out/'source-after.json').write_text(json.dumps(after,indent=2)+'\n')
verification=None
if code==0 and program.exists():
 with (out/'verify.stdout').open('wb') as stdout,(out/'verify.stderr').open('wb') as stderr:verification=subprocess.run(['/usr/bin/codesign','--verify','--strict',str(program)],stdout=stdout,stderr=stderr).returncode
result={'status':'PASS' if code==0 and before==after and verification==0 else 'FAIL','exit':code,'source_unchanged':before==after,'verify_exit':verification,'wall_seconds':time.monotonic()-start,'scope':__doc__,'compiler_sha256':hashlib.sha256(cli.read_bytes()).hexdigest(),'program_sha256':hashlib.sha256(program.read_bytes()).hexdigest() if program.exists() else None}
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True);raise SystemExit(0 if result['status']=='PASS' else 1)
