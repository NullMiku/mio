#!/usr/bin/env python3
"""Eight fixed random seeds: real ordinary Sweep, replayable actor decisions.
OS interleaving is unconstrained; Epoch order is independently tested by E5.
"""
from pathlib import Path
import fcntl,hashlib,json,os,shutil,signal,struct,subprocess,sys,time
r=Path.cwd();out=(r/sys.argv[1]).resolve();prior=(r/sys.argv[2]).resolve()
assert out.is_relative_to(r/'build/m19ef-evidence');out.mkdir()
lock=os.fdopen(os.dup(int(os.environ['MIO_E5_TEST_LOCK_FD'])),'a+') if 'MIO_E5_TEST_LOCK_FD' in os.environ else (r/'build/.m19ef-native-test.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,data):(out/name).write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')
snap=out/'source-snapshot';snap.mkdir();manifest={}
for folder in ('bunko','selfhost','tests/m19ef'):
 for p in sorted((r/folder).rglob('*.mio')):
  rel=p.relative_to(r);dest=snap/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);manifest[str(rel)]=sha(p)
save('source-manifest.json',manifest);shutil.copyfile(__file__,out/'controller.py')
previous=json.loads((prior/'source-manifest.json').read_text())
relevant=lambda m:{k:v for k,v in m.items() if k.startswith(('bunko/','selfhost/')) or k=='tests/m19ef/old-sweep/builder.mio'}
assert relevant(manifest)==relevant(previous),'builder production inputs differ'
commands=json.loads((prior/'commands.json').read_text());built=next(x for x in commands if x['label']=='build');assert built['exit']==0 and not built['timed_out']
builder=prior/'sweep-builder';seeds=[1,7,17,257,65537,104729,999983,1234567]
save('plan.json',dict(status='FROZEN_RUNNING',seeds=seeds,runs_per_seed=1,retries=0,min_progress_per_actor=10000,dead_old_objects=100003,LCG=dict(multiplier=48271,modulus=2147483647,initial='seed+actor+1'),decision='index=(2*state+actor)%64; state=48271*state%2147483647',replay_scope='per-actor heap operations; not an assertion of identical kernel scheduling',builder_sha256=sha(builder),original_build=built))
rows=[]
def run(label,args,timeout=600):
 args=list(map(str,args));start=time.monotonic()
 with (out/(label+'.stdout')).open('xb') as so,(out/(label+'.stderr')).open('xb') as se:
  child=subprocess.Popen(args,cwd=snap,stdout=so,stderr=se,start_new_session=True);timed=False
  while True:
   got,status,u=os.wait4(child.pid,os.WNOHANG)
   if got:break
   if time.monotonic()-start>timeout:
    timed=True;os.killpg(child.pid,signal.SIGKILL);_,status,u=os.wait4(child.pid,0);break
   time.sleep(.03)
 row=dict(label=label,argv=args,exit=os.waitstatus_to_exitcode(status),timed_out=timed,wall_seconds=time.monotonic()-start,cpu_seconds=u.ru_utime+u.ru_stime,peak_rss_bytes_darwin=u.ru_maxrss,stdout_sha256=sha(out/(label+'.stdout')),stderr_sha256=sha(out/(label+'.stderr')))
 rows.append(row);save('commands.json',rows);print(label,row['exit'],flush=True);assert row['exit']==0 and not timed,row
 return (out/(label+'.stdout')).read_bytes()
