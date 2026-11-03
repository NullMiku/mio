# Bulk white-before-scan contract v1

The original workload and all positive predicates are retained: calls>=16000,
nonnull>=10000, actual prewhite>0, expected graph contents, one completed Epoch,
exact queue accounting, distinct native identities, black/scanned>=8000, a real
dead object and zero final heap.

The retained bulk-21 from E6-accept-20261103-01 exits0 with correct graph data,
but reports16104/10102/0. Its required adversarial witness is absent; this FAIL
is permanent. Dense arrays alone never guarantee mutator-before-scan ordering.

Only the bulk image uses a copied factory with an Acquire read of actual
prewhite counter440 before gc_work_take. If zero, it follows the existing
deadline/take loop. The production pause gate remains serviced on every loop,
so legitimate heap/STW owners receive acknowledgments and perform typed writes.
Existing producer Release publication provides ordering; actual current-Epoch
Init resets the counters before launch. The gate holds no queue/heap lock and
retains original abort/deadline handling. No color, object, root, phase, count,
GC work or clock is fabricated. Canonical production GC is unchanged.

The gate proves white-edge ordering, not physical simultaneous scanning while
it waits. Ungated ordinary/immutable/array cases still require real in-scan
observations and Collector/Mutator intervals. Full E4 still runs all32 samples
per original family; directed8 never substitutes for complete acceptance.

E6-bulk-directed-20261103-01:8 native positives, minimum22 real prewhite
publications. Original zero-white and nonpositive counter packets remain
rejected by the unchanged shared strict predicates in bulk_trace.py.
