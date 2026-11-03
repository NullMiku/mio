# Concrete E2/E3/E4 integration gaps

This is an audit of remaining work, not an implemented handshake or collector.
The production collector must stay STW while any of these gaps exists.

## Precise roots and frame lifetime

`lower.mio:emit_shadow_push/pop` currently materializes exact roots only around
allocation/calls; x24 points into the calling native stack. A worker must not
retain these stack addresses after the owner resumes/pops/returns/exits.
The Init handshake needs an owned snapshot copy, or a proven pinned-frame
lifetime, with explicit overflow/OOM behavior. Merely publishing x24 is unsafe.

`emit_block` opcodes17/18 emit branches directly; there is currently no
back-edge GC poll. Each added poll needs the solved stack/type entry state,
exact locals/globals/cells/upvalues, and must restore the pre-poll native ABI.
`emit_call`, `emit_call_value`, return paths and NativeFS/native-call modes need
consistent registration/handshake ownership. Runtime loops also need bounded
latency or a declared blocked-native mode. User callbacks cannot run during STW.

SATB initial roots must remain owned until the epoch completes. A mutator's
current frames can then change; an unsynchronized worker walk of live frames
is never permitted. Remark takes another complete current-epoch snapshot.
Native thread exit cannot free registry/root storage while an epoch still uses it.

## Current pointer publication inventory

The following existing post-barrier callsites are **not** a complete SATB audit.
They run after stores and cannot recover overwritten old edges:

| Area | Current functions / stores | Required next proof |
| --- | --- | --- |
| Globals | `emit_block` opcodes19/20 → `emit_global` | distinguish pointer layouts; old global roots/snapshot lifetime; release publication |
| Captured locals | cell-set in `emit_block`; captured-cell update opcode41 | save old Cell value before store, only for reference Cell layout |
| Map existing entry | `emit_map_operation`, entry payload+56 | value bitmap; SATB before overwrite; post remembered barrier after |
| Map inserted entry | Map head payload+40; entry next/key/value +40/+48/+56 | construction color; old head edge before publish; precise key/value bitmap |
| Array/Storage | descriptor and backing storage writes around lower.mio array helpers | pointer element widths/layout; backing-store replacement; bulk-copy paths |
| Closure | closure capture and environment initialization | precise capture descriptors; publication color and TLS roots |
| Generational links | `emit_gen_remember`, `gen_register`, minor/promotion | shared ownership, duplicate suppression, Minor/Old exclusion |
| LOS | same typed stores plus mapping list/prune | exact classification and epoch reader lifetime before unlink/unmap |

Numeric Storage cannot be enqueued by inspecting payload bit patterns. New
objects must have a documented initialized/published color; allocation cannot
publish a black container containing unhandled white references. Promotion is
excluded from active Old cycles by the initial scalar protocol until a real
handoff is implemented.

## Shared state owner/synchronization requirements

| State | Current owner | Needed concurrent contract |
| --- | --- | --- |
| Header type/layout | allocating mutator | immutable after safe release publication; preserve precise layout |
| Header flags/age/mark | mutator/STW collector | atomic transitions or exclusive phase ownership; no lost bit updates |
| Free bins + ordinary side metadata | STW allocator/collector | synchronized allocator/sweeper ownership and quarantine before reuse |
| Young/remembered chains | single mutator | serialized or proven atomic insertion/removal; overflow/duplicates bounded |
| LOS links/bytes/charges | single mutator/STW | owned unlink + epoch readers + failed-release ownership |
| Per-thread shadow chain | owner mutator x24 | release-published current-epoch snapshot after parked acknowledgement |
| Mark/SATB queues | absent | producer reservation/publication distinction, acquire consumer, no overwrite |
| Phase/epoch | absent | release transitions, acquire observers, current-epoch acknowledgements |
| Eight-field snapshot | single mutator, plain sequence | actual lock or fully proven seqlock; consistent atomic publication |
| Profile/policy | legacy generated STW code | pure Mio authority; atomic/safepoint publication and saturating arithmetic |

Do not assume spare bytes in the 3072B metadata region. Concurrent state needs a
versioned extension and an explicit reference/lifetime/managed-charge plan.
The existing runtime x23/x24 convention must remain intact at public ABI calls.

Acquire on the last sequence load alone does not order previous data loads on
A64. Release of an odd sequence alone does not order subsequent field stores.
A snapshot implementation must prove BOTH reader and writer ordering; changing
only the sequence loads/stores is insufficient. A small explicit synchronization
protocol may be preferable, but it also needs bounded waits and failure behavior.

## Acceptance still required

The raw pthread smoke is deliberately unmanaged and cannot close any of these
root/barrier/sweep gaps. Tests must include current-epoch stale acknowledgements,
exit/registration during marking, queue exhaustion, GCStress, exact integer
precision, LOS failed unmap ownership, and real mutator/GC overlap. Phase guard
unit tests are useful preparation only. No managed concurrent GC or profile
performance result exists at this checkpoint.

## Native import table and full global capacity

The unmanaged thread witness reserves the first __DATA words for imports and
uses a separate test state area. `darwin.executable` currently binds those initial
slots. **It cannot be passed the managed compiler's existing user-global data
layout unchanged:** that would overwrite user globals. Production integration
must explicitly reserve/place imports outside all existing user/private words,
validate offsets, and preserve the full 2048-user-global capacity and exact-root
classification. The current Mach-O writer bounds globals at2052 to accommodate
four existing private ABI words; imports require a deliberate compatible layout
extension, not stealing those words or reducing user globals. The GF5 full-global
capacity regression must be rerun after that integration. This is another reason
the working raw thread witness does not constitute complete E2 acceptance.
