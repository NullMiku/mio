# E4 typed SATB checkpoint — scoped PASS, E4 IN_PROGRESS

Evidence: `build/m19ef-evidence/E4-satb-20261030-07/`.
Frozen source-manifest SHA256:
`6fa8e1b4be91fc40274ddae23ceda5167be7b632f10f8f9466f2050c57a6e2f8`.
This is also the exact input manifest of the running E3 candidate17.
M19e NOT_ACCEPTED; E5/E6 NOT_RUN.

## What actually passed

All170 child commands met their expected exits.104 ordinary native programs:
32 two-Worker Array deletion/numeric-update samples;32 captured local/upvalue
Cell mutation samples;32 immutable Old cycles;8 allocation Abort/join samples.
All96 completed mark cycles drained and joined the real independent marker.
Each Array sample published6001 typed non-null old values, with11 or more
still-white observations;434 total. It marked exactly12009 Old objects, retained
exactly1 unreachable Old witness as white, and final compatibility Major reports0.
Each Cell sample has five prewrites/four non-null old values,7black/1white and
final Major0. Immutable samples retain8001black/1white. Successful cycles total
640544 actual Old scans.2961 observations bracket actual in-flight object scans;
they do not count time in empty loops or clock bookkeeping as scanning.

The scanner's32 repetitions now cover20 cases, including actual pointer-word,
numeric-word and byte Array descriptor flags and a wrong-low-kind negative.
Both newly generated copies of each image have equal complete signed bytes.
Four default E3 images have expected functional outputs and deterministic new
signed bytes. Their change from candidate16 is expected after the documented
registry progress fix. Native GC package5 tests and lower package9 tests pass.
Final source-unchanged check passed. This is not a new compiler fixed point.

Total measured child wall960.865s, CPU1389.242s, largest child peakRSS1829519360B
(Darwin; includes compiler/test processes). GC pause p50/p95/p99: N/A; complete
all-Mutator pause intervals are not sampled yet. No performance improvement is
claimed. Full per-command measurements/hashes and all diagnostic words remain.

## Implemented scope and important limits

`runtime/gc/old_mark.mio` implements neutral exact Old tracing/color/work,
Init/Remark and independent thread termination. `old_satb.mio` publishes typed
old values before replacement, and performs remembered-header CAS preserving
concurrent color. Compiler adapters cover globals, captured Cells/upvalues and
Array element slots. Numeric slots are excluded by solved type/storage layout.

The valid local lambda fixture required a compiler analysis correction: sole
fallthrough literal closure stores establish non-nil; function projections keep
all callable targets without rejoining a temporary nil placeholder. Branch
entry to a store cannot establish that fact. Native binding checks remain strict.
The registry lock now distinguishes a changed GC heartbeat from stalled lock
ownership, retains a1s no-progress timeout and an independent30s ceiling.

Allocation, Minor and bulk mutations during Mark still Abort/join in this
checkpoint. It supports one experimental cycle and does no concurrent sweep.
Queue overflow safely aborts but positive compensation/recovery is incomplete.
It cannot satisfy G4.1–G4.7 collectively. Public concurrent capabilities remain
false. Earlier failures01–06 remain, including descriptor rejection, missing
scan overlap, registry contention, the bad hard-deadline expression and valid
lambda rejection. Their evidence was not overwritten or recategorized as PASS.

## Continuation

E3 candidate17 is automatically rerunning the entire ordinary Worker matrix and
native regressions on these same frozen inputs. Keep source unchanged until it
finishes. Current E3 acceptance remains the historical candidate16 snapshot.

The NEXT Minor/allocation increment is staged, not installed or tested, under
`build/m19ef-dev/minor-staged/`, with before/after hashes in `changes.json`.
It needs review and real native tests before use. It holds the marker pause
through full construction until gc_end, supports nested Minor pause/ack/release,
and publishes promoted Old objects before resuming. Core algorithms remain
neutral IR; owned context extension offsets are supplied by the adapter.

After its implementation: complete bulk/runtime/map/LOS write coverage, actual
queue overflow compensation, repeated epoch/Abort recovery and full E4 gates.
Only then proceed to E5, and E6 full regression plus new Seed→A→B→C→D.
