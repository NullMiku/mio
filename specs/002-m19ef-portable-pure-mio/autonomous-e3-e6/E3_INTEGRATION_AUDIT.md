# E3 automatic root integration audit — 2026-10-30 (development)

E3 IN_PROGRESS. E4/E5/E6 NOT_RUN. M19e NOT_ACCEPTED.

The archive supplement was installed without overwriting existing files. Its
13 installed files match the ZIP byte-for-byte; the archive path/symlink and
SHA256 audit is in `build/m19ef-evidence/E3-auto-roots-20261030-01/`.
The previous E3 -05 evidence was independently checked: 98 successful bounded
commands, 176 frozen Mio input files matching their manifest. Those results are
historical scoped evidence, not acceptance of the changed source here.

## Concrete implementation in this continuation

- Portable `runtime/gc/threads.mio`: `thread_attach` attaches the calling thread
  to the v3 registry, acquires TLS/mutex/condition resources, uses the existing
  `thread_enter` protocol and rolls back through ownership-aware `thread_close`.
  It creates no fake worker and never claims a native create/join occurred.
- `aot/lower/attached_roots.mio`: separate Darwin/AArch64 adapter for startup,
  actual pthread TLS lookup, release publication, cooperative polling, detach
  and cleanup. Context/registry/diagnostic storage is appended after all user
  and existing private data. No frozen object or heap metadata offsets change.
- `lower.mio`: internal `compile_with_attached_roots` selects this adapter.
  Solved opcode-entry state supplies locals, globals, cells, closure environment
  and live operands. Polls happen before opcode operand mutation, including
  loop backedges, calls and explicit returns. Existing transient caller frames
  protect call arguments. Shadow push/pop publish the new head; pop publication
  preserves the result in x0. Adapter calls preserve x0–x17 and LR; x18 remains
  reserved, x19–x28 retain the established native ABI.
- Ordinary test sources contain no manual Root/TLS/registry calls. The native
  Mio builder invokes the real source frontend, lowering, Darwin linker and
  Mio signer. Native binaries and real runtime counters must be checked before
  this slice is described as verified.

## Boundaries still open

This is an opt-in **main-thread** integration path. It rejects TLS from a foreign
thread and leaves precise managed threading/concurrent capability flags false.
It does not yet expose a language thread API or run ordinary language functions
on two managed mutators. Legacy allocation still collects through the executing
thread's exact chain; it has not been replaced by all-mutator snapshots in this
compiler path. The prior runtime-IR two-mutator fixture remains a separate test.

NativeFS/public blocking calls still need the compiled blocked/resume protocol.
Internal runtime loops need latency bounds, and all error/exit paths and attach
resource failures require adversarial validation. Runtime extension accounting
and final embedded Bunko resource regeneration remain necessary for acceptance.

Therefore G3.1–G3.7 are not collectively PASS. SATB, concurrent tracing/sweep,
atomic eight-field snapshots and new source-level Seed→A→B→C→D remain unimplemented
or unverified. Do not start E4 implementation or relabel a previous fixed point.
