# E4 typed bulk/Map and allocation/Minor checkpoint

E4 IN_PROGRESS; E5/E6 NOT_RUN; M19e NOT_ACCEPTED.

Accepted scoped source: `build/m19ef-evidence/E4-bulk-20261030-05`. Source manifest SHA256:
`18062f555e8e73f30f909cea747b99cb45e1dfaab4c57ca89a30270856c09b83`. Current source and every frozen Mio input
matched at completion. Exact native execution records from candidate04 were
retained and verified by `complete.py`; candidate05 continues only the missing
default-image/native-unit checks. The original04 controller ValueError remains
as a harness failure. No failed child command was accepted or discarded.

All168 ordinary source programs passed:32 bulk/Map,32 allocation/Minor/LOS,
32 captured Cell,32 adversarial Array,32 immutable cycles and8 legacy-Major
cancellations. 160 actual complete independent Old mark cycles,
1153909 actual Old scans and10449 observations
inside a real object scan. Minimum still-white prewrite observations per sample:
Array127, bulk24.

Bulk programs each performed16104 exact prewrites/10102 non-null old references,
forwarded Array push/reserve/truncate/self-append/cross-append and1000 existing
Map value replacements plus100 new entries. Dense4×200000 reference LOS graph
was actually traced; final legacy Major reclaimed6400192 bytes and occupancy0.
Dense graph samples explicitly use16MiB; existing Minor/Cell/cancellation and
immutable pressure cases retain1MiB. No artificial marker delay was introduced.

Minor programs require exactly8010 scans BEFORE Remark and before Workers begin
allocating: a new ordinary Node plus LOS storage/descriptor are promoted and
scanned in addition to the existing graph. Then another100 Minors interleave
with two allocating Workers. Every run has≥200 successful pause/Minor handshakes,
≥3 actual promotions, depth0, surviving values and final Major occupancy0.
Startup uses one-way actual initial-world-release publication (version4), fixing
a retained10s late-marker/pause deadlock; all8 cancellation samples pass.

The reference bulk component passes15 meaningful alignment/range/memmove/clear
checks in each of32 native runs. The exact scanner passes20 real layout checks
in each of32 runs. Four default ordinary E3 programs are rebuilt, executed and
reproduced; whole signed bytes equal accepted E3 candidate17. Native GC5/Lower9
package tests pass. This is default-path isolation, not a full final-tree E3/E6
rerun or source bootstrap. Signing, outputs, exits, hashes and metrics are in
commands.json and summary.json; original failures01–04 remain.

Measured child wall572.401s, CPU610.033s,
peak RSS1930215424 bytes (includes compiler/test overhead).
Per-pause p50/p95/p99 N/A: no individual pause timestamps were recorded.

Remaining: positive queue overflow compensation, repeated/aborted epoch recovery,
complete E4 fault/type/ownership gates, E5 concurrent sweep/LOS ownership,
E6 same-final-source regressions/snapshot consistency and NEW Seed→A→B→C→D.
GC capability flags remain false. No commit/push/tag/release or other worktree
edits. Pure Mio production compilation/codegen/signing/runtime throughout.

Reproduce fresh: `python3 tests/m19ef/old-mark-bulk/run.py build/m19ef-evidence/NEW`.
The controller's tuple correction is retained; it reruns all required native
samples. Python only freezes/launches/measures/audits.
