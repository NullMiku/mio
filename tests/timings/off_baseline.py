#!/usr/bin/env python3
"""Compare the source-verified pre-change native seed and timing-disabled CLI."""
import hashlib,json,os,platform,statistics,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];os.chdir(ROOT)
out=ROOT/'build/timings/off-baseline';out.mkdir(parents=True,exist_ok=True)
compilers={'before':ROOT/'build/timings/seed','after':ROOT/'build/timings/mio'}
rows=[]
for case,source in [('hello','examples/hello_world.mio'),('bunko','tests/timings/bunko.mio')]:
    for repeat in range(12):
        for mode in (['before','after'] if repeat%2==0 else ['after','before']):
            label=f'{case}-{repeat}-{mode}';artifact=out/(label+'.native');argv=[str(compilers[mode]),'build',source,'-o',str(artifact)]
            start=time.perf_counter_ns()
            with (out/(label+'.stdout')).open('wb') as so,(out/(label+'.stderr')).open('wb') as se:
                child=subprocess.Popen(argv,stdout=so,stderr=se);_,status,u=os.wait4(child.pid,0);child.returncode=os.waitstatus_to_exitcode(status)
            row={'label':label,'argv':argv,'case':case,'mode':mode,'repeat':repeat,'exit':child.returncode,'wall_seconds':(time.perf_counter_ns()-start)/1e9,'cpu_seconds':u.ru_utime+u.ru_stime,'user_seconds':u.ru_utime,'system_seconds':u.ru_stime,'peak_rss_bytes':u.ru_maxrss if platform.system()=='Darwin' else u.ru_maxrss*1024,'artifact_sha256':hashlib.sha256(artifact.read_bytes()).hexdigest()}
            assert row['exit']==0 and not (out/(label+'.stdout')).read_bytes() and not (out/(label+'.stderr')).read_bytes(),row
            rows.append(row)
summary={}
for case in ('hello','bunko'):
    assert len({r['artifact_sha256'] for r in rows if r['case']==case})==1
    summary[case]={mode:{key:statistics.median([r[key] for r in rows if r['case']==case and r['mode']==mode]) for key in ('wall_seconds','cpu_seconds','peak_rss_bytes')} for mode in compilers}
    summary[case]['after_before_wall_ratio']=summary[case]['after']['wall_seconds']/summary[case]['before']['wall_seconds']
(out/'measurements.json').write_text(json.dumps(rows,indent=2)+'\n');(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2),flush=True)
