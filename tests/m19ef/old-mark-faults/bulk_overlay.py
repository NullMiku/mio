"""Test-only same-Epoch white-edge rendezvous; never edit production GC.

Collector stays outside queue/heap locks before its first take until a REAL
Old-white prewrite publishes counter440. It continues servicing the production
pause/ack/release protocol and the original deadline/abort path. No work, color,
counter, phase or root is fabricated. Other E4 workloads remain ungated and
must independently witness actual in-scan Collector/Mutator overlap.
"""
def install(snapshot):
    path=snapshot/'bunko/kiso/runtime/gc/old_mark.mio'
    source=path.read_text()
    anchor='tcheck(f,5,old_phase_abort,"done");ir.invoke_function(f,"gc_work_take",5,[0,16,17]);'
    assert source.count(anchor)==1
    gate=('tcheck(f,5,old_phase_abort,"done");'
          'ir.put(f,ir.acquire_load,6,0,0,440);'
          'ir.branch(f,ir.zero,6,"deadline");'
          'ir.invoke_function(f,"gc_work_take",5,[0,16,17]);')
    path.write_text(source.replace(anchor,gate))
