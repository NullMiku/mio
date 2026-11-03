# E4 implementation boundary (investigation, not acceptance)

E4 NOT_RUN/NOT_ACCEPTED. This document contains inspected gaps and candidate
invariants only. No concurrent marker, SATB queue, scanner or sweeper described
below has been implemented or validated. E3 must finish first.

## Existing production stores requiring SATB review

| Store path | Current mechanism | E4 work |
|---|---|---|
| lower opcode19 global | solved global slot store, E3 heap epoch | typed old-value prewrite |
| opcode23 captured local Cell | Cell.value + remembered owner | prewrite Cell.value |
| opcode48 upvalue | captured Cell.value + remembered owner | same prewrite |
| Struct setter | typed fields, bitmap, remembered owner | old field before overwrite |
| Array index/set | typed storage slot and remembered storage | prewrite pointer-layout slot |
| forwarded array.push/append/reserve/truncate | runtime storage copy/replace/zero | cover old storage link, replaced or cleared slots and batch operations |
| Map put/delete/growth | descriptor/entries storage/value replacement | keys and values by layout; deletion and rehash must not lose old edges |
| Closure/Environment/Cell construction | initialized during E3 stopped epoch | born-object color + complete publication |
| nullable scalar boxing | scalar Cell layout tag | never enqueue numeric bits |
| Enum construction | per-variant bitmap | birth publication; immutable after creation |
| LOS objects | same typed layout, separate owner/list | lifecycle and color must coordinate with Minor |
| native String/ByteArray helpers | strings have no pointer payload; descriptors may link storage | audit pointer-bearing descriptors, not byte bits |
| NativeFS and codegen temporaries | caller roots and helper frames | Init/Remark snapshots include all generated frames |
| Minor promotion/metadata | legacy CPU emitter, E3 stopped heap | coordinate marker pause and born-black Old promotion |

`emit_gen_remember` only performs postwrite old-generation tracking. Calling it
is not SATB. Prewrite must run before overwriting the typed old pointer and be
ordered before publishing the new value. Integer/float slots must not enqueue.

## Portable tracing extraction needed

The actual scanner still lives in lower.mio's emit_runtime_mark (not in the
portable core). Header kind low32:100 Struct bitmap,101 Array storage edge,
102 typed Storage,103 Closure environment,104 Environment cells,105 Cell pointer
flag,106 String bytes/no edges,107 Enum bitmap. Exact pointer edges must move
into neutral scalar IR, with a visitor operation and explicit bounds/error result.
A target adapter supplies word loads/atomics/calls; no CPU assembler belongs in
core. Reusing the legacy marker as a callback does not prove G4.1.

## Candidate synchronization design, still unimplemented

- Separate native collector from the Mutator registry; it must not park for its
  own Init/Remark handshake. Preserve actual clock/identity/phase overlap trace.
- Only stable Old references may remain in the concurrent queue if Minor can
  reclaim Young. Init must account for Young→Old frontier, including Old→Young
  edges whose descendants are Old; simply skipping Young is incorrect.
- Minor must pause/ack the marker before touching generation/color/list state.
  Existing automatic Major-on-eighth-Minor and OOM Major retries must be gated:
  never let the legacy allocator free Old underneath a marker.
- New/promoted Old require a born-black rule; typed prewrite also covers Young
  deletions that can otherwise erase the snapshot's path to Old.
- A bounded publish queue needs linearized ownership and in-flight accounting.
  On full, release queue ownership and allow the real marker to drain, then
  retry while preserving the overwritten old value. Timeout/error aborts the
  mark and forbids reclaim; that fallback cannot count as concurrent PASS.
- Concurrent color must use verified unused metadata/flags and atomic updates
  that preserve Minor age/generation/remembered bits. A second side bitmap or
  header epoch bit is a design choice requiring write-mask audit, not a claim
  that any high bit is already available.
- Remark stops all Mutators, drains in-flight publications and latest roots,
  then proves queue quiescence before ReadyToSweep. E5 owns actual reclaim.

No permanent E3 heap-stop operation can substitute for true Old concurrent
tracing. No old GF4 fixed point can substitute for E6's new full source bootstrap.

## Integration constraints found while E3 candidate16 runs

- Current worker import layout:25 OS symbols (posix_spawn at24), three actual
  callbacks25..27, then three8800-byte contexts. Use a calculated import-count
  helper if E4 adds VM services; do not silently shift fixed callbacks or TLS
  getters. The native linker bounds runtime extension at4096 words. A fourth
  full context plus the queue exceeds that bound: allocate collector control,
  queue and color state via a separate explicit OS adapter mapping instead.
- A collector entry may reuse the OS configured-stack create operation but
  must not call Mutator thread_enter and register as a thread it will stop.
  Keep its native lifecycle/join/error ownership explicit and independently
  traced. E3 main/worker TLS resources remain unchanged in the default path.
- New core scalar IR can express typed scanning using existing unsigned
  divide/multiply/add and explicit bounds; any bit-op extension belongs in IR
  plus CPU lowering and must receive its own native semantic test. Do not put
  ARM64 helpers in gc/ merely for convenience.
- Scanner callback edges must be individually typed: Array storage link,
  Closure environment, Environment cells, Cell tag bit8, Storage pointer flag,
  Struct/Enum bitmap. Header kind and declared payload size bounds precede
  reads; numeric storage and String bytes have no visitor calls. Return a
  failure before any malformed bounds read. Caller supplies valid mapped object
  lifetime; scanner alone cannot prove a queued pointer is still owned.
- A possible internal E4 bridge can add an explicit opt-in mode or operation
  to the existing native start bridge; the accepted E3 path must keep default
  output identical. It must remain clear whether requests are legacy Major,
  Old Init, Remark or Abort, and tests must never call STW Major and report it
  as concurrent Mark. No such mode exists yet.
