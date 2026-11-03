"""The unchanged strict bulk oracle, shared by directed and full E4 checks."""
import struct
def verify_bulk(stdout,raw):
    lines=stdout.splitlines();assert len(lines)==9,stdout
    assert lines[:2]==[b'0',b'2'] and lines[5:]==[b'hai',b'hai',b'4',b'0'],stdout
    calls,nonnull,prewhite=map(int,lines[2:5])
    assert calls>=16000 and nonnull>=10000 and prewhite>0,('real_white_prewrite',calls,nonnull,prewhite)
    assert len(raw)==552
    old=struct.unpack('<24Q',raw[:192]);mut=struct.unpack('<45Q',raw[192:])
    assert old[0]==1330406477 and old[1]==4 and old[2]==0
    assert old[3]==old[4] and old[3]>=8000 and old[5]>=1 and old[23]==0
    assert old[12:17]==(1,1,0,1,1) and mut[26]==0
    assert old[17:20]==(old[3],old[3],old[3]) and old[20:23]==(0,0,1)
    assert len(set([old[6],mut[42],mut[43],mut[44]]))==4
    return dict(calls=calls,nonnull=nonnull,prewhite=prewhite,epoch=old[22],scanned=old[3],black=old[4],white=old[5],final_heap=mut[26])
