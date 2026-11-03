# E4 write coverage — development, not acceptance

Current candidate: `build/m19ef-evidence/E4-satb-20261030-06`.
E4 IN_PROGRESS. This table distinguishes implementation from native coverage.
The original preimplementation audit is historical; no row here grants E4 PASS.

| Actual source path | Barrier/order | Native evidence | Status |
|---|---|---|---|
| `lower.mio` opcode19 / `emit_global` | Solved heap-reference slot: acquire old value → neutral visit/publication → release new pointer | New ordinary array fixture deletes final Holder global during Mark | Implemented, candidate running |
| opcode23 captured local | Solved local type, Cell.value prewrite → release store → remembered CAS | Ordinary cell fixture now in candidate06 | Implemented, unverified |
| opcode48 upvalue | Solved capture type, same Cell.value order | Same ordinary cell fixture, five prewrite/four non-null calls | Implemented, unverified |
| opcode33/35 / `emit_set_index` | Bounds checked; Storage.pointer flag gates exact prewrite; release word store → remembered CAS | Two real Workers delete6000 Node pointers and update6000 numeric slots | Implemented, candidate running |
| `emit_gen_remember` | Existing list owner remains E3 heap epoch; neutral CAS sets remembered bit40, preserving concurrent color bit41 | Array test exercises same storage header while marker claims colors | Implemented, contention proof still needed |
| Struct/Enum | Native construction path only; no newly proven mutable field setter | Production scanner covers bitmap bounds; no setter acceptance | Not accepted as mutable write coverage |
| Array push/append/reserve/truncate | Abort/join before unsupported opcode executes | Earlier guarded prototype runs; complete bulk SATB still absent | Unsupported for successful concurrent cycle |
| Map operations | Conservative Abort/join guard | Native adversarial map mutation still needed | Unsupported for successful concurrent cycle |
| Closure/Environment/Cell initialization | Legacy allocator Abort/join guard runs before allocation; fresh bytes are not prelogged | Allocation Abort fixture | Concurrent birth unsupported |
| Nullable scalar boxing | Same allocation guard; type analysis includes boxed nullable scalar roots | E3 regression only | Concurrent birth unsupported |
| String/ByteArray helpers | Byte/numeric slots are not logged as pointers; allocations still Abort/join | Actual flagged descriptors added to scanner regression | Partial; helper write audit incomplete |
| Minor / promotion / automatic Major | Abort/join before legacy collection | Prototype safety only | Cooperation unfinished |
| LOS | Exact scanner uses same pointer layout; no concurrent allocation/reclaim permission | Original scanner fixture owns real LOS | Lifecycle/Sweep unfinished |

`gc_old_prewrite` runs under the executing Mutator's E3 heap epoch. Its queue
publication returns before the overwriting release-store. Remark owns a real
all-Mutator snapshot, so no Mutator publication can still race close-if-drained.
The marker's own active task is counted separately. A full queue or protocol
error aborts and joins before compatibility mutation; such a cycle is never a
concurrent Mark success. Positive backpressure/recovery acceptance remains open.

Old colors remain Old-only. No Minor is currently permitted concurrently with
that marker. The next pause/request/ack/release protocol is only a draft in
`build/m19ef-dev/old_pause.mio`; it is not installed production code or evidence.


## Later actual source, bulk candidate04 (under validation)

The earlier table above describes historical SATB06. Current source implements
allocation/Minor and typed bulk/Map; it is not an accepted full E4 tree.

| Write path | Actual order/ownership | Native evidence/status |
|---|---|---|
| Global/Cell/upvalue/index reference slots | acquire old → exact Old queue → release new → remembered CAS where heap-owned | SATB07 accepted scoped; current Minor03 Cell32 + Array12, bulk03 Cell32/Array32 pass |
| Array reserve descriptor.storage40 | prewrite old storage → release new initialized storage → remembered | bulk03 ordinary32, real growth while Mark active |
| Array push word slots | actual Storage.reference24 selects prewrite → aligned release → remembered | bulk03 ordinary32; numeric/byte path skips pointer interpretation |
| Array append reference storage | neutral gc_copy_reference_slots; checked aligned ranges, direction-aware overlapping word copies, prewrite each destination before Release | bulk03 ordinary32 self-append + cross-array; component initially failed undefined platform function |
| Array truncate reference storage | neutral gc_clear_reference_slots; prewrite every dropped pointer then full-word release0 | bulk03 ordinary32 clear3000/6000 actual Old references |
| Map existing entry.value56 | actual entry bitmap32 bit2 gates prewrite → release value → remembered | bulk03 ordinary32 replace1000 keys and real lookups |
| Map insertion descriptor.head40 | initialize fresh next/key/value with exact bitmap under constructor marker pause; prewrite head → release link → remembered | bulk03 ordinary32 insert100 new entries |
| Struct/Enum payload | constructor-only. parser/statement.mio permits identifier and IndexExpression assignments; FieldExpression assignment is rejected. codegen has no SetField opcode | source audit: parser lines113–145/codegen615–640/disasm names; no claim of mutable-field support |
| Closure/Environment/Cell, nullable box, Array/Map/string constructors | allocator requests marker pause; nested allocation/Minor retain pause across complete heap epoch until universal gc_end | Minor03 ordinary32, bulk03 ordinary32, Cell32; no partially initialized concurrent scan allowed |
| Minor/promotions | request/ACK before heap/list/header changes; promoted Old published to real queue; resume after complete constructor epoch | Minor03 ordinary32 pre-Remark exact8010; bulk03 reruns32, ≥200 real Minors per sample |
| Major | explicit legacy operation Abort/joins marker before existing full collection | fixed startup race,8 cancellations pass in Minor03 and bulk03 |
| LOS | real dense4×200000 reference graph traced, then legacy Major actual munmap/accounting | bulk03 ordinary32 reclaimed6400192 bytes each; NOT concurrent sweep/LOS ownership acceptance |

