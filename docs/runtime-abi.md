# Mio Runtime ABI — contract revision RA-1

Status: **in force for Mio-2.1 native targets** (darwin-arm64, linux-amd64, windows-amd64). Machine-checked by
`bunko/kiso/runtime/abi` (declared profiles) and `tests/runtime-abi` (behaviour on every target).

## 1. Versions and what they name

| name | what it versions | where |
|---|---|---|
| **RA-1** (`abi.contract_revision = 1`) | this contract: guarantees every native target gives a Mio program | `kiso/runtime/abi` |
| **Object ABI v1** (`gc.layout_version = 1`) | the frozen generational object layout of M19b/M19c | `kiso/runtime/gc/layout.mio` |
| **x64-marksweep-v1** | the object layout of the x86-64 backends | `kiso/aot/lowerlinux`, `kiso/aot/lowerwinrt` (`object_layout_profile = 2`) |
| M19ef protocol | the concurrent Old-GC protocol (`kiso/runtime/gc`), Darwin only, not enabled by default | `specs/002-m19ef-portable-pure-mio` |

RA-1 does not introduce a third object layout. It names the two layouts that exist (*profiles*) and fixes the
behaviour both must have. Changing a profile's layout requires a new profile version and a migration test; changing a
guarantee below requires RA-2.

## 2. What is uniform, what is per target

**Language semantics (must be identical on every target).** For the same program and input every target produces the
same output and exit status as the reference VM, or fails with an explicit runtime error the VM also reports. An object
reachable from a root is never freed or overwritten; an unreachable object never becomes observable again. Scalar
payloads (`int64`, `float64`, packed nullable scalars, enum tags) are never treated as references. These are tested by
`tests/runtime-abi` on every target, in the default configuration and with `mio build --gc-stress`.

**Binary layout (uniform inside a target, not across targets).** Native images never exchange heap objects, link with
each other or share a heap with another runtime, and the Go+C reference backend (`internal/aot/linuxamd64`) produces
independent executables. Cross-target byte compatibility of objects is therefore not required; each target must match
its own profile exactly, and the profile is checked against the emitter constants.

**Free per target.** Collection algorithm and policy, heap reservation, thresholds, safepoint placement (subject to §4),
root-finding mechanism, OS adapter and executable format.

## 3. Object layout

Common to all profiles: 64-bit little-endian words; every heap object starts with a **16-byte header** (two words);
objects never move (non-moving collectors only); references are full machine addresses or 0 for `mu`.

| | generational-v1 (darwin-arm64) | x64-marksweep-v1 (linux-amd64, windows-amd64) |
|---|---|---|
| header | 16 B; type id / size, GC state | 16 B: `[0] kind \| total_bytes << 8`, `[8]` mark word |
| alignment / size granule | 16 B / 16 B | 8 B / 8 B |
| type metadata | type ids 100–107 (struct, descriptor/storage, closure, environment, cell, box, enum) | kind byte in the header, e.g. 1 struct, 2 enum, 3 array, 4/5 byte/word backing, 6 string, 7 closure, 11 box; 0 = free block |
| pointer layout | per-type exact layout from the analysed Mochi | struct/enum: reference bitmap at `[24]`; array: `width \| reference << 8` at `[32]` |
| GC metadata | separate 3072 B side metadata region (young list, remembered list, counters, LOS state) | collector state words in the data segment; mark word in the header |
| large objects | separate large-object space from 128 KiB (`gc.default_los_threshold`), same generations and barrier | none: large objects are ordinary blocks of the free-list heap |
| generations | Young/Old, promotion age 2..8, non-moving promotion | single generation |

Strings: interned constants are tagged ids on Darwin and static data on x86-64; both are skipped by marking. Nullable
scalars are boxed on every target.

## 4. Root protocol

* **Globals** are roots for the whole program run, on every target.
* **Stack roots** are exact. Darwin keeps a solved *shadow frame* per call; x86-64 places an *inline frame descriptor*
  (`jmp over; count; rbp-relative slots`) after every call and poll site, so a frame is scanned from its return address.
  Every value of reference type live across a call or safepoint — locals, parameters, and evaluation-stack temporaries
  such as pending call operands — is in a described slot.
* **Closure captures** live in heap environments/cells (Darwin types 104/105, x86-64 closure kind 7) that are traced
  like any object; a captured mutable variable is one shared cell.
* **Register roots**: no target keeps a reference only in a register across a safepoint. On x86-64 no runtime
  routine collects, so routine temporaries need no roots; on Darwin the allocator is the collecting routine and the
  values live across it are in the caller's shadow frame.
* **Safepoints**: a collection can start only at a safepoint. Darwin: allocation (and, under `--gc-stress`, every
  allocation). x86-64: function entry and loop back-edges. Runtime routines never collect in the middle.
* **Root lifetime**: a described slot is a root while its frame is active; a frame's roots end when it returns.
  A stale slot can keep an object alive until the frame returns, never longer.

## 5. GC semantics

* **Allocation** returns zeroed memory of at least the requested size; exhaustion is the explicit runtime error
  `memory` (never a silent fallback).
* **Reachability and precise scanning**: only header-described references are traced; marking ignores 0 and, on
  x86-64, anything outside the heap bounds.
* **Write barrier and cross-generation references**: Mio has no struct field assignment, so reference stores are array
  element stores, map inserts/overwrites, `array.push`/`append_all`, captured-cell assignment and global assignment.
  On the generational profile every one of these records an Old→Young edge in the remembered set; the single-generation
  profile needs no barrier. `tests/runtime-abi/cases/cross_generation.mio` exercises every path.
* **Lifetime**: an object lives exactly as long as it is reachable at the last safepoint; there is no finalization and
  no weak reference in the language.
* **Threads / TLS (future constraint)**: every target is single-mutator today. The M19ef protocol (per-mutator
  safepoints, SATB, TLS roots) exists only for Darwin and is not enabled by default. A target must refuse to start
  managed threads it cannot register with its collector (fail closed); enabling threads on any target requires RA-2.

## 6. Target notes

* **darwin-arm64**: AArch64 code, Mach-O written by `kiso/aot/macho`, ad-hoc signed by `kiso/aot/sign`.
* **linux-amd64**: SysV-style frames with rbp chain, static ELF64, raw syscalls, no libc.
* **windows-amd64**: Win64 calling convention at every KERNEL32 boundary (`rt.*` routines realign RSP to 16 bytes and
  reserve 32 bytes of shadow space; rcx, rdx, r8–r11 are treated as clobbered); program functions and Win64 boundary
  routines have RUNTIME_FUNCTION/UNWIND_INFO; the ported runtime routines (allocator, collector, object helpers) have
  no unwind records. Nothing in the image raises or handles SEH exceptions, so the gap affects only debuggers and
  crash reports; a fault ends the process with the Windows exception code. Roots do not depend on unwinding: the
  collector walks the rbp chain with the same inline descriptors as Linux.

## 7. Verification

| check | where | engine |
|---|---|---|
| declared profiles satisfy RA-1, match emitter constants | `bunko/kiso/runtime/abi` (`mio test`) | native and reference VM |
| contract behaviour, default and `--gc-stress` | `tests/runtime-abi/run.py` on each target | native |
| VM / native differential of the contract programs | `run.py --reference` | reference |
| target-specific collectors | `internal/aot` Linux GC stress, Darwin M19ef witnesses | as recorded by CI |

See [docs/testing.md](testing.md) and [docs/ci-pr-integration.md](ci-pr-integration.md) for how the results are run and
reported.
