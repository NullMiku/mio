"""Original complete workload oracle; natural Epochs and controlled cancels differ explicitly."""
import struct

def verify_cancel_gate(case,gate):
 assert len(gate)==16 and gate[:2]==(1330420001,1),gate
 assert gate[2]==gate[3]==gate[9] and gate[4]>0 and gate[5]>0,gate
 assert gate[6:9]==((3,3,3) if case=='epochs-cancel' else (1,1,1)),gate
 assert gate[11]==0 and gate[12]>0 and gate[13]==1 and gate[14]>0 and gate[15]>0,gate
 return gate

def verify_workload(case,stdout,data,digest,natural_epochs=False,repeat=0):
 observations=[]
 if case in ('fatal','oom','oom-bound'):
  n=list(map(int,stdout.splitlines()));assert n[:3]==[0,69,2],n
  if case=='fatal':
   assert len(data)==456 and n==[0,69,2],(len(data),n)
   original=struct.unpack('<16Q',data[:128]);assert original[0]==1330398546 and original[1]==3 and original[-1]==1
   fatal=struct.unpack('<9Q',data[128:200]);sweep=struct.unpack('<32Q',data[200:]);assert fatal==(1330401613,1,4,0,1,1,1,1,85),fatal
   assert sweep[:4]==(1330406979,3,4,0) and sweep[4]>=400003 and sweep[6]>0 and sweep[7]==0 and sweep[12:14]==(1,0) and sweep[14] in (0,1) and sweep[15]==0 and sweep[25]==0,sweep
  else:
   assert len(data)==328 and n==[0,69,2,2],(len(data),n)
   fatal=struct.unpack('<9Q',data[:72]);sweep=struct.unpack('<32Q',data[72:]);assert fatal==(1330401613,1,4,0,1,1,1,1,0),fatal
   assert sweep[:4]==(1330406979,3,4,0) and sweep[4]>=400003 and sweep[6:8]==(0,0) and sweep[12:16]==(1,1,1,1) and sweep[25]>0 and sweep[4]==sweep[5]+sweep[25],sweep
  observations.append(dict(case=case,repeat=repeat,stdout=stdout.decode(),fatal_words=list(fatal),sweep_words=list(sweep),source_manifest_sha256=digest));return observations[-1]
 assert len(data)==808,(len(data),stdout,data[:256]);sweep=struct.unpack('<32Q',data[:256]);old=struct.unpack('<24Q',data[256:448]);mut=struct.unpack('<45Q',data[448:]);n=list(map(int,stdout.splitlines()))
 if case in ('ordinary','minor'):
  assert len(n)==(14 if case=='ordinary' else 18),n
  assert n[0]==0 and n[1]>=65 and n[2]>=(100003 if case=='ordinary' else 400003) and n[3:6]==[3,0,0] and n[6]>=3200000 and n[7]>0 and n[8]>=10000 and n[9]>=10000 and n[10]+n[11]>0 and n[12]==0 and n[-1]==0,n
  if case=='minor':assert min(n[13:17])>=0 and n[16]>=n[15] and sweep[26:29]==tuple(n[13:16]) and sweep[29]>=n[16] and (sweep[31]==1 if n[13]>0 else True),(n,sweep) # v2: eight deterministic Minors are mandatory in the separate lifecycle image.
  assert sweep[:4]==(1330406979,3,3,0) and sweep[4]==sweep[5]>=100003 and sweep[6:8]==(0,0) and sweep[8]>=3200000,sweep
  assert sweep[12:16]==(1,1,1,1) and sweep[16]>0 and sweep[16]%2==0 and sweep[17]>0 and sweep[10]<=sweep[18]<=sweep[19]<=sweep[11],sweep
  assert sweep[21]==0 and sweep[22]==sweep[23]==sweep[24]>=1 and sweep[25]==0,sweep
  assert len(set([sweep[9],mut[42],mut[43],mut[44]]))==4 and mut[24]==0 and mut[26]==0
  assert old[0]==1330406477 and old[1:3]==(4,0) and old[5]>=100003 and old[12:17]==(1,1,0,1,1)
 elif case=='epochs':
  assert len(n)==121 and n[-1]==0,n
  for cycle in range(8):
   v=n[cycle*15:cycle*15+15];cancel=(cycle%3==0 and not natural_epochs)
   assert v[0]==0 and v[1]>=65 and v[3:6]==([4,0,0] if cancel else [3,0,0]) and v[8]>=1000 and v[9]>=1000 and v[12]==0,v
   if cancel:assert v[13]==2 and v[14]>0 and 0<=v[2]<400003,v
   else:assert v[2]>=400003 and v[7]>0 and v[10]+v[11]>0 and v[13] in (2,3) and v[14]==0,v
  assert sweep[:4]==(1330406979,3,3,0) and sweep[4]==sweep[5]>=100003 and sweep[6:8]==(0,0) and sweep[12:16]==(8,8,1,1) and sweep[20]==8 and sweep[25]==0,sweep
  assert old[12:17]==(8,8,0,1,1) and old[22]==8 and mut[24]==0 and mut[26]==0
  for off in (7,14):assert mut[off:off+6]==(8,8,8,8,24,24),mut
 elif case=='reenter':
  assert len(n)==17 and n[:4]==[0,69,2,0] and n[4]>=400003 and 0<=n[5]<n[4] and n[6:9]==[4,1,1] and n[9]>=65 and n[10]+n[5]>=n[4] and n[11:14]==[3,0,0] and n[14]>0 and n[15:]==[0,0],n
  assert sweep[:4]==(1330406979,3,3,0) and sweep[4]==sweep[5] and sweep[6:8]==(0,0) and sweep[12:16]==(2,2,1,1) and sweep[20]==2 and sweep[25]==0 and mut[24]==0 and mut[26]==0,sweep
  assert old[12:17]==(2,2,0,1,1) and old[22]==2
 elif case=='late':
  assert len(n)==17 and n[0]==0 and n[1]>=67 and n[2:5]==[2,2,2400003] and n[5]>=8 and n[6]>=2 and n[7]>0 and n[8]==1 and n[9]==0 and n[10]>0 and n[11]==0 and n[12]>=0 and n[13]>=2 and n[14:]==[0,0,0],n
  assert sweep[:4]==(1330406979,3,3,0) and sweep[4]==sweep[5] and sweep[6:8]==(0,0) and sweep[12:16]==(2,2,1,1) and sweep[20]==2 and sweep[25]==0 and mut[24]==0 and mut[26]==0,sweep
  for off in (7,14):assert mut[off:off+6]==(1,1,1,1,3,3),mut
 elif case=='shutdown':
  assert n==[0,69,2] and sweep[0:2]==(1330406979,3) and sweep[2] in (3,4) and sweep[3]==0 and sweep[4]>=400003 and sweep[4]==sweep[5]+sweep[25] and sweep[6:8]==(0,0) and sweep[12:16]==(1,1,1,1), (n,sweep)
  for off in (7,14):assert mut[off:off+6]==(1,1,1,1,3,3),mut
 else:
  assert len(n)==30,n
  fault=case=='los-fault';assert n[0]==0 and n[1]>=4 and n[2]>=34,n
  assert n[3:9]==([1,2,294912,22,15,15] if fault else [0,1,147456,0,16,16]),n
  assert n[11]==0 and n[12]>=35 and n[13:19]==[0,1,147456,22 if fault else 0,16,16],n
  assert n[9]-n[19]==(131120 if fault else 0) and n[10]-n[20]==(131120 if fault else 0) and n[21:24]==[1,1,0] and n[24]>=0 and n[25]>=2 and n[26:]==[1,0,0,0],n
  assert sweep[:4]==(1330406979,3,3,0) and sweep[4]==sweep[5] and sweep[6:8]==(0,0) and sweep[12:16]==((3,3,1,1) if fault else (2,2,1,1)) and sweep[20]==2 and sweep[21]==0 and sweep[22:25]==(1,1,1) and sweep[25]==0,sweep
  assert mut[24]==0 and mut[26]==0 and mut[30]>0 and mut[31]>0
 observations.append(dict(case=case,repeat=repeat,stdout=stdout.decode(),sweep_words=list(sweep),old_words=list(old),mutator_words=list(mut),source_manifest_sha256=digest))
 return observations[-1]
