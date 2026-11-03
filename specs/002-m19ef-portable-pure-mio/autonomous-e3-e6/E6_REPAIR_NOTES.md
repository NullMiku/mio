# E6 repair, 2026-11-03

The failed `E3-workers-E6-20261031-01/global-snapshot-0` exited0 and returned the
expected output. Its actual callback intervals overlap by1296000ns. The first
failing predicate was NativeFS boundary counts7/0; Worker B snapshot roots/epoch
were also0/0. The previous description as an interval-overlap failure was
imprecise. `thread_wait_started` acknowledges registration, not execution of the
ordinary callback. The old waiter neither calls NativeFS nor performs a heap
operation that records its snapshot. `rt_wait` is a distinct cooperative wait
protocol, not the NativeFS boundary counter.

The fixture now performs an actual NativeFS read and an owned Minor in Worker B
before publishing readiness. Main waits for that readiness AND the blocked
Reader before clearing the global and releasing the FIFO. No existing assertion
is removed or relaxed. The shared `worker_trace.py` names the same predicates
and is used by directed and complete E3 validation. No Runtime/GC change was
justified by this failure.

Directed evidence: `build/m19ef-evidence/E6-global-snapshot-directed-20261103-01`.
Eight actual repaired programs pass all original lifecycle, NativeFS, snapshot,
overlap, LOS and zero-final-heap checks. A freshly compiled original fixture
remains rejected. Seven damaged evidence packets are rejected. Full E3 is then
run without reducing its workload, under `E3-workers-E6-20261103-01`.

Host orchestration also now inherits the existing flock descriptor into nested
snapshot/Sweep/ABCD drivers and uses unique output names. Frozen historical
failures are untouched. `e6/accept.py` runs complete same-Mio-source regressions
and requires a NEW source-bootstrap ABCD, then exact equality with the native
compiler used for those regressions. It cannot grant G6 or M19e on its own.

The 2026-11-03 user authorization permits implementation/test repairs and,
only after complete E6 acceptance, M19f development. No Git write or external
worktree modification is authorized. E6 remains IN_PROGRESS.

The real CLI stdio probe (`E6-LSP-directed-20261103-01`) then exposed a separate
implementation bug: request and cancel frames read together were both queued;
the checkpoint serviced newly received frames but ignored cancellation already
in `pending`. `cooperative.mio` now services queued cancellation notifications,
keeps all other frames in order and tracks a checked prefix to avoid repeated
parsing. Tests cover same-read cancellation, cursor adjustment, request order,
malformed payloads and cancellation-ID reuse. Full unified CLI must be rebuilt;
the earlier ABCD is not accepted for this changed compiler source.

`E6-LSP-policy-repair-20261103-01` passed both native cancellation tests, the
actual stdio session,28 native policy checks ×8, and a full current CLI build.
That CLI's SHA256 is0225cb1296f08af147e491ae1f5f17e31d2ed79b3ad0208737f86cb039c3bad8.
Its actual unified CLI stdio session also passes. This is a build tool for the
next regressions, not a substitute for a new ABCD fixed point.

The next complete E3, `E3-workers-E6-20261103-02`, passes608 commands with
expected exits,436 ordinary user runs,32 native tests,64 managed heap fixtures,
11 historical whole-byte images,64 repaired global cases and an actual failed
readiness-probe cleanup case. All Mio inputs and VERSION remain unchanged.
Manifest SHA256:57d37554b0f7dce1bcf4dd51a5014053bce20dc4e550f7d5a74d4d9d6222d19a.
No existing assertion was weakened; the failure fixture does not count as a
positive concurrent witness. Final same-source E4/E5/E6 acceptance now follows.

All native commands of `E3-workers-E6-20261103-01` completed with expected exits,
including64 repaired global samples and11 historical whole-image comparisons.
That candidate correctly failed its final canonical-source comparison after
the LSP repair; it remains superseded, with no new-source E3 PASS. Directed LSP,
legacy pressure-policy component checks, new CLI build and complete regression
continue on the next snapshot. Pressure-component inputs/counter substitution
are explicitly test-only; actual kernel Unknown and concurrent snapshots remain
separate native tests. No policy component result stands in for real GC work.

E6-accept-20261103-01 subsequently fails E4 bulk-21 with16104 calls,10102
nonnull and0 prewhite; application graph and native exit are correct. This is a
missing adversarial witness, not evidence of a Runtime memory defect. The new
bulk-only copied-factory handshake preserves real marker pause/ack/release and
the deadline while waiting for actual white-edge publication before scanning.
No original predicate or workload is relaxed. Directed8 pass (minimum22 white
edges); the historical zero-white packet remains rejected. Other E4 scans stay
ungated. See tests/m19ef/old-mark-faults/BULK_CONTRACT.md.

All canonical Mio inputs remain byte-identical to completed E3. Only test-control
Python/docs change. E3/current E2 proofs may be retained by exact compiled-input
and log validation; full E4 is freshly rerun. A new ABCD remains mandatory.
