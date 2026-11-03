# E3 checkpoint — 2026-10-30

**E3 IN_PROGRESS; E4/E5/E6 NOT_RUN; M19e NOT_ACCEPTED.**
The requested E3–E6 objective is not complete. This checkpoint implements and
verifies automatic **main-thread** TLS, exact shadow publication and cooperative
polls for ordinary Mio functions. It does not accept managed user workers,
Concurrent Mark/Sweep or a new compiler fixed point.

## Source and preservation

Worktree: `/Users/hatsunemiku/.codex/worktrees/m19ef-portable-gc/mio`.
Branch: `EXP/m19ef-portable-gc`; HEAD: `f8410f48ee69eb2bcd228eafe423b92fc1dd7d2f`.

Frozen evidence: `build/m19ef-evidence/E3-auto-roots-20261030-08/`.
The sorted SHA256 Manifest covers 182 actual Mio source files. Its SHA256 is
`dbba802cb521e320fcd2df76902691df61add4cb1fab2c3e4df0ab9c8d92748e`.
Both the frozen snapshot and current source matched after all runs. Of the 176
previous checkpoint inputs, 174 are byte-identical; only `lower/lower.mio` and
`runtime/gc/threads.mio` were intentionally extended. Their original contents
were backed up in `E3-auto-roots-20261030-01/`, alongside the initial tracked
patch and status. Existing generated Bunko resources were preserved.

The 13 supplemental ZIP files were installed without overwriting existing files.
Initial ZIP/installed byte hashes, path/symlink checks and the original package
manifest are in `E3-auto-roots-20261030-01/package-install-audit.json`.
No other worktree was modified. No Commit/Push/Tag/Release/reset/clean/stash.

## Implementation

- `bunko/kiso/runtime/gc/threads.mio`: target-neutral `thread_attach` creates the
  current thread's TLS/mutex/condition resources, registers it through the actual
  lifecycle protocol, and rolls failed acquisitions back through owned cleanup.
  It does not fabricate a worker or count create/join operations.
- `bunko/kiso/aot/lower/attached_roots.mio`: separate Darwin/AArch64 adapter for
  startup, real TLS lookup, release publication, `gc_poll`, detach and cleanup.
  The reserved Darwin register x18 is untouched. User values in x0–x17 and LR
  survive callbacks; the existing callee-saved ABI remains in force.
- `bunko/kiso/aot/lower/lower.mio`: explicit internal
  `compile_with_attached_roots` integration entry. Before every solved opcode
  boundary it materializes precise globals/locals/cells/environment/operands,
  polls, then restores the prior chain. Shadow push/pop also publish the head.
  This covers entry, loop backedges, calls and explicit returns in the selected
  path, without pausing inside a half-initialized object. Allocation-result x0
  is preserved through pop publication. The legacy compile APIs emit unchanged
  runtime images; the new path is not yet the ordinary CLI default.
- `tests/m19ef/automatic-roots/`: real Mio frontend→lowering→Darwin linker→Mio
  signing builder, three ordinary source samples and an audit-only controller.
  Samples contain no manual Root/TLS/registry calls.
- `tests/m19ef/main-attach/main.mio`: actual native attach/rollback/reuse witness,
  including invalid version, duplicate attachment and five acquisition faults.

Imports and runtime state are appended after all existing source/private globals.
The 16B object header, 3072B heap metadata and LOS ABI are unchanged. Portable GC
imports no Darwin/CPU code. Capability flags for managed threading and concurrent
collection remain false. Linux/AMD64/Windows remain NOT_IMPLEMENTED.

## Verified native results

All **161 child commands** in the frozen run met deadlines and expected exits;
controller exit was 0. Read `commands.json`, `completion.json`,
`automatic-observations.json`, `gate-results.json` and `summary.json`.

| Ordinary source (16 runs each) | Correct stdout | Polls/run | Publications/run | Max frames | Minor/run |
|---|---|---:|---:|---:|---:|
| recursion, captures, Nullable, Struct/Array | `15400` | 18734 | 60018 | 9 | 1807 |
| no heap, loops, ten-argument calls | `55000` | 43010 | 131031 | 3 | 0 |
| Map, generic Box, 128KiB array | `4797` | 1590 | 4937 | 3 | 83 |

Every run observed one actual registration, one exit and three real resources
acquired/released. Each sample was independently rebuilt twice by the native
Mio builder; its entire signed Mach-O bytes matched. This is image reproducibility,
**not** a source-level compiler bootstrap fixed point. Strict codesign verification
passed. Native signed SHA256 values are recorded in `summary.json`.

The attach failure/reuse witness emitted exactly `[2,2,15,15,0,0,0,5]`:
registrations, exits, acquisitions, releases, creates, joins, membership, injected
faults. All five injected operations follow the real cleanup path; no fake native
thread was counted. The version mismatch acquires nothing; duplicate attach is
rejected without disturbing ownership; the calling thread successfully reattaches.

