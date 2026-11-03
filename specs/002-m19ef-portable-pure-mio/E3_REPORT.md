# E3 continuation — 2026-10-29

**E3 IN_PROGRESS. M19e NOT_ACCEPTED. M19f NOT_RUN.**

This checkpoint connects the existing cooperative runtime to the real production
managed heap. It does not yet integrate ordinary compiled Mio user functions as
registered mutators. It does not accept E3, concurrent GC, or a new fixed point.

## Source changes

- `runtime/gc/stw.mio`: target-neutral Runtime IR for bounded, coordinator-owned
  exact root snapshots, stopped collection and stopped allocation. A failed root
  scan/overflow cannot invoke the collector. Allocation returns NULL on rejected
  scanning. The caller retains the stopped epoch through object initialization
  and publication; all heap allocation is serialized at this transitional stage.
- `runtime/gc/safepoints.mio`: pass opaque visitor data through the exact frame
  walker; include a coordinator's own shadow chain when it is not a registered
  list member. Previously the scanner only visited the registry list and could
  omit the collecting caller's roots. Linked coordinators are scanned once.
- `aot/lower/stw_bridge.mio`: explicitly target-specific transitional adapter.
  Calls the unchanged production initializer, allocator, Minor, Major, marker,
  LOS and remembered barrier. Saves/restores x19–x30 and installs a private exact
  snapshot in x24 for the duration of each call. No foreign x24 is shared.
- `tests/m19ef/managed-roots/main.mio`: native Mio builder for a real pthread
  runtime-IR witness. No simulated arena, collector, or free list. Uses the
  production 16-byte headers, side metadata and exact layout descriptors.

The portable code imports no CPU/OS instructions. The existing legacy tracing
and sweeping implementations remain AArch64/Darwin emitters. This transitional
bridge does not make those algorithms portable or concurrent. Target capability
flags remain disabled for precise managed threading/concurrent GC.

## Real native checks

Frozen candidate evidence: `build/m19ef-evidence/E3-managed-20261029-05/`.
See its `results.json`, `managed-observations.json`, `summary.json` and complete
`source-snapshot/`; a summary is authoritative only after the controller finishes.
Every child command has stdout/stderr, exit, external timeout, wall/CPU/peak RSS,
seed SHA256 and source-manifest SHA256. Heavy checks run serially.

The 64 native managed repetitions have actually completed successfully. Each:

1. Creates two distinct pthread mutators. A allocates a production graph:
   Struct → Array → Storage → Map → entry → Closure → environment → scalar Cell,
   with nullable reference fields and an independent 131072-byte LOS payload.
   B also allocates a Cell and publishes it into the shared Struct.
2. Transfers ownership to B with Release/Acquire publication; A drops its exact
   roots. Only B roots the graph for 1000 Minor collections. The native fixture
   traverses all graph layouts to the scalar Cell, checks values, compares the
   root Struct and LOS addresses, and checks LOS ownership after every round.
3. Checks the actual Old bits of Struct and LOS after promotion. Publishes a
   newly allocated Young Cell through the Old Struct, runs the production
   remembered barrier and Minor, then verifies its value and remembered head.
4. B waits through the production cooperative condition-variable blocked mode.
   Roots remain pinned while parked. A exits, Major runs with B retaining the
   graph, A's context re-registers, and the new worker allocates/publishes another
   Young Cell. A subsequent Minor checks the remembered path again.
5. Drops both threads' roots, runs Major, and checks occupied bytes, Young head
   and LOS count are zero. Checks LOS reclaimed bytes are 131088. No dead LOS or
   dead ordinary payload is read. Ordinary reclamation is additionally proved
   by bump-frontier metadata and controlled allocation at the returned address.
6. Roots the newly allocated Cell only through the unregistered coordinator's
   frame, runs Major, checks its content and exact 32-byte occupied count, then
   removes that frame and checks the next Major returns occupancy to zero.
7. Rejects collection without ownership, a full snapshot followed by additional
   registered roots, and a stale worker acknowledgement. GC counters remain
   unchanged on rejection. The stale-epoch fault is injected under the worker's
   mutex so its periodic park loop cannot repair it before the negative scan.
8. Joins all three actual thread lifetimes, checks re-registration/exit counts,
   and confirms the blocked wait path was exercised.

Each successful binary prints four little-endian uint64 counters:
`[1000, 1002, 4, 131088]`. Across 64 repetitions this is **64128 Minor, 256 Major,
192 native creates/joins, 64 context re-registrations**. These are correctness
witnesses, not profile/performance measurements or concurrent Mark/Sweep proof.

The graph descriptors and exact frames are constructed by a runtime-IR fixture;
the same production scanner consumes them. This does not prove the compiler's
type solver automatically constructs those frames in threaded user functions,
or that language Array/Map/Closure operations execute concurrently safely.

