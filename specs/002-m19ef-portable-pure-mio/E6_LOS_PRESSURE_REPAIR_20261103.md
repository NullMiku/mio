# E6 LOS allocation-pressure repair — 2026-11-03

E6 remains IN_PROGRESS / NOT_ACCEPTED. No commit, push, tag or release.
The original Full30 FAIL and E6 round03 full JSON selfhost exit2 remain FAIL.
The subsequent streamed selfhost diagnostic passed107/failed0 in1133.5 seconds;
it did not waive the original failure or establish a new-source acceptance.

The bounded observed 8 MiB reproducer completes50 scopes of40 real128 KiB LOS
allocations, then falsely OOMs on7 MB: only480 bytes live, LOS objects0, but
22216704 bytes remain charged against25231360. Routine release caps each
collection at8 mappings; the allocator's finite Minor/Major retries can exhaust
without releasing enough already-dead mappings. This is a confirmed Runtime bug.
Whether it fully explains the original full-CLI failure must still be checked.

`large_objects.mio` keeps normal release batch8 and adds one finite pressure
pass. `lower.mio` invokes it after the existing final Major/rebuild, refreshes
actual charge and takes the existing final retry. Major already joins/aborts
an active Old collector under owned heap synchronization; errors fail closed
through the existing bridge. The pass does not mark objects or release live
nodes. Each failed real munmap is relinked, charged and advanced once. Heap
limits, object layout, GC roots and allocator retry count are unchanged.

Directed evidence:
`build/m19ef-evidence/E6-los-pressure-directed-20261103-02`.
Old Runtime false OOM reproduced. New real native images are signed and reproduce
exactly; same8 MiB control/churn/live-LOS contents pass;9 MB true OOM stays exit2.
A test-only adapter copy uses actual unaligned munmap calls: release fails,
charge/ownership remain and OOM terminates within the bounded deadline.

`GC_METADATA_RUNTIME_REPAIR_V2` keeps all11 original native metadata probes and
current signed reproduction. Pinned before-emitter fixtures independently
reproduce historical GF4 whole images; repaired-current bytes are expected to
change. Historical equality is not discarded or misreported as current GC PASS.

Next snapshot must rebuild emitter A and then regression CLI B: one rebuild
still embeds its producer's old Runtime. Fresh E3/E4/E5 fixed32 and remaining
E6 gates, including all selfhost JSON tests and independent native ABCD exact
signed/raw B=C=D, are required. Old-source passes cannot substitute.
