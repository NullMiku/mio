"""Test-only callers of the FORMAL neutral gc_memory_snapshot runtime entry.
No snapshot implementation or GC work is replaced by this adapter.
"""
def install(snap, unknown=False):
    p=snap/'bunko/kiso/aot/lower/worker_roots.mio';s=p.read_text()
    needle='    attached_save(c,"attached_worker_collect");';assert s.count(needle)==1
    s=s.replace(needle,needle+'e6_snapshot_query(c,p,first);')
    s+='''
// TEST ONLY: mode60 tests nested ownership; mode61 tests acquire/release.
waza e6_snapshot_args(c:arm64.Assembler) -> unit {
 emit(c,arm64.ldr_x(0,31,72));move_x(c,1,24);move_x(c,2,23);emit(c,arm64.add_imm_x(3,31,0,iie));emit(c,arm64.add_imm_x(4,31,64,iie));
}
waza e6_snapshot_sentinel(c:arm64.Assembler,check:bool) -> unit {
 kaku si=0;aida(si<9){moshi(check){emit(c,arm64.ldr_x(9,31,si*8));emit(c,arm64.cmp_imm_x(9,999,iie));arm64.assembler_b_cond(c,1,"runtime_error");}sore{wr_num(c,9,999);emit(c,arm64.str_x(9,31,si*8));}si=si+1;}
}
waza e6_snapshot_ownership(c:arm64.Assembler,p:[]macho.AddressPatch,first:int64,owned:bool) -> unit {
 emit(c,arm64.ldr_x(0,31,72));emit(c,arm64.ldr_x(10,0,gc.thread_registry));emit(c,arm64.add_imm_x(11,10,gc.gc_registry_owner,iie));emit(c,arm64.ldar_x(12,11));emit(c,arm64.cmp_x(12,0));moshi(owned){arm64.assembler_b_cond(c,1,"runtime_error");}sore{arm64.assembler_b_cond(c,0,"runtime_error");}
 old_control(c,p,first,14);arm64.assembler_cbz_x(c,14,"runtime_error");emit(c,arm64.add_imm_x(11,14,512,iie));emit(c,arm64.ldar_x(12,11));emit(c,arm64.cmp_x(12,0));moshi(owned){arm64.assembler_b_cond(c,1,"runtime_error");}sore{arm64.assembler_b_cond(c,0,"runtime_error");}
 moshi(owned){emit(c,arm64.add_imm_x(11,10,gc.gc_registry_phase,iie));emit(c,arm64.ldar_x(12,11));emit(c,arm64.cmp_imm_x(12,gc.gc_stopped,iie));arm64.assembler_b_cond(c,1,"runtime_error");}
}
waza e6_snapshot_query(c:arm64.Assembler,p:[]macho.AddressPatch,first:int64) -> unit {
 emit(c,arm64.ldr_x(9,31,144));emit(c,arm64.cmp_imm_x(9,60,iie));arm64.assembler_b_cond(c,0,"e6_snapshot_entry");emit(c,arm64.cmp_imm_x(9,61,iie));arm64.assembler_b_cond(c,1,"e6_not_snapshot");
 arm64.assembler_label(c,"e6_snapshot_entry");wr_poll(c,p,first,"gc_mutator_poll");emit(c,arm64.ldr_x(9,31,144));emit(c,arm64.cmp_imm_x(9,60,iie));arm64.assembler_b_cond(c,1,"e6_snapshot_unowned");wr_poll(c,p,first,"gc_heap_enter");
 arm64.assembler_label(c,"e6_snapshot_unowned");emit(c,arm64.sub_imm_x(31,31,112,iie));wr_current(c,p,first);emit(c,arm64.str_x(0,31,72));emit(c,arm64.ldr_x(9,31,256));emit(c,arm64.str_x(9,31,80));
 // Actual failure probes: no destination write or ownership transition is legal.
 kaku bad=0;aida(bad<5){e6_snapshot_sentinel(c,iie);e6_snapshot_args(c);moshi(bad==0){wr_num(c,0,0);}moshi(bad==1){wr_num(c,2,0);}moshi(bad==2){wr_num(c,3,0);}moshi(bad==3){emit(c,arm64.add_imm_x(3,31,1,iie));}moshi(bad==4){wr_num(c,4,0);}wr_imports(c,p,first);arm64.assembler_bl(c,"attached_gc_memory_snapshot");emit(c,arm64.cmp_imm_x(0,4,iie));arm64.assembler_b_cond(c,1,"runtime_error");e6_snapshot_sentinel(c,hai);bad=bad+1;}
 emit(c,arm64.ldr_x(9,31,80));emit(c,arm64.cmp_imm_x(9,60,iie));arm64.assembler_b_cond(c,1,"e6_skip_odd_probe");e6_snapshot_ownership(c,p,first,hai);
 // Fault injection is confined to an already-owned epoch and restored before
 // any other observer can run. An odd unpublished version must be rejected.
 e6_snapshot_sentinel(c,iie);emit(c,arm64.ldr_x(9,23,2656));emit(c,arm64.str_x(9,31,88));emit(c,arm64.add_imm_x(9,9,1,iie));emit(c,arm64.str_x(9,23,2656));e6_snapshot_args(c);wr_imports(c,p,first);arm64.assembler_bl(c,"attached_gc_memory_snapshot");emit(c,arm64.str_x(0,31,96));emit(c,arm64.ldr_x(9,31,88));emit(c,arm64.str_x(9,23,2656));emit(c,arm64.ldr_x(0,31,96));emit(c,arm64.cmp_imm_x(0,4,iie));arm64.assembler_b_cond(c,1,"runtime_error");e6_snapshot_sentinel(c,hai);e6_snapshot_ownership(c,p,first,hai);
 arm64.assembler_label(c,"e6_skip_odd_probe");e6_snapshot_args(c);wr_imports(c,p,first);wr_call(c,"gc_memory_snapshot");
 emit(c,arm64.ldr_x(9,31,80));emit(c,arm64.cmp_imm_x(9,60,iie));arm64.assembler_b_cond(c,1,"e6_snapshot_check_released");e6_snapshot_ownership(c,p,first,hai);
 // Independent M19c ABI slot contract, not an unlocked sequence-only read.
 kaku offsets=[2640,2648,2760,2616,2608,2632,2664,2656];kaku si=0;aida(si<8){emit(c,arm64.ldr_x(9,31,si*8));emit(c,arm64.ldr_x(10,23,offsets[si]));emit(c,arm64.cmp_x(9,10));arm64.assembler_b_cond(c,1,"runtime_error");si=si+1;}emit(c,arm64.ldr_x(9,31,64));emit(c,arm64.ldr_x(10,23,2752));emit(c,arm64.cmp_x(9,10));arm64.assembler_b_cond(c,1,"runtime_error");
 wr_current(c,p,first);wr_call(c,"gc_end");arm64.assembler_b(c,"e6_snapshot_checked");
 arm64.assembler_label(c,"e6_snapshot_check_released");e6_snapshot_ownership(c,p,first,iie);
 arm64.assembler_label(c,"e6_snapshot_checked");emit(c,arm64.ldr_x(9,31,56));wr_num(c,10,1);emit(c,arm64.and_x(9,9,10));arm64.assembler_cbnz_x(c,9,"runtime_error");
 emit(c,arm64.ldr_x(0,31,72));emit(c,arm64.ldr_x(9,0,8688));emit(c,arm64.add_imm_x(9,9,1,iie));emit(c,arm64.str_x(9,0,8688));emit(c,arm64.str_x(9,31,256));
 // Buffer is caller-private native storage, immutable across this real OS write.
 wr_poll(c,p,first,"gc_block_enter");wr_num(c,0,2);emit(c,arm64.add_imm_x(1,31,0,iie));wr_num(c,2,72);wr_num(c,16,4);emit(c,arm64.svc(128));emit(c,arm64.cmp_imm_x(0,72,iie));arm64.assembler_b_cond(c,1,"runtime_error");wr_current(c,p,first);wr_call(c,"gc_block_leave");
 emit(c,arm64.add_imm_x(31,31,112,iie));attached_restore(c);arm64.assembler_label(c,"e6_not_snapshot");
}
'''
    needle='emit(c,arm64.cmp_imm_x(0,360,iie));arm64.assembler_b_cond(c,1,"runtime_error");attached_restore(c);';assert s.count(needle)==1
    s=s.replace(needle,'''emit(c,arm64.cmp_imm_x(0,360,iie));arm64.assembler_b_cond(c,1,"runtime_error");emit(c,arm64.sub_imm_x(31,31,48,iie));wr_num(c,9,1330408008);emit(c,arm64.str_x(9,31,0));kaku sc=0;aida(sc<3){wr_ctx(c,p,first,9,sc);emit(c,arm64.ldr_x(10,9,8688));emit(c,arm64.str_x(10,31,(sc+1)*8));sc=sc+1;}emit(c,arm64.ldr_x(9,23,2752));emit(c,arm64.str_x(9,31,32));emit(c,arm64.ldr_x(9,23,2672));emit(c,arm64.str_x(9,31,40));wr_num(c,0,2);emit(c,arm64.add_imm_x(1,31,0,iie));wr_num(c,2,48);wr_num(c,16,4);emit(c,arm64.svc(128));emit(c,arm64.cmp_imm_x(0,48,iie));arm64.assembler_b_cond(c,1,"runtime_error");emit(c,arm64.add_imm_x(31,31,48,iie));attached_restore(c);''')
    p.write_text(s)

    if unknown:
        # Actual public OS query failure, not a fabricated pressure result.
        p=snap/'bunko/kiso/aot/lower/memory_policy.mio';s=p.read_text()
        a=s.index('arm64.assembler_label(code, "memory.rate.store")');b=s.index('arm64.assembler_label(code, "memory.evaluate")',a)
        block=s[a:b];needle='observation_word(code, 3531607401);';assert block.count(needle)==1
        block=block.replace(needle,'emit(code,arm64.movz_x(9,33,0));') # !ern... is not a valid sysctl key.
        needle='arm64.assembler_label(code, "memory.system.unavailable");';assert block.count(needle)==1
        # Existing System value is ignored while availability==0. In this
        # negative variant only, retain the actual syscall errno there for audit.
        block=block.replace(needle,needle+'emit(code,arm64.str_x(0,19,2672));')
        p.write_text(s[:a]+block+s[b:])
