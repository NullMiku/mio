# E0 baseline audit — 2026-10-27

Base and remote `Mio-2.1`: `f8410f48ee69eb2bcd228eafe423b92fc1dd7d2f`.
Isolated branch: `EXP/m19ef-portable-gc`. Original untracked specifications copied
without changing their originals. No changes imported from other dirty worktrees.
Full original statuses, seed commands/exits and historical evidence hashes:
`build/m19ef-evidence/E0-baseline-20261027-01/`.

Seed `/Volumes/Sector0/AppData/Mio/mio/build/gofree-native/mio` SHA256
`4c3f7dcbea536d756c3c4a93c18a999412625184bd5c90123f1c16a0cd9e36da`;
actual native version and strict OS signature verification exit 0. GF4 complete
B=C=D signed/unsigned historical fixed point is traceable in GF4 REPORT.md.
GF5 CANDIDATE.json says FINAL_REVALIDATION_IN_PROGRESS; selfhost subgate records
103 passed, 0 failed. Preserve this distinction: no historical overall GF5 PASS
is inferred. M19c historical independent functionality PASS is not global M19 PASS.

| State/ABI | Authoritative implementation | Frozen contract / future owner |
| --- | --- | --- |
| Ordinary object | lower/lower.mio runtime_alloc/mark | type at header+0, flags high 32, length +8, payload +16; 16B alignment |
| Flags | lower/generational.mio sweep/remember | marked=1, scanning=2, Old=8, age starts bit4, remembered=256 (within flags word) |
| Side metadata | lower/generational.mio, large_objects.mio | ordinary `end+header-origin`, 16B `{youngNext,rememberedNext}`; LOS `header-16` |
| Arena metadata | lower/lower.mio | 3072B; origin=metadata+3072; end remains fixed during growth |
| Young/remembered | generational.mio | heads 1048/1056; mode1064; threshold1072; counts1080/1088; currently single mutator |
| Threshold | lower.mio init, generational.mio gen_adapt | initial3; lower2/upper8 runtime comparisons; promotion changes flags/links, never payload address |
| LOS | large_objects.mio | head2560/bytes2568/reclaimed2576/count2584/threshold2592; default131072 physical span |
| LOS mapping | large_objects.mio | next+0,length+8,youngNext+16,rememberedNext+24,header+32,payload+48; failed release retains ownership; at most8 prune attempts |
| Exact roots | lower.mio emit_shadow_push/pop/runtime_mark/scan; lower/types | x24 frame head; `{previous,count,exact values}`; locals/globals/upvalues/cells/operands solved by types; no raw stack scanning |
| Object scan | lower.mio runtime_scan_dispatch | typed Storage/TypedArray/Closure/Cell/Map layouts; numeric buffers not guessed as references |
| Runtime ABI | lower.mio | x23 metadata, x24 shadow head, x20 operand stack; target adapter must preserve these at public ABI call boundary; 16B SP alignment |
| Pressure | memory_runtime.mio / memory_policy.mio | goal2600,limit2608,committed2616,reserved2624,rate2632,level2640,reason2648,seq2656,GCActive2664; objectLimit2712,LOSCommitted2720,highwater2784 |
| Snapshot | memory_policy.mio memory.snapshot | eight fields; existing sequence is NOT synchronization; atomic protocol still required |

No new concurrent metadata allocated in old 3072B space. Thread registry, queues,
epochs and reader synchronization require a separately versioned extension.
Shared fields are presently single-mutator-owned; none may be treated as already
safe for worker access. E3 must supply ownership/synchronization for each field.

Couplings and migration:

- generational/LOS/mark/scan directly use `arm64.Assembler`: preserve compatibility
  while moving semantic rules into gc; CPU adapter lowers RuntimeOps.
- memory_policy has Go-generated machine words: freeze as legacy STW path until
  F1 replaces authoritative policy with pure Mio; no generator run in this work.
- memory_runtime uses Darwin page/syscall assumptions: move to OS VM adapter,
  pass queried page size into neutral budget arithmetic.
- observation reads CPU counter: target Clock operation must provide monotonic
  units and conversion; algorithms must not assume this counter's frequency.
- Mach-O writer currently has no system symbol binding: E2 needs an explicit
  public-libSystem bridge; no private kernel thread entry point is permitted.

Existing coverage references: GF4 runtime/core-manifest and 11 actual native
metadata witnesses (ages, remembered, promotion, major, precision, threshold,
cross graph, alternating, minor scan, raw Storage, shadow-pop); source/GC72 and
four typed-call cases per generation. M19c independent acceptance contains
specialized LOS/pressure/budget/precision witnesses and fixed-point provenance.
Those are historical evidence, never acceptance of this new source snapshot.

E0: PASS (audit only). E1 native negative/contract tests are preserved separately.
No Concurrent, profile, performance or new fixed-point PASS is claimed here.
