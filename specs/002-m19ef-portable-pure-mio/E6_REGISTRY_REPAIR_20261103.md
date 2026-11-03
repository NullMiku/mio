# E6 registry/park protocol repair — 2026-11-03

E6 remains NOT_ACCEPTED. Original Full30, E6-main-final round03, and
E6-main-los-20261103-01 stay FAIL; no historical record is rewritten.

The last full round completed633 fresh E3 commands,687 fresh E4 commands,
8 SATB counterexamples, Known/Unknown4000-read witnesses, then stopped at
E5 epochs-19, native exit1. Its original runtime PC maps to attached_heap_enter
calling gc_heap_enter, status2. This packet alone does not identify which
internal timeout branch fired, and is not used to claim the exact cause closed.

Two independent native protocol components establish and repair real defects:

* Registry acquisition kept the pre-park one-second deadline when a successful
  parked epoch completed without a changed heartbeat. The old signed program
  reports timeout2 with seen2 and the lock already free; the repaired program
  acquires it. Only actual completion publication renews the soft deadline.
  A stalled input still times out, and continuous completion progress still
  stops at the original thirty-second hard limit.
* gc_park_locked sampled the current registry Epoch after observing zero owner.
  A legal next owner could publish Epoch8 before that read, yielding ack7 but
  seen8. The repaired function preserves the last actual parked acknowledgment
  and publishes seen7. No context/object layout or timeout limit changes.

Pure-Mio production changes are confined to gc/threads.mio and
 gc/safepoints.mio for these protocol fixes. GC Core remains target neutral.
The before factories and complete signed native image hashes are retained.
Formal evidence: E6-registry-park-formal-20261103-02. These are explicitly
controlled-input protocol components, never a fabricated collector witness.

Actual production Core/allocator, real two native Mutators and1000 ownership
transfers pass in E6-core-owner-directed-20261103-01, packet
(1000,1002,4,131088):1002 Minor,4 Major and131088 bytes LOS reclamation. This
manual-root fixture is directed protocol coverage, not ordinary-user E3 PASS.
Fresh ordinary-user E3 and a new fixed point remain mandatory.

The separate Epoch test organization bug is documented in E5 contract v2.2.
E6-registry-epochs-directed-20261103-01/epochs-3 exited0 but missed the planned
active cancellation; it stays FAIL. New controlled cancellation/reentry/
shutdown/true-OOM/size-OOM directed cases passed original full native oracles,
with actual same-Epoch partial work+pending claims and production abort/join.
The old packet and70 corrupt gate packets remain rejected. Independent ungated
natural8-Epoch programs passed32/32 before completion-cookie hardening; those
results are historical directed evidence, not a substitute for new-source full
regressions after the final Core change.

Next: native resource refresh, new compiler generations, a new canonical freeze,
fresh E3/E4/E5 v2.2 fixed32 and all E6 gates including all selfhost JSON tests,
actual CLI/LSP and independent signed/raw ABCD B=C=D. No Commit/Push/Tag/Release.
