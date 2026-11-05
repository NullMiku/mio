# kiso/aot/lowerlinux

Pure-Mio lowering of Mochi IR to a static Linux x86-64 ELF64 executable (no libc, no linker, no VM).
It sits next to `kiso/aot/lower` (the Darwin ARM64 backend) and reuses the target-neutral type analysis
`kiso/aot/lower/types`, the x86-64 encoder `kiso/aot/x86_64` and the ELF writer `kiso/aot/elf`.

Files: `lowerlinux.mio` (opcodes, functions, closures), `runtime_objects.mio` (arrays, strings, UTF-8),
`runtime_fs.mio` (NativeFS: files, directories, stat), `runtime_os.mio` (arguments, environment, exit, spawn),
`gc.mio` (allocator, precise mark & sweep collector, crash reporting), `runtime_testing.mio` (test report channel), `runtime_socket.mio` (IPv4 TCP sockets).

Execution model: the Mochi operand stack is the native stack; every function has an rbp frame (arguments pushed by the
caller). Heap objects start with a 16-byte header (kind | size << 8, mark word). Nullable scalars are boxed.
The collector runs at function entry and loop back-edges; each call/poll site is followed by an inline frame descriptor
(`jmp over; count; rbp offsets`) that lists the reference slots of that frame, so roots are exact.

Not supported (reported as errors or as run-time "unsupported operation" stubs, never skipped silently):
maps, string ordering, `chant` of floats, threads, TLS and concurrent collection.
Tests: `internal/aot/linux_purelower_test.go` (differential against the Mochi VM, GC stress, native fixed points).
