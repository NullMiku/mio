# Latest continuation — 2026-10-29

E3 now has an actual production managed-heap multi-mutator runtime witness, not
only handshake buffers. See [E3_REPORT.md](E3_REPORT.md) and
`build/m19ef-evidence/E3-managed-20261029-05/`. The bounded portable root snapshot
feeds the unchanged real allocator, Minor/Major, LOS and remembered barrier.
The 64 managed repetitions,32 native tests, prior handshake/lifecycle witnesses
and11 byte-identical historical production GC metadata probes passed. Source
hashes remained unchanged; the complete result is in that directory’s summary. **E3 remains IN_PROGRESS:** compiler
TLS/shadow/safepoint integration for ordinary user functions is still required.
M19e is NOT_ACCEPTED; M19f and the final-source fixed point are NOT_RUN.

The older records below are historical checkpoints, with their original scope.

# Current continuation status — 2026-10-28

E2 native thread/synchronization acceptance is now **PASS**; see [E2_REPORT.md](E2_REPORT.md)
and `build/m19ef-evidence/E2-acceptance-20261027-01/`. The frozen candidate passes32
native tests,6896 actual native thread creations/joins,8192 injected failures,
real TLS capacity recovery, two-worker registry enumeration, spurious-wake and
quarantine recovery checks, and11 historical-byte-identical GC metadata probes.
This accepts E2 only. E3 integration has started; managed concurrent GC, M19f,
full final-source CLI validation and compiler fixed point remain unaccepted.

The older checkpoint and development notes below are retained as historical
records. Their E2 IN_PROGRESS language predates this explicit acceptance.

# Intermediate implementation checkpoint — 2026-10-27

**M19e IN_PROGRESS; M19f NOT_RUN; overall NOT_ACCEPTED.** This is an actual
implementation checkpoint, not completion of the requested M19e→M19f program.
E0 audit and E1 initial runtime contract pass their scoped tests. E2 has actual
native primitive witnesses but is not accepted as a complete GC thread backend.
E3–E6 and F0–F4 remain unaccepted/not run.

## Implemented source

- `bunko/kiso/runtime/gc/`: pure Mio semantic RuntimeOp contract, memory-order
  validation, frozen object ABI constants, and scalar concurrent-phase safety
  predicates. No CPU assembler, OS service, target page size or executable format.
  Mock recorder exists only in `_test.mio`; it never claims native concurrency.
- `bunko/kiso/runtime/target/`: explicit target capabilities and rejection of
  unavailable operations/concurrent collector support. Future targets default to
  unsupported. Optional system pressure can remain Unknown.
- `bunko/kiso/aot/arm64/atomic.mio`: checked base A64 LDAR/STLR, LDXR/LDAXR,
  STXR/STLXR, DMB ISH and CLREX encoders. No optional LSE requirement.
- `bunko/kiso/runtime/cpu/aarch64/`: strong CAS retry/mismatch handling,
  fetch-add and semantic memory-order lowering. No OS API in this module.
- `bunko/kiso/runtime/os/darwin/`: public libSystem import bindings, pthread ABI
  symbol data, target-owned opaque storage sizes and explicit capability status.
  Indirect native call instructions live in the CPU adapter, not this OS module.
  It is a primitive adapter, not the collector's thread/root registry.
- `sign.adhoc_linked`: explicit signing path that preserves dyld binding data.
  Binding payloads larger than one Mach-O page are covered by an actual
  boundary test and an aligned virtual extent. Existing `adhoc` still refuses
  nonempty LINKEDIT input; normal static output is
  unchanged in the eleven complete-byte comparisons.
- Existing generational/LOS emitters reference frozen portable layout constants.
  **Their actual mark/sweep/barrier algorithms are still ARM64-coupled legacy
  STW implementations. Extracting constants does not make those algorithms
  portable.** They have not been replaced or advertised as concurrent.
