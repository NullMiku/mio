# E6 actual current-source validation

After the 2026-11-03 repairs, use `accept.py NEW_OUTPUT COMPLETE_E3_OUTPUT
--compiler ACTUAL_CURRENT_NATIVE_CLI --compiler-sha256 ITS_SHA256 --los-before-builder PRESERVED_OLD_LOS_BUILDER`. It freezes
all sources plus the VERSION fixture, verifies complete exact-Mio-source E3,
runs current E2/E4/E5, negative SATB, owned snapshots, fixed-seed actor replay,
M19c policy, all Bunko/selfhost tests and actual CLI/LSP, then requires a NEW
ABCD. The new D must exactly equal the compiler used for these regressions.
No historical ABCD is substituted and no failed candidate is overwritten.
The final G6 review is still required; the runner cannot waive a gate.

`run.py` requires accepted E5 v2.1 and both directed owned-snapshot cases before
it freezes a final candidate. Resource generation, every compiler generation,
raw unsigned pipeline capture, user images and signatures are native Mio.
Python copies inputs, records measurements and checks actual outputs.

`gc_memory_snapshot(ctx, shadow, heap, words64, availability8)` is a formal
neutral Runtime-IR entry in `gc.mutator_program()`. Both output ranges must be
caller-private, valid, aligned and disjoint from heap/context or shared mutable
storage. The old eight-word ABI is unchanged; availability is returned separately
under the same protection and version (0 Unknown, nonzero Known). Invalid
arguments do not touch output or ownership. Nested complete heap scopes stay
owned; a newly acquired scope is released. Post-acquisition invariant failure
retains ownership for the existing fatal/error recovery contract; a failed
output must never be consumed.

All metadata writers execute under stopped heap ownership or the shared Sweep
lock. The new entry acquires both through production `gc_heap_enter`, copies the
fields and availability, checks the bracketed version and releases only its own
scope. It is a lock-based copy into owned native storage, not a claim that the
old plain Sequence loads/stores form a lock-free publication protocol.

`snapshot/` calls this production entry from ordinary compiled Worker functions.
Mode60 checks nested preservation; mode61 first leaves existing ownership and
checks that the entry itself acquires/releases both protections. Real allocation,
Old→Young mutation, Minor and Collector reclamation produce the sampled values.
Five real invalid-argument calls per read must leave sentinels untouched; an
owned odd-version fault is restored before releasing the scope and must fail
without exposing an output. Kernel records contain the eight fields plus their
coherent availability, so identical versions can be compared across threads.

The Unknown variant makes the actual public sysctl query use an invalid name.
The real failure sets availability0. For audit only, its actual errno is retained
in the existing System input field, which production policy ignores while
unavailable; this is never interpreted as a pressure level. No new production
metadata slot, fake GC work, fixed sleep or pressure-policy replacement is used.

The preliminary `E6-final-20261031-01` A/B/C builds and their smokes are real and
preserved; D was deliberately interrupted once the missing formal snapshot
entry was confirmed. Those artifacts are not a final E6 fixed-point claim.
Final freeze/self-bootstrap must use the completed snapshot implementation.

## Main-project continuation after integration

From `/Volumes/Sector0/AppData/Mio/mio` on `Mio-2.1`:

```sh
python3 tests/m19ef/e6/resume.py --out build/m19ef-evidence/E6-main-NEW \
  --compiler /absolute/path/to/verified-native-mio \
  --compiler-sha256 SHA256_OF_THAT_COMPILER \
  --historical-e3 /absolute/path/to/E3-workers-20261030-17 \
  --los-before-builder /absolute/path/to/preserved/old/LOS-builder
```

This creates fresh complete E3 evidence, then runs `accept.py` including full
E4, fixed32 E5, snapshots, native suites and NEW ABCD. The pinned compiler is
a build tool, never substituted for the new-source fixed point. Native fixture
files/FIFOs are relative to the executing checkout; their controllers set cwd
accordingly. The original development worktree and evidence remain intact.

## Evidence paths and a completed E4 prefix

`accept.py` requires `--historical-e3` for the preserved historical17 hash
reference and supplies its complete same-source E3 path directly to E4. E4
validates those inputs before any native build; nested main-project evidence
outputs are supported. The historical images are reference hashes only.

`--completed-e4-prefix PATH` may retain an interrupted controller's completed
native prefix only when compiler hash, all Mio inputs, actual argv/cwd,
expected exits/deadlines, logs, artifact pins and bulk overlay match. Every
original semantic assertion is re-evaluated against the authentic packet.
Retained command rows preserve their original executed argv/timings and are
marked as retained, never as new native executions. Missing tail checks run
afresh. The original full-controller failure remains FAIL permanently.
This avoids rerunning 672 unchanged successful native commands solely because
the old top-level evidence-directory discovery could not find a nested E3.


## LOS allocation pressure repair

The 2026-11-03 full JSON selfhost exit2 remains FAIL. The subsequent streamed
107-test run passed, but was diagnostic and did not waive that failure. A bounded
8 MiB native reproducer then showed live480/LOS count0 yet22216704 bytes charged
for dead mappings, causing a false7 MB OOM. `los-pressure/` verifies the existing
routine release cap8, the new single pressure pass after final Major/rebuild,
real live-object contents, preserved true over-capacity OOM, and real failing
munmap ownership/charge. The preserved before-builder is an explicit negative
control only. Runtime source changed: new current CLI, affected full regressions
and a new ABCD are required; previous-source acceptance cannot be reused.


For a Lower/Runtime repair, `prepare_current.py` first builds the new emitter
CLI A and then uses A to emit the regression CLI B. This is necessary because
one source rebuild still embeds the previous compiler's Runtime in A itself.
The preparation is not an ABCD fixed-point claim; the independent full ABCD and
exact B=C=D requirement remain mandatory after all current-source regressions.


E3 metadata contract `GC_METADATA_RUNTIME_REPAIR_V2` retains all11 original
native probes unchanged, requires signed current-image reproduction, and uses
pinned before-repair emitter fixtures to reproduce the exact historical GF4
images independently. The current repaired images are expected to differ in
bytes. Before fixtures are comparison data, never accepted as the repaired GC.


## Completed-park registry deadline repair

`E6-main-los-20261103-01` remains FAIL at E5 epochs-19 (actual STW-entry status2).
A deterministic native protocol component established a separate real defect:
a successful parked epoch could advance seen_epoch and release the registry
while its initial heartbeat stayed unchanged, yet the old lock acquisition
reported the expired pre-park one-second deadline. The Core now renews that
soft deadline only on a changed completed seen_epoch after successful gc_poll;
no-progress timeout and the original thirty-second hard ceiling remain.
`registry-park/` preserves exact before-image hashes and controlled-input
component evidence. Those inputs never stand in for a Collector. A fixed32
actual8-Epoch directed run and fresh full E3/E4/E5/E6 are independently required.

The E5 v2.2 matrix now separates ungated natural8-Epoch execution from mandatory
same-Epoch partial-cancellation recovery. All original cases and assertions
remain across the three required parts;608 native programs replace576, with
512 Epochs across the two Epoch programs and224 guaranteed partial cancellation
scenarios. The old unscheduled cancellation failure stays rejected. See the
versioned E5 contract for proof scope; controlled cancellation does not stand
in for actual ungated overlap.