## Failures and preservation

- `E3-managed-20261029-01`: initial Cell + LOS witness, 1000 Minor / 1 Major.
- `...-02`: expanded test failed SIGSEGV; preserved image, exit and LLDB dump.
  The fixture reused its import-table virtual register for an assertion constant
  before configuring contexts. Reloading the import pointer fixed the fixture.
  This attempt was not a frozen final-source run.
- `...-03`: frozen graph/promotion/remembered/negative tests passed (1000 retained
  rounds, 1001 Minor, 1 Major).
- `...-04`: frozen blocked/exit/re-register/reuse/coordinator-root extension
  passed (1001 Minor, 4 Major); further fixture coverage is included in -05.

Older E2/E3 evidence and user changes remain preserved. No Git publication writes.

## Required continuation before E3 acceptance

1. Wire compiler-generated `emit_shadow_push/pop` into actual per-thread context
   publication/TLS. Insert exact safepoints for allocation, call/return and loop
   backedges from solved entry types. The ordinary CLI compiler is unchanged.
2. Integrate those compiled user functions with the production thread entry and
   heap adapter. Run actual language Array/Map/Struct/Cell/Closure/nullable/LOS
   operations, including shared mutation and GCStress. The IR witness is only an
   integration stepping stone; do not relabel it a full language-level pass.
3. Cover all NativeFS/system-call blocked transitions, live stack-frame lifetime
   changes and exit races through that compiler path, including failure cases.
4. Preserve exact globals and all 2048 user slots in that managed threaded path.
5. Re-run the entire E3 gate on one frozen source; only then begin E4 SATB and
   truly concurrent Old marking. E5, E6, profiles and fixed point remain required.

Reproduction entry: `tests/m19ef/README.md`. The frozen evidence controller can
be copied to a fresh evidence directory and run from this worktree; it derives
its output directory from `__file__` and refuses to overwrite an existing snapshot.

## Completed frozen regression and hashes

The -05 controller completed with exit0: all 98 child commands met their
deadlines and exited0. All32 native unit/regression tests, the previous native
handshake/lifecycle witnesses and all11 production GC metadata images passed.
The11 complete signed metadata images are byte-identical to historical GF4 D.
Both snapshot and current worktree Mio source hashes remained unchanged. This
is scoped compatibility evidence, not full M19b/c/E6 or new fixed-point acceptance.

| Input/artifact | SHA256 |
| --- | --- |
| Mio source manifest | `52675b4b374ce31f9e4efd3a32c4c98dc44d6d629d0fec81de2db2bf258cd3b7` |
| managed-builder | `1ee0eee4531b24a89bc6a6fd5bb91f819202124fcf7c801a421e910893cd27e6` |
| managed-native | `fe92a7282479a7d210b88db3e57492307e29b3b755ab1834db0c51586ccf2a7f` |
| roots-builder | `f177f023348782218222839d4256be0baf0d597d75aa4bf3a8889131ec9eac20` |
| roots-native | `661ef0dd6d6f6ed59e7b795fa09427af597bc3a682c72fdd2f49735ab5b8d0cb` |
| lifecycle-builder | `f7024004ab4f345525650f1c76fb4cd05d808f5d959d74801ba6f2a79219ae49` |
| lifecycle-native | `a55c6586e31020c486ebfe5a72b22d7c16b8c61e11f63e4b7860b1d5d4f4e9d9` |
| runtime-builder | `04b2d99528814e077e9fa59bcd6c1311d5c0aeb8d0bec524748b90d0e806e02e` |

## 2026-10-30 continuation (append-only)

The newer same-source checkpoint implements automatic main-thread TLS attach,
exact Shadow Frame publication and opcode-boundary cooperative polls for ordinary
source programs. It passed 48 ordinary native runs, attach failure/reuse checks,
32 native package tests, 64 existing multi-mutator heap fixtures and 11 legacy GC
witnesses. The source Manifest remained unchanged. All 2048 user globals were
also executed through the new attached path, and 2049 was rejected.

This does not yet integrate ordinary compiled user workers or their shared-heap
allocation/blocked-call protocol. **E3 remains IN_PROGRESS; M19e NOT_ACCEPTED.**
See `autonomous-e3-e6/E3_CHECKPOINT_20261030.md` and its linked source/evidence;
the earlier -05 results above remain preserved as historical scoped evidence.

E3 candidate16 now passes G3.1–G3.7 for the bounded internal native user-function
bridge. See `specs/002-m19ef-portable-pure-mio/autonomous-e3-e6/E3_FINAL_REPORT.md`.
E4–E6 and M19e are not accepted by that E3 result.
