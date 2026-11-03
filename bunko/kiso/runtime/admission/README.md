# Runtime Admission Controller (M19d)

`yobu "kiso/runtime/admission";`

This is executable Mio code, supported by the Go VM, Go Darwin ARM64 AOT and
pure Mio Darwin ARM64 lowering. It is a single-owner event-loop decision core.
It does not create threads, execute tasks, implement HTTP, call the collector,
or acquire synchronization locks. Its mutable arrays are private by convention
because Mio currently exposes struct fields; adapters must not mutate them.

## Ownership and integration

The flow is GC → copied M19c pressure words → `observe_words` → admission →
scheduler. The scheduler must own task payloads and their GC roots until actual
execution ends. Admission stores integer tickets and resource estimates only.
Class selection (Interactive, IO, Compute, Background) belongs to trusted local
routing policy. Do not accept a priority class or estimate directly from an
untrusted client. Weights 5:3:1:1 are relative dispatch weights under contention,
not CPU quotas or preemption guarantees.

`observe_words` consumes **exactly eight copied M19c words**: level, reason,
used, committed, limit, allocation rate, GC-active, sequence. Call the existing
native `memory.snapshot` on its owning runtime thread and pass the copy here,
outside collection. No automatic language-level accessor or scheduler pump is
installed in M19d; this explicit adapter boundary remains for the future runtime.
Odd/zero sequence rejection is input validation, **not** atomic publication.
Never read/write this controller or M19c snapshot from concurrent threads.
No callback, user code or admission operation may run inside Stop-the-World.

Time is supplied as nonnegative **monotonic milliseconds**; there is no wall
clock dependency. `create` accepts global concurrency 1..4096, a positive minimum
per-task memory estimate, reserved headroom bytes, and the initial clock reading.
Invalid configuration returns `mu`. The core starts with no usable memory input;
provide a valid snapshot before normal admission. Memory figures use signed
64-bit nonnegative bytes; the adapter must reject unrepresentable native values.

## Event-loop API

- `configure`: per-class concurrency hard cap, queue cap, max task lifetime
  (1..60000ms), only when no tasks are active or waiting. Defaults permit each
  class to borrow all idle global concurrency and queue space.
- `try_acquire`: immediate grant or structured rejection.
- `enqueue`: immediate grant, bounded enqueue, or structured rejection. A caller
  absolute deadline is mandatory; effective deadline also respects class lifetime.
  Requests must have estimates >= the configured minimum estimate.
- `tick`: expire all due waiters, mark running deadline expiry, and dispatch at
  most one queued task. Return events carry ticket/state/reason. Invoke on queue,
  completion and timer events. After a grant, schedule execution and another loop
  turn if capacity is still available. Do not spin on an empty result.
- `next_deadline`: earliest queue/running expiry, or -1 for no task timer.
  The adapter must also periodically refresh pressure and latency feedback.
- `cancel`: waiting tasks are removed immediately. Running tasks become
  CancelPending; tell their executor to stop cooperatively.
- `release(ticket, now)`: executor acknowledgement of actual completion. Running
  cancellation/timeout continues consuming concurrency and estimated bytes until
  acknowledgement. Repeated release and stale reused tickets fail safely.
- `state`, `class_of`: inspect current tickets. Terminal records may be reused;
  after reuse old ticket lookup returns 0/-1. Consumers must process returned
  Tick events and cancellation acknowledgements promptly, not use this as a
  permanent task history. Ticket IDs never wrap (exhaustion rejects new work).
- `stat`, `total_stat`, `active`, `waiting`, `allowed`, `queue_capacity`: bounded
  accounting. Public Stat constants name the per-class fields.

Process due timers before other events at the same timestamp if deadline expiry
must take precedence over a simultaneous cancellation. Time-bearing calls reject
clock rollback. `release` also checks the absolute running deadline directly.

## Budgets and recovery

`allowed = min(latency, memory, configured, pressure_recovery)`.
Latency feedback is injected measured duration, target duration and observed queue
wait, not a claimed p99. Over-target duration or >10ms queue wait reduces the
latency budget by 10% (at least one). Healthy measured feedback increases by one;
Elevated/High/Critical suppress increases. Missing metrics use target=0 and do not
invent data. This is an initial deterministic feedback policy, not M19f tuning.

Memory concurrency uses `(limit-max(used,committed)-reserve)/minimum_estimate`.
Each grant also reserves the individual task estimate. This deliberately charges
in-flight estimates in addition to observed usage: conservative double charging
is possible. Releasing a permit never decrements observed GC usage. Estimates
are admission hints, not a guarantee against arbitrary future allocation/OOM.

Queue capacity is `min(32,ceil(healthy_concurrency/4))`, with per-class caps and
`min(20ms, caller deadline, class deadline)` wait bounds. Capacity is fixed from
configured healthy concurrency; pressure never grows it. Per-class FIFO and
weighted round robin allow idle borrowing and reclaim it on future completions.
New arrivals cannot bypass existing waiters. Blocked class heads do not block
other classes. Without preemption, fairness assumes executors eventually finish
or acknowledge cancellation; the controller cannot forcibly stop an infinite task.

Critical immediately stops grants while running tasks continue. Bounded queueing
still works. It stays restricted while M19c's hysteretic level remains Critical;
it never rewrites or second-guesses that level (including forecast reason bit 4).
Once a Normal snapshot confirms safe headroom, it allows one probe. Three seconds
of Normal/safe observations precede 5% of healthy capacity per second growth
(integer minimum one). There is no elapsed-time catch-up burst. Elevated or
unsafe/GC-active input resets the stability window; High reduces the recovery cap
at most once per second; Critical reentry resets to zero immediately. New safe
headroom after an unsafe interval restarts the three-second window.

State is bounded to `(hard+queue_cap)` ticket slots, 48 class counters, and fixed
scalar cells. Tick returns at most `hard+queue_cap` events; it scans at most ten
weighted class opportunities, each over the bounded slot table. Operations are
O(hard+queue_cap), or at most ten times that for Tick, with no busy wait. Tick's
Mio result array can allocate and trigger GC, which is why it must run outside GC.

## Validation

Run `python3 scripts/validate-admission.py --evidence build/a-new-directory`.
The scenario source is `tests/m19d/scenarios.mio`; named assertions are checked
against exact output in `TestM19dAdmissionDifferential`. Both ARM64 backends run
with and without GCStress, retain controller aliases and LOS payload roots during
real GC, and verify real collector telemetry. Native images and structured timing/
scheduling/GC records are saved when `MIO_M19D_EVIDENCE_DIR` is set. Scheduling
counts and clock/pressure/latency inputs are deterministic simulations; compile,
sign/execute timing and GC counts are real measurements. They are not HTTP load
or production throughput/latency measurements. Future HTTP rejection mapping
(e.g. 503) belongs entirely in an HTTP adapter.
