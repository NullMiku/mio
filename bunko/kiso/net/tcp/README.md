# `kiso/net/tcp`

Blocking, IPv4-only TCP for Mio. The public connection management, error
translation, short-write handling, and `kiso/io` adapters are implemented in
`tcp.mio`. The low-level `mio/sys/socket` functions are native system-call
primitives: the VM uses a host syscall adapter, and Darwin/ARM64 Native AOT
lowers the same signatures to direct BSD syscalls.

```mio
yobu "kiso/net/tcp";

waza send_greeting(connection: tcp.Connection?) -> unit {
    moshi (connection == mu) { kaesu; }
    kaku sent = tcp.write_all(connection, [uint8(72), uint8(105)], 0, 2);
    kaku closed = tcp.close(connection);
}

kaku address = tcp.ipv4(uint8(127), uint8(0), uint8(0), uint8(1), 8080);
kaku result = tcp.connect(address);
send_greeting(result.connection);
```

Server-side functions: `listen`, `listen_with_backlog`, `accept`, and
`close_listener`. Connections expose `read`, `write`, `write_all`, `close`,
`reader`, and `writer`.

`read` and `write` are byte-stream operations and can return partial counts.
`read.eof` signals a graceful remote close. Use `kiso/io.read_full` to read an
exact byte count, or `tcp.write_all` to retry short writes. Resources should
be explicitly closed; the runtime also closes remaining handles at shutdown.

Current scope: IPv4 literals, blocking sockets, macOS ARM64 Native AOT and
Unix-like VM backends. DNS, IPv6, timeouts, TLS, and a Windows socket backend
are not implemented in this first iteration.

Two runnable examples live in `examples/tcp_echo_server.mio` and
`examples/tcp_echo_client.mio`. Start the server first, then the client.
They use loopback port 18080; the server serves one connection and exits.

Native AOT on macOS ARM64 uses the existing two-stage toolchain:

```sh
go run ./cmd/mio build examples/tcp_echo_client.mio
go run ./cmd/mochi-aot -o tcp-client examples/tcp_echo_client.mochi
codesign --force --sign - tcp-client
./tcp-client
```

For a VM run, use `go run ./cmd/mio run examples/tcp_echo_client.mio`.