Same-source regression also passed all 32 native package tests, the prior native
root/handshake and lifecycle witnesses, 64 real multi-mutator heap fixture runs
(64128 Minor / 256 Major / 192 actual thread lifetimes), and all 11 production GC
metadata witnesses. Their complete signed bytes equal the historical GF4 D
images. The two-mutator fixture still constructs its own root layouts and is
**separate** from the ordinary-code automatic main-thread tests.

Additional same-candidate evidence:
`build/m19ef-evidence/E3-auto-globals-20261030-01/`.
Four native runs preserved and printed **every one of 2048 user globals** with
TLS/Shadow/poll insertion enabled. A 2049-global ordinary source was rejected by
lowering with the specifically expected exit 67 and no output image. Its source,
compiler/image hashes, exact output, exit and metrics are recorded separately.

Measured total child wall time: 486.842s; child CPU: 464.790s; largest child peak
RSS: 1581154304 bytes (Darwin). These include compiler/test overhead and are not
GC performance measurements. GC pause p50/p95/p99: N/A, no per-pause timestamps.

## Preserved development failures

- `E3-auto-roots-20261030-01`: builder used an undefined output identifier.
- `...-02` / `...-03`: test builder's Nullable narrowing was not established by
  OS exit; a function return now establishes the checked non-null path.
- `...-05` / `...-06`: container sample used incorrect generic syntax. Original
  failures remain; corrected source passes unchanged functional assertions.
- `...-04` / `...-07`: development success, superseded by the frozen -08 run.

No failed test was deleted, disabled or given a fake success exit.

## Exact continuation boundary

G3.1–G3.7 are not collectively accepted; full gate statuses and reasons are in
`gate-results.json`. Still required before E4:

1. Generalize the compiler TLS adapter from its main context to actual managed
   user workers. Keep shared TLS-key/registry/context ownership valid until joins;
   foreign/unregistered calls currently fail closed.
2. Connect ordinary-code allocation and collection to the complete stopped
   all-mutator root snapshot. The selected path still invokes legacy allocation
   through its executing thread's exact chain; it is not safe to enable arbitrary
   shared-heap user workers. Retain stopped ownership through initialization and
   publication, or establish another proven heap-operation protocol.
3. Integrate NativeFS/public blocking calls and resume/exit paths with root
   publication, parked epochs and safe registry removal. Bound runtime loops and
   cover errors, stale epochs, OOM, false-pointer payloads and shutdown in ordinary
   compiled multi-thread source.
4. Prove ordinary cross-thread-only reachability and eventual death, then repeat
   the entire E3 matrix on that final source. Regenerate embedded Bunko resources
   with native Mio and revalidate before claiming a complete new compiler.

E4 SATB/target-neutral real Old tracing, E5 concurrent reclamation/LOS ownership,
atomic eight-field snapshots and E6 full regressions plus Seed→A→B→C→D have not
been completed. There is no environment/permission failure to report; the
remaining obstacle is unfinished implementation and proof, not a passed gate.

Reproduce this completed scoped checkpoint from the current worktree with a new
output directory (the controller refuses to overwrite existing evidence):

```sh
python3 tests/m19ef/automatic-roots/run.py build/m19ef-evidence/E3-auto-roots-resume-NEW
```

Python only freezes, launches, measures and audits. Every compiler, runtime,
code-generation, link and signing operation is performed by verified native Mio;
no Go/C/Python production stage was introduced. Do not proceed to E4 acceptance
or claim M19e PASS from this checkpoint.

## Later ordinary Worker continuation

See `E3_WORKER_PROGRESS_20261030.md` for actual automatic multi-mutator source
integration, blocked NativeFS/output/wait fixes, preserved failures and current
frozen Worker candidates. The main-only continuation list above is historical.
Full E3 and M19e remain unaccepted pending all gates.

## Final E3 acceptance

Candidate16 completed G3.1–G3.7. See `E3_FINAL_REPORT.md` for the accepted
bounded ordinary Worker path, frozen hash, actual evidence and explicit limits.
The earlier main-only boundaries above are historical. M19e remains NOT_ACCEPTED.

## E4 continuation pointer

Do not restart the completed ordinary Worker integration. Current source work,
retained native failures and exact running candidate are tracked in
`E4_PROGRESS_20261030.md`, `E4_WRITE_SITE_AUDIT_20261030.md` and `status.json`.
The immutable concurrent prototype passed its bounded candidate05; typed SATB
development remains IN_PROGRESS. E5/E6 have not passed. Follow the latest
actual source manifest and command results rather than interpreting a scoped
prototype result as E4 or M19e acceptance.