- `selfhost/resources/bunko_data.mio` regenerated using native Mio
  `selfhost/embed-bunko` / `resourcegen`, without Go or another code generator.

The protocol predicates encode Init→Mark→Remark→Sweep guards, in-flight producer
termination, reader/epoch reclamation guards, abort terminal state, Minor
exclusion and SATB overflow backpressure. Their native unit tests are semantic
contract tests. They do not stop a real mutator or implement tracing/queues.

## Evidence and verification

The authoritative final-source scoped run is
`checkpoint-20261027-04/`: source Manifest/hash, exact commands/exits,
stdout/stderr, per-child wall/CPU/RSS, actual native tests and witnesses, and
source-unchanged verification. Its completed summary records26 native unit tests,16 native thread repetitions
and11 GC metadata witnesses passing, with unchanged source. Older directories below are development evidence,
not substitutes for this final-source checkpoint. The failed checkpoint03
compile (string len requires an array) is preserved; the boundary test now uses
UTF8 bytes and retains the same required multi-page layout assertions.

The long CLI source-check retry was explicitly interrupted for the CPU/OS
instruction-emission refactor (exit -15); it is not a PASS or a completed source
diagnostic. A complete final-source CLI check and compiler fixed point have not
been completed. This remains an acceptance gap.

All paths below are inside this worktree's `build/m19ef-evidence/` unless stated.
Every accepted observation below is backed by actual execution, not static code
inspection. Development failures are retained in
`development-failures-20261027.json`; earlier evidence directories are preserved.

- `E0-baseline-20261027-01`: local/remote HEAD, all original dirty statuses,
  historical GF4/GF5/M19b/c evidence paths/hashes, seed SHA256 and actual version
  and strict signature verification. GF5 overall remains historical
  FINAL_REVALIDATION_IN_PROGRESS; its passed subgates are not relabelled.
- `E1E2-final-contract-20261027-01`: final source manifest and seven native test
  package runs. Read `results.json` and each full JSON stdout for exact results.
  The first complete native CLI source check exhausted its 180-second bound
  (TIMEOUT, no PASS). The longer retry is recorded separately in
  `E1-cli-check-20261027-02`; it was explicitly interrupted for the layering
  refactor and is not a PASS, native build or fixed point.
- `E2-thread-20261027-03`: actual native seed→Mio builder→Mio-linked/signed
  executable; system signature verification; 64/64 successful repetitions and
  one intentional missing-wake failure (expected exit71 within deadline).
  Every ordinary run verifies 200,000 contended atomic additions, 10,000
  bidirectional acquire/release messages, distinct pthread identity, TLS
  isolation, strong CAS success/mismatch, condition-variable wait/wake, join,
  key/condition/mutex cleanup, monotonic timer and queried page size.
  These are raw native thread tests with **no managed GC**, not G4/G5 witnesses.
- `E2-final-native-20261027-01`: final-source native builder/image/signature
  and 16 additional smoke repetitions plus expected timeout failure; per-child
  CPU/wall/peak RSS recorded. Concurrent source-check activity and 5ms audit
  polling are identified as noise; these are not GC/profile performance claims.
- `E2-regression-20261027-01`: existing ARM64 7/7, Mach-O 2/2 and lower 9/9
  native tests; actual production GC emitter sources compiled beside the
  immutable GF4 metadata fixture; all eleven generated images execute exit0.
  All eleven complete signed files are byte-for-byte identical to historical
  GF4 D-generation metadata witnesses. This is narrow compatibility evidence,
  not full M19b/c/NativeFS/LSP/LOS/pressure acceptance on a new compiler.
- `E1-resources-20261027-01`: native resource generator build/execution logs,
  old resource backup and before/after hashes. A second native regeneration
  in `E1-resources-repro-20261027-01` is byte-for-byte identical.

The seed is the verified native GF4 D candidate, SHA256
`4c3f7dcbea536d756c3c4a93c18a999412625184bd5c90123f1c16a0cd9e36da`.
Ordinary source compilation, native instruction generation, binding and signing
were performed by Mio. Python/shell were only audit/test controllers. No
Go VM/Go compiler/C/Clang/LLVM compiler generated any new production component.

