# kiso/aot/lowerwinrt

Heap-capable pure-Mio lowering of Mochi IR to a Windows AMD64 PE32+ console image (stage 3). It is the Linux backend
(`kiso/aot/lowerlinux`: allocator, precise mark & sweep collector with inline frame descriptors, strings, arrays, structs,
enums, nullable scalars, closures, maps, floats, NativeFS) with the ELF/syscall assumptions replaced by a Windows layer.
`kiso/aot/lowerwin` remains the small scalar backend; this package supersedes it for programs that need a heap.

Files copied from `lowerlinux` and changed only where noted: `lowerwinrt.mio` (frames use `sub rsp` + unwind records; write/exit
helpers call `rt.write` / `rt.exit`; two-pass-free layout), `gc.mio` (heap/mark-stack initialisation, commit-on-demand bump
allocation, fixed data base), `runtime_fs.mio` (`syscall` -> `call rt.syscall`; os/socket runtime removed), `runtime_objects.mio`,
`maps.mio` (unchanged). `winos.mio` is new and holds everything Windows-specific.

* Image: fixed base 0x140000000, no relocations, `.data` at RVA 0x2000000 (`pe.executable_placed`) so absolute data addresses are
  constants; KERNEL32 is called through `call [rip+rel32]`. Stack reserve 64 MiB. Text must stay below 32 MiB.
* Win64 ABI at the API boundary: `rt.write`, `rt.exit`, `rt.virtual_alloc`, `rt.commit`, `rt.init`, `rt.syscall` realign RSP to 16
  bytes, reserve 32 bytes of shadow space, keep stack arguments in their own slots and treat rcx, rdx, r8-r11 as clobbered.
* Heap: 8 GiB VirtualAlloc reservation, first 16 MiB committed, further 16 MiB steps committed by `rt.alloc.grow`; 512 MiB mark
  stack committed up front. Exhaustion is the explicit runtime error "memory".
* `rt.syscall` implements the Linux system calls the fs layer issues, on Win32: read, write, open (read / create+truncate /
  create+append / directory), close, stat (mode only), mkdir, getdents (synthesised from FindFirstFileW/FindNextFileW). Anything else
  returns -ENOSYS. `/dev/stdin|stdout|stderr` map to the standard handles. Directory order is the OS enumeration order.
* Unwind info: program functions and Win64 boundary routines are frame-pointer functions with RUNTIME_FUNCTION/UNWIND_INFO; the
  ported Linux runtime routines (allocator, collector, object helpers, fs layer) are not covered.
* Not implemented (explicit runtime error "unsupported operation"): os arguments/environment/spawn/exec/pid/chmod/remove/rmdir/
  real_path/monotonic_ms/stdin readiness, sockets, testing runtime. Threads, TLS and concurrent GC are not enabled. No crash
  handler: a fault ends the process with the Windows exception code.
