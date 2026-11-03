# E4 queue/heap ownership protocol (implementation audit, gates still open)

Current production control extension5; current native candidate is listed in
status.json. This document describes actual code, not blanket E4 acceptance.
GC Core imports neutral IR/array only. CPU/OS services live in adapters.

| State | Owner/writer | Readers/publication |
|---|---|---|
| Registry, user Shadow Frames/TLS | E3 registered Mutators | Init/Remark acquire actual stopped/native-blocked Epoch before merged snapshot; joined/detached frames excluded |
| Queue buffer/head/tail/count/active/closed | Producers and sole collector under strong CAS queue lock | Release unlock / Acquire lock; closure requires queue0/active0/deferred0 under real Remark |
| Work epoch112 | exclusive all-Mutator Init, prior marker joined | transferred through real creation/resume synchronization; monotonic, no live reconfiguration |
| Discovered color41 | neutral visit CAS | Acquire header reads; claim once, exactly one queued or deferred task |
| Deferred flag42 | successful discoverer on full queue; sole marker clears on republish | outstanding104 atomic increment BEFORE Release flag; decrement AFTER offer+CAS clear |
| Deferred count104 | atomic RMW producers / sole marker | Acquire in quiet/Remark, never ignored during termination |
| Telemetry queue increments | queue-lock writer, Release counter stores | Acquire public query; final diagnostic also follows actual join |
| Remembered bit40/list | existing Mutator heap epoch owns list; CAS updates header | preserve concurrent discovered/deferred flags; existing Old→Young semantics retained |
| Ordinary bump/layout, LOS links, Young list, promotions | Mutator heap epoch AFTER marker pause ACK | release resume / acquire gate; marker scans/layout walks finish before ACK |
| Marker current task | sole real independent native worker | active count includes its edge publications until complete |
| Queue/control mapping/handles | main Runtime owns until actual join and all user joins | failed cleanup retains ownership; fatal process teardown is explicit, not a successful reclaim |

The16B header/3072B metadata/LOS prefix sizes remain unchanged. Bits41/42 are
explicit Old-mode flags; current legacy masks preserve them, and Young age
calculation never handles already-Old objects. Versioned private control is512B;
queue data follows it in an independently owned OS mapping. Its space/stacks are
Runtime-private, not user objects. Existing managed working-page accounting is
not a physical-RSS metric; E6 must separately audit/report private Runtime cost.

## Full queue compensation

1. A typed exact Old reference is claimed once by CAS color41.
2. Successful queue offer owns a queued task. Full offer returns1 and increments
   actual overflow96; no pointer is overwritten by the Mutator yet.
3. Discoverer atomically increments outstanding104, then CAS-publishes bit42 in
   the owned header. Only then may prewrite return and release-store the new slot.
4. Empty queue with outstanding tasks makes the independent marker walk real
   owned headers. It republishes flag42 tasks, then atomically clears that flag
   and decrements outstanding. Full/contended reoffer retains flag/count for the
   next bounded walk. Normal enqueued objects do not have flag42.
5. There is exactly one marker/consumer. It cannot consume its own reoffer until
   that walk returns, so a header cannot be reoffered twice before flag clear.
6. Heap layout cannot change during the walk: allocation/Minor requests pause
   and waits until the marker completes its current scan/walk and acknowledges.
   Typed slot updates can still execute and publish more work.

The color-claim→deferred publication gap is covered by one of three real
ownership states: a Mutator producer holds its heap epoch (Remark cannot pass
it), the marker owns an active task, or Init still owns the stopped world before
launch. Thus Remark cannot close while an unpublished claim is in flight.

## Epochs and cancellation

Init accepts fresh control or prior Ready/Abort only after actual handle-join
proof (or no handle was ever created). With user producers parked and collector
joined, it discards old queue state, advances Epoch, clears colors/deferred flags,
rebuilds the complete Young frontier and exact roots, then launches a real worker.
Actual start/join counters remain cumulative; per-cycle tracing counters reset.

Initial stopped-world release is a one-way Release signal296 published AFTER
successful gc_end_base. Sampling current registry.owner would miss a short real
release before the next constructor and deadlock startup against pause ACK; the
retained Minor02 failure demonstrates this. Subsequent pause/request/ack/released
sequences are monotonic and never accept an old ACK. Constructor pause lasts
through its complete heap epoch, including nested promotion.

Intentional cancellation is not a new scanner/type error. A visit that observes
an existing Abort returns a cancellation result; worker propagation preserves
any real first error but does not manufacture another one. Join/OS/clock errors
still latch their actual error and retain ownership. Zero clocks and overflowing
deadlines fail closed rather than extending a wait or fabricating timestamps.

Fatal Old-mode errors use direct Abort/join result handling to avoid recursive
runtime_error. The72B packet records magic/version/phase/error/actual starts/
actual joins/done/joined/cleanup result. A cleanup failure never unmaps active
control or counts a failed join as success. OS process termination subsequently
owns terminal resource teardown; this is not E5 concurrent sweep acceptance.

Current accepted scoped results, failed candidates and remaining gates are in
E4_PROGRESS_20261030.md and the exact evidence directories, not inferred from this
protocol audit. E5 concurrent reclamation, consistent8-field snapshot and new
compiler fixed point remain unfinished.
