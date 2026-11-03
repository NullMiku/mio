# Native compilation timing

Baseline: committed `f8410f4`, explicitly authorized by the user on 2026-11-03
without asserting M19e PASS. Implementation lives in its own worktree; no GC
acceptance checkout was modified. No commit/push/tag/release is performed.

Build with a trusted native seed, using the source Bunko override for the first
bootstrap (the old seed does not embed the new profiler):

```sh
SEED build selfhost/cli --bunko-root bunko -o build/timings/mio
build/timings/mio build examples/hello_world.mio --timings
build/timings/mio build selfhost/cli --timings=detail -o build/timings/compiler
build/timings/mio build examples/hello_world.mio --timings-output=timings.json
python3 tests/timings/run.py --compiler build/timings/mio
build/timings/mio test bunko/kiso/profiler --bunko-root bunko
```

All compiler instrumentation, counter aggregation, report formatting, JSON, and
OS adapter APIs are pure Mio. The Python script is an external test/measurement
harness, not part of the compiler. It measures each child with `perf_counter_ns`
and OS `wait4`, saves actual Wall/CPU/peak RSS, hashes every source file, verifies
ad-hoc signatures, and asserts complete signed output SHA256 equality across
repeated enabled/disabled builds. Runs are sequential. Heavy cases run on/off/on (two timed measurements and a
complete-byte comparison); small cases repeat both modes with alternating order.
It also compares Mochi bytes and tests lexer, parser, checker, native frame-limit,
output-write failures, and invalid options. The program is executed separately
for Hello and Bunko, outside its compilation measurement.

The current native OS adapter exposes integer millisecond samples of the ARM64
virtual counter. `kiso/os.monotonic_ns()` provides nanosecond **units**, with
`monotonic_resolution_ns() == 1000000`; it does not invent sub-millisecond
precision. The profiler reads only the OS API and contains no Darwin/ARM64 code.
JSON declares `resolution_ns`; short phases may legitimately report zero. A future
adapter can improve resolution without changing profiler logic. Timer bookkeeping
is charged to the enclosing phase. Quantization may move a millisecond between
adjacent phases; exclusive accounting still reconciles exactly.

Total starts after successful option validation, before frontend initialization,
and stops after artifact publication/chmod or failure diagnostics. It includes
timer bookkeeping and compiler diagnostics, excludes report rendering/JSON
publication and process startup/shutdown, and never includes execution of the
compiled program. External OS wall time separately covers the complete process.
Flags are supported only for `build`. `--timings-output=...` also enables stderr
reporting. `--timings=detail` additionally shows min/max inclusive duration per call.

| Stage | Real boundary |
|---|---|
| Module loading | `frontend.load_package`, including recursive requests/cache checks; nested frontend stages subtracted for exclusive time |
| Lexing | `lexer.lex_with_progress` inside the parser entry |
| Parsing | `parser.parse_with_progress`, inclusive of lexing; exclusive subtracts it |
| Name resolution | `resolver.resolve_package_with_progress` per package |
| Type checking | `typecheck.check_package_with_progress` per package |
| Mochi IR generation | module codegen entry; encoding is nested and subtracted |
| IR encoding / decoding | `encode_layout_version` and pipeline `mochi.decode` |
| Native type analysis | each actual `types.analyze_types` call, including retries in existing specialization |
| Native lowering | native backend entry, including runtime/instruction construction; type analysis and final word assembly subtracted |
| Machine code emission | final `arm64.assembler_assemble` word/fixup materialization; instruction selection is interleaved with lowering |
| Executable generation | `macho.executable`, including image layout and address patches |
| Code signing | pure-Mio `sign.adhoc` |
| Output writing | `fs.write_all` and executable `chmod` |
| Other / overhead | measured Total minus all exclusive instrumented stages |

No independent Optimization, Register Allocation, or Linking phase is claimed.
Cumulative inclusive times can exceed Total because of nesting/recursive module
loads. Sum exclusive rows 0–12 and Other (row 13); do not add Total (row 14) again.
Each ordinary error return closes its scope before propagating. Source diagnostics
are reconstructed using the existing compiler behavior; repeated frontend stages
are measured in the same invocation context. Rendering counts toward Other.
Fatal process termination (signals, runtime corruption, OS kill) cannot execute a
Mio report finalizer.
