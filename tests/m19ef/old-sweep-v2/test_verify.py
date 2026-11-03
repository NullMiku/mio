"""Adversarial oracle regression using the actual directed native packet."""
from pathlib import Path
import struct,sys,json
from verify import verify
out=Path(sys.argv[1]);stdout=(out/'late-0.stdout').read_bytes();raw=(out/'late-0.stderr').read_bytes();accepted=verify(stdout,raw)
cases={}
def reject(name,edit,output=stdout):
 data=bytearray(raw);edit(data)
 try:verify(output,bytes(data))
 except (AssertionError,StopIteration):cases[name]='REJECTED'
 else:raise AssertionError('false acceptance: '+name)
def change(code,field,value,occurrence=0):
 def edit(data):
  seen=0
  for i in range(struct.unpack_from('<Q',data,256)[0]):
   at=320+i*64
   if struct.unpack_from('<Q',data,at+8)[0]==code and struct.unpack_from('<Q',data,at+32)[0]==1:
    if seen==occurrence:struct.pack_into('<Q',data,at+field*8,value);return
    seen+=1
  raise AssertionError('fixture event missing')
 return edit
reject('missing_native_join',change(24,1,999))
reject('unsuccessful_native_join',change(24,3,22))
reject('stale_epoch',change(41,4,2))
reject('minor_without_stw_ownership',change(41,6,0))
reject('minor_outside_sweep',change(42,5,3))
reject('missing_registry_leave',change(16,1,999))
reject('exit_after_sweep',change(15,0,499))
reject('uncommitted_event',change(51,0,0))
reject('trace_overflow',lambda d:struct.pack_into('<Q',d,256,501))
reject('phase2_only_is_insufficient',lambda d:d.__setitem__(slice(320,None),bytes(len(d)-320)),stdout.replace(b'\n3\n',b'\n2\n',1))
(out/'verifier-negative-results.json').write_text(json.dumps(dict(native_positive='ACCEPTED_WITH_PHASE3',negative_cases=cases),indent=2)+'\n');print(json.dumps(cases))
from verify_fatal import verify_fatal
fatal_stdout=(out/'fatal-0.stdout').read_bytes();fatal_raw=(out/'fatal-0.stderr').read_bytes();verify_fatal(fatal_stdout,fatal_raw)
fatal_cases={}
for name,offset,value in [('completed_sweep_cannot_count_as_abort',200+2*8,3),('no_pending_claims_cannot_prove_active_abort',200+6*8,0),('joined_cleanup_cannot_count_as_cancel_only',200+13*8,1)]:
    damaged=bytearray(fatal_raw);struct.pack_into('<Q',damaged,offset,value)
    try:verify_fatal(fatal_stdout,bytes(damaged))
    except (AssertionError,StopIteration):fatal_cases[name]='REJECTED'
    else:raise AssertionError('false fatal acceptance: '+name)
for code,name in [(51,'missing_real_batch'),(20,'missing_actual_invalid_join_trigger'),(54,'missing_before_cancel'),(55,'missing_after_cancel')]:
    damaged=bytearray(fatal_raw)
    for i in range(struct.unpack_from('<Q',damaged,456)[0]):
        at=520+i*64
        if struct.unpack_from('<Q',damaged,at+8)[0]==code:struct.pack_into('<Q',damaged,at+8,999)
    try:verify_fatal(fatal_stdout,bytes(damaged))
    except (AssertionError,StopIteration):fatal_cases[name]='REJECTED'
    else:raise AssertionError('false fatal acceptance: '+name)
(out/'fatal-verifier-negative-results.json').write_text(json.dumps(fatal_cases,indent=2)+'\n');print(json.dumps(fatal_cases))
