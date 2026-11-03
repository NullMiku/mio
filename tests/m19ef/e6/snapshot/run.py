#!/usr/bin/env python3
"""Real two-mutator owned snapshot native witness; not E6 acceptance alone."""
from pathlib import Path
import sys,os,json,hashlib,shutil,subprocess,signal,time,struct,fcntl
from overlay import install
r=Path.cwd();out=(r/sys.argv[1]).resolve();assert out.is_relative_to(r/'build/m19ef-evidence');out.mkdir();lock=os.fdopen(os.dup(int(os.environ['MIO_E5_TEST_LOCK_FD'])),'a+') if 'MIO_E5_TEST_LOCK_FD' in os.environ else (r/'build/.m19ef-native-test.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
unknown=len(sys.argv)>2 and sys.argv[2]=='unknown'
assert len(sys.argv)==2 or unknown
compiler=r/'build/m19ef-evidence/E6-final-20261031-01/mio-B';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();assert sha(compiler)=='f09e8d7188784000491d54471f6339f57e6e55b2d6b67d8d5d86430c06aa4973'
snap=out/'source-snapshot';snap.mkdir();manifest={}
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
for folder in ('bunko','selfhost','tests/m19ef'):
 for p in sorted((r/folder).rglob('*.mio')):
  rel=p.relative_to(r);d=snap/rel;d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,d);manifest[str(rel)]=sha(p)
shutil.copyfile(__file__,out/'controller.py');shutil.copyfile(Path(__file__).with_name('overlay.py'),out/'overlay.py');save(out/'canonical-manifest.json',manifest);install(snap,unknown);overlaid={str(p.relative_to(snap)):sha(p) for p in sorted(snap.rglob('*.mio'))};save(out/'source-manifest.json',overlaid)
save(out/'provenance.json',dict(scope='owned snapshot core native witness; preliminary B compiler is actually source-bootstrapped from GF4, not an E6 final fixed-point claim',compiler=str(compiler),compiler_sha256=sha(compiler),production_core='bunko/kiso/runtime/gc/observations.mio',test_adapter_file='bunko/kiso/aot/lower/worker_roots.mio',unknown_os_query_variant=unknown,os_fault='invalid sysctl key; actual errno retained in ignored System slot while availability=0' if unknown else None,script_sha256=sha(Path(__file__)),overlay_sha256=sha(Path(__file__).with_name('overlay.py'))));rows=[]
def run(label,args,timeout=1200):
 args=list(map(str,args));start=time.monotonic();print(label,'START',flush=True)
 with (out/(label+'.stdout')).open('xb') as so,(out/(label+'.stderr')).open('xb') as se:
  child=subprocess.Popen(args,cwd=snap,stdout=so,stderr=se,start_new_session=True);timed=False
  while True:
   got,status,u=os.wait4(child.pid,os.WNOHANG)
   if got:break
   if time.monotonic()-start>timeout:timed=True;os.killpg(child.pid,signal.SIGKILL);got,status,u=os.wait4(child.pid,0);break
   time.sleep(.05)
 row=dict(label=label,argv=args,cwd=str(snap),exit=os.waitstatus_to_exitcode(status),expected_exit=0,timed_out=timed,wall_seconds=time.monotonic()-start,cpu_seconds=u.ru_utime+u.ru_stime,peak_rss_bytes_darwin=u.ru_maxrss,stdout_sha256=sha(out/(label+'.stdout')),stderr_sha256=sha(out/(label+'.stderr')));rows.append(row);save(out/'commands.json',rows);print(label,row['exit'],flush=True);assert row['exit']==0 and not timed,row
 return (out/(label+'.stdout')).read_bytes()
run('compiler-signature',['codesign','--verify','--strict',compiler]);builder=out/'snapshot-builder';run('build',[compiler,'build','tests/m19ef/old-sweep/builder.mio','--bunko-root',snap/'bunko','-o',builder]);run('builder-signature',['codesign','--verify','--strict',builder]);image=out/'snapshot-native';common=[builder,snap,'tests/m19ef/e6/snapshot/main.mio',snap/'bunko'];run('generate',common+[image,'67108864','32']);run('signature',['codesign','--verify','--strict',image]);copy=out/'snapshot-repro-native';run('reproduce',common+[copy,'67108864','32']);assert image.read_bytes()==copy.read_bytes() and Path(str(image)+'.unsigned').read_bytes()==Path(str(copy)+'.unsigned').read_bytes()
stdout=run('snapshot-0',[image],180);n=list(map(int,stdout.splitlines()));assert len(n)==5 and n[0]==0 and n[1]>=65 and n[2:]==[400003,0,0],n
data=(out/'snapshot-0.stderr').read_bytes();assert len(data)==288856,len(data);records=[struct.unpack_from('<9Q',data,i*72) for i in range(4000)];seen={}
for record in records:
 assert record[0]<=3 and record[6] in (0,1) and record[7]%2==0 and record[8] in (0,1),record
 if record[7] in seen:assert seen[record[7]]==record,(record,seen[record[7]])
 seen[record[7]]=record
assert len(seen)>100 and max(seen)>min(seen)
sweep=struct.unpack_from('<32Q',data,288000);old=struct.unpack_from('<24Q',data,288256);mut=struct.unpack_from('<45Q',data,288448);counts=struct.unpack_from('<6Q',data,288808);assert counts[:4]==(1330408008,0,2000,2000) and counts[4] in (0,1),counts
if unknown:
 assert counts[4]==0 and counts[5]>0 and all(v[8]==0 and v[1]&16==0 for v in records),(counts,records[:2])
assert mut[24]==mut[26]==0 and len(set(mut[42:45]))==3 and max(mut[32],mut[34])<min(mut[33],mut[35]);assert sweep[4]==sweep[5]==400003 and sweep[6:8]==(0,0)
assert all(sha(r/k)==v for k,v in manifest.items()) and all(sha(snap/k)==v for k,v in overlaid.items())
save(out/'summary.json',dict(status='PASS_DIRECTED_OWNED_SNAPSHOT_NOT_E6_ACCEPTANCE',snapshot_reads=4000,nested_owned_reads=2000,acquire_release_reads=2000,invalid_argument_rejections=20000,odd_version_rejections=2000,unique_published_versions=len(seen),same_sequence_all_eight_fields_equal=True,system_pressure_available=counts[4],system_raw_value_or_actual_errno=counts[5],unknown_os_query_variant=unknown,unknown_input_policy='coherent availability accompanies the eight-field snapshot; unavailable remains Unknown',writer='actual allocations, Old→Young stores, Minor and real Collector reclamation',roots='ordinary compiler-generated roots, no manual user roots',stdout=n,sweep_words=sweep,old_words=old,mutator_words=mut,source_unchanged=True,E6='IN_PROGRESS',M19e='NOT_ACCEPTED'))
