# E5 acceptance contract v2 — 2026-10-30

This revision is authorized by the user's explicit contract repair request.
Full30 remains FAIL permanently. All old sources, controllers, manifests, logs,
failed samples and event-diagnostic-06 remain immutable historical evidence.
The old `old-sweep/run.py` and `old-sweep/late/main.mio` remain unchanged.

## Why the old assertion is invalid

The Main load after pthread_join and gc_block_leave has no ordering against
Collector Sweep completion. A legal foreign STW owner can delay Main while
Collector finishes. Event-diagnostic-06 sample2 proves native Join success
before Sweep end, followed by Main Phase=3. Acquire does not observe history.
A Phase=2 snapshot also does not prove real user work or kernel termination.

## Evidence and ordering

The versioned test overlay records real lifecycle operations with an AcqRel
LDAXR/STLXR sequence, DMB, and Release per-record commit. Payload fields are
independent observations, not an atomic compound snapshot. Same-Epoch ordering
uses events on both sides of real actions; verification never substitutes a
sampled Phase for lifecycle proof. Overflow, missing records, stale Epoch,
unsuccessful Join or illegal STW owner fails closed.

Required chain in Epoch1: Sweep begin < callback user invocation < callback
rendezvous < actual first batch completion/unlock < user-work begin marker < user-work end marker < actual user return <
registry unlink < leave return < callback last event < successful public native
pthread_join return < Collector's before-Phase3 event < after-Phase3 event.
The callback last event bounds actual native termination from below; successful
pthread_join bounds it above. Both bounds are within Sweep. Registry unlink
alone never proves native termination. No kernel termination timestamp is claimed.

Eight requests, eight real Minor begin/end pairs must occur after the real
batch and before user return in Epoch1. Both Minor endpoints must observe the
actual Worker context as STW owner and Sweep Phase2. The production coordinator,
heap lock, root scan, Minor and gc_end are unchanged. Real live/dead object,
LOS, promotion, reuse, cleanup and public Join checks remain mandatory.

## Deterministic test organization

A test-only two-way Epoch1 rendezvous operates outside the Sweep lock. Collector
waits at entry for the ordinary compiled late callback to publish its precise
roots as blocked through production gc_block_enter. Collector reclaims a real
batch, releases its lock, publishes completion, and waits for successful native
Join. Worker resumes through production gc_block_leave, executes real user
allocations, reads and eight Minors, then exits. Main's successful native Join
releases Collector and waits for the real Phase3 transition before resuming.
No fixed sleep, increased workload, fake reclaim or production state transition
is used. Every later Sweep batch and the entire second Epoch run normally.

This controlled schedule deliberately constrains the test execution window;
it proves lifecycle/Minor safety and complete exit ordering, not simultaneous
CPU execution during its rendezvous. Independent unmodified ordinary/minor/
epoch workload images retain actual batch-sequence user-operation overlap
checks with no test gates. Thus controlled scheduling cannot stand in for
concurrency. The original probabilistic Minor coverage is replaced by the
mandatory eight actual same-Epoch Minors, while the two-mutator mutation,
promotion/reuse, memory and natural concurrency workloads remain required.

The regression intentionally requires the post-Join observation to be Phase3
while all lifecycle bounds and eight Minors are proven within Sweep. This is a
direct native counterexample to the old oracle, not a relaxed phase assertion.
Negative verifier tests must reject Phase2-only, stale Epoch, missing native
Join, failed Join, out-of-Sweep exit and invalid Minor ownership.

## Runtime audit and gates

gc_block_leave must retain its foreign-owner handshake: returning early would
allow precise Shadow Frames to change during scanning. Registry removal is
serialized with scanning; bootstrap/shadow cleanup follows removal; native
resources remain owned until successful Join. Sweep reclaims only the closed
Remark death set, with allocator/Minor ownership protected by the real sweep
lock. The diagnosed observation race establishes no Runtime memory-safety
fault; production GC semantics are therefore unchanged by this repair.

Directed validation precedes candidate freeze. Freeze canonical source,
test overlay, controller, contract and verifier hashes before exactly one full
fixed32 matrix. Never relabel Full30 PASS. E5 requires the full matrix and
all affected regression gates; E6 begins only after those pass. Other targets
remain NOT_IMPLEMENTED. No Commit, Push, Tag or Release.

## Revision v2.1: active fatal cancellation

The first v2 fixed32 candidate was rejected at fatal-5: native exit1 and actual
cancel-only85 were correct, but Sweep had already completed normally (Phase3,
400003/400003 reclaimed). This is retained as a separate new FAIL, never PASS.
An instantaneous Phase2 print before invalid Join does not order the subsequent
fatal cancellation against Collector completion. The original fatal source and
oracle remain untouched.

The revised fatal fixture uses the same test-only Epoch rendezvous. Main
publishes blocked exact roots; Collector executes and unlocks a real batch;
Main resumes via normal gc_block_leave and triggers the actual invalid Join.
Collector waits outside all GC/allocator locks for the actual production
cancel's Release Phase4. The verifier requires committed same-Epoch batch <
before-cancel < after-cancel records, actual Phase2→4, nonzero real reclaimed
objects AND nonzero pending claims, actual cancel-only85, zero Sweep joins,
no discarded mappings or false joined cleanup. Normal completed Sweep is
explicitly rejected as a substitute. This is deterministic coverage of active
cancellation; the independent ungated programs still prove natural concurrency.
The fatal packet is a terminal partial observation while other threads may
run; only immutable individually committed events are used, not a fabricated
all-thread snapshot. Process termination is recorded as OS teardown.

The next candidate must freeze v2.1 and execute the entire fixed32 matrix anew;
it cannot resume the failed v2 matrix or reuse its successful samples as PASS.

## Oracle assurance v2.1.1 (E6 source revalidation)

Fatal acceptance additionally requires the recorded actual invalid Join entry
(value3) after the batch and before cancellation. A generic runtime error such
as a test gate timeout cannot replace the intended trigger. The immutable final
v2.1 corpus is independently checked against this additional predicate without
altering its logs or historical result; the E6 current-source matrix must use
v2.1.1 from its initial freeze. Cache reuse now requires canonical compiler AND
overlay-source equivalence before selecting a directed native compiler; stale
pre-resource-refresh or pre-snapshot compilers are not selected automatically.
