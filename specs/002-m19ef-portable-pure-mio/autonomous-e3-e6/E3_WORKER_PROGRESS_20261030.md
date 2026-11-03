# E3 ordinary Worker continuation — 2026-10-30

E3 IN_PROGRESS; E4/E5/E6 NOT_RUN; M19e NOT_ACCEPTED.
This report supersedes the main-only continuation boundary, without changing
its historical test results. The complete objective is still unfinished.

## Implemented source path

`tests/m19ef/user-workers/builder.mio` runs the native Mio frontend, solved
lowering, Darwin linker and Mio signer. Four explicitly selected internal
startup bridge functions provide start/join/wait/collect. Ordinary callbacks
use normal Mio functions and compiler-generated roots: no source sample
publishes a root vector, manipulates TLS, or constructs a GC frame.
The language has no public thread API yet; this is the internal native user
function path permitted by E3.md, not general foreign-thread attachment.

- `runtime/gc/threads.mio`: shared-key child ownership, real lifecycle entry,
  registry insertion/removal under the collector registry lock, key retained
  by main until every child is joined.
- `runtime/gc/mutators.mio`: target-neutral IR for heap entry, root publication,
  epoch completion/poll, native blocked/resume and natural completion waits.
  Publish is Release; snapshots require current Epoch acknowledgments and an
  Acquire observation. Cross-thread frame walks happen while every mutator is
  parked and the registry lock prevents both insertion and removal.
- `aot/lower/worker_roots.mio`: separate Darwin/AArch64 adapter, actual TLS per
  native thread, compiler-generated closure bootstrap root, private stack
  chains, bounded all-mutator snapshot and native entry/return bridges. It
  preserves x0–x17/LR and never uses Darwin-reserved x18. Callee-save native
  state and per-thread NativeFS handles are initialized and cleaned up.
- `lower.mio`: normal solved opcode root maps and polls apply to callbacks,
  including direct/indirect calls, parameters spilled past the first eight
  registers, captured cells, generic layouts, return and recursion. Heap
  operations retain an E3 stopped epoch through initialization/publication.
  Array-forwarded opcodes must be resolved BEFORE selecting this guard.
- `nativefs.mio`, numeric formatter and chant output: blocking ABI transitions
  publish exact roots and park; resume waits out a pending GC. Native condition
  flags survive the transition, including syscall success/error flags. Dynamic
  chant temporaries stay rooted for the entire output call.
- `runtime/os/darwin/worker.mio`: public pthread attributes configure an 8MiB
  stack for ordinary compiled Mio functions; opaque ABI storage and stack
  policy stay in the OS adapter. Attribute cleanup cannot discard a successfully
  created native handle. First errors are preserved independently.

This remains an E3 STW shared-heap protocol. It is not Concurrent Old Mark or
Sweep. Those capabilities remain false. The transitional actual generational
heap implementation is reused; new Old tracing semantics still belong in the
portable core at E4. Object header16B, heap metadata3072B, Side Metadata and LOS
ABI are preserved. Linux/AMD64/Windows remain NOT_IMPLEMENTED.

## Verified frozen candidates and retained failures

- `E3-workers-20261030-09`: scoped pass, 256 ordinary worker runs, 385 child
  commands; source Manifest SHA256
  `5baee7a955d5df523046ad5db04f883f497617d32898cc3a256783f41dd67970`.
- `E3-workers-20261030-11`: scoped pass, 280 ordinary worker runs, 415 child
  commands; source Manifest SHA256
  `7284bb6a5875753c2289e1aaeca49f07dbf2918ccf00cfefc9aa0646d263999a`.
  Observed 129834 Minor, 20148 Major and 600 actual child lifetimes across
  those ordinary runs. Each run checks balanced real ownership and distinct
  pthread identities. NativeFS/FIFO tests check overlapping lifetimes and
  blocked calls, cross-thread-only survival, LOS death/reclamation and final
  occupied bytes0. 32 native package tests, old managed fixture64 times,
  main-only integration, lifecycle and all11 old production GC images pass.
  Whole signed old GC witness bytes equal historical GF4 D, which proves
  compatibility only; it is not a new compiler fixed point.
- Candidate11 child wall708.647s, CPU680.523s, max child RSS1604861952B.
  These include compiler/test overhead, not per-GC pause metrics. Pause
  p50/p95/p99 are N/A because no per-pause timestamp series was recorded.
- `E3-workers-20261030-06`: real native crash after thread_enter parked.
  LLDB showed caller-save import register x7 clobbered to10000000. Native
  worker entry now reloads imports before invoking the clock.
- `E3-print-20261030-02`: old candidate on exactly the corrected printing
  source failed1 before the FIFO could drain,8192B output, GC marker absent.
  `...-03` passes0, marker before drain and200003B output with the fix.
- `E3-stack-20261030-01`: ordinary recursive Worker depth90 failed SIGBUS
  (-10) on the default pthread stack. The controller expected SIGSEGV(-11),
  so its assertion failed too; neither failure was hidden. Candidate12's
  configured-stack development builder passes exact output91/0.
- Candidate12 preserved a real generic-Enum source syntax error. Corrected
  `Packet.Data[Box<Node>](...)` passes84/84/0 in `E3-shapes-20261030-01`.
- Other development source diagnostics, unused unreachable-bridge validation
  failure and all original logs remain in candidates01–12.

`E3-workers-20261030-13` is the new frozen run for the configured stack,
first-error cleanup and forwarded array guard. It adds deep/shapes/remembered
samples to the full regression. Its completion must be checked before any
new acceptance: the previous candidate11 did not contain these fixes.

## Deliberate bounds and remaining gates