All168 ordinary programs in bulk03 passed, with complete actual sources and
traces. That whole candidate still FAILED on its subsequent component generation:
UNDEFINED_RUNTIME_FUNCTION because thread_platform_program omitted the worker
startup wrapper referenced by the complete Old IR composition. Candidate04 uses
worker_platform_program/worker_bindings/worker_symbols consistently and runs the
same15-check component FIRST, then reruns all ordinary samples. No tests were
dropped. Overflow compensation, repeated epochs, complete fault audit and E5/E6
remain unaccepted. Capability flags stay false.

## Authoritative candidate08 coverage, pending complete E3 revalidation

The historical tables above are superseded for current implementation status.
Frozen manifest `d7e36e3e3bd280cedb9b5c6c7394bae1ccd6710976211af81ffc5ab136a8275e`.
All candidate08 native executions and exact assertions passed. Full E4 gates
remain IN_PROGRESS until same-source E3 revalidation and final review complete.

| Write/operation class | Final implemented rule | Candidate08 real native proof |
|---|---|---|
| Globals, captured Cell/local/upvalue, Array reference index | acquire old → neutral exact prewrite → Release new → preserved remembered CAS | Cell32; Array32 × four complete epochs; ordinary allocation32 |
| Array reserve/push/append/truncate | initialized storage/slot publication; neutral checked direction-aware reference copy and full-word clear; scalar/byte path excluded | bulk32 plus 32 ×15-check real component; real Array/Map workload retained |
| Map replacement/insertion | actual bitmap selects value prewrite; initialized entry → prewrite head → Release head; remembered postwrite | bulk32, 1000 replacements/100 insertions per program |
| Struct/Enum/Closure/Env/Cell/nullable constructor | language has no mutable FieldExpression store opcode; complete constructor heap epoch pauses marker, including nested allocation/Minor | shapes32, lifecycle32 late lambda-capturing registration, ordinary32, stress32 |
| Numeric/float/byte/string payload | exact type layout; no integer/float payload used as edge; immutable bytes require no prewrite | shapes32, scanner32 ×20 checks; 6000 numeric writes per Array epoch |
| Minor/new Old promotion | real request/ACK; complete paused constructor ownership; exact promoted item published, including queue-full deferred tasks | ordinary32 ≥200 Minors; stress32 every-allocation GCStress, ≥184 Mark-period Minors each |
| Queue full/contended/epoch | owned task bit42 and published outstanding count; exact completed/inflight accounting; reuse only after actual join | 32 eight-epoch programs, 256 real cycles/96 explicit cancellations; queue64 ×2002 items |
| Registry/Native block/exit | actual E3 stopped snapshots; new user registration, blocked FIFO roots and exit removal | lifecycle32, blocking32; same-source full E3 now running |
| Major/OOM/shutdown | explicit Abort/actual join precedes compatibility mutation or process teardown; retain mapping on cleanup failure | cancellation8, fatalOOM16, clock error32, actual stack OS failure32, actual self-join OS error/retry32 |

Actual native images remain reproducible under two separate builds. Four
unchanged default E3 images equal candidate17 whole signed bytes. Core scanner
ownership rejects non-owned/stale LOS references before dereference (bounds32 ×9).
SATB-disabled negative candidate02 keeps all four epochs and exposes at least167
lost snapshot objects per program over8 real runs; production source unchanged.
This does not prove actual post-sweep UAF: Sweep is not implemented or accepted.
No handwritten Root publication is used by positive ordinary user programs.
