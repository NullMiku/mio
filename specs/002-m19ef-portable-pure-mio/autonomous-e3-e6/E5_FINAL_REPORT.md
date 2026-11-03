# E5 final acceptance — PASS within the Darwin ARM64 native bridge scope

2026-10-31 Asia/Tokyo. G5.1–G5.6 PASS under the independently versioned
[E5 contract v2.1](E5_CONTRACT_V2.md). E6 is the next gate; M19e NOT_ACCEPTED.
No Commit, Push, Tag or Release. No other worktree was modified.

## Code and contract repair

The old post-Join Phase2 oracle has no happens-before relation to Collector
completion. A legal STW ownership wait can delay Main beyond Sweep. The retained
event-diagnostic-06 sample2 is the original natural counterexample. v2.1 instead
requires actual user work, real Collector batches, registry exit, actual native
Join success and eight real same-Epoch Minors with legitimate STW ownership.
The native regression deliberately observes Phase3 after the real Join: it passes
only if the separately bounded lifecycle is already proven inside Sweep.

New code: `tests/m19ef/old-sweep-v2/late.mio`, `fatal.mio`, `overlay.py`,
`verify.py`, `verify_fatal.py`, `test_verify.py`, `run.py`, `matrix.py` and
`ungated_matrix.py`. `tests/m19ef/run_native_e5.py full` routes to this matrix.
The original `old-sweep/run.py`, original late/fatal sources and all old logs
remain unchanged. Python prepares explicit test-only source overlays and records
or audits evidence; native Mio performs frontend/codegen/link/sign and executes
all real GC work. The overlay is not installed in production GC sources.

The test adapter's AcqRel sequence reservation, DMB and per-record Release
commit establish event order. A successful public pthread_join bounds native
termination above; the callback's last event bounds it below. Registry unlink
is separate evidence and never substitutes for native termination. For every
accepted late sample both termination bounds precede Collector's before-Phase3
record in the same Epoch. User-work begin/end markers enclose actual allocations,
reads and eight Minor calls; each Minor begin/end has the real Worker as STW owner.

The controlled rendezvous is outside GC/allocator locks, between real batches.
It establishes deterministic lifecycle/Minor ordering; it does not claim physical
CPU concurrency during a gate. Independent unchanged ordinary/minor/epoch/LOS
images prove real Collector/Mutator overlap and object reclamation. No fixed
sleep, added sweep workload, fake reclaim or production GC semantic change was
used. All 32 natural Minor samples also retained nonzero Sweep Minor/promotion/
reuse evidence, independently of the 256 controlled same-Epoch Minor calls.

## Actual final run

Evidence: `build/m19ef-evidence/E5-v21-fixed32-20261030-01/`.
Authority: `final-integrity-review.json`, `freeze.json`, both source snapshots,
commands/logs, native images and per-sample lifecycle event records.

Frozen contract/source/control inputs: 349 files, SHA256
`4ef0cea350e360ee3f291e1aa7c5f541e47c0c1b0b884cd876ba61e58e51dd1e`.
All original 257 Mio inputs were byte-identical to Full30 at this gate.

- 7 resource/protocol failure families ×32 =224 native executions.
- 9 ungated workload families ×32 =288 native executions: ordinary, Minor,
  eight Epochs, LOS, failed LOS release, reentry, shutdown, OOM and bounded OOM.
- Late lifecycle ×32 and active fatal cancellation ×32 =64 native executions.
- Total: **576** native executions; all expected exits, no timeout.
- **256** real same-Epoch Worker-owned Minors; 32 Phase3 counterexample passes.
- All 32 fatal samples reclaimed a real 256-object batch, retained 399747 pending
  claims, transitioned Phase2→4 and reported cancel-only85 with zero Sweep Joins.
  Terminal process teardown is not reported as joined cleanup.
- **16** adversarial oracle cases rejected, including phase-only evidence, stale
  Epoch, bad STW owner, missing/failed Join, out-of-Sweep exit, missing batch or
  cancellation events, completed-Sweep substitution and log overflow.
- **32 native tests** across GC/Target/CPU/OS/ARM64/Mach-O/Lower/Pipeline passed
  on the canonical frozen sources, without the test schedule overlay.
- All 11 user-image signed AND unsigned complete-byte reproductions equal.
- Every recorded command/log hash and all frozen input hashes verified.

Measured final matrix children: CPU 1200.160008s; summed child wall 878.666668s.
These include build costs, not GC pause measurements. Pause p50/p95/p99: N/A.

## Runtime audit

gc_block_leave correctly waits for a foreign STW owner while preserving exact
Roots; Sweep Phase2 does not authorize bypassing this wait. Registry removal
serializes with scanning, bootstrap/shadow cleanup follows unlink, and native
resources remain owned until actual successful Join. Sweep consumes Remark's
closed dead set; allocator/Minor metadata operations hold the production sweep
lock. No diagnosed memory-safety defect justified changing these mechanisms.
Production GC/runtime source changes for this contract repair: **none**.
The repair is in the actual test code, ordering facilities and acceptance oracle.

## Failures permanently retained

- Original **Full30 FAIL**: `E5-sweep-20261030-30/`; all 1384 files hash-verified.
  Its failed late-11 assertion was never rewritten to PASS.
- Historical Sample24 remains its original coverage failure; current results do
  not alter that record. The requested Minor is now deterministically witnessed.
- First v2 fixed32 candidate **FAIL at fatal-5** remains in
  `E5-v2-fixed32-20261030-01/`: Sweep completed normally before fatal cancellation.
  v2.1 fixes trigger ordering and rejects normal completion as active-abort proof.
  The final candidate ran the entire matrix from zero, without reusing samples.
- Directed setup failures, trace overflow and development source-change rejection
  records remain separate; only frozen directed v21-02 and the full v21 matrix
  contribute to this acceptance.

Bounds: main+two reusable managed Workers, Darwin ARM64 internal native bridge,
existing heap/LOS/header/precise-root limits. This is not universal race freedom,
public concurrent CLI enablement, other-platform support, a new compiler fixed
point or M19e acceptance. E6 must validate the final source and new self-bootstrap.
