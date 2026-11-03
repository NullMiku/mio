#!/usr/bin/env python3
"""Final unified CLI source regression against unchanged accepted GF2 fixtures.
Python is an isolated audit controller. A separately identified Mio audit witness,
compiled and signed by the same candidate from the same frozen compiler core,
exercises existing target-GCStress/heap APIs without adding product commands.
"""
import argparse,hashlib,json,os,shutil,signal,subprocess,tempfile,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--gc-witness',action='store_true');a=p.parse_args()
root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);candidate=a.candidate.resolve();work=Path(tempfile.mkdtemp(prefix='mio-final-source-',dir='/tmp')).resolve();cli=work/'mio';shutil.copy2(candidate,cli);frozen=root/'build/gofree-evidence/GF2/probe-array-r1';commands=[];results=[]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def manifest():return [{'path':str(x.relative_to(root)),'sha256':sha(x)} for x in sorted([*root.glob('bunko/**/*.mio'),*root.glob('selfhost/**/*.mio')])]
before=manifest();(out/'source-before.json').write_text(json.dumps(before,indent=2)+'\n')
def policy(folder,label,program,deny_repo=True,deny_mio=False):
 f=folder/(label+'.sb');s='(version 1)(allow default)(deny network*)(deny process-fork)(deny process-exec)(allow process-exec (literal '+json.dumps(str(program))+'))'
 if deny_repo:s+='(deny file-read* (subpath '+json.dumps(str(root))+'))(deny file-read* (subpath "/Volumes/Sector0/AppData/Mio/mio"))'
 s+='(allow file-read* (literal '+json.dumps(str(program))+'))(allow file-read* (subpath '+json.dumps(str(folder))+'))'
 if deny_mio:s+='(deny file-read* (literal '+json.dumps(str(cli))+'))'
 f.write_text(s+'\n');return ['/usr/bin/sandbox-exec','-f',str(f),str(program)]
def run(folder,label,argv,timeout=180,cwd=None):
 start=time.monotonic()
 with (folder/(label+'.stdout')).open('wb') as stdout,(folder/(label+'.stderr')).open('wb') as stderr:
  proc=subprocess.Popen(list(map(str,argv)),cwd=cwd or folder,env={'PATH':'','MIO_BUNKO':''},stdout=stdout,stderr=stderr,start_new_session=True)
  try:code=proc.wait(timeout=timeout)
  except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait();code=None
 commands.append({'label':label,'argv':list(map(str,argv)),'cwd':str(cwd or folder),'exit':code,'seconds':time.monotonic()-start});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');return code,(folder/(label+'.stdout')).read_bytes()
