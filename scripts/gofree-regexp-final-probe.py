#!/usr/bin/env python3
"""Frozen full regexp matrix through the final offline unified CLI.
Retains raw exact-reference mismatches. Independently verifies only anchored
single-scalar Unicode property extensions against unchanged Unicode15 facts;
never reports those cases as exact Go parity.
"""
import argparse,hashlib,json,re,shutil,subprocess,tempfile,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);baseline=root/'build/gofree-evidence/GF3/regexp-expanded-r2';work=Path(tempfile.mkdtemp(prefix='mio-regexp-final-',dir='/tmp')).resolve();cli=work/'mio';shutil.copy2(a.candidate,cli)
for old,new in [('driver.mio','driver.mio'),('cases.json','cases.json')]:shutil.copy2(baseline/old,work/new)
cases=json.loads((work/'cases.json').read_text());expected=(baseline/'reference.stdout').read_text().splitlines();assert len(cases)==len(expected)==9030
facts_path=root/'selfhost/unicodegen/unicode15.tables';facts_bytes=facts_path.read_bytes();facts_sha=hashlib.sha256(facts_bytes).hexdigest();assert facts_sha=='95dd35e484156420bfaf54313bafdd0cf19fb6b43816644bd7765d3b6fe84765'
facts={}
for line in facts_bytes.decode().splitlines():
 key,encoded=line.split('|');facts[key]=list(map(int,encoded.split(',')))
def policy(name,program):
 path=work/(name+'.sb');path.write_text('(version 1)(allow default)(deny network*)(deny process-fork)(deny process-exec)(allow process-exec (literal '+json.dumps(str(program))+'))(deny file-read* (subpath '+json.dumps(str(root))+'))(deny file-read* (subpath "/Volumes/Sector0/AppData/Mio/mio"))\n');return ['/usr/bin/sandbox-exec','-f',str(path),str(program)]
commands=[]
def run(label,argv):
 start=time.monotonic();r=subprocess.run(argv,cwd=work,env={'PATH':'','MIO_BUNKO':''},capture_output=True,timeout=180);(out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr);commands.append({'label':label,'argv':list(map(str,argv)),'exit':r.returncode,'seconds':time.monotonic()-start});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');return r
app=work/'regexp.native';r=run('compile',policy('compiler',cli)+['build','driver.mio','-o',str(app)]);assert r.returncode==0,r.stderr
r=run('verify',['/usr/bin/codesign','--verify','--strict',str(app)]);assert r.returncode==0
r=run('native',policy('runtime',app));actual=r.stdout.decode().splitlines();raw=[];extensions=[];unresolved=[]
for i,c in enumerate(cases):
 observed=actual[i] if i<len(actual) else None;equal=r.returncode==0 and observed==expected[i];record={**c,'expected':expected[i],'actual':observed,'status':'PASS' if equal else 'FAIL'};raw.append(record)
 if equal:continue
 match=re.fullmatch(r'\^\\p\{([^{}]+)\}\$',c['pattern']);value=None
 if expected[i]=='E' and observed in ('T','F') and match and len(c['text'])==1:
  key=re.sub(r'[_ -]','',match.group(1)).lower();triples=facts.get(key);cp=ord(c['text'])
  if triples:
   contains=any(triples[j]<=cp<=triples[j+1] and (cp-triples[j])%triples[j+2]==0 for j in range(0,len(triples),3));value='T' if contains else 'F'
 if value==observed:extensions.append({**record,'unicode_facts_expected':value,'classification':'DOCUMENTED_CORRECT_PROPERTY_EXTENSION'})
 else:unresolved.append(record)
(out/'raw-exact-reference-results.json').write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n');(out/'unicode-extensions.json').write_text(json.dumps(extensions,ensure_ascii=False,indent=2)+'\n');(out/'unresolved.json').write_text(json.dumps(unresolved,ensure_ascii=False,indent=2)+'\n')
summary={'status':'PASS_WITH_DOCUMENTED_UNICODE_EXTENSION' if r.returncode==0 and len(actual)==len(cases) and not unresolved else 'FAIL','total':len(cases),'exact_reference_equal':sum(x['status']=='PASS' for x in raw),'unicode_property_extensions_verified':len(extensions),'unresolved':len(unresolved),'exit':r.returncode,'candidate_sha256':hashlib.sha256(cli.read_bytes()).hexdigest(),'facts_sha256':facts_sha,'frozen_cases_sha256':hashlib.sha256((work/'cases.json').read_bytes()).hexdigest(),'frozen_reference_stdout_sha256':hashlib.sha256((baseline/'reference.stdout').read_bytes()).hexdigest(),'scope':__doc__}
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2),flush=True);raise SystemExit(0 if summary['status']!='FAIL' else 1)
