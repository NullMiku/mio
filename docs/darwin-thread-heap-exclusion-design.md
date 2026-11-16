# Darwin ARM64 threads: heap exclusion and stop-the-world collection

Status: implementation-ready design plus the one change that has landed with it (narrower Epoch classification, section 3). Nothing in sections 4-6 is implemented. The numbers in section 1 come from static analysis of emitted images and from the logs of one historical macOS run; no native macOS ARM64 measurement was taken for this document (the host was Linux x86-64).

## 1. What the cost is

The Darwin thread build ("worker bridge", `bunko/kiso/aot/lower/worker_roots.mio`, `lower.mio`) polls at every solved opcode boundary and, before every opcode classified as a heap step, calls `attached_heap_enter` -> `gc_heap_enter` -> `gc_begin`. Three different things hide behind that call and must not be confused:

| Term | What happens | Cost class |
| --- | --- | --- |
| Epoch entry (heap exclusion) | `gc_begin`: take the registry lock, bump the registry epoch, publish `owner`/`phase=handshake`, then loop over every registered thread (`trylock` of its mutex, read `progress`/`ack_epoch`) until all are acknowledged, then `phase=stopped`. The owner keeps the Epoch until its next poll (`gc_mutator_poll` -> `gc_end`: clear owner, wake every thread's condition variable, unlock registry). | per heap opcode, O(threads), kernel wake-ups |
| Roots snapshot | `gc_scan_roots` walks every acknowledged thread's published shadow frames into `ctx+wr_snapshot` (4000 entries). Done by `runtime_alloc` and `attached_worker_collect`, not by plain heap steps. | per allocation |
| Collection | `gc_collect_stopped` (minor/major) inside an already stopped Epoch. | per collection |

A low collection count therefore says nothing about Epoch cost: a program can enter millions of Epochs and collect once.

Historical evidence (macOS 15 runner, run 43438227070, 3 cores, mpmc_long, stack sample 25 s after start, symbolized against an image rebuilt from the identical tree with `--emit-symbols`): the top-of-stack distribution was 27.9 % `native_word_wait_spin`, 26 % `__psynch_cvwait`, 14.6 % `mach_absolute_time`, 7.9 % `__psynch_cvbroad`, then `attached_gc_poll`, `attached_platform_now`, `attached_registry_lock_retry`, `pthread_mutex_trylock`, `attached_gc_begin_member`. That is the signature of the Epoch protocol (condition-variable parking, broadcast on `gc_end`, clock reads in the owner's retry loop and the park deadline, registry lock retries), not of a stopped system. It does **not** prove a rate, a starvation pattern or the absence of a lost wake-up: no per-worker counters existed. The `mpmc_probe` phase (benchmarks/threads/efficiency.mio) was added to produce exactly those facts on a real Mac.

Static cost per message (before this change, `tests/threads/mpmc_long.mio` for darwin-arm64): 148 heap-entering call sites in 582 polled opcodes; `send` 29 of 103, `receive` 35 of 111, plus `lock`/`unlock`/`wake_*`/`sleep_on` on both sides. Linux x86-64 runs the same workload in 215 ms (Linux uses a heap lock, not per-opcode Epochs).

## 2. Current states and ownership (as implemented)

Per thread (`gc/threads.mio`): `thread_progress` in {`at_work`=0, `parked`=1 (inside a blocked region: native wait, join, ulock), `finished`=2, `gc_parked`=3 (acknowledged an Epoch at a poll)}; `ack_epoch`, `seen_epoch`; `thread_shadow` (published root frame chain); `thread_mutex`/`thread_condition`.

Registry (`gc/safepoints.mio`): `epoch`, `owner` (0 = none), `phase` (`handshake`=1, `stopped`=2), `heartbeat`, member list, registry lock.

Heap ownership by state:

| State | Who may touch the heap |
| --- | --- |
| `owner == 0` | Every thread, but only through opcodes that need no exclusion (they run between two polls) |
| `owner == T`, phase handshake | T waits for acknowledgements; other threads park at their next poll (`gc_poll`) or are already `parked`/`finished` |
| `owner == T`, phase stopped | T alone: allocation, initialization, publication, snapshot, collection. Everything else is parked. T keeps it until its next poll |

Lock order today: registry lock is taken only by the Epoch owner (and thread registration); the owner takes thread mutexes only with `trylock` (never blocks), a thread takes only its own mutex (`gc_poll`, `gc_block_enter/leave`). There is no cycle: nobody blocks on a second lock while holding one. An owner stuck behind an unscheduled thread retries for up to 120 s then aborts the process; a parked thread aborts after 600 s without an owner heartbeat.

Roots: published by `attached_roots_publish` (`emit_shadow_push`) in front of every opcode, before its poll, and valid until the next push. A parked or blocked thread's roots stay valid because its frame chain is not touched while it is acknowledged. The heap is non-moving.

Why an opcode body without its own Epoch is safe today: a thread acknowledges an Epoch only at the poll that precedes an opcode, and `gc_begin` returns only after every non-blocked thread has acknowledged. So an Epoch-free body never overlaps an Epoch owner, a collection, or any other Epoch-owning mutation; it can overlap only other Epoch-free bodies. ARM64 ordering: the acknowledgement is a release store (`stlr`) after the body's loads and stores in program order; the owner reads it with acquire; resumption goes through `gc_park_locked` under the thread mutex.

## 3. Landed: narrower Epoch classification (`heap_step_exempt`, lower.mio)

Exempted from the pre-opcode Epoch in every worker build (the Safepoint poll and shadow-root push stay for all opcodes):

* 19/23/49 with a non-nullable integer/float/bool target in a global slot or a non-captured local: one plain store into `__DATA` or the thread's own frame. Reference, nullable (boxing allocates) and captured-cell targets keep the Epoch. (In `old_sweep` builds 49 keeps its Epoch: that mode retains its previous scalar-store rule.)
* 32, 34, 37, 39, 40, 47, 60 and 31 (when the element is not boxed): loads only. (The old-sweep mode already used this list under its own assumptions; here it is justified by the argument in section 2, and by each lowering: `rt_get_field`, enum tag/payload, upvalue cell load, array length/capacity/element loads, all ending in `runtime_error` on failure.)
* 50-53, 55: register arithmetic. 66: emits no code.

Allocation is never exempted: `runtime_alloc` takes its own Epoch. Not changed: 24 (already not a heap step), 25 calls (already not), 30/33/35/36/38/41-46/48/54/56-65/67.

Effect (static call sites, cross-built darwin-arm64 images): mpmc_long 148 -> 22, pingpong_long 130 -> 16, channel_races 201 -> 19. Dynamic Epoch counts per message are NOT measured (native Darwin was not available). `tests/threads/heap_epochs.py` pins the classification (zero sites in a scalar loop and a read loop; sites kept for reference stores, captured cells, nullable boxing), `tests/threads/heap_epochs.mio` runs the same functions beside Epoch-owning mutators with a sequential cross-check.

**Constraint this places on section 4:** the argument "no Epoch-free body overlaps a mutation" holds only while every mutation is a full stop-the-world Epoch. The heap-lock protocol below breaks it for array reads.

## 4. Proposal: ordinary heap exclusion separate from collection

Goal: protected heap operations (allocation fast path, initialization, stores with barriers, push) take a cheap lock instead of a full-thread Epoch; a real collection still runs the full Epoch.

### 4.1 State

Add `heap_lock` (one word in the registry block; 0 free, otherwise the owner context pointer, bit 0 = waiters). Keep `owner/phase/epoch` exactly as they are: they now describe collection only.

Thread states: add no new `progress` values. A thread waiting for `heap_lock` is `parked` (blocked region), which `gc_begin` already counts as acknowledged.

### 4.2 Operations

`heap_enter` (replaces `gc_heap_enter` for plain heap steps):
1. Fast path: `ldaxr/stlxr` CAS `heap_lock` 0 -> self. Success: done (no registry lock, no epoch bump, no acknowledgement loop).
2. Slow path: shadow roots are already published by the preceding push; call `gc_block_enter` (progress = `parked`), `ulock_wait` on `heap_lock` until it can be taken (CAS), then `gc_block_leave`.
3. Re-check: after `gc_block_leave` returns no collection can be active, because collection requires `heap_lock` (4.3) and this thread holds it. Operands are on the shadow-rooted operand stack and the heap is non-moving, so nothing cached is stale; the opcode body then pops its operands as usual.

`heap_leave`: at the next poll (same release point as today): clear `heap_lock` with `stlr`; if the waiter bit is set, `ulock_wake` one waiter.

### 4.3 Allocation failure and collection

The allocator slow path runs with `heap_lock` held. It then calls `gc_begin` unchanged **while holding `heap_lock`** ("collector owns heap_lock"): other threads are either parked on `heap_lock` (blocked region, already acknowledged), blocked in a native wait, or running Epoch-free opcodes (acknowledge at their next poll). `gc_scan_roots`, `gc_collect_stopped`, `gc_end` are unchanged; `gc_end` does not release `heap_lock`; the next poll's `heap_leave` does.
A thread that wants an Epoch for another reason (`attached_worker_collect`, `old_*` control) first takes `heap_lock` the same way.

### 4.4 Lock order

`heap_lock` -> registry lock -> (thread mutex by `trylock` only). A thread holding a thread mutex never waits for `heap_lock` or the registry lock. `gc_block_enter/leave` take only the thread's own mutex and are called with no other lock held except in the case "waiting for `heap_lock`" where nothing is held. The `heap_lock` holder never blocks on anything that depends on a thread waiting for `heap_lock` (waiters are `parked`).

### 4.5 Initialization, publication, registration, exit

* Initialization/publication: unchanged rule: an object is initialized and published inside one `heap_lock` hold; collection needs `heap_lock`, so the collector never sees a partially initialized object.
* Registration (`thread_attach`/`thread_enter`): registers under the registry lock as today; a child that has not registered is not in the member list, so it needs no acknowledgement, and it cannot touch the heap before `thread_enter` returns (it takes `heap_lock` like anyone). The parent stays in a blocked region in `thread_wait_started` (60 s).
* Exit/failure/shutdown: a thread must release `heap_lock` before `gc_mutator_poll` in `thread_leave`; a faulting thread exits the whole process in public mode, so a lock held by a dead thread is not observable there. In test builds a failed thread must be treated as `finished` and `heap_lock` force-released by the cleanup path only after its owner is proven gone (not designed here; the first implementation should abort instead).

### 4.6 Modes

* old_mark_proto/old_sweep: keep full Epochs for every operation that calls `old_abort_before_mutation` or the sweep lock helpers until separately audited; select by the existing `old_*_enabled` predicates.
* GC stress: unchanged; a stress collection is an Epoch taken with `heap_lock` held.

### 4.7 What must be re-audited (unresolved invariants)

1. **Epoch-free reads (this is the blocker for keeping section 3 under the new protocol).** With `heap_lock`, a mutator runs concurrently with other threads' Epoch-free opcodes. Array length (+8) and payload pointer (+40) are two words that `push`/`reserve`/`truncate` replace: a concurrent index read can pair a new length with an old pointer. Reads 31/32/60 must either take `heap_lock` or use a validated read (re-read the length after the element). Struct fields are immutable and enum tag/payload are immutable after publication, upvalue cells are single words, so 34/37/39/40/47 stay Epoch-free. A published object must also be fully initialized before the store that publishes it (release store), which the present Epoch hides.
2. Free bins, young list, remembered set, large-object table and memory accounting: all are only touched under `heap_lock` or inside an Epoch; every non-opcode caller (`worker_heap_alloc`, `worker_sweep_*`, nativefs cleanup, channel `words_new/free`) must be audited for an access outside both.
3. `runtime_alloc_legacy` currently expects an Epoch-owned complete snapshot; the allocation fast path under `heap_lock` must either skip the snapshot (non-collecting path) or the slow path must escalate before taking it.
4. Fairness and the 120 s/600 s deadlines: `heap_lock` waiters sit in `parked`, so the owner deadline is not charged to them; add a bound on time spent waiting for `heap_lock` only if a hang diagnosis requires it.
5. Wake loss on `heap_lock`: the waiter bit / ulock compare must follow the same handshake as the channel waiter counts (announce with a full barrier, then compare-and-wait).

### 4.8 Regressions that detect violations

| Invariant | Detector |
| --- | --- |
| Epoch-free body never races a mutation | `tests/threads/heap_epochs.mio` (extend with concurrent array push + index readers), `channel_graphs`, `gc_stress`, normal and `--gc-stress` |
| Collector never sees a partial object | `gc_stress`, `alloc_cache`, `gc_lifecycle` under stress |
| Roots valid while waiting for `heap_lock` | `reclaim`, `captures`, `channel_lifecycle` |
| No lock cycle / lost wake | `creation_limit`, `channel_races`, `mpmc_long` (must complete), `pingpong_long` |
| Exit/failure while holding the lock | `shutdown_active`, `stack_overflow`, `invalid_handles` |

### 4.9 Limits, stated honestly

A single `heap_lock` still serializes every protected heap operation: the best case is the uncontended-CAS cost per heap opcode plus serialization of allocation-heavy threads. It removes the O(threads) acknowledgement loop, the registry lock and the broadcast wake-up from ordinary operations; it does not make heap access scale. Per-thread allocation caches (thread-local free lists, per-thread young lists, buffered remembered-set updates) are the next step, and are worth building only if, after the heap-lock change, a native profile still shows the allocator/`heap_lock` as the dominant cost with more than two allocating threads (`alloc_2`/`alloc_4` weak-scaling elapsed time still growing with workers).

### 4.10 Smallest next implementation step

Implement `heap_lock` with the section 4.2/4.3 protocol behind a build flag (default off), for scalar-free paths only: replace the `attached_heap_enter` call in `lower.mio` for opcodes 33/35/48/59/61/63/64 (stores/push) and keep full Epochs for allocation. Gate: darwin-thread-core/programs/faults green in normal and stress modes, then `mpmc_probe` and `alloc_*` phases compared on one Mac.

## 5. Experiment: single-registered-mutator fast path (not implemented)

Expected benefit: only single-mutator phases of thread-enabled programs (main before the first `start`, after the last `join`). It is not a multi-thread scaling fix. Required answers before any code:

* Count publication: `registrations - exits` is updated with `fetch_add` (acq_rel) under the registry lock; a fast path would read it with acquire. Reading 1 is not "one runnable thread": a created-but-unregistered child is invisible to the count. `thread_open_shared` marks the child `starting` and `thread_wait_started` blocks the parent until the child is `running`, so the fast path is safe only if it is switched off before `attached_worker_start` creates the child and stays off until the child has exited and been closed (`thread_close`).
* Nested starts: a child that starts a grandchild does the same; the count is 1 only for the thread that is the sole registered mutator, and a start by a registered thread is the transition 1 -> 2 and must run under the registry lock with the fast path disabled first.
* 1 -> n -> 1: disable by setting a `multi` word (release) before the child is created; re-enable only after `thread_close` of the last child; the transition back must observe the child's `exits` increment (acquire) and its published roots are irrelevant afterwards.
* Pending collection: the fast path must still observe `owner != 0` (another thread cannot exist, but `gc_end` of the thread's own previous Epoch must happen): keep the poll, skip only the acknowledgement loop and registry lock.
* Roots remain valid because the poll/push are unchanged; the real collection path still calls `gc_begin` and obtains ownership.
Not implemented here because it cannot be validated without native Darwin runs of the start/join, nested and shutdown suites.

## 6. Validation status

See DARWIN_THREADS_REPORT.md of the task (native Darwin: NOT_RUN). Commands to run on an Apple M4 Pro are listed there; the benchmark driver is `scripts/ci/thread_bench.py`.
