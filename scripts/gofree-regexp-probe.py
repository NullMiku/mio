#!/usr/bin/env python3
"""Isolated development audit: pure Mio native regexp against Go RE2 reference.
Go/Python are audit dependencies only, never production compiler dependencies.
"""
import argparse,json,os,shutil,signal,subprocess,time,hashlib,random
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--compiler',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--extra-cases',type=Path);a=p.parse_args();root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);compiler=a.compiler.resolve();commands=[]
def run(label,argv,stdin=None,timeout=180,env=None):
 with (out/(label+'.stdout')).open('wb') as stdout,(out/(label+'.stderr')).open('wb') as stderr:
  start=time.monotonic();proc=subprocess.Popen(list(map(str,argv)),cwd=out,env=env or {'PATH':''},stdin=subprocess.PIPE,stdout=stdout,stderr=stderr,start_new_session=True)
  try:proc.communicate(stdin,timeout=timeout);code=proc.returncode
  except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.communicate();code=None
 commands.append({'label':label,'argv':list(map(str,argv)),'exit_code':code,'wall_seconds':time.monotonic()-start});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');return code
patterns=['','a','abc','a|bc','(ab|a)*c','a*','a+','a?','a{0}','a{2,4}','a{2,}','^a$','(?m)^a$','(?s)a.b','a.b','[a-z]+','[^a-z]','[[:alpha:]]','[[:^digit:]]','[a\\d-]','\\d+','\\D','\\w','\\W','\\s','\\S','\\bfoo\\b','\\Bfoo','\\Aabc\\z','(?i)hello','(?i)[a-z]','(?i)[^a-z]','(?i)k','(?i)s','(?:a|b)+','(?P<name>a)','(?<name>a)','(?i:a)b','(?i)a(?-i)b','a+?','a{1,2}?','\\Q.*+?\\E','\\Qab\\E+','\\x{1f600}','\\x41','\\101','\\0','\\12','[\\x00-\\x7f]','[a-]','[]a]','[^]a]','[\\d-a]','(?U)a*','a{01}','{1}','a{1}{2}','(?i-)a','a{,2}','a{1,2','a{1001}','a{3,2}','a**','*a','(','[','\\','\\1','\\b','[\\b]','\\q','a)']
patterns += ['\\p{Han}+','\\pL','\\PL','\\p{^Lu}','\\P{^Lu}','\\p{Greek}','\\p{Latin}','\\p{Letter}','\\p{lowercase_letter}','\\p{Assigned}','\\p{ASCII}','(?i)é','(?i)Σ','(?i)å','(?i)[Α-Ω]','(?i)\\p{Lu}','(?i)\\P{Lu}','[\\p{Han}a-z]','[\\P{Han}]','(?i)[\\W]','(?i)[[:^lower:]]','\\p{Invalid}','\\p{}','\\p{','\\p']
texts=['é','É','σ','Σ','ς','Å','å','漢','字','α','Ω','ω','\u0378','\ue000','\U0001f600','' ,'a','b','aa','ab','abc','bc','c','aaaaac','xabcx','a\nb','a\n','hello','HELLO','foox','foo','xfoo',' foo ','3',' ','\t','\v','\n','_','-','a-','😀','中文','K','ſ','\0','.*+?','abab']
cases=[{'pattern':pat,'text':txt} for pat in patterns for txt in texts]
if a.extra_cases:cases += json.loads(a.extra_cases.read_text())
(out/'cases.json').write_text(json.dumps(cases,ensure_ascii=False))
go=out/'reference.go';go.write_text('''package main
import("encoding/json";"os";"fmt";"regexp")
func main(){var cases []struct{Pattern string;Text string};if json.NewDecoder(os.Stdin).Decode(&cases)!=nil {os.Exit(2)};for _,c:=range cases{r,e:=regexp.Compile(c.Pattern);if e!=nil{fmt.Println("E")}else if r.MatchString(c.Text){fmt.Println("T")}else{fmt.Println("F")}}}
''')
gobin=shutil.which('go');assert gobin,'isolated Go reference unavailable';assert run('reference',[gobin,'run',go],(out/'cases.json').read_bytes(),env=os.environ.copy())==0
src=out/'driver.mio';src.write_text('''yobu "kiso/regexp"; yobu "kiso/fs"; yobu "kiso/string"; yobu "kiso/encoding/json"; yobu "kiso/math";
waza run() -> unit { kaku input=fs.read_all("cases.json"); kaku doc=json.parse(input.data); moshi(doc.error!=""){math.fail(doc.error);kaesu;} kaku index=0; aida(index<len(doc.values[doc.root].children)){ kaku at=doc.values[doc.root].children[index]; kaku pat=json.member(doc,at,"pattern"); kaku txt=json.member(doc,at,"text"); kaku re=regexp.compile(doc.values[pat].text); moshi(re.error!=""){chant("E");} sore{moshi(regexp.matches(re,doc.values[txt].text)){chant("T");}sore{chant("F");}} index=index+1; } } run();
''')
policy=out/'compiler.sb';policy.write_text('(version 1)(allow default)(deny process-fork)(deny process-exec)(allow process-exec (literal '+json.dumps(str(compiler))+'))\n');unsigned=out/'driver.unsigned';data=('\n'.join(map(str,[root,src,root/'bunko',unsigned]))+'\n').encode();(out/'compile.stdin').write_bytes(data)
assert run('compile',['/usr/bin/sandbox-exec','-f',policy,compiler],data)==0
program=out/'driver.native';shutil.copy2(unsigned,program);program.chmod(0o755);assert run('development-sign',['/usr/bin/codesign','--force','--sign','-',program])==0;assert run('verify',['/usr/bin/codesign','--verify','--strict',program])==0
runtime=out/'runtime.sb';runtime.write_text('(version 1)(allow default)(deny network*)(deny process-fork)(deny process-exec)(allow process-exec (literal '+json.dumps(str(program))+'))\n');code=run('native',['/usr/bin/sandbox-exec','-f',runtime,program])
expected=(out/'reference.stdout').read_text().splitlines();actual=(out/'native.stdout').read_text().splitlines();results=[]
for i,c in enumerate(cases):
 observed=actual[i] if i<len(actual) else None;results.append({**c,'expected':expected[i],'actual':observed,'status':'PASS' if code==0 and observed==expected[i] else 'FAIL'})
(out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n');(out/'summary.json').write_text(json.dumps({'total':len(results),'passed':sum(x['status']=='PASS' for x in results),'exit':code},indent=2)+'\n')
manifest=[{'path':str(x.relative_to(root)),'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in sorted(set(root.glob('bunko/**/*.mio'))|set(root.glob('selfhost/**/*.mio')))];(out/'source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print((out/'summary.json').read_text(),flush=True);raise SystemExit(0 if all(x['status']=='PASS' for x in results) else 1)
