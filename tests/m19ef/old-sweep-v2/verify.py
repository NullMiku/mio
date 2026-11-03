"""Fail-closed lifecycle contract v2. No phase snapshot alone is acceptance."""
import struct
NAMES={1:'sweep_begin',2:'before_sweep_end',3:'after_sweep_end',10:'worker_start',11:'user_call',12:'user_return',13:'leave_enter',14:'leave_return',15:'callback_last',16:'registry_unlinked',20:'join_enter',21:'completion_enter',22:'completion_return',23:'native_join_enter',24:'native_join_return',25:'block_leave_enter',26:'block_leave_return',31:'phase_load',40:'minor_request',41:'minor_begin',42:'minor_end',50:'collector_rendezvous',51:'batch_unlocked',52:'worker_rendezvous',57:'user_work_begin',58:'user_work_end'}
def verify(stdout,data):
    assert len(data)==32872,len(data)
    sweep=struct.unpack('<32Q',data[:256]);old=struct.unpack('<24Q',data[32320:32512]);mut=struct.unpack('<45Q',data[32512:])
    count=struct.unpack_from('<Q',data,256)[0];assert 0<count<=500,count
    events=[]
    for i in range(count):
        v=struct.unpack_from('<8Q',data,320+i*64);assert v[0]==i+1
        events.append(dict(zip(('seq','id','subject','value','epoch','phase','owner','ns'),v)))
    es=[e for e in events if e['epoch']==1]
    def one(code,subject=None):
        matches=[e for e in es if e['id']==code and (subject is None or e['subject']==subject)]
        assert len(matches)==1,(code,subject,matches)
        return matches[0]
    join=next(e for e in es if e['id']==24);b=join['subject'];begin=one(1);end=one(2)
    # Callback entry may precede epoch? B is created only after Sweep launch.
    chain=[begin,one(11,b),one(52),one(51),one(57,b),one(58,b),one(12,b),one(16,b),one(14,b),one(15,b),join,end,one(3)]
    assert all(a['seq']<z['seq'] for a,z in zip(chain,chain[1:])),chain
    assert join['value']==0
    # Every actual Minor is bounded by request, production STW ownership and end.
    minors=[e for e in es if e['id']==41];assert len(minors)==8,len(minors)
    requests=[e for e in es if e['id']==40 and e['subject']==b];assert len(requests)==8
    finishes=[e for e in es if e['id']==42];assert len(finishes)==8
    for req,start,finish in zip(requests,minors,finishes):
        assert one(57,b)['seq']<req['seq']<start['seq']<finish['seq']<one(58,b)['seq']
        assert start['owner']==finish['owner']==b and start['phase']==finish['phase']==2,(start,finish)
    n=list(map(int,stdout.splitlines()))
    assert len(n)==17 and n[0]==0 and n[1]>=67 and n[2:5]==[2,3,2400003] and n[5]>=8 and n[6]>=2 and n[7]>0 and n[8]==1 and n[9]==0 and n[10]>0 and n[11]==0 and n[12]>=0 and n[13]>=2 and n[14:]==[0,0,0],n
    phases=[e for e in es if e['id']==31];assert any(e['value']==3 and e['seq']>end['seq'] for e in phases)
    assert sweep[:4]==(1330406979,3,3,0) and sweep[4]==sweep[5] and sweep[6:8]==(0,0) and sweep[12:16]==(2,2,1,1) and sweep[20]==2 and sweep[25]==0 and mut[24]==mut[26]==0
    for off in (7,14):assert mut[off:off+6]==(1,1,1,1,3,3)
    return dict(events=events,stdout=n,contract='E5-lifecycle-v2',native_termination_bounds=[one(15,b)['seq'],join['seq']],sweep_bounds=[begin['seq'],end['seq']],minor_count=8,phase3_regression=True,sweep_words=sweep,old_words=old,mutator_words=mut)