Reproduction instructions: `tests/m19ef/README.md`. All GC fixture evidence and
original worktrees are preserved. No Commit/Push/Tag/Release was performed.

## Explicit remaining work

1. Finish E2 RuntimeOp→OS dispatch, production import-table placement preserving
   all 2048 user globals (the raw witness reserves initial __DATA slots),
   production thread lifecycle/registry contract
   and failure injection (create/join/TLS/park failures). The native primitive
   smoke does not prove a managed GC worker is safe to enable.
2. E3: real per-mutator precise shadow chains, registration/exit and blocked-call
   protocol, safepoint insertion and current-epoch Init/Remark handshakes.
   Existing x24 single-mutator ABI cannot be shared unsynchronized.
3. E4: move the real Old tracing/barrier semantics into target-independent Mio;
   cover every root/global/cell/map/array/struct/LOS pointer publication; implement
   actual bounded SATB queues, overflow repair and termination detection.
4. E5: concurrent allocator/sweeper ownership and epoch/quarantine; LOS unlink,
   failed munmap ownership and reader-safe release. Show real mutator/collector
   overlap. Existing STW free lists/LOS chains cannot be used concurrently.
5. Atomic eight-field memory.snapshot and shared metadata ownership remain
   unimplemented. The old odd/even sequence remains single-thread-only.
6. E6: full M19b/c/GCStress/LOS/pressure/NativeFS/CLI/LSP regressions, thousands
   of managed interleavings and final-source Seed→A→B→C→D signed/unsigned fixed
   point. Historical fixed points are not acceptance of this new source.
7. M19f: pure Mio authoritative policy replacing the Go-maintained legacy
   template; High/Balanced/Low integration, cap/pressure/hysteresis correctness,
   workload measurements with pause and p50/p95/p99 distributions, final native
   fixed point. No profile or GC performance PASS is claimed.
8. Linux ARM64/AMD64 and Windows AMD64 are NOT_IMPLEMENTED. Their descriptor /
   semantic operation contract exists; there is no executable backend or pass.

The existing collector remains STW. There is no public switch that silently
pretends to enable concurrent GC. `darwin.capabilities()` explicitly keeps
`precise_roots` and `concurrent_collector` false, so concurrent acceptance fails
closed. Completing the requested architecture and acceptance still requires
substantial implementation; this report does not substitute for it.

## Primary ABI references

The instruction semantics were checked against Arm's
[A64 memory systems documentation](https://documentation-service.arm.com/static/62d6777531ea212bb6627683)
and public threading signatures against Apple's
[libpthread header](https://github.com/apple-oss-distributions/libpthread/blob/main/include/pthread/pthread.h).
The installed SDK headers were also read for the current Darwin opaque type
sizes. These ABI-specific choices are confined to the adapters.


## E2 continuation in progress

Current changes have not yet replaced the accepted historical checkpoint above.
Production additions now include target-neutral scalar Runtime IR, CPU lowering,
Darwin ABI mapping data, appended import placement, and native lifecycle/cleanup
protocols. New thread extension ABI v2 is separate from the unchanged3072B heap
metadata and16B object headers. Its version guard rejects v1 before acquiring
resources. The registry is an enumerable guarded list, not just a counter.

Development native images/logs are preserved in
`build/m19ef-evidence/E2-resume-20261027-01/`. r8 actually executed exit0 with98
context-one starts/joins,488 acquisitions/releases, a two-worker shared registry,
128 injected failures, and real TLS capacity510 before/after. These are preliminary
observations; final-source phase acceptance is still pending. r7's failure was a
fixture migration error (old test-buffer offsets) and is preserved. The current
r9 candidate adds predicate rechecking/deadline preservation after an unrelated
condition-variable signal. E3 and concurrent GC remain unaccepted.
