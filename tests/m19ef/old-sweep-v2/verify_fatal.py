"""Actual active-Sweep cancel-only proof, terminal process cleanup is separate."""
import struct

def verify_fatal(stdout,data):
    assert stdout==b'0\n69\n2\n' and len(data)==32520,(stdout,len(data))
    regs=struct.unpack('<16Q',data[:128]);fatal=struct.unpack('<9Q',data[128:200]);sweep=struct.unpack('<32Q',data[200:456])
    assert regs[0]==1330398546 and regs[1]==3 and regs[-1]==1
    assert fatal==(1330401613,1,4,0,1,1,1,1,85),fatal
    assert sweep[:4]==(1330406979,3,4,0) and sweep[4]>=400003 and sweep[6]>0 and sweep[7]==0 and sweep[12:14]==(1,0) and sweep[14] in (0,1) and sweep[15]==0 and sweep[25]==0,sweep
    # Terminal packet is collected while other threads can still run. Only
    # immutable Release-committed records are evidence; never invent a joined
    # global snapshot from this prefix. Required records precede this report.
    count=struct.unpack_from('<Q',data,456)[0];assert 0<count<=500,count
    events=[]
    for i in range(count):
        v=struct.unpack_from('<8Q',data,520+i*64)
        if v[0]!=i+1:continue
        events.append(dict(zip(('seq','id','subject','value','epoch','phase','owner','ns'),v)))
    def one(code):
        es=[e for e in events if e['id']==code and e['epoch']==1];assert len(es)==1,(code,es)
        return es[0]
    begin,ready,batch,trigger,cancel,after=[one(c) for c in (1,53,51,20,54,55)]
    assert trigger['value']==3,'actual invalid Join must trigger this fatal path; a gate timeout cannot substitute'
    assert begin['seq']<ready['seq']<batch['seq']<trigger['seq']<cancel['seq']<after['seq']
    assert begin['phase']==batch['phase']==cancel['phase']==2 and after['phase']==4
    assert 0<sweep[5]<sweep[4] and sweep[4]==sweep[5]+sweep[6],sweep
    assert not any(e['epoch']==1 and e['id']==2 for e in events),'completed Sweep cannot substitute for active cancellation'
    return dict(contract='E5-lifecycle-v2.1.1',events=events,fatal_words=fatal,sweep_words=sweep,completed_before_cancel=sweep[5],pending_at_cancel=sweep[6],actual_join_count=0,cleanup='terminal OS process teardown; never claimed as joined cleanup')
