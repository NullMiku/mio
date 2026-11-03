# E3 Gate review — candidate16 accepted

E3 PASS for the explicit bounded Darwin ARM64 internal native user-function path.
Candidate16 completed its full same-source regression and source equality checks.
This safety argument accompanies `E3_FINAL_REPORT.md` and actual native evidence.

Candidate Manifest SHA256:
`3c08cd3a3aa11f24aa8854795a06a12e9c2addc3468cbf070903041505323a6f`.

| Gate | Current implementation and witness | Final status |
|---|---|---|
| G3.1 | main +2 real user Workers; shared TLS key; re-registration/reuse; private contexts; callback returns; automatic join; blocking fs/output/wait; distinct actual pthread identities | PASS |
| G3.2 | solved exact global/local/operand/capture/cell maps; native callee-save ABI; ten-arg calls; generic Enum/Struct; recursion90; temporary chant/report strings; returned captured Worker closures | PASS |
| G3.3 | every solved opcode polls; heap stop retained through initialization; forwarded opcode guard; Acquire/Release Epoch and root head; complete bounded all-mutator snapshots | PASS |
| G3.4 | normal frontend-compiled source on shared production allocator; A allocates/B alone retains after A exits; Minor/Major; actual death via occupied/LOS metadata, no freed payload read | PASS |
| G3.5 | object-level stable promotion/remembered/LOS old witnesses; ordinary Old→Young Array/Map; FIFO blocked roots; register/exit serialization; natural user waits and repeated joins | PASS |
| G3.6 | exact type roots, scalar/float and precise old witnesses; OOM2; two-slot exhaustion1; duplicate join1;1000-entry snapshot overflow1; old lifecycle faults, configured-stack failure protocol and rejected object/narrow bridge ABIs | PASS |
| G3.7 | same-source32 CPU/OS/A64/Mach-O/Lower/GC/pipeline native tests, main integration, old managed64, lifecycle and11 exact GC images; no manually published roots in ordinary source | PASS |

## Linearization and lifetime argument

1. Root records contain values selected by solved pointer layouts, not guessed
   bits. The executing thread writes the full record, then Release-publishes
   its head. Native blocked entry publishes the frame before changing progress
   under that context's mutex. Native return cannot restore running progress
   until the coordinator has released its Epoch.
2. A coordinator locks the registry, publishes Epoch/owner and checks every
   member under its context mutex. A running member must park and acknowledge
   this Epoch. Already-blocked members are acknowledged under their mutex.
   Snapshot traversal requires matching current acknowledgments and Acquire
   heads. No running thread's frame is walked speculatively.
3. The collector holds the registry lock through scanning/heap operations.
   Add/remove use that same lock, so a removed context cannot remain reachable
   by an in-progress enumerator. A leaving member can still poll using its
   context after clearing TLS; it does not use adapter TLS callbacks there.
   Context/stack/opaque resources remain owned until actual pthread_join.
4. Before registration, the compiler-generated callback bootstrap frame is
   published and pthread_create publishes its argument context. Parent call
   frames pin the callback until the child enters. Shared key deletion is
   exclusively main-owned and happens after every actual child join.
5. Heap operations own the stopped Epoch through object initialization and
   publication, including forwarded array fast paths. The next solved boundary
   publishes all results before releasing ownership and polling. A contender
   polls while acquiring the registry, so it can acknowledge another owner
   rather than deadlocking while still runnable.
6. User join first waits for natural completion, then invokes owned cleanup;
   it never changes the stop predicate during a legitimate user wait. Errors
   preserve owned handles/resources or terminate the process without freeing
   metadata out from under threads. Output and filesystem native calls park
   exactly at OS boundaries, preserving both registers and native flags.
7. Normal exit joins all callbacks before writing the test completion packet,
   and retains main TLS until that write/NativeFS cleanup finish. Worker-mode
   ordinary process spawn uses posix_spawn; GC code never runs in a fork child.

## Explicit supported bounds

Darwin ARM64 internal native startup bridge, main plus2 reusable Worker slots,
main-owned starts/joins,8MiB Worker stack,1000 merged Root entries,1024 walked
frames,30s natural-completion deadline and bounded handshake/resource failure.
Overflow is an observed safe rejection, not silent truncation. Public thread API
is not added. Foreign threads are not auto-attached. Worker-mode fork-based
spawn_test is rejected at build time; normal os.spawn uses public posix_spawn.
Legacy default compile images retain their previous ABI and behavior.

These bounds do not claim concurrent Old collection. The E3 heap protocol is
STW, and E4 must replace real Old tracing semantics with target-neutral code
plus SATB before independent collector overlap can be accepted. E5 sweep and
E6 final source/embedded-resource reconciliation and new full compiler fixed
point remain NOT_RUN. No pause percentiles are inferred from aggregate CPU.


## Candidate17 revalidation

See `E3_REVALIDATION_20261030_17.md` and candidate17/E3-acceptance.json.
All prior bounded E3 gates pass on the new registry/type-analysis source;
manifest6fa8e1b4be91fc40274ddae23ceda5167be7b632f10f8f9466f2050c57a6e2f8.
Earlier candidate16 evidence remains historical and unchanged.
