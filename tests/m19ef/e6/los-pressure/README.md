# LOS allocation-pressure regression

The original observed 8 MiB image finishes 50 scopes of 40 real 128 KiB LOS
allocations, then falsely exits2 for a 7 MB request: live480 bytes, LOS count0,
but dead mappings still charge22216704 of the25231360-byte working budget.
Original evidence is preserved in `E6-legacy-los-churn-20261103-01`.

The fix retains the routine8-release batch. After the existing final Major
has rebuilt generational links (and joined an active Old collector), one finite
pressure pass attempts each already-dead mapping once and refreshes its charge.
Failed public munmap calls retain linkage and charge. Live objects are untouched.
No collection, budget, heap size, retry count or concurrent Sweep gate is changed.

The directed controller builds the current pure Mio generator, uses the same
8 MiB observed heap, requires the old-runtime false OOM, and verifies normal
allocation, churn recovery, a live LOS object's contents across recovery, and a
9 MB over-capacity request that must still exit2. Full E3/E4/E5 and new ABCD are
required after this Runtime change; old-source results are not new PASS evidence.
