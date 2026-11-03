"""Test-only native event adapter. Production sources are copied, never edited.
Derived from retained event-diagnostic-06; generated instructions remain pure Mio.
"""
from pathlib import Path
def install(snap):
    def edit(name,fn):
     p=snap/name;s=p.read_text();p.write_text(fn(s))
    def replace(s,a,b,n=1):
     assert s.count(a)==n,(a,s.count(a),n)
     return s.replace(a,b)
    def ev(n,subject='0',value='0'):
     return f'tconstant(f,29,{n});ir.invoke_function(f,"diagnostic_event",28,[29,{subject},{value}]);'
    # Diagnostic-only native buffer after the original owned worker contexts.
    # Independent diagnostic linker buffer; production limit remains byte-identical.
    edit('bunko/kiso/runtime/os/darwin/link.mio',lambda s:replace(s,'runtime_words>4096','runtime_words>16384'))
    edit('bunko/kiso/aot/lower/old_sweep.mio',lambda s:replace(replace(s,'concurrent_old_root_words=3306','concurrent_old_root_words=7502'),'kaesu 30;','kaesu 31;'))
    edit('bunko/kiso/aot/lower/worker_roots.mio',lambda s:replace(replace(s,'worker_root_words=3304','worker_root_words=7500'),'["worker_sweep_account","worker_sweep_unmap"]','["worker_sweep_account","worker_sweep_unmap","diagnostic_event_native"]'))
    p=snap/'bunko/kiso/aot/lower/worker_roots.mio';s=p.read_text()
    # Native record preserves all caller scratch and flags, takes no GC/heap lock.
    s+='''
    // DIAGNOSTIC COPY ONLY: AcqRel sequence reservation, per-slot Release commit.
    waza diagnostic_emit(c:arm64.Assembler,p:[]macho.AddressPatch,first:int64,event:int64,subject:int64,value:int64) -> unit {
     emit(c,arm64.sub_imm_x(31,31,32,iie));emit(c,arm64.str_x(0,31,0));emit(c,arm64.str_x(1,31,8));emit(c,arm64.str_x(2,31,16));
     move_x(c,1,subject);move_x(c,2,value);wr_num(c,0,event);arm64.assembler_bl(c,"diagnostic_event_native");
     emit(c,arm64.ldr_x(0,31,0));emit(c,arm64.ldr_x(1,31,8));emit(c,arm64.ldr_x(2,31,16));emit(c,arm64.add_imm_x(31,31,32,iie));
    }
    waza diagnostic_runtime(c:arm64.Assembler,p:[]macho.AddressPatch,first:int64) -> unit {
     attached_save(c,"diagnostic_event_native");emit(c,arm64.sub_imm_x(31,31,32,iie));emit(c,arm64.read_nzcv(9));emit(c,arm64.str_x(9,31,8));
     wr_imports(c,p,first);arm64.assembler_bl(c,"attached_platform_now");emit(c,arm64.str_x(0,31,0));
     attached_data_address(c,p,first+3400,9);
     arm64.assembler_label(c,"diagnostic_reserve");emit(c,arm64.ldxr_x(10,9,hai));emit(c,arm64.add_imm_x(11,10,1,iie));emit(c,arm64.stxr_x(12,11,9,hai));arm64.assembler_cbnz_x(c,12,"diagnostic_reserve");
     emit(c,arm64.cmp_imm_x(10,500,iie));arm64.assembler_b_cond(c,2,"diagnostic_overflow");emit(c,arm64.dmb_ish());
     wr_num(c,12,64);emit(c,arm64.mul_x(13,10,12));emit(c,arm64.add_x(13,9,13));emit(c,arm64.add_imm_x(13,13,64,iie));
     emit(c,arm64.ldr_x(12,31,176));emit(c,arm64.str_x(12,13,8));emit(c,arm64.ldr_x(12,31,184));emit(c,arm64.str_x(12,13,16));emit(c,arm64.ldr_x(12,31,160));emit(c,arm64.str_x(12,13,24));
     old_control(c,p,first,14);arm64.assembler_cbz_x(c,14,"diagnostic_no_control");emit(c,arm64.add_imm_x(15,14,704,iie));emit(c,arm64.ldar_x(12,15));emit(c,arm64.str_x(12,13,32));emit(c,arm64.add_imm_x(15,14,712,iie));emit(c,arm64.ldar_x(12,15));emit(c,arm64.str_x(12,13,40));
     arm64.assembler_label(c,"diagnostic_no_control");wr_ctx(c,p,first,14,0);emit(c,arm64.add_imm_x(14,14,456,iie));emit(c,arm64.ldar_x(12,14));emit(c,arm64.str_x(12,13,48));emit(c,arm64.ldr_x(12,31,0));emit(c,arm64.str_x(12,13,56));emit(c,arm64.stlr_x(11,13));
     arm64.assembler_label(c,"diagnostic_overflow");emit(c,arm64.ldr_x(9,31,8));emit(c,arm64.write_nzcv(9));emit(c,arm64.add_imm_x(31,31,32,iie));attached_restore(c);
     attached_save(c,"diagnostic_report");attached_data_address(c,p,first+3400,1);wr_num(c,0,2);wr_num(c,2,32064);wr_num(c,16,4);emit(c,arm64.svc(128));attached_restore(c);
    }
    '''
    s=replace(s,'    kaku functions=gc.worker_thread_program(iie);','    diagnostic_runtime(c,p,first);\n    kaku functions=gc.worker_thread_program(iie);')
    s=replace(s,'    kaku bindings=darwin.worker_bindings();','    kaku diagnostic=ir.function("diagnostic_event");ir.call(diagnostic,298,3,[0,1,2]);ir.put(diagnostic,ir.result,0,3,0,0);array.push(functions,diagnostic);\n    kaku bindings=darwin.worker_bindings();array.push(bindings,ir.Binding {operation:298,slot:30,arguments:[0,1,2],result_bits:64});')
    s=replace(s,'emit(c,arm64.str_x(0,26,8656));','emit(c,arm64.str_x(0,26,8656));diagnostic_emit(c,p,first,10,26,31);')
    s=replace(s,'emit(c,arm64.blr_x(16));','diagnostic_emit(c,p,first,11,26,31);emit(c,arm64.blr_x(16));diagnostic_emit(c,p,first,12,26,31);')
    s=replace(s,'    move_x(c,0,26);wr_call(c,"thread_leave");','    diagnostic_emit(c,p,first,13,26,31);move_x(c,0,26);wr_call(c,"thread_leave");diagnostic_emit(c,p,first,14,26,31);')
    s=replace(s,'emit(c,arm64.str_x(31,26,gc.thread_user));emit(c,arm64.movz_x(0,0,0));stw_bridge_leave(c);','emit(c,arm64.str_x(31,26,gc.thread_user));diagnostic_emit(c,p,first,15,26,31);emit(c,arm64.movz_x(0,0,0));stw_bridge_leave(c);')
    s=replace(s,'attached_save(c,"attached_worker_join");','attached_save(c,"attached_worker_join");diagnostic_emit(c,p,first,20,31,0);')
    s=replace(s,'wr_call(c,"thread_wait_completion");','diagnostic_emit(c,p,first,21,0,31);wr_call(c,"thread_wait_completion");diagnostic_emit(c,p,first,22,0,31);')
    s=replace(s,'    attached_save(c,"attached_worker_collect");','    attached_save(c,"attached_worker_collect");emit(c,arm64.cmp_imm_x(0,0,iie));\n    emit(c,arm64.ldr_x(9,31,144));emit(c,arm64.cmp_imm_x(9,0,iie));arm64.assembler_b_cond(c,1,"diagnostic_not_minor");wr_current(c,p,first);diagnostic_emit(c,p,first,40,0,31);arm64.assembler_label(c,"diagnostic_not_minor");')
    s=replace(s,'arm64.assembler_label(c,"worker_minor");arm64.assembler_bl(c,"gen_minor");','arm64.assembler_label(c,"worker_minor");diagnostic_emit(c,p,first,41,31,31);arm64.assembler_bl(c,"gen_minor");diagnostic_emit(c,p,first,42,31,31);')
    # report only after all real owners are joined, before control mapping is freed
    p.write_text(s)
    edit('bunko/kiso/aot/lower/old_sweep.mio',lambda s:replace(s,'attached_restore(c);\n}', 'arm64.assembler_bl(c,"diagnostic_report");attached_restore(c);\n}'))
    # Trace Phase query's actual returned value without changing it.
    edit('bunko/kiso/aot/lower/old_sweep.mio',lambda s:replace(s,'emit(c,arm64.ldar_x(0,9));old_result(c,0);arm64.assembler_label(c,next);i=i+1;}','emit(c,arm64.ldar_x(0,9));moshi(modes[i]==20){diagnostic_emit(c,p,first,31,31,0);}old_result(c,0);arm64.assembler_label(c,next);i=i+1;}'))
    # Portable instrumentation around actual operations. It changes no protocol decision.
    edit('bunko/kiso/runtime/gc/threads.mio',lambda s:replace(replace(s,'ir.branch(f,ir.label,0,"unlinked");tinc(f,thread_exits);','ir.branch(f,ir.label,0,"unlinked");'+ev(16)+'tinc(f,thread_exits);'),'tload(f,2,thread_handle);tconstant(f,3,0);tcall(f,thread_join,1,[2,3],faults);','tload(f,2,thread_handle);tconstant(f,3,0);'+ev(23,'0','2')+'tcall(f,thread_join,1,[2,3],faults);'+ev(24,'0','1')))
    p=snap/'bunko/kiso/runtime/gc/mutators.mio';s=p.read_text();start=s.index('waza gc_block_leave_program');end=s.index('waza thread_wait_started_program');part=s[start:end];part=replace(part,'tprepare(f);','tprepare(f);'+ev(25));part=replace(part,'treturn(f,0);',''+ev(26)+'treturn(f,0);');s=s[:start]+part+s[end:];p.write_text(s)
    
    p=snap/'bunko/kiso/runtime/gc/old_sweep.mio';s=p.read_text();s=replace(s,'ir.branch(f,ir.label,0,"begin");','ir.branch(f,ir.label,0,"begin");'+ev(1));s=replace(s,'ir.branch(f,ir.label,0,"complete");tconstant(f,5,3);ir.put(f,ir.release_store,0,0,5,712);','ir.branch(f,ir.label,0,"complete");'+ev(2)+'tconstant(f,5,3);ir.put(f,ir.release_store,0,0,5,712);'+ev(3));p.write_text(s)
    p=snap/'bunko/kiso/aot/lower/worker_roots.mio'
    s=p.read_text()
    # A separate adapter owns the schedule. No production GC decision changes.
    s=s.replace('arm64.assembler_label(c,"diagnostic_overflow");emit(c,arm64.ldr_x(9,31,8));', 'arm64.assembler_label(c,"diagnostic_overflow");emit(c,arm64.ldr_x(0,31,176));emit(c,arm64.ldr_x(1,31,184));emit(c,arm64.ldr_x(2,31,160));arm64.assembler_bl(c,"e5_test_schedule");emit(c,arm64.ldr_x(9,31,8));')
    # An ordinary callback reaches this bridge through compiler-generated roots.
    s=s.replace('    attached_save(c,"attached_worker_collect");', '''    attached_save(c,"attached_worker_collect");
    emit(c,arm64.ldr_x(9,31,144));emit(c,arm64.cmp_imm_x(9,46,iie));arm64.assembler_b_cond(c,1,"e5_not_rendezvous");
    wr_poll(c,p,first,"gc_block_enter");diagnostic_emit(c,p,first,52,31,31);wr_current(c,p,first);wr_call(c,"gc_block_leave");emit(c,arm64.str_x(31,31,144));attached_restore(c);arm64.assembler_label(c,"e5_not_rendezvous");''')
    s += '''
// TEST ONLY. Two-way Epoch1 rendezvous at a genuine unlocked batch boundary.
// Main/worker waits publish blocked precise roots via the production protocol.
waza e5_test_schedule_runtime(c:arm64.Assembler,p:[]macho.AddressPatch,first:int64) -> unit {
 attached_save(c,"e5_test_schedule");old_control(c,p,first,19);arm64.assembler_cbz_x(c,19,"e5_schedule_done");
 emit(c,arm64.add_imm_x(9,19,704,iie));emit(c,arm64.ldar_x(10,9));emit(c,arm64.cmp_imm_x(10,1,iie));arm64.assembler_b_cond(c,1,"e5_schedule_done");
 attached_data_address(c,p,first+3401,20);emit(c,arm64.ldr_x(21,31,144));
 emit(c,arm64.cmp_imm_x(21,50,iie));arm64.assembler_b_cond(c,0,"e5_wait_ready");
 emit(c,arm64.cmp_imm_x(21,51,iie));arm64.assembler_b_cond(c,0,"e5_batch_done");
 emit(c,arm64.cmp_imm_x(21,52,iie));arm64.assembler_b_cond(c,0,"e5_user_ready");
 emit(c,arm64.cmp_imm_x(21,24,iie));arm64.assembler_b_cond(c,1,"e5_schedule_done");
 emit(c,arm64.ldr_x(9,31,128));arm64.assembler_cbnz_x(c,9,"e5_schedule_done");
 wr_ctx(c,p,first,9,2);emit(c,arm64.ldr_x(10,31,152));emit(c,arm64.cmp_x(9,10));arm64.assembler_b_cond(c,1,"e5_schedule_done");
 wr_num(c,9,1);emit(c,arm64.add_imm_x(10,20,16,iie));emit(c,arm64.stlr_x(9,10));
 // Regression: delay observer until the actual Collector has finished normally.
 emit(c,arm64.add_imm_x(20,19,712,iie));wr_num(c,22,3);arm64.assembler_b(c,"e5_wait");
 arm64.assembler_label(c,"e5_user_ready");wr_num(c,9,1);emit(c,arm64.stlr_x(9,20));emit(c,arm64.add_imm_x(20,20,8,iie));wr_num(c,22,1);arm64.assembler_b(c,"e5_wait");
 arm64.assembler_label(c,"e5_batch_done");emit(c,arm64.add_imm_x(10,20,8,iie));emit(c,arm64.ldar_x(9,10));arm64.assembler_cbnz_x(c,9,"e5_schedule_done");wr_num(c,9,1);emit(c,arm64.stlr_x(9,10));emit(c,arm64.add_imm_x(20,20,16,iie));wr_num(c,22,1);arm64.assembler_b(c,"e5_wait");
 arm64.assembler_label(c,"e5_wait_ready");wr_num(c,22,1);
 arm64.assembler_label(c,"e5_wait");wr_imports(c,p,first);arm64.assembler_bl(c,"attached_platform_now");move_x(c,23,0);wr_num(c,9,10000000000);emit(c,arm64.add_x(23,23,9));
 arm64.assembler_label(c,"e5_wait_loop");emit(c,arm64.ldar_x(9,20));emit(c,arm64.cmp_x(9,22));arm64.assembler_b_cond(c,0,"e5_schedule_done");
 wr_imports(c,p,first);arm64.assembler_bl(c,"attached_platform_now");emit(c,arm64.cmp_x(0,23));arm64.assembler_b_cond(c,3,"e5_wait_loop");arm64.assembler_b(c,"runtime_error");
 arm64.assembler_label(c,"e5_schedule_done");attached_restore(c);
}
'''
    s=s.replace('    diagnostic_runtime(c,p,first);', '    e5_test_schedule_runtime(c,p,first);diagnostic_runtime(c,p,first);')
    p.write_text(s)
    p=snap/'bunko/kiso/runtime/gc/old_sweep.mio';s=p.read_text()
    s=replace(s, 'ir.branch(f,ir.label,0,"begin");'+ev(1), 'ir.branch(f,ir.label,0,"begin");'+ev(1)+ev(50))
    s=replace(s, 'ir.branch(f,ir.nonzero,5,"failed");tcheck(f,21,1,"complete");', 'ir.branch(f,ir.nonzero,5,"failed");'+ev(51)+'tcheck(f,21,1,"complete");')
    p.write_text(s)
    p=snap/'bunko/kiso/aot/lower/worker_roots.mio';s=p.read_text()
    s=s.replace('attached_save(c,"e5_test_schedule");old_control', 'attached_save(c,"e5_test_schedule");emit(c,arm64.stp_pre_x(19,20,31,-16));emit(c,arm64.stp_pre_x(21,22,31,-16));emit(c,arm64.stp_pre_x(23,24,31,-16));old_control')
    start=s.index('waza e5_test_schedule_runtime');head=s[:start];tail=s[start:]
    tail=tail.replace('ldr_x(21,31,144)', 'ldr_x(21,31,192)').replace('ldr_x(9,31,128)', 'ldr_x(9,31,176)').replace('ldr_x(10,31,152)', 'ldr_x(10,31,200)')
    tail=tail.replace('wr_num(c,9,10000000000)', 'move_bits(c,9,uint32(2),uint32(1410065408))')
    tail=tail.replace('arm64.assembler_label(c,"e5_schedule_done");attached_restore(c);', 'arm64.assembler_label(c,"e5_schedule_done");emit(c,arm64.ldp_post_x(23,24,31,16));emit(c,arm64.ldp_post_x(21,22,31,16));emit(c,arm64.ldp_post_x(19,20,31,16));attached_restore(c);')
    s=head+tail
    p.write_text(s)

    p=snap/'bunko/kiso/aot/lower/worker_roots.mio';s=p.read_text()
    markers=''
    for mode,event in ((47,57),(48,58)):
        markers+=f'emit(c,arm64.ldr_x(9,31,144));emit(c,arm64.cmp_imm_x(9,{mode},iie));arm64.assembler_b_cond(c,1,"e5_not_marker_{mode}");wr_current(c,p,first);diagnostic_emit(c,p,first,{event},0,31);emit(c,arm64.str_x(31,31,144));attached_restore(c);arm64.assembler_label(c,"e5_not_marker_{mode}");'
    s=s.replace('arm64.assembler_label(c,"e5_not_rendezvous");', 'arm64.assembler_label(c,"e5_not_rendezvous");'+markers)
    p.write_text(s)
    p=snap/'bunko/kiso/aot/lower/worker_roots.mio';s=p.read_text()
    # Suppress subsequent batch notifications BEFORE reserving trace slots.
    # The first rendezvous remains recorded; normal batches still execute.
    needle='emit(c,arm64.str_x(9,31,8));'
    assert s.count(needle)==1
    s=s.replace(needle,needle+'emit(c,arm64.ldr_x(9,31,176));emit(c,arm64.cmp_imm_x(9,51,iie));arm64.assembler_b_cond(c,1,"e5_record_event");attached_data_address(c,p,first+3402,9);emit(c,arm64.ldar_x(9,9));arm64.assembler_cbnz_x(c,9,"diagnostic_overflow");arm64.assembler_label(c,"e5_record_event");')
    p.write_text(s)

    p=snap/'bunko/kiso/aot/lower/worker_roots.mio';s=p.read_text()
    s=s.replace('arm64.assembler_label(c,"e5_not_rendezvous");', 'arm64.assembler_label(c,"e5_not_rendezvous");emit(c,arm64.ldr_x(9,31,144));emit(c,arm64.cmp_imm_x(9,49,iie));arm64.assembler_b_cond(c,1,"e5_not_fatal_rendezvous");wr_poll(c,p,first,"gc_block_enter");diagnostic_emit(c,p,first,53,31,31);wr_current(c,p,first);wr_call(c,"gc_block_leave");emit(c,arm64.str_x(31,31,144));attached_restore(c);arm64.assembler_label(c,"e5_not_fatal_rendezvous");')
    s=s.replace('emit(c,arm64.cmp_imm_x(21,52,iie));', 'emit(c,arm64.cmp_imm_x(21,53,iie));arm64.assembler_b_cond(c,0,"e5_fatal_ready");emit(c,arm64.cmp_imm_x(21,52,iie));')
    s=s.replace('arm64.assembler_label(c,"e5_user_ready");', 'arm64.assembler_label(c,"e5_fatal_ready");wr_num(c,9,1);emit(c,arm64.add_imm_x(10,20,24,iie));emit(c,arm64.stlr_x(9,10));arm64.assembler_label(c,"e5_user_ready");')
    s=s.replace('emit(c,arm64.stlr_x(9,10));emit(c,arm64.add_imm_x(20,20,16,iie));wr_num(c,22,1);', 'emit(c,arm64.stlr_x(9,10));emit(c,arm64.add_imm_x(10,20,24,iie));emit(c,arm64.ldar_x(9,10));arm64.assembler_cbnz_x(c,9,"e5_wait_cancel");emit(c,arm64.add_imm_x(20,20,16,iie));wr_num(c,22,1);')
    s=s.replace('arm64.assembler_label(c,"e5_wait_ready");', 'arm64.assembler_label(c,"e5_wait_cancel");emit(c,arm64.add_imm_x(20,19,712,iie));wr_num(c,22,4);arm64.assembler_b(c,"e5_wait");arm64.assembler_label(c,"e5_wait_ready");')
    p.write_text(s)
    p=snap/'bunko/kiso/runtime/gc/old_sweep.mio';s=p.read_text();start=s.index('waza sweep_cancel_old_program()');head=s[:start];tail=s[start:]
    tail=replace(tail,'tconstant(f,5,4);ir.put(f,ir.release_store,0,0,5,712);',ev(54)+'tconstant(f,5,4);ir.put(f,ir.release_store,0,0,5,712);'+ev(55))
    p.write_text(head+tail)
