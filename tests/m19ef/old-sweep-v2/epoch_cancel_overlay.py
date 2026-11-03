"""Test-only same-Epoch cancellation rendezvous after real unlocked Sweep work.
Never used for ungated overlap acceptance. No mark/clear/accounting work changed.
"""
from pathlib import Path

def install(root:Path):
 def edit(rel,a,b):
  p=root/rel;s=p.read_text();assert s.count(a)==1,(rel,a,s.count(a));p.write_text(s.replace(a,b))
 edit('bunko/kiso/aot/lower/worker_roots.mio','worker_root_words=3304','worker_root_words=3500')
 edit('bunko/kiso/aot/lower/old_sweep.mio','concurrent_old_root_words=3306','concurrent_old_root_words=3502')
 edit('bunko/kiso/aot/lower/old_sweep.mio','kaesu 30;','kaesu 31;')
 edit('bunko/kiso/aot/lower/worker_roots.mio','["worker_sweep_account","worker_sweep_unmap"]','["worker_sweep_account","worker_sweep_unmap","epoch_cancel_gate_native"]')
 edit('bunko/kiso/aot/lower/worker_roots.mio','    kaku functions=gc.worker_thread_program(iie);','    epoch_cancel_runtime(c,p,first);\n    kaku functions=gc.worker_thread_program(iie);')
 edit('bunko/kiso/aot/lower/worker_roots.mio','    kaku bindings=darwin.worker_bindings();','    kaku gate=ir.function("epoch_cancel_gate");ir.call(gate,299,5,[0]);ir.put(gate,ir.result,0,5,0,0);array.push(functions,gate);\n    kaku bindings=darwin.worker_bindings();array.push(bindings,ir.Binding {operation:299,slot:30,arguments:[0],result_bits:64});')
 edit('bunko/kiso/runtime/gc/old_sweep.mio','tcheck(f,21,1,"complete");ir.branch(f,ir.nonzero,21,"step_failed");','ir.invoke_function(f,"epoch_cancel_gate",5,[0]);ir.branch(f,ir.nonzero,5,"failed");tcheck(f,21,1,"complete");ir.branch(f,ir.nonzero,21,"step_failed");')
 edit('bunko/kiso/aot/lower/old_sweep.mio','arm64.assembler_label(c,"sweep_report_no_state");attached_restore(c);','arm64.assembler_label(c,"sweep_report_no_state");arm64.assembler_bl(c,"epoch_cancel_report");attached_restore(c);')
 edit('bunko/kiso/aot/lower/worker_roots.mio','    attached_save(c,"attached_worker_collect");','''    attached_save(c,"attached_worker_collect");
    emit(c,arm64.ldr_x(9,31,144));emit(c,arm64.cmp_imm_x(9,47,iie));arm64.assembler_b_cond(c,1,"epoch_not_arm");
    old_control(c,p,first,10);arm64.assembler_cbz_x(c,10,"runtime_error");attached_data_address(c,p,first+3400,11);wr_num(c,9,1330420001);emit(c,arm64.str_x(9,11,0));wr_num(c,9,1);emit(c,arm64.str_x(9,11,8));emit(c,arm64.ldr_x(9,10,112));arm64.assembler_cbz_x(c,9,"runtime_error");emit(c,arm64.str_x(31,11,24));emit(c,arm64.str_x(31,11,32));emit(c,arm64.str_x(31,11,40));emit(c,arm64.ldr_x(12,11,48));emit(c,arm64.add_imm_x(12,12,1,iie));emit(c,arm64.str_x(12,11,48));emit(c,arm64.add_imm_x(12,11,16,iie));emit(c,arm64.stlr_x(9,12));emit(c,arm64.str_x(9,31,144));attached_restore(c);
    arm64.assembler_label(c,"epoch_not_arm");emit(c,arm64.cmp_imm_x(9,48,iie));arm64.assembler_b_cond(c,1,"epoch_not_wait");arm64.assembler_bl(c,"epoch_cancel_wait");emit(c,arm64.str_x(0,31,144));attached_restore(c);arm64.assembler_label(c,"epoch_not_wait");
''')
 p=root/'bunko/kiso/aot/lower/worker_roots.mio';s=p.read_text();s+='''
// TEST COPY ONLY. All gate state is after the three owned worker contexts.
waza epoch_cancel_save(c:arm64.Assembler,name:string) -> unit {
 arm64.assembler_label(c,name);emit(c,arm64.stp_pre_x(19,20,31,-16));emit(c,arm64.stp_pre_x(21,22,31,-16));emit(c,arm64.stp_pre_x(29,30,31,-16));
}
waza epoch_cancel_return(c:arm64.Assembler) -> unit {emit(c,arm64.ldp_post_x(29,30,31,16));emit(c,arm64.ldp_post_x(21,22,31,16));emit(c,arm64.ldp_post_x(19,20,31,16));emit(c,arm64.ret());}
waza epoch_cancel_runtime(c:arm64.Assembler,p:[]macho.AddressPatch,first:int64) -> unit {
 epoch_cancel_save(c,"epoch_cancel_gate_native");move_x(c,19,0);attached_data_address(c,p,first+3400,20);emit(c,arm64.add_imm_x(9,20,16,iie));emit(c,arm64.ldar_x(10,9));emit(c,arm64.add_imm_x(9,19,704,iie));emit(c,arm64.ldar_x(11,9));emit(c,arm64.cmp_x(10,11));arm64.assembler_b_cond(c,1,"epoch_gate_done");arm64.assembler_cbz_x(c,10,"epoch_gate_done");
 // Called only after a completed real batch and production lock release.
 emit(c,arm64.ldr_x(9,19,552));arm64.assembler_cbz_x(c,9,"epoch_gate_error");emit(c,arm64.str_x(9,20,32));emit(c,arm64.ldr_x(9,19,536));arm64.assembler_cbz_x(c,9,"epoch_gate_error");emit(c,arm64.str_x(9,20,40));emit(c,arm64.ldr_x(9,20,56));emit(c,arm64.add_imm_x(9,9,1,iie));emit(c,arm64.str_x(9,20,56));emit(c,arm64.str_x(11,20,72));emit(c,arm64.add_imm_x(9,20,24,iie));emit(c,arm64.stlr_x(11,9));
 wr_imports(c,p,first);arm64.assembler_bl(c,"attached_platform_now");move_bits(c,9,uint32(6),uint32(4230196224));emit(c,arm64.add_x(21,0,9));
 arm64.assembler_label(c,"epoch_gate_wait");emit(c,arm64.add_imm_x(9,19,712,iie));emit(c,arm64.ldar_x(10,9));emit(c,arm64.cmp_imm_x(10,2,iie));arm64.assembler_b_cond(c,1,"epoch_gate_cancelled");wr_imports(c,p,first);arm64.assembler_bl(c,"attached_platform_now");emit(c,arm64.cmp_x(0,21));arm64.assembler_b_cond(c,3,"epoch_gate_wait");arm64.assembler_b(c,"epoch_gate_error");
 arm64.assembler_label(c,"epoch_gate_cancelled");emit(c,arm64.cmp_imm_x(10,4,iie));arm64.assembler_b_cond(c,1,"epoch_gate_error");emit(c,arm64.ldr_x(9,20,64));emit(c,arm64.add_imm_x(9,9,1,iie));emit(c,arm64.str_x(9,20,64));
 arm64.assembler_label(c,"epoch_gate_done");wr_num(c,0,0);epoch_cancel_return(c);
 arm64.assembler_label(c,"epoch_gate_error");emit(c,arm64.ldr_x(9,20,88));emit(c,arm64.add_imm_x(9,9,1,iie));emit(c,arm64.str_x(9,20,88));wr_num(c,0,4);epoch_cancel_return(c);
 epoch_cancel_save(c,"epoch_cancel_wait");wr_poll(c,p,first,"gc_block_enter");wr_current(c,p,first);move_x(c,19,0);attached_data_address(c,p,first+3400,20);wr_imports(c,p,first);arm64.assembler_bl(c,"attached_platform_now");move_bits(c,9,uint32(6),uint32(4230196224));emit(c,arm64.add_x(22,0,9));
 arm64.assembler_label(c,"epoch_main_wait");emit(c,arm64.add_imm_x(9,20,24,iie));emit(c,arm64.ldar_x(21,9));emit(c,arm64.add_imm_x(9,20,16,iie));emit(c,arm64.ldar_x(10,9));arm64.assembler_cbz_x(c,10,"runtime_error");emit(c,arm64.cmp_x(21,10));arm64.assembler_b_cond(c,0,"epoch_main_ready");wr_imports(c,p,first);arm64.assembler_bl(c,"attached_platform_now");emit(c,arm64.cmp_x(0,22));arm64.assembler_b_cond(c,3,"epoch_main_wait");arm64.assembler_b(c,"runtime_error");
 arm64.assembler_label(c,"epoch_main_ready");emit(c,arm64.ldr_x(9,19,gc.thread_registry));emit(c,arm64.add_imm_x(9,9,gc.gc_registry_epoch,iie));emit(c,arm64.ldar_x(10,9));emit(c,arm64.str_x(10,20,96));emit(c,arm64.add_imm_x(9,19,gc.thread_progress,iie));emit(c,arm64.ldar_x(10,9));emit(c,arm64.cmp_imm_x(10,gc.thread_parked,iie));arm64.assembler_b_cond(c,1,"runtime_error");emit(c,arm64.str_x(10,20,104));emit(c,arm64.str_x(19,20,112));emit(c,arm64.ldr_x(9,19,gc.thread_identity_value));emit(c,arm64.str_x(9,20,120));wr_current(c,p,first);wr_call(c,"gc_block_leave");move_x(c,0,21);epoch_cancel_return(c);
 attached_save(c,"epoch_cancel_report");attached_data_address(c,p,first+3400,1);wr_num(c,0,2);wr_num(c,2,128);wr_num(c,16,4);emit(c,arm64.svc(128));attached_restore(c);
}
''';p.write_text(s)
 # Ordinary source fixtures use private rendezvous opcodes only in this copy.
 p=root/'tests/m19ef/old-sweep-v2/epochs-cancel.mio';s=p.read_text()
 old='signal[0]=1;kaku baseline_a=signal[2];kaku baseline_b=signal[3];kaku marked=rt_collect(3);kaku expected_epoch=rt_collect(17);kaku cancelling=cycle-(cycle/3)*3==0;'
 assert s.count(old)==1
 s=s.replace(old,'signal[0]=1;kaku baseline_a=signal[2];kaku baseline_b=signal[3];kaku cancelling=cycle-(cycle/3)*3==0;moshi(cancelling){rt_collect(47);}kaku marked=rt_collect(3);kaku expected_epoch=rt_collect(17);moshi(cancelling){rt_collect(48);}')
 p.write_text(s)
 for case in ('reenter','shutdown','oom','oom-bound'):
  p=root/'tests/m19ef/old-sweep'/case/'main.mio';s=p.read_text()
  if case=='reenter':
   old='kaku marked=rt_collect(3);signal[0]=1;kaku phase_before=rt_collect(20);';new='rt_collect(47);kaku marked=rt_collect(3);signal[0]=1;rt_collect(48);kaku phase_before=rt_collect(20);'
  elif case=='shutdown':old='chant(rt_collect(3));signal[0]=1;chant(rt_collect(20));';new='rt_collect(47);chant(rt_collect(3));signal[0]=1;rt_collect(48);chant(rt_collect(20));'
  else:old='chant(rt_collect(3));chant(rt_collect(20));';new='rt_collect(47);chant(rt_collect(3));rt_collect(48);chant(rt_collect(20));'
  assert s.count(old)==1,(case,old);p.write_text(s.replace(old,new))
