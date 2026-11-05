# Runtime ABI contract tests (RA-1)

Target-independent programs that every native target must run with the same output as the reference VM. They check
the guarantees of [docs/runtime-abi.md](../../docs/runtime-abi.md), not a particular collector:

| case | contract clause |
|---|---|
| `object_layout` | header, alignment and size rounding of every small size class; field layout of mixed structs; scalar payloads that look like heap addresses are never references |
| `stack_roots` | stack roots in nested calls (five frames) and deep recursion (900 frames) |
| `closures` | closure captures and mutable captured cells, closures in arrays, maps and struct fields |
| `maps_arrays` | references held only by map entries, nested arrays and arrays of maps; overwritten entries |
| `large_objects` | objects above the large-object threshold: retained while referenced, reclaimed otherwise (about 2.5 GiB allocated) |
| `safepoint_roots` | expression temporaries and pending call operands at every safepoint, loop-carried values, indirect calls |
| `cross_generation` | old-to-young references through every reference store of the language (write barrier) |
| `gc_stress` | a mixed object graph rebuilt under continuous garbage |

Every case checks its own invariants and prints `<case>: ok` last; `<case>.expected` is the complete transcript of the
reference VM (`tests/windows-amd64/refvm`). Each case runs twice per target: in the default configuration and built with
`mio build --gc-stress`.

```sh
python3 tests/runtime-abi/run.py --mio <native mio CLI> --target linux-amd64 --output build/runtime-abi \
    [--reference <refvm>]          # VM / native differential, recorded as engine "reference"
python3 tests/runtime-abi/run.py ... --build-only   # cross-target images: execution is NOT_RUN, exit 2
```

`results.json` records PASS / FAIL / NOT_RUN per case, mode and engine. A failing case is never skipped and an expected
transcript is never edited to match a native result.
