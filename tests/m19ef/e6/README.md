# E6 actual current-source validation

After the 2026-11-03 repairs, use `accept.py NEW_OUTPUT COMPLETE_E3_OUTPUT
--compiler ACTUAL_CURRENT_NATIVE_CLI --compiler-sha256 ITS_SHA256`. It freezes
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
