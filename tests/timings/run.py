#!/usr/bin/env python3
"""External measurement/verification only; all compiler instrumentation is Mio.
Runs sequentially. Each child gets its own OS resource-usage record (wait4).
No old timing numbers or estimates are used.
"""
import argparse, hashlib, json, os, platform, subprocess, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--compiler',default='build/timings/mio');p.add_argument('--out',default='build/timings/results');p.add_argument('--repeats',type=int,default=2);p.add_argument('--cases',nargs='*',default=['hello','bunko','frontend','native-aot','selfhost']);a=p.parse_args()
os.chdir(ROOT);out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True);compiler=str(Path(a.compiler).resolve())
CASES={'hello':'examples/hello_world.mio','bunko':'tests/timings/bunko.mio','frontend':'selfhost/frontend','native-aot':'examples/m17e_aot/build.mio','selfhost':'selfhost/cli'}
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
manifest={str(f.relative_to(ROOT)):digest(f) for base in ('selfhost','bunko','examples','tests/timings') for f in sorted((ROOT/base).rglob('*')) if f.is_file() and f.suffix in ('.mio','.py')}
(out/'source-sha256.json').write_text(json.dumps(manifest,indent=2)+'\n')
env={'platform':platform.platform(),'machine':platform.machine(),'compiler':compiler,'compiler_sha256':digest(compiler),'source_manifest_sha256':digest(out/'source-sha256.json'),'git_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'baseline_note':'f8410f4; explicitly authorized without M19e PASS','repeats':a.repeats,'clock':'Python perf_counter_ns for external elapsed; OS wait4 for child CPU/RSS; compiler OS monotonic adapter for stage measurements'}
(out/'environment.json').write_text(json.dumps(env,indent=2)+'\n');rows=[]
def run(label,argv):
    stdout=out/(label+'.stdout');stderr=out/(label+'.stderr');start=time.perf_counter_ns()
    with stdout.open('wb') as so,stderr.open('wb') as se:
        child=subprocess.Popen(argv,stdout=so,stderr=se)
        pid,status,usage=os.wait4(child.pid,0);child.returncode=os.waitstatus_to_exitcode(status)
    row={'label':label,'argv':argv,'exit':child.returncode,'wall_seconds':(time.perf_counter_ns()-start)/1e9,'user_seconds':usage.ru_utime,'system_seconds':usage.ru_stime,'cpu_seconds':usage.ru_utime+usage.ru_stime,'peak_rss_bytes':usage.ru_maxrss if platform.system()=='Darwin' else usage.ru_maxrss*1024,'stdout_sha256':digest(stdout),'stderr_sha256':digest(stderr)}
    rows.append(row);(out/'measurements.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(row),flush=True);return row
for case in a.cases:
    source=CASES[case];hashes=[]
    for repeat in range(a.repeats):
        # Reverse order on alternating rounds to reduce order/cache bias.
        modes=['off','on'] if repeat%2==0 else ['on','off']
        if case in ('frontend','native-aot','selfhost'):
            modes=['on','off'] if repeat==0 else ['on']
        for mode in modes:
            label=f'{case}-{repeat}-{mode}';artifact=out/(label+'.native');report=out/(label+'.json');argv=[compiler,'build',source,'-o',str(artifact)]
            if mode=='on':argv+=[('--timings=detail' if repeat==0 else '--timings'),f'--timings-output={report}']
            row=run(label,argv);assert row['exit']==0,(label,(out/(label+'.stderr')).read_text())
            row['artifact_sha256']=digest(artifact);hashes.append(row['artifact_sha256'])
            signed=subprocess.run(['/usr/bin/codesign','--verify','--strict',str(artifact)],capture_output=True)
            (out/(label+'.signature.stderr')).write_bytes(signed.stderr)
            assert signed.returncode==0,(label,signed.stderr)
            assert (out/(label+'.stdout')).read_bytes()==b'',label
            if mode=='on':
                data=json.loads(report.read_text());stages=data['stages'];total=data['total_ns'];assert len(stages)==15 and total>0
                assert sum(s['exclusive_ns'] for s in stages[:-1])==total,(label,data)
                assert all(s['inclusive_ns']>=s['exclusive_ns']>=0 for s in stages)
                assert stages[-1]['calls']==1 and stages[-1]['inclusive_ns']==total
                assert all(s['inclusive_ns']%data['resolution_ns']==0 for s in stages)
                assert 0<=row['wall_seconds']-total/1e9<max(2,row['wall_seconds']*.1),(label,row,data)
                row['timings']=data
            else:assert b'Compilation timings' not in (out/(label+'.stderr')).read_bytes()
            (out/'measurements.json').write_text(json.dumps(rows,indent=2)+'\n')
    assert len(set(hashes))==1,(case,hashes)
    if case in ('hello','bunko'):
        row=run(case+'-execute',[str(artifact)]);assert row['exit']==0
        expected=b'Hello, Mio!\n' if case=='hello' else b'9\nBunko ok\n'
        assert (out/(case+'-execute.stdout')).read_bytes()==expected
    (out/(case+'.PASS')).write_text('repeated timing reconciliation and complete signed artifact SHA256 equality\n')
# Failure paths: only the work actually executed should have calls.
if 'hello' in a.cases:
    for kind in ('lex','parse','type','lower'):
        label=kind+'-failure';report=out/(label+'.json');artifact=out/(label+'.native')
        row=run(label,[compiler,'build',f'tests/timings/{kind}-error.mio','-o',str(artifact),'--timings',f'--timings-output={report}'])
        assert row['exit']==1 and not artifact.exists(),row
        data=json.loads(report.read_text());assert sum(s['exclusive_ns'] for s in data['stages'][:-1])==data['total_ns']
        if kind=='lower':
            assert data['stages'][8]['calls']==1 and data['stages'][9]['calls']==0,(label,data)
            assert b'E_LOWER 6 / 0' in (out/(label+'.stderr')).read_bytes()
        else:assert data['stages'][8]['calls']==0,(label,data)
        assert data['stages'][1]['calls']>=1 and data['stages'][2]['calls']>=1
        row['timings']=data
    (out/'measurements.json').write_text(json.dumps(rows,indent=2)+'\n')
if 'hello' in a.cases:
    ir_hashes=[]
    for mode in ('off','on'):
        label='mochi-'+mode;artifact=out/(label+'.mochi');argv=[compiler,'build',CASES['hello'],'--emit=mochi','-o',str(artifact)]
        if mode=='on':argv+=['--timings']
        row=run(label,argv);assert row['exit']==0;row['artifact_sha256']=digest(artifact);ir_hashes.append(row['artifact_sha256'])
    assert ir_hashes[0]==ir_hashes[1],'timing must not change IR bytes'
    report=out/'write-failure.json'
    row=run('write-failure',[compiler,'build',CASES['hello'],'-o',str(out/'absent-parent'/'a.out'),f'--timings-output={report}'])
    assert row['exit']==1
    data=json.loads(report.read_text());assert data['stages'][12]['calls']==1
    assert sum(s['exclusive_ns'] for s in data['stages'][:-1])==data['total_ns']
    row['timings']=data
    for label,args in [('bad-detail',['--timings=bogus']),('empty-json',['--timings-output=']),('path-collision',['-o',str(out/'collision'),f'--timings-output={out}/./collision'])]:
        row=run(label,[compiler,'build',CASES['hello']]+args);assert row['exit']==2
    (out/'measurements.json').write_text(json.dumps(rows,indent=2)+'\n')
assert manifest=={f:digest(ROOT/f) for f in manifest},'source changed during run' 
(out/'PASS').write_text('All selected cases passed. Full signed outputs identical with and without timings.\n')
