# Native Socket / Native argument boundary regression

The main project TCP library is retained. Pure Mio frontend/type checking,
MMA binding signatures and the Darwin ARM64 adapter now implement the same
opaque-resource ABI as that library. Resource kind 3 uses the existing
NativeFS generation-checked table; exact byte-array roots and the existing
syscall enter/leave handshake remain authoritative. GC Core is unchanged.

The native argument checker validates assignability after contextual literal
inference for all Native FS/OS/testing/socket calls. In particular, the old
compiler incorrectly accepted `runtime.close(123,456)` during `check`.
This is a confirmed frontend defect; no unsupported claim of an exploitable
Runtime memory corruption is made.

`run.py NEW_OUTPUT --compiler ABSOLUTE_NATIVE_MIO --compiler-sha256 SHA256`
builds a fresh native Mio source-to-native pipeline, verifies its signature,
produces identical signed images twice, and executes exactly eight native
cases with real kernel loopback peers. These test lifecycle, error bounds,
foreign/stale handles, binary bidirectional payload, zero-read versus EOF,
actual RST and suppressed SIGPIPE. Python only coordinates real peers and
records native outcomes; all production compilation/signing/IO is Mio.
There are no retries, fixed sleeps in Mio, GC semantic changes or waived
assertions. Host readiness waits observe successful native listen publication.

The native type-check tests also validate all nine signatures and reject
wrong types, wrong arity, unknown primitives and preexisting FS/OS ABI type
mismatches. A socket's numeric resource token is never a managed heap root.
The adapter's status buffer and payload/IP arrays are exact managed roots.

The first failed directed candidate remains in E6-socket-directed-20261103-01.
The corrected two-check/eight-native-case candidate is
E6-socket-directed-20261103-02. Neither result constitutes E6 or M19e PASS.
The complete E6 runner includes the socket regression with the new compiler.