The internal bridge currently supports main plus two reusable joinable Worker
slots, starts/joins from main only,1000 total snapshot entries and1024 frame
walk nodes. Overflows fail closed before collection; they do not truncate roots.
Native join waits for natural completion with a30s deadline; normal waits are
not cancelled by join. Heap/handshake watchdogs remain bounded. These limits
must be reported and tested, not mistaken for unlimited public thread support.

Remaining E3 work: finish candidate13, inspect all G3.1–G3.7 against current
source, extend production-path negative/precision/bounds coverage where needed,
verify fault paths for the new OS stack adapter, and reconcile native Bunko
resource generation. No E3_FINAL_REPORT or full E3 PASS is issued by this report.
No E4/E5 implementation or new Seed→A→B→C→D acceptance has occurred.

Reproduce the ordinary-worker matrix, serially, in this worktree with a new path:

```sh
python3 tests/m19ef/user-workers/run.py build/m19ef-evidence/E3-workers-resume-NEW
```

The controller only copies sources, launches/measures processes and audits
results. Every compiler/runtime/link/sign operation is pure native Mio. No
commit/push/tag/release/reset/clean/stash or other-worktree write occurred.

## Candidate13 and newly reproduced process boundary

Candidate13 completed all477 child commands and336 ordinary Worker runs with
source unchanged. Manifest SHA256:
`1bc77845a643f8afa99bfd7e198498021238db4bde2957a0d2cd384629dbab5c`.
Observed133009 Minor,20586 Major and704 actual child lifetimes; child aggregate
wall688.910s/CPU662.872s/maxRSS1665400832B. The configured-stack, typed callee-root
and forwarded-array changes pass the complete scoped matrix.

`E3-worker-boundaries-20261030-01` then passed captured callback roots after100
Major, automatic shutdown join, duplicate-join exit1 and snapshot overflow exit1.
Its separate native OS fixture passed six attribute fault/success cases, including
actual pthread creation/join and successful-handle retention after injected
attribute cleanup failure. This fixture does not count as ordinary-root proof.

The same boundary audit found an additional **real failure**: existing native
`os.spawn` uses fork. While another managed Worker runs GC, the fork child can
inherit a coordinator owned by a vanished sibling and wait forever in its copied
condition state. Original sample exit was -9 after45s external timeout; expected0
was not obtained. `spawn-child.sample` records the real native child parked in
`_pthread_cond_wait`/`__psynch_cvwait`. This failure prevents full E3 acceptance.

Current candidate14 implements public `posix_spawn` through the Darwin adapter
and reuses bounded unmanaged path/argv copying plus normal parent wait/cleanup.
GC/TLS code never executes in the spawned child's pre-exec path. The independent
fork-based `spawn_test` redirection/CPU-deadline ABI is explicitly rejected in
worker lowering until it has a safe managed implementation; legacy default
lowering remains unchanged. Testing report writes also gain blocked transitions
and serialize the shared failure counter. Candidate14 is under native validation,
not yet accepted. Its source Manifest is
`48a23cc95cc2df372535d3098fe27037552df991c9098a0c65225aa2e5f1bc67`.

Remaining follow-up includes worker test-packet completion ordering: automatic
joins must finish before publishing the test completion packet, while main TLS
is still registered for the blocked write protocol. Do not claim E3 PASS until
these boundary fixes and the full same-source regression are verified again.

## Candidate14/15 follow-up

Candidate14 passed8 repetitions of the original failing spawn source (256 real
posix_spawn children while another Worker performed Major GC), plus captured
callbacks and the ordinary/graph/NativeFS regression samples. Its report FIFO
completed100 Major before draining200001 bytes, with the expected assertion
exit1. The development controller then failed its final-zero assertion: stdout
was64 because the test's top-level file-write result remained a valid managed
root. This was a sample lifetime error, not evidence that GC should collect a
live value. Original source/output/trace and failed assertion are preserved.
Candidate15 moves that value into a helper scope; all4 blocked-report runs now
pass exact final occupied0, LOS0 and expected exit1.

Candidate15 also passes test packet ordering (delayed user failure, then the
completion marker), the six real OS configured-stack success/fault cases,
captured callback closure/LOS survival, safe duplicate/snapshot/slot rejection,
public process spawn and current ordinary root samples. Its complete affected
package and historical fixture matrix is still running.

A further API audit is checking whether internal bridge binding return types
are validated as native int64, in addition to parameter kinds and arity. The
current source only validates parameters. A reachable object-returning or narrow
stub must never be replaced with an untyped native integer result. The planned
negative compilation samples live in `E3-worker-abi-20261030-01`; they are not
run as unsafe native images. This check remains open before final E3 acceptance.

## ABI boundary confirmed and candidate16

Candidate15 completed its full scoped matrix with unchanged source and all372
ordinary Worker runs,32 native package tests, old managed64 and11 production
GC witnesses passing. Its ordinary runs observed133897 Minor,7114080 Major and
756 actual child lifetimes. These totals include an intentionally continuous
Major Worker during real process-spawn tests, not an Old concurrent collector.

The separate compile-only ABI counterexamples confirmed the missing check:
both an object-returning rt_collect and an int8-returning rt_collect produced
native images with exit0 where rejection67 was required. Those images were
**never executed**. Their source, commands, metrics, images and hashes remain
in `E3-worker-abi-20261030-01`.

The lowering now validates each reachable bridge result as a nonnullable native
integer word and rejects narrowed integer parameter/result representations.
Unreachable unused bridge declarations remain legal. Candidate16 adds three
negative source compilation tests (object result, narrow result, narrow input)
and reruns the complete frozen matrix with the source-identical runtime path.
Its exact audit controller is copied into the evidence directory as well as
hashed in provenance. E3 remains IN_PROGRESS until this final ABI fix passes.
