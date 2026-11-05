# kiso/aot/lowerwin

Pure-Mio lowering of Mochi IR to a Windows AMD64 PE32+ console image (stage 2: scalar subset). It reuses the
target-neutral type analysis `kiso/aot/lower/types`, the shared encoder `kiso/aot/x86_64` and the PE writer
`kiso/aot/pe` (extended with `executable_framed` for frame-pointer unwind data). No libc, linker, C, Go or Python in the
compile path.

Supported: int64 and fixed-width integers (wrapping), bool, string constants (`chant`, locals, arguments, globals),
local variables, `moshi/sore/aida`, function calls with arguments and results, recursion, `os.exit` (native function
shape produced by the frontend), `chant` of int/bool/string, division-by-zero trap.

Not supported and rejected at build time with an explicit error (never skipped or mis-compiled): floats, nullable
scalars, arrays, maps, structs, enums, closures/captured locals, string comparison/concatenation, integer conversions,
heap allocation and GC, file system, arguments, environment, threads/TLS. No Windows capability flag is enabled.

Model: the Mochi operand stack is the native stack; arguments are pushed by the caller (a private internal convention).
Win64 ABI applies at the API boundary: `rt.write` / `rt.exit` realign RSP to 16, reserve 32 bytes of shadow space, keep
the fifth `WriteFile` argument and the bytes-written cell in their own slots, and use only volatile registers across
calls. Every emitted function is `push rbp; mov rbp,rsp; [sub rsp,N]` ... `lea rsp,[rbp]; pop rbp; ret` and has a
matching RUNTIME_FUNCTION/UNWIND_INFO (PUSH_NONVOL rbp, SET_FPREG, ALLOC). `tests/windows-amd64/verify_pe.py` checks
the unwind records against the real prologue bytes. Stack: the PE default 1 MiB reserve; deep recursion beyond it
faults (not yet reported as a Mio error).

Status of checks lives in `/docs`-style reports under `tests/windows-amd64`; anything not run is NOT_RUN.
