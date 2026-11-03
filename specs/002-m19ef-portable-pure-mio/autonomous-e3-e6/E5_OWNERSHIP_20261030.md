# E5 installed ownership protocol — native gates IN_PROGRESS

Original16B header,16B side entry,3072B heap metadata and LOS32B prefix remain.
Full-mode separately mapped control extension version1 occupies bytes512..1023;
existing Mark512 layout/version5 and default Worker images remain separate.
Header44 is checked unused by kind/legacy color/generation/age/remembered masks.
It means this exact allocated Old object belongs to the closed Remark dead set.
It is never a root edge, never set on Young objects/new promotions after Remark.

| Storage | Owner / synchronization | Release/reuse proof |
|---|---|---|
| User roots/native buffers | existing real registry epochs, blocked publication | full Remark scans stopped/pinned roots; live readers keep black Old |
| Dead claim set | same Remark owns stopped heap, real marker already joined | claim once; no resume gap between closing mark and preparing dead tasks |
| Intrusive next task | old unused side.youngNext, heap/sweep lock | cache next before destroying any storage; no concurrent whole-heap walk |
| Free bin and ordinary header | shared neutral strong-CAS heap lock | exact processed span only; no coalesce across an unprocessed task |
| Young/remembered/LOS/occupied | Mutator registry heap epoch FIRST, then same lock | never lock→registry; dead remembered members removed before Sweep launch |
| Sweeper | independent actual native thread, token1 | between tasks observes cancel and Mutator waiter; never joins Mutators |
| Mutator lock token | exact current registered context pointer | release before gc_end releases registry; reentry preserves existing owner |
| New ordinary/LOS and promotions | original compiler safe constructor epoch + shared lock | outside captured dead set; no concurrent metadata mutation in step |
| LOS unmap | shared lock; exact owned previous link saved before OS call | only successful real unmap updates other list/charges; no read after unmap |
| Failed LOS release | original mapping/header/charges retained, explicit quarantine chain | actual retry uses original owned address; no fabricated OS success |
| Join/control mapping | main retains all mappings until real join proof | failed join/clock keeps handle; cannot count terminal process teardown as reclaim |
| Abort while Mutator owns lock | cancellation Release BEFORE join | waiting collector checks cancel without needing owned lock; cannot deadlock join |

Lock deadline30s; collector cycle deadline30s; join deadline10s, checked zero clocks.
Task/claim walks also bounded by actual heap/list counts. Mutator waiter prevents
collector from repeatedly winning CAS while an actual stopped heap owner waits.
No fake delay, mock free list, hand root publication or permanent STW Sweep.

Sweep telemetry publishes Acquire/Release counters: claimed544,swept552,pending536,
quarantine576,bytes560; seq664 surrounds only a real nonempty batch, bounded by256 objects and8 actual LOS calls.
Observe increments only after same odd seq is acquired before/after real clock.
Empty queue checks do not count concurrent reclaim. first632/last640, real pthread
identity624, actual starts648/joins656 and unmap attempts736/successes744 are real.
Natural finish releases shared lock while retaining registry ownership, waits for
collector completion, performs real join, then reacquires lock before gc_end.
Such a final wait does not supply positive overlap proof; ordinary Workers must
have already progressed/observed actual nonempty steps in the concurrent window.

Abort joins before clearing claims and counts abandoned-but-still-charged tasks760.
No aborted task is freed twice. A later legacy Major may reclaim retained objects
only after both collectors have joined. Next Init reconstructs mark state; next
Remark captures a fresh closed dead set. Quarantine explicit retry remains owned
until successful release or an explicit cancellation's accounting-preserved handoff.

Native validation still required: compilation and IR validation; ordinary large dead graph
with two automatic-root Workers, actual progress/overlap, Young promotion/Old→Young;
LOS reader hold/drop and failure/retry; free-bin reuse/address stability; repeated
cycles, abort/OOM/shutdown/clock/join; all affected E3/E4 source regressions; E6.
No statement in this implementation audit grants E5 PASS or permits target capability enablement.


### Bounded batch and fatal cleanup review

A Sweep lock turn performs at most8 actual object reclamations, acquiring cancel
between each. A batch never publishes odd seq for an empty queue. Per-object
counters/LOS syscalls stay exact; next tasks are cached before storage release.
Waiter priority applies between bounded turns. No artificial delay was added.

Fatal cleanup may join/discard only when raw caller TLS context equals acquired
registry owner and registry phase is stopped. Otherwise cancel-only85 preserves
mappings/handles/task claims through immediate terminal OS teardown. That path
is not reported as successful join/reclaim; normal shutdown first joins users.
Manual fatal32 verified this distinction before the bounded-batch change; final
same-source repetition is still required.


### Current global root ownership (candidate16)

A blocked ordinary caller frame cannot own an obsolete copy of a shared global
as a root. Worker Shadow descriptor low32 counts all entries; high32 counts the
leading exact global slot addresses. Only those entries are dereferenced by the
neutral walker after the real stopped registry and all ack epochs are checked.
This is a precise compiler-generated static slot map. Native parameters/locals
remain direct values. Direct v1 frames remain accepted; snapshot capacity checks
still apply before any heap callback. Global stores remain SATB + remembered as
before. Object header16B, side16B and LOS layout/threshold unchanged.


Current after17: maximum256 total object attempts and8 actual LOS syscalls per
lock turn; cancel checked between objects. Earlier1..8 descriptions are history.
Counter736 records every actual LOS syscall attempt, including errors; each batch
captures its prior value+8 and ends at that bound. Real object budget decrements
on each successful step. No empty-task loops extend odd seq, and no sleeps or
mock work are introduced. Strict actual same-odd-batch clock observation remains.
