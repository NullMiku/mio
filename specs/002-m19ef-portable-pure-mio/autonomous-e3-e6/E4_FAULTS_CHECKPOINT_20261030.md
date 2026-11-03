# E4 fault/type/blocking/epoch scoped checkpoint

E4 IN_PROGRESS; E5/E6 NOT_RUN; M19e NOT_ACCEPTED.

Frozen candidate `build/m19ef-evidence/E4-faults-20261030-04` source manifest:
`e07cd0a0ed181ed1c92475665ae2647e8e95e25c0b4a005db5b65573af7c1c5c`. All current/frozen Mio bytes match.
All542 expected native child outcomes pass; Python only orchestrates/audits.

264 ordinary programs:32 Generic/Enum/Nullable/string/float/ten-argument-stack,
32 real blocked FIFO,32 eight-epoch,32 bulk/Map,32 allocation/Minor,32 captured
Cell,32 Array and32 immutable; plus8 explicit cancellations. Repeat programs
execute256 actual epochs with96 explicit Major-cancel/recoveries. Actual cumulative
native starts/joins8/8 and each user slot8/8, resources24/24 per repeat program.

16 actual terminal OOM programs (8 hard-budget,8 static storage bound) each
return2 and record Abort6/error0/native starts1/joins1/done1/joined1/cleanup0.
32 actual OS clock-error tests return safe Core error4 and retain the real
handle; the harness separately performs real native join. Clock counterexample
before repair remains `E4-clock-counterexample-20261030-01` (defect exit90).

Each Minor program retains the1MiB object bound, original128KiB byte LOS and
additional128KiB reference LOS. Exact pre-Remark scans8012, promotions≥5, ≥200
successful pause/Minor handshakes, eventual262240-byte LOS reclaim and occupancy0.
The corrected fixture performs actual object reads while marking, no marker
sleep/delay. Native blocked Root tests complete Remark while both callbacks
remain blocked/parked, then actual FIFO I/O succeeds and final Major occupancy0.

Array owner storage is actually traced before mutations (FIFO completion≥9).
Workers create black-owner→white edges and remove them; every run has positive
still-white prewrites (minimum175). All12021 Old
objects are actually scanned/black and the dead witness is white. No sweep is
performed yet. Remaining counterexample/lifecycle extension is described below.

All32 ownership-negative components,32 reference-bulk15-check components,
64 real3-thread queue components and32 twenty-layout scanners pass. Four default
E3 ordinary programs reproduce and their whole signed bytes equal accepted
E3-17. Native GC5/Lower9 tests pass. This does NOT replace full final-tree E3/E6.

Measured child wall624.495s, CPU676.050s,
peak RSS1955643392 bytes, includes compilation/tests.
Pause p50/p95/p99 N/A. No new compiler fixed point has run.

Retained failures: faults02 Generic declaration lexed `>=` without separating
generic close/assignment, rejected65 before any image; faults03 program passed
values2688/2688 and mark but retained a newly assigned empty global array,
correct final occupancy112. Fixture now uses a nullable Holder and releases it;
collector was correct. All prior runtime/OS/overlap/budget failures remain.

Before full E4 acceptance: strengthen the black-owner case with retained live
edges and demonstrate actual snapshot/root danger with controlled SATB-disabled
negative input (production tree untouched), cover a Worker registered AFTER Init,
and rerun full affected E3 on the final same source. Complete E4 gate review must
still precede E5. Capability flags remain false; no Git publication operations.