def record(name,ok,**data):
 results.append({'case':name,'status':'PASS' if ok else 'FAIL',**data});(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(name,results[-1]['status'],flush=True)
corpus=[]
for previous in json.loads((frozen/'results.json').read_text()):
 if previous.get('gc_stress') is False:
  name=str(previous['case']);old=frozen/(name+'-normal');source=old/'case.mio';folder=work/name;folder.mkdir();shutil.copy2(source,folder/'case.mio');expected=(frozen/(name+'-normal-native.stdout')).read_bytes()
  corpus.append({'name':name,'folder':str(folder),'source':str(folder/'case.mio'),'heap':8388608,'stress':True,'expected_exit':previous['native_exit'],'expected_hex':expected.hex(),'source_sha256':sha(source)})
for name,heap,stress,expected_exit in [('nullable-array-make',8388608,True,0),('native-fs-map-offset',8388608,True,0),('native-fs',8388608,True,0),('los-alias',8388608,True,0),('oom',65536,False,2)]:
 source=frozen/name/'case.mio';folder=work/name;folder.mkdir();shutil.copy2(source,folder/'case.mio');expected=(frozen/(name+'-native.stdout')).read_bytes()
 corpus.append({'name':name,'folder':str(folder),'source':str(folder/'case.mio'),'heap':heap,'stress':stress,'expected_exit':expected_exit,'expected_hex':expected.hex(),'source_sha256':sha(source)})
path_case=work/'native-path-roots';path_case.mkdir();path_source=path_case/'case.mio'
path_source.write_text('yobu "kiso/os";yobu "kiso/fs";yobu "kiso/array";yobu "kiso/string";kaku at=0;kaku completed=0;aida(at<64){kaku current=os.canonical_path(".");kaku values=array.make[uint8](1024,uint8(at));moshi(values[0]!=uint8(at)){os.exit(1);}moshi(current!=mu){moshi(len(string.to_bytes(current))>0){completed=completed+1;}}at=at+1;}chant(completed);chant(fs.is_character_device("/dev/null"));\n')
corpus.append({'name':'native-path-roots','folder':str(path_case),'source':str(path_source),'heap':8388608,'stress':True,'expected_exit':0,'expected_hex':b'64\nhai\n'.hex(),'source_sha256':sha(path_source)})
multi=work/'multi';multi.mkdir();shutil.copytree(frozen/'multi/sample',multi/'sample')
tree=[{'path':str(x.relative_to(multi)),'sha256':sha(x)} for x in sorted(multi.rglob('*.mio'))]
corpus.append({'name':'multi-module','folder':str(multi),'source':str(multi/'sample/app'),'heap':8388608,'stress':True,'expected_exit':0,'expected_hex':(frozen/'multi-native.stdout').read_bytes().hex(),'source_sha256':hashlib.sha256(json.dumps(tree,sort_keys=True).encode()).hexdigest(),'source_tree':tree})
(out/'corpus.json').write_text(json.dumps(corpus,indent=2)+'\n')
for c in corpus:
 if c['name']=='oom':continue
 folder=Path(c['folder']);app=folder/'normal.native';code,_=run(folder,'build',policy(folder,'compile',cli)+['build',c['source'],'-o',str(app)])
 executed=None;actual=None;verify=None
 if code==0 and app.exists():
  verify,_=run(folder,'verify',['/usr/bin/codesign','--verify','--strict',app]);executed,actual=run(folder,'native',policy(folder,'runtime',app,deny_mio=True))
 ok=code==0 and verify==0 and executed==c['expected_exit'] and actual==bytes.fromhex(c['expected_hex']) and not list(folder.glob('*.mochi'))
 record(c['name']+'-normal-cli',ok,build_exit=code,native_exit=executed,source_sha256=c['source_sha256'],application_sha256=sha(app) if app.exists() else None)
for name,source,expected in [('syntax','kaku = ;','E0101'),('type','kaku value: int64="wrong";','E0301'),('resolve','chant(missing);','E0201')]:
 folder=work/('invalid-'+name);folder.mkdir();(folder/'case.mio').write_text(source);app=folder/'invalid.native';code,_=run(folder,'invalid',policy(folder,'compile',cli)+['build',str(folder/'case.mio'),'--format=json','-o',str(app)])
 diagnostic=None
 try:diagnostic=json.loads((folder/'invalid.stderr').read_text()).get('code')
 except (ValueError,AttributeError):pass
 record('invalid-'+name,code==1 and diagnostic==expected and not app.exists(),exit=code,diagnostic=diagnostic)
if a.gc_witness:
 folder=out/'gc-witness';folder.mkdir();source=folder/'main.mio';source.write_text('''yobu "kiso/fs";yobu "kiso/os";yobu "kiso/string";yobu "kiso/encoding/json";yobu "kiso/aot/sign";yobu "selfhost/pipeline";
waza run() -> unit {
 kaku loaded=fs.read_all("manifest.json");kaku document=json.parse(loaded.data);moshi(loaded.error!=mu || document.error!=""){os.exit(2);kaesu;}
 kaku output=string.new_builder();string.write_string(output,"[");kaku at=0;
 aida(at<len(document.values[document.root].children)){
  kaku row=document.values[document.root].children[at];kaku root=json.text(document,json.member(document,row,"folder"));kaku input=json.text(document,json.member(document,row,"source"));kaku target=json.text(document,json.member(document,row,"target"));kaku heap=json.integer(document,json.member(document,row,"heap"));kaku stress=json.text(document,json.member(document,row,"stress"))=="true";
  moshi(heap==mu){os.exit(2);kaesu;}kaku compiled=pipeline.build_source_with_options(root,input,"",heap,stress);kaku error=compiled.error;
  moshi(error==""){kaku signed=sign.adhoc(compiled.bytes);error=signed.error;moshi(error==""){moshi(fs.write_all(target,signed.bytes).error!=mu || os.chmod(target,493)!=0){error="cannot publish audit program";}}}
  moshi(at>0){string.write_string(output,",");}string.write_string(output,"{\\"name\\":");string.write_string(output,json.quote(json.text(document,json.member(document,row,"name"))));string.write_string(output,",\\"error\\":");string.write_string(output,json.quote(error));string.write_string(output,"}");at=at+1;
 }
 string.write_string(output,"]");moshi(fs.write_all("build-results.json",string.to_bytes(string.builder_string(output))).error!=mu){os.exit(2);}
}run();
''')
 witness=folder/'witness.native';code,_=run(folder,'witness-build',policy(folder,'witness-compile',cli,deny_repo=False)+['build',str(source),'--bunko-root',str(root/'bunko'),'-o',str(witness)],timeout=1800,cwd=root)
 witness_cases=[dict(c,target=str(Path(c['folder'])/'gc.native')) for c in corpus];(folder/'manifest.json').write_text(json.dumps(witness_cases,ensure_ascii=False)+'\n')
 build_exit=None
 if code==0:
  build_exit,_=run(folder,'witness-execute',policy(folder,'witness-runtime',witness),timeout=900)
 record('same-candidate-native-gc-witness-build',code==0 and build_exit==0,build_exit=code,execute_exit=build_exit,witness_sha256=sha(witness) if witness.exists() else None,witness_source_sha256=sha(source),scope='Mio audit witness, same final compiler core and candidate; never an installed compiler dependency')
 built=[]
 if build_exit==0:built=json.loads((folder/'build-results.json').read_text())
 for c in witness_cases:
  target=Path(c['target']);matching=next((x for x in built if x['name']==c['name']),None);executed=None;actual=None;verify=None
  if matching and matching['error']=='' and target.exists():
   verify,_=run(Path(c['folder']),'gc-verify',['/usr/bin/codesign','--verify','--strict',target]);executed,actual=run(Path(c['folder']),'gc-native',policy(Path(c['folder']),'gc-runtime',target,deny_mio=True))
  record(c['name']+'-gc-api',verify==0 and executed==c['expected_exit'] and actual==bytes.fromhex(c['expected_hex']),native_exit=executed,heap=c['heap'],gc_stress=c['stress'],error=matching['error'] if matching else 'witness did not produce a result',application_sha256=sha(target) if target.exists() else None)
after=manifest();(out/'source-after.json').write_text(json.dumps(after,indent=2)+'\n');record('frozen-source-unchanged',before==after)
(out/'provenance.json').write_text(json.dumps({'scope':__doc__,'candidate':str(candidate),'candidate_sha256':sha(cli),'source_manifest_sha256':sha(out/'source-before.json'),'work':str(work),'frozen_expectations':str(frozen)},indent=2)+'\n');raise SystemExit(0 if all(x['status']=='PASS' for x in results) else 1)
