# E2 native thread/synchronization acceptance — 2026-10-28

**E2 PASS, Darwin ARM64 only. M19e NOT_ACCEPTED; E3–E6 and M19f remain required.**

Authoritative evidence: `build/m19ef-evidence/E2-acceptance-20261027-01/`.
The controller copies and hashes all input Mio sources before execution, runs
serially against that snapshot, records commands/exits/stdout/stderr/wall/CPU/RSS,
and verifies both snapshot and worktree source are unchanged at completion.
Manifest SHA256: `2064be43c368ec6f0e9029428d1654f52dca9fb6cc4373b5b814c9ae55aaa136`.
Native seed SHA256: `4c3f7dcbea536d756c3c4a93c18a999412625184bd5c90123f1c16a0cd9e36da`.

## Implementation boundaries

- `runtime/ir`: target-neutral scalar functions, virtual values, semantic native
  operations, symbolic control flow. Runtime execution performs no managed
  allocation. This is production runtime generation, not a mock interpreter.
- `runtime/gc/threads.mio`: lifecycle, registration/unregistration, ownership,
  failure cleanup, first-error CAS, finite waits, quarantine/retry protocols.
  No CPU instructions, pthread names, OS error numbers or executable formats.
- `runtime/cpu/aarch64/program.mio`: register/stack ABI, native lowering and
  function-address relocation. Native return widths are explicit binding data.
- `runtime/os/darwin/operations.mio`: public ABI selectors and widths, native
  timespec/clock conversion, Darwin timeout normalization. No instruction emitter.
- `runtime/os/darwin/link.mio`: append imports after every user/private global;
  preserve multi-page LINKEDIT. The ordinary static writer remains unchanged.
- `macho.executable_with_runtime_data`: separately bounded private extension;
  the old2052-word source/private envelope and2048-user limit stay intact.

Thread extension ABI v2 has288 bytes, including exact shadow-head slot168,
registry linkage256, membership264 and epoch slots272/280. Registry v2 has64
bytes: version0, active8, registrations16, exits24, head32, lock40, epoch48,
coordinator state56. These are separately owned native buffers, never overlays
on the frozen3072-byte GC metadata,16-byte object headers or LOS prefixes.
The version guard rejects the preliminary v1 before resource acquisition.

## Ownership and synchronization

Context/import/buffer addresses are initialized before native create. The parent
owns key/mutex/condition/handle flags and acquisition/release accounting. Worker
TLS is installed before publishing registration. Registry membership/list/count
transitions are serialized by an AcqRel CAS lock with a monotonic deadline;
enumeration requires that lock. Unlink precedes membership removal/public exit.
A context cannot be destroyed while still linked. Root precision/GC epochs are
not established by this thread acceptance; E3 must integrate them.

Stop, progress and state publication use release stores/acquire readers. Errors
are latched by strong CAS, so a successful operation cannot erase another
thread's first error. The waiting predicate is checked while holding its mutex;
spurious/unrelated wakes recheck it and retain the original absolute deadline.
Join failures retain ownership and preserve the independent completion marker.
Only a successful real join permits handle release; a failed cleanup retains the
remaining resources in quarantine. Retrying a corrected join completes cleanup.

## Actual native results

-32/32 unit/regression tests, including the original full2048-global/private OS
  and testing-state native pipeline regression.
-64 fault-instrumented lifecycle runs and16 production runs without fault hooks.
  Total6896 real native thread creations and successful joins; two simultaneous
  workers and a distinct parent observed; locked registry enumeration verified.
-8192 one-shot injected faults across TLS key creation, mutex/condition setup,
  thread create, worker TLS set/get, join and park, with production cleanup paths.
-Real TLS exhaustion reports native error35; capacity510 before/after every run.
  This verifies returned OS key capacity, not merely a synthetic resource counter.
-Real join-self error11; replacing a worker handle by the caller's valid handle
  forces both join attempts to fail. Ownership is verified retained; restoring
  the actual worker handle permits real join and balanced cleanup.
-Actual condition-variable timeout normalization, unrelated signal/re-park,
  stopped predicate wake and externally bounded missing-wake negative(exit71).
-16 atomic/message runs, each200000 contended fetch-add operations and10000
  bidirectional release/acquire publications plus CAS success/mismatch and TLS.
-11 actual production GC metadata witnesses execute and their complete signed
  bytes equal historical GF4 D outputs. This is compatibility evidence only.
-All sources, generators, native signing and image generation are Mio. Python
  only copies/launches/measures/audits; codesign verifies but does not sign.

The fault hook substitutes a result before acquisition; it does not fake an OS
thread. Real acquisitions/joins/destruction still execute. Both instrumented and
uninstrumented binaries are tested. Each process checks all2052 existing data
words after lifecycle operations and compares real TLS capacity before/after.
RSS is measured, but no claim is made that libSystem releases every cached page.

See summary.json, results.json, lifecycle-observations.json, runtime-comparison.json
and the source snapshot. Development failures/r1–r9 artifacts remain preserved;
they are not acceptance inputs. No test was removed or weakened to obtain PASS.

## Explicit exclusions

No managed multi-mutator GC, safepoint/root handshake, SATB, concurrent mark/sweep,
atomic eight-field memory.snapshot, profile tuning or new compiler fixed point
is accepted here. Default managed GC remains the old STW implementation. Future
Linux ARM64/AMD64 and Windows AMD64 backends remain NOT_IMPLEMENTED. No Commit,
Push, Tag or Release occurred. E3 starts after this accepted source snapshot.