run('builder-signature',['codesign','--verify','--strict',builder])
original=(snap/'tests/m19ef/old-sweep/ordinary/main.mio').read_text();observations=[]
for seed in seeds:
 source=original
 edits=[('kaku progress=0;kaku observed=0;kaku observed_epoch=0;',f'kaku progress=0;kaku observed=0;kaku observed_epoch=0;kaku state={seed}+id+1;kaku digest=0;'),('kaku index=(progress*2+id)-((progress*2+id)/64)*64;', 'kaku index=(state*2+id)-((state*2+id)/64)*64;'),('progress=progress+1;', 'digest=digest*131+index;digest=digest-(digest/2147483647)*2147483647;state=state*48271;state=state-(state/2147483647)*2147483647;progress=progress+1;signal[10+id]=digest;signal[12+id]=state;'),('kaku signal:[]int64=[0,0,0,0,0,0,0,0,0,0];','kaku signal:[]int64=[0,0,0,0,0,0,0,0,0,0,0,0,0,0];'),('chant(signal[7]);','chant(signal[7]);chant(signal[10]);chant(signal[11]);chant(signal[12]);chant(signal[13]);')]
 # Capture progress/digest only after actual user joins, so printing itself
 # cannot race a later actor iteration and mix two different decision prefixes.
 edits.extend([('kaku swept=rt_collect(30);chant(started);','kaku swept=rt_collect(30);signal[1]=1;rt_join(a);rt_join(b);chant(started);'),('signal[1]=1;rt_join(a);rt_join(b);live=mu;','live=mu;')])
 for old,new in edits:assert source.count(old)==1;source=source.replace(old,new)
 path=snap/('seed-'+str(seed)+'.mio');path.write_text(source);image=out/('seed-'+str(seed)+'-native');copy=out/('seed-'+str(seed)+'-reproduced-native')
 run('seed-'+str(seed)+'-build',[builder,snap,path.name,snap/'bunko',image,'16777216','32'])
 run('seed-'+str(seed)+'-signature',['codesign','--verify','--strict',image])
 run('seed-'+str(seed)+'-reproduce',[builder,snap,path.name,snap/'bunko',copy,'16777216','32']);assert image.read_bytes()==copy.read_bytes() and Path(str(image)+'.unsigned').read_bytes()==Path(str(copy)+'.unsigned').read_bytes()
 label='seed-'+str(seed);n=list(map(int,run(label,[image],60).splitlines()));raw=(out/(label+'.stderr')).read_bytes();assert len(n)==18 and len(raw)==808
 sweep=struct.unpack('<32Q',raw[:256]);old=struct.unpack('<24Q',raw[256:448]);mut=struct.unpack('<45Q',raw[448:])
 assert n[0]==0 and n[1]>=65 and n[2]>=100003 and n[3:6]==[3,0,0] and n[6]>=3200000 and n[7]>0 and min(n[8:10])>=10000 and n[10]+n[11]>0 and n[12]==0 and n[-1]==0,n
 assert sweep[:4]==(1330406979,3,3,0) and sweep[4]==sweep[5]>=100003 and sweep[6:8]==(0,0) and sweep[8]>=3200000
 assert sweep[12:16]==(1,1,1,1) and sweep[16]>0 and sweep[16]%2==0 and sweep[17]>0 and sweep[10]<=sweep[18]<=sweep[19]<=sweep[11]
 assert sweep[21]==0 and sweep[22]==sweep[23]==sweep[24]>=1 and sweep[25]==0
 assert len(set([sweep[9],mut[42],mut[43],mut[44]]))==4 and mut[24]==0 and mut[26]==0
 assert old[0]==1330406477 and old[1:3]==(4,0) and old[5]>=100003 and old[12:17]==(1,1,0,1,1)
 decisions=[]
 for actor in (0,1):
  state=seed+actor+1;digest=0;sequence=[]
  for i in range(n[8+actor]):
   index=(2*state+actor)%64;sequence.append(index);digest=(digest*131+index)%2147483647;state=state*48271%2147483647
  assert digest==n[13+actor] and state==n[15+actor],('native decision replay mismatch',seed,actor)
  decisions.append(sequence)
 save(label+'-decision-replay.json',dict(seed=seed,actual_actor_progress=n[8:10],native_digest=n[13:15],native_final_state=n[15:17],replayed_decisions=decisions,scope='reconstructed deterministic actor paths, checked against native final digest/state; not a fabricated GC event trace'))
 observations.append(dict(seed=seed,source_sha256=sha(path),image_sha256=sha(image),stdout=n,sweep=list(sweep),old=list(old),mutator=list(mut)))
save('observations.json',observations)
assert all(sha(r/k)==h and sha(snap/k)==h for k,h in manifest.items())
save('summary.json',dict(status='PASS_FIXED8_RANDOM_SEED_ACTOR_REPLAY_REAL_SWEEP',seeds=seeds,native_executions=8,min_actor_progress=10000,decision_replay='all native final states/digests checked',source_manifest_sha256=sha(out/'source-manifest.json'),E6='IN_PROGRESS'))
