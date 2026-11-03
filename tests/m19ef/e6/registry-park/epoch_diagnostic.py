"""Failure-only native STW diagnostics in a copied adapter/Core; no GC work edits."""
from pathlib import Path

def install(root:Path):
 p=root/'bunko/kiso/runtime/gc/threads.mio';s=p.read_text()
 marker='ir.branch(f,ir.label,0,"timeout");treturn(f,2);'
 assert s.count(marker)==1
 save='tconstant(f,20,7001);ir.put(f,ir.store,0,0,20,8712);'
 for reg,off in [(6,8720),(4,8728),(12,8736),(15,8744),(16,8752),(11,8760),(13,8768)]:save+=f'ir.put(f,ir.store,0,0,{reg},{off});'
 save+='tload(f,17,thread_registry);ir.put(f,ir.acquire_load,18,17,0,gc_registry_epoch);ir.put(f,ir.store,0,0,18,8776);ir.put(f,ir.acquire_load,18,17,0,gc_registry_owner);ir.put(f,ir.store,0,0,18,8784);ir.put(f,ir.store,0,0,0,8792);'
 p.write_text(s.replace(marker,'ir.branch(f,ir.label,0,"timeout");'+save+'treturn(f,2);'))
 p=root/'bunko/kiso/runtime/gc/safepoints.mio';s=p.read_text();marker='ir.branch(f,ir.label,0,"abort");ir.invoke_function(f,"gc_end",2,[0]);treturn(f,2);';assert s.count(marker)==1
 save='tconstant(f,22,7002);ir.put(f,ir.store,0,0,22,8712);'
 for reg,off in [(21,8720),(20,8728),(13,8736),(18,8744),(15,8752),(16,8760),(17,8768)]:save+=f'ir.put(f,ir.store,0,0,{reg},{off});'
 save+='tload(f,24,thread_registry);ir.put(f,ir.acquire_load,25,24,0,gc_registry_epoch);ir.put(f,ir.store,0,0,25,8776);ir.put(f,ir.acquire_load,25,24,0,gc_registry_owner);ir.put(f,ir.store,0,0,25,8784);ir.put(f,ir.store,0,0,0,8792);'
 p.write_text(s.replace(marker,'ir.branch(f,ir.label,0,"abort");'+save+'ir.invoke_function(f,"gc_end",2,[0]);treturn(f,2);'))
 p=root/'bunko/kiso/aot/lower/worker_roots.mio';s=p.read_text();marker='waza wr_call(c:arm64.Assembler,name:string) -> unit {arm64.assembler_bl(c,string.concat("attached_",name));arm64.assembler_cbnz_x(c,0,"runtime_error");}';assert s.count(marker)==1
 s=s.replace(marker,'waza wr_call(c:arm64.Assembler,name:string) -> unit {arm64.assembler_bl(c,string.concat("attached_",name));kaku failure="runtime_error";moshi(name=="gc_heap_enter"){failure="epoch_failure_diagnostic";}arm64.assembler_cbnz_x(c,0,failure);}')
 marker='    // The legacy allocator may collect, so it sees a coordinator-owned complete';assert s.count(marker)==1
 body='''    arm64.assembler_label(c,"epoch_failure_diagnostic");emit(c,arm64.sub_imm_x(31,31,16,iie));emit(c,arm64.str_x(0,31,0));emit(c,arm64.str_x(30,31,8));wr_current(c,p,first);emit(c,arm64.add_imm_x(1,0,4095,iie));emit(c,arm64.add_imm_x(1,1,4095,iie));emit(c,arm64.add_imm_x(1,1,522,iie));wr_num(c,0,2);wr_num(c,2,88);wr_num(c,16,4);emit(c,arm64.svc(128));emit(c,arm64.ldr_x(0,31,0));emit(c,arm64.ldr_x(30,31,8));emit(c,arm64.add_imm_x(31,31,16,iie));arm64.assembler_b(c,"runtime_error");
'''
 s=s.replace(marker,body+marker);p.write_text(s)
