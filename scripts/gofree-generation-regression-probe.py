#!/usr/bin/env python3
"""Isolated audit scheduling, not a product build step. Run unchanged semantic,
heap/GC, metadata and typed-call fixtures against every real GF4 generation.
"""
import argparse,json,time,subprocess,sys,hashlib
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--chain',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=Path(__file__).resolve().parents[1];chain=a.chain.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);results=[];started=time.monotonic()
for stage in ['A','B','C','D']:
 candidate=chain/stage/'mio'
 while not (candidate.exists() and (chain/stage/'image.json').exists()):
  if time.monotonic()-started>10000 or (chain/'results.json').exists():raise SystemExit('Generation unavailable; chain finished or audit wait bound exceeded')
  time.sleep(3)
 stage_out=out/stage;stage_out.mkdir();print(stage,'REGRESSION_START',flush=True)
 probes=[('source-gc',[sys.executable,'scripts/gofree-final-source-probe.py','--candidate',str(candidate),'--output',str(stage_out/'source-gc'),'--gc-witness']),('runtime',[sys.executable,'scripts/gofree-runtime-metadata-probe.py','--candidate',str(candidate),'--output',str(stage_out/'runtime')]),('typed-calls',[sys.executable,'scripts/gofree-typed-call-source-probe.py','--frontend',str(candidate),'--linker',str(candidate),'--cli','--output',str(stage_out/'typed-calls')])]
 for name,argv in probes:
  with (stage_out/(name+'.controller.stdout')).open('wb') as stdout,(stage_out/(name+'.controller.stderr')).open('wb') as stderr:code=subprocess.run(argv,cwd=root,stdout=stdout,stderr=stderr).returncode
  result={'stage':stage,'probe':name,'status':'PASS' if code==0 else 'FAIL','exit':code,'argv':argv,'candidate_sha256':hashlib.sha256(candidate.read_bytes()).hexdigest()};results.append(result);(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(stage,name,result['status'],flush=True)
  if code!=0:raise SystemExit(1)
print('ALL_GENERATION_REGRESSIONS_PASS',flush=True)
