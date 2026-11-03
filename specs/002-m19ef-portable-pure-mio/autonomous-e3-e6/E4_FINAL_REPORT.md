# E4 final report — PASS

G4.1–G4.7 pass on the same242-file frozen Mio source as complete E3 revalidation18.
Manifest `d7e36e3e3bd280cedb9b5c6c7394bae1ccd6710976211af81ffc5ab136a8275e`. Main evidence `build/m19ef-evidence/E4-faults-20261030-08/`;
reviewed gate overlay `E4-acceptance.json`. E5/E6 NOT_RUN, M19e NOT_ACCEPTED.
No Sweep or new compiler fixed point is claimed.

Portable IR implements exact object scanning, bounded synchronized queue,
Old color/epoch/mark state, SATB before reference publication, full queue task
ownership/compensation and coordinated constructor/Minor/promotion pauses.
Darwin/AArch64 is isolated in CPU/OS/lowering adapters;14 GC production files
have no platform dependency. Init and Remark use real E3 all-Mutator snapshots;
marker is an independent actual pthread. It does not register as a Mutator.
Remark closes only after current roots, queue0, in-flight0 and deferred0, then
actually joins. See write-site and queue-ownership audits for linearization.

All685 child commands meet expected exits/deadlines.328 ordinary user programs
exercise648 actual marker starts/joins:544 successful full mark cycles and104
explicit cancellation cycles.32 formal every-allocation GCStress programs each
execute at least184 coordinated Minor collections while Mark remains active.
32 eight-epoch programs force full32-slot queues and96 explicit Major recoveries;
64 queue components move128128 real producer/consumer items.32 Array programs
always execute four epochs each: all128 functional checks pass,127 additionally
capture prewhite deletion and actual in-scan observation; each program requires
an actual adversarial epoch. No failed epoch is dropped/retried for acceptance.
Ordinary markers emit11349 final-cycle in-scan overlap observations. Aggregate
last-cycle scans1304716; full all-cycle scans N/A because early per-epoch counters
reset. Distinct native user/collector identities and real timestamps are saved.

Globals/Cell/upvalue/Array/Map/bulk, Generic/Nullable/Enum/Closure, exact scalar
payloads, concurrent births/promotions, blocked LOS and late registration pass.
Mutability audit confirms Struct/Enum have constructor-only fields in this
language; there is no supported mutable field-store opcode to leave unbarriered.
Native scanner32 ×20 checks include numeric words containing real heap addresses.
Owned-bounds32 ×9 checks reject non-owned/stale LOS pointers before dereference.
SATB-disabled frozen negative mutant02 changes only the prewrite factory:8 real
programs ×4 fixed epochs expose at least167 lost snapshot objects per program.
Retained black-owner references demonstrate why the production barrier is needed;
this is a negative source variant, not GC acceptance or actual post-Sweep UAF.

Failure proof includes32 actual invalid-stack OS errors22,32 actual self-join
OS errors11 followed by real original-handle retries,32 actual invalid-clock
failures,16 fatal OOMs and the stated cancellation cases. Error/handle ownership
is retained; successful cleanup counts only actual joins. Fatal teardown is OS
process termination, never mislabeled concurrent reclaim. All old failed runs
remain, including zero-overlap witnesses, actual OOM and deadlocks that were fixed.

Four default E3 images remain whole-byte identical to accepted17. Complete E3
revalidation18 runs all538 commands/372 ordinary samples/32 native tests/64 heap
repetitions/11 old witnesses from this exact source. Old GF4 bytes are compatibility
proof only. Source before/after hashes and seed/signature/provenance are recorded.
Child totals: wall842.448s, CPU1042.529s,
largest child peakRSS1830387712B. These include compiler cost;
GC pause p50/p95/p99 N/A. No performance improvement is inferred.

Bounds: Darwin ARM64, main+two reusable managed Workers,1000 merged exact roots,
8MiB configured native Worker stacks, queue1..32768 with exact deferred ownership,
30s collector lifetime/10s join waits with checked clocks, separate512B version5
control+queue mapping. Ordinary exact object starts are a compiler/layout invariant;
LOS identity is checked against owned mappings. Default public compile ABI remains
compatible; internal native startup bridge is explicit. Linux/AMD64/Windows and
concurrent capability remain disabled until full E5/E6 acceptance. Header16B,
side16B,metadata3072B,LOS128KiB threshold preserved. No Commit/Push/Tag/Release.

Reproduce frozen scope with a NEW output directory:
`python3 tests/m19ef/old-mark-faults/run.py build/m19ef-evidence/E4-resume-NEW`
Then run same-source negative counterexample and full user-workers controller.
Python only freezes/launches/audits; native Mio performs all compilation/runtime/
codegen/link/signing. E5 production implementation may now proceed autonomously.
