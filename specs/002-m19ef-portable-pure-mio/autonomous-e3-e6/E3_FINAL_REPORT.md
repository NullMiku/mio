# E3 final report — 2026-10-30

**E3 PASS** for the bounded Darwin ARM64 internal native user-function bridge.
**M19e NOT_ACCEPTED. E4/E5/E6 NOT_RUN.** No concurrent Old collection or new
compiler fixed point is accepted by this report.

All G3.1–G3.7 pass on the same frozen211-file Mio source Manifest:
`3c08cd3a3aa11f24aa8854795a06a12e9c2addc3468cbf070903041505323a6f`.
Evidence: `build/m19ef-evidence/E3-workers-20261030-16/`.
Review: `E3_GATE_REVIEW_20261030.md`; machine result: `E3-acceptance.json` in
that evidence directory. The conservative original controller summary remains
unchanged; this independently reviewed overlay closes its pending E3 gates.

## Actual source implementation

Ordinary callbacks run the normal frontend/solved codegen path with automatic
per-thread TLS, exact compiler frames and polls. `user-workers/builder.mio`
uses an explicit internal startup bridge for start/join/wait/collect; no ordinary
sample constructs a root vector or calls a manual publication API. Runtime core
`gc/mutators.mio`, `threads.mio`, `safepoints.mio` and `stw.mio` express neutral
IR. Darwin/AArch64 register/entry/OS implementation lives in `worker_roots.mio`,
CPU lowering and `os/darwin/worker.mio`. Source dependency audit confirms no
CPU/OS imports in the ten GC core files.

A current-Epoch stop owns complete Acquire/Release-published root snapshots and
keeps heap ownership through initialization/publication, including forwarded
array mutations. Registration/removal uses the same registry lock as root walks;
contexts and native stacks remain owned until real join. Blocking NativeFS,
chant, numeric output and test-report writes park with exact roots and preserve
kernel condition flags. Joining waits for natural completion. Normal shutdown
joins all callbacks before the test completion packet and key destruction.
Ordinary os.spawn uses public posix_spawn, with copied unmanaged argv and bounded
cleanup; no GC/TLS code runs in a fork child. Binding input/results reject unsafe
object/nullable/narrow representations instead of forging native pointers.

## Reproducible native evidence

- 538 bounded child commands met expected exits; all32 native
  package tests pass. The exact controller, command argv/exit/deadline, native
  artifacts/signature checks, stdout/stderr, hashes, CPU/wall/RSS and frozen
  sources are preserved.
- 372 ordinary Worker runs; 134013
  actual Minor and 7335606 actual Major collections; 756
  child lifetimes with distinct pthread identities and balanced resources.
  Source programs cover cross-thread-only graph retention after producer exit,
  eventual occupied0/LOS0, Node/Array/Map/Nullable/Cell/Closure/Enum/generic
  layouts, nonmoving promotion/remembered writes,131072-byte LOS, recursion90,
  ten-argument callee roots, captured Worker factory closures and slot reuse.
- Real FIFO input and blocked stdout/stderr continue100 Major collections before
  draining. Exact output and actual reclaimed LOS bytes are asserted. Long user
  waits complete naturally; automatic shutdown waits for outstanding callbacks.
- OOM exits2; slot exhaustion, duplicate join and snapshot overflow exit1;
  object/narrow return and narrow input bridge declarations reject67 without
  producing an image. Six OS stack-attribute success/fault cases preserve first
  error and successful native handle ownership through real join. Delayed test
  assertion records precede completion. Prior lifecycle/handshake fault suites
  and main-thread integration pass from this same source.
- Old managed fixture64 repetitions and all11 production metadata witnesses
  pass. Whole signed old GC images equal historical GF4 D. That is ABI/behavior
  compatibility evidence, not new compiler bootstrap acceptance.

Measured child totals: wall785.434s,
CPU777.793s; maximum single-child RSS
1723367424B. These include compiler/test overhead.
GC pause p50/p95/p99: N/A (no per-pause timestamp series). High Major totals
include a deliberately continuous Major Worker during process-spawn tests;
they do not describe concurrent Old tracing.

## Bounds, failures and preservation

Main plus two reusable joinable Worker slots; starts/joins owned by main;
8MiB Worker stack;1000 merged Root entries;1024 frame walk nodes;30s natural
completion deadline. Overflow fails before collection, never by truncating
roots. The bridge is internal; no public language thread API or foreign-thread
attachment is claimed. Worker-mode fork-based spawn_test is rejected at build
time pending a separate safe implementation. Legacy default compile behavior
and ABI remain compatible. Linux/AMD64/Windows remain NOT_IMPLEMENTED and
concurrent target capability remains false.

All earlier development failures remain: clobbered native import register,
blocked-output missing transition, default pthread stack SIGBUS, fork child
inherited GC wait (sampled and timed out), wrong bridge return types, source
syntax diagnostics and the report sample's correctly live64-byte file result.
See `E3_WORKER_PROGRESS_20261030.md` for exact directories and corrections.
The initial entire211-file final snapshot and initial182-file source backup
protect prior work. `preservation-audit.json` confirms the pre-existing modified
generational/LOS/Mach-O/sign/Bunko resource files were unchanged in this
continuation. No commit/push/tag/release/reset/clean/stash or other-worktree write.

Re-run from this worktree, with a new output path:

```sh
python3 tests/m19ef/user-workers/run.py build/m19ef-evidence/E3-workers-NEW
```

Use the frozen `controller.py` to reproduce this exact driver. Python only
freezes, launches, measures and audits; all compiler/runtime/link/sign operations
are native Mio. Embedded Bunko regeneration, full final source regression and
Seed→A→B→C→D remain E6 obligations. Next actual work is E4 target-neutral Old
tracing/SATB with independent collector overlap; E3 STW is not that proof.


## Candidate17 revalidation

See `E3_REVALIDATION_20261030_17.md` and candidate17/E3-acceptance.json.
All prior bounded E3 gates pass on the new registry/type-analysis source;
manifest6fa8e1b4be91fc40274ddae23ceda5167be7b632f10f8f9466f2050c57a6e2f8.
Earlier candidate16 evidence remains historical and unchanged.
