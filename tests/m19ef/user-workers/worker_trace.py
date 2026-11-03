"""Strict oracle for the original five E3 ordinary user-worker workloads."""
import struct

def verify_worker_trace(case, raw):
    assert len(raw)==360,('trace_size',case,len(raw))
    v=struct.unpack('<45Q',raw)
    assert v[:6]==(1,1,0,0,3,3),('main_lifecycle',case,v[:6])
    assert len(set(v[42:45]))==3 and all(v[42:45]),('real_pthread_identities',case,v[42:45])
    for base in (7,14):
        assert v[base]==v[base+1] and v[base+2]==v[base+3] and v[base+4]==v[base+5] and v[base+2]>0 and v[base+6]>0,('worker_lifecycle',case,base,v[base:base+7])
    assert v[24]==0 and v[26]==0 and v[21]>0 and v[22]>0 and v[23]>0,('gc_reclamation',case,v[21:27])
    if case in ('handoff','blocking','global-snapshot'):
        assert v[25]>=131120,('los_reclaimed',case,v[25])
    if case in ('nativefs','blocking','global-snapshot'):
        assert v[30]>0 and v[31]>0,('native_boundaries',case,v[30:32])
        assert max(v[32],v[34])<min(v[33],v[35]),('worker_overlap',case,v[32:36])
    if case=='blocking':
        assert v[23]>=50,('major_count',case,v[23])
    assert all(v[i]>0 and v[i+1]>0 for i in (36,38,40)),('real_snapshots_and_epochs',case,v[36:42])
    return v
