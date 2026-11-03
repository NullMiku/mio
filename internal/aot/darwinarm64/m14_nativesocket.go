package darwinarm64

// Mio's low-level socket module uses the same opaque, generation-checked
// resource table as native FS. Only IPv4 stream sockets are exposed in M14.
// TCP connection management remains in the pure-Mio kiso/net/tcp package.
func appendM14SocketEntries(b *m8Assembler, emptyTagged uint64) {
	// Convert Darwin errno to the stable one-byte socket status protocol.
	// Darwin: EBADF=9, EINVAL=22, EAFNOSUPPORT=47, ENOTSOCK=38,
	// ETIMEDOUT=60, ECONNREFUSED=61, ECONNRESET=54, EPIPE=32,
	// EADDRINUSE=48, EACCES=13, EPERM=1, EWOULDBLOCK=35.
	b.label("m14.socket.classify")
	b.cbz(0, "m14.socket.classify.ok")
	for _, item := range []struct{ errno, code uint16 }{
		{22, 1}, {47, 1}, {9, 2}, {38, 2}, {60, 3}, {61, 4},
		{54, 5}, {32, 5}, {48, 6}, {13, 7}, {1, 7}, {35, 8},
	} {
		b.emit(cmpImmX(0, uint32(item.errno)))
		b.bc(0, "m14.socket.classify.errno."+socketDecimal(item.errno))
	}
	b.emit(movzX(0, 9), m8Ret())
	b.label("m14.socket.classify.ok")
	b.emit(movzX(0, 0), m8Ret())
	for _, item := range []struct{ errno, code uint16 }{
		{22, 1}, {47, 1}, {9, 2}, {38, 2}, {60, 3}, {61, 4},
		{54, 5}, {32, 5}, {48, 6}, {13, 7}, {1, 7}, {35, 8},
	} {
		b.label("m14.socket.classify.errno." + socketDecimal(item.errno))
		b.emit(movzX(0, item.code), m8Ret())
	}

	// alloc(fd, errno) -> resource. If the handle table is exhausted, close
	// the newly created descriptor rather than leaking a live TCP socket.
	b.label("m14.socket.alloc")
	m14Enter(b)
	b.emit(subImmX(31, 31, 32), strX(0, 31, 0), strX(1, 31, 1))
	b.emit(movX(2, 1), movX(1, 0), movzX(0, m14SocketKind))
	b.bl("m14.handle.alloc")
	b.emit(strX(0, 31, 2))
	b.cbnz(0, "m14.socket.alloc.done")
	b.emit(ldrX(0, 31, 0), cmpZeroX(0))
	b.bc(11, "m14.socket.alloc.done")
	b.emit(movzX(16, m14SYSClose), svc(0x80))
	b.label("m14.socket.alloc.done")
	b.emit(ldrX(0, 31, 2), addImmX(31, 31, 32))
	m14Leave(b)

	// Configure every new socket to suppress SIGPIPE on writes and allow
	// immediate server restarts. Darwin's SO_NOSIGPIPE is 0x1022;
	// SOL_SOCKET=0xffff, SO_REUSEADDR=4, option value is native int(1).
	b.label("m14.socket.configure")
	m14Enter(b)
	b.emit(subImmX(31, 31, 32), strX(0, 31, 0), movzX(9, 1), strX(9, 31, 1))
	for _, option := range []uint16{0x1022, 4} {
		b.emit(ldrX(0, 31, 0), movzX(1, 0xffff), movzX(2, option), addImmX(3, 31, 8), movzX(4, 4), movzX(16, m14SYSSetsockopt), svc(0x80))
		b.bc(2, "m14.socket.configure.return")
	}
	b.emit(movzX(0, 0))
	b.label("m14.socket.configure.return")
	b.emit(addImmX(31, 31, 32))
	m14Leave(b)

	// prepare(fd, errno) -> resource. A failed setsockopt closes the raw fd
	// before creating an inspectable error handle.
	b.label("m14.socket.prepare")
	m14Enter(b)
	b.emit(subImmX(31, 31, 32), strX(0, 31, 0), cmpZeroX(1))
	b.bc(1, "m14.socket.prepare.alloc")
	b.bl("m14.socket.configure")
	b.cbz(0, "m14.socket.prepare.ready")
	b.emit(strX(0, 31, 1), ldrX(0, 31, 0), movzX(16, m14SYSClose), svc(0x80))
	b.emit(m8Movn(0, 0), ldrX(1, 31, 1))
	b.b("m14.socket.prepare.alloc")
	b.label("m14.socket.prepare.ready")
	b.emit(ldrX(0, 31, 0), movzX(1, 0))
	b.label("m14.socket.prepare.alloc")
	b.bl("m14.socket.alloc")
	b.emit(addImmX(31, 31, 32))
	m14Leave(b)

	// open() -> resource; native errors remain queryable via status().
	b.label("m14.socket_open")
	m14Enter(b)
	b.emit(movzX(0, 2), movzX(1, 1), movzX(2, 6), movzX(16, m14SYSSocket), svc(0x80))
	b.bc(2, "m14.socket_open.error")
	b.emit(movzX(1, 0))
	b.b("m14.socket_open.alloc")
	b.label("m14.socket_open.error")
	b.emit(movX(1, 0), m8Movn(0, 0))
	b.label("m14.socket_open.alloc")
	b.bl("m14.socket.prepare")
	m14Leave(b)

	b.label("m14.socket_status")
	m14Enter(b)
	b.emit(subImmX(31, 31, 32), strX(1, 31, 0), movzX(1, m14SocketKind))
	b.bl("m14.handle.lookup")
	b.cbz(0, "m14.socket_status.invalid")
	b.emit(ldrX(0, 0, 3))
	b.bl("m14.socket.classify")
	b.b("m14.socket_status.write")
	b.label("m14.socket_status.invalid")
	b.emit(movzX(0, 2))
	b.label("m14.socket_status.write")
	b.emit(movX(1, 0), ldrX(0, 31, 0))
	b.bl("m14.status.byte")
	b.emit(addImmX(31, 31, 32))
	m14ReturnTagged(b, emptyTagged)

	appendM14SocketAddressOperation(b, "socket_bind_ipv4", m14SYSBind, emptyTagged)
	appendM14SocketAddressOperation(b, "socket_connect_ipv4", m14SYSConnect, emptyTagged)

	// listen(resource, backlog, status) -> empty string.
	b.label("m14.socket_listen")
	m14Enter(b)
	b.emit(subImmX(31, 31, 48), strX(1, 31, 1), strX(2, 31, 0), movzX(1, m14SocketKind))
	b.bl("m14.handle.lookup")
	b.cbz(0, "m14.socket_listen.closed")
	b.emit(ldrX(9, 0, 0), cmpZeroX(9))
	b.bc(11, "m14.socket_listen.closed")
	b.emit(strX(9, 31, 2), ldrX(10, 31, 1), cmpZeroX(10))
	b.bc(11, "m14.socket_listen.invalid")
	b.emit(movzX(11, 65535), m8Cmp(10, 11))
	b.bc(8, "m14.socket_listen.invalid")
	b.emit(ldrX(0, 31, 2), movX(1, 10), movzX(16, m14SYSListen), svc(0x80))
	b.bc(2, "m14.socket_listen.status")
	b.emit(movzX(0, 0))
	b.b("m14.socket_listen.status")
	b.label("m14.socket_listen.closed")
	b.emit(movzX(0, 9))
	b.b("m14.socket_listen.status")
	b.label("m14.socket_listen.invalid")
	b.emit(movzX(0, 22))
	b.label("m14.socket_listen.status")
	b.bl("m14.socket.classify")
	b.emit(movX(1, 0), ldrX(0, 31, 0))
	b.bl("m14.status.byte")
	b.emit(addImmX(31, 31, 48))
	m14ReturnTagged(b, emptyTagged)

	// accept(resource) -> resource. NULL address pointers mean no peer address
	// is copied into Mio-owned memory.
	b.label("m14.socket_accept")
	m14Enter(b)
	b.emit(movzX(1, m14SocketKind))
	b.bl("m14.handle.lookup")
	b.cbz(0, "m14.socket_accept.closed")
	b.emit(ldrX(0, 0, 0), cmpZeroX(0))
	b.bc(11, "m14.socket_accept.closed")
	b.emit(movzX(1, 0), movzX(2, 0), movzX(16, m14SYSAccept), svc(0x80))
	b.bc(2, "m14.socket_accept.error")
	b.emit(movzX(1, 0))
	b.b("m14.socket_accept.alloc")
	b.label("m14.socket_accept.error")
	b.emit(movX(1, 0), m8Movn(0, 0))
	b.b("m14.socket_accept.alloc")
	b.label("m14.socket_accept.closed")
	b.emit(m8Movn(0, 0), movzX(1, 9))
	b.label("m14.socket_accept.alloc")
	b.bl("m14.socket.prepare")
	m14Leave(b)

	appendM14IOEntry(b, "socket_read", true, emptyTagged, m14SocketKind)
	appendM14IOEntry(b, "socket_write", false, emptyTagged, m14SocketKind)

	b.label("m14.socket_close")
	m14Enter(b)
	b.emit(subImmX(31, 31, 48), strX(1, 31, 0), movzX(1, m14SocketKind))
	b.bl("m14.handle.lookup")
	b.cbz(0, "m14.socket_close.closed")
	b.emit(strX(0, 31, 1), ldrX(0, 0, 0), cmpZeroX(0))
	b.bc(11, "m14.socket_close.done")
	b.emit(movzX(16, m14SYSClose), svc(0x80))
	b.bc(2, "m14.socket_close.save")
	b.emit(movzX(0, 0))
	b.b("m14.socket_close.save")
	b.label("m14.socket_close.done")
	b.emit(movzX(0, 0))
	b.label("m14.socket_close.save")
	b.emit(strX(0, 31, 2), ldrX(10, 31, 1), movzX(11, 0), strX(11, 10, 2), ldrX(0, 31, 2))
	b.bl("m14.socket.classify")
	b.b("m14.socket_close.write")
	b.label("m14.socket_close.closed")
	b.emit(movzX(0, 2))
	b.label("m14.socket_close.write")
	b.emit(movX(1, 0), ldrX(0, 31, 0))
	b.bl("m14.status.byte")
	b.emit(addImmX(31, 31, 48))
	m14ReturnTagged(b, emptyTagged)
}

// bind/connect(resource, IPv4 octets, port, status) -> empty string. The
// sockaddr_in is assembled in a private 16-byte stack buffer. Validate length
// and numeric range before any pointer arithmetic or Darwin syscall.
func appendM14SocketAddressOperation(b *m8Assembler, name string, sysno uint16, emptyTagged uint64) {
	prefix := "m14." + name
	b.label(prefix)
	m14Enter(b)
	b.emit(subImmX(31, 31, 80), strX(1, 31, 1), strX(2, 31, 2), strX(3, 31, 3), movzX(1, m14SocketKind))
	b.bl("m14.handle.lookup")
	b.cbz(0, prefix+".closed")
	b.emit(ldrX(9, 0, 0), cmpZeroX(9))
	b.bc(11, prefix+".closed")
	b.emit(strX(9, 31, 4), ldrX(0, 31, 1))
	b.bl("m14.array.ptr")
	b.emit(cmpImmX(1, 4))
	b.bc(1, prefix+".invalid")
	b.emit(strX(0, 31, 5), ldrX(10, 31, 2), cmpZeroX(10))
	b.bc(11, prefix+".invalid")
	b.emit(movzX(11, 65535), m8Cmp(10, 11))
	b.bc(8, prefix+".invalid")

	// [sp+48..sp+63]: sin_len=16, sin_family=AF_INET(2), sin_port=BE,
	// sin_addr=4 exact octets, sin_zero=8 bytes.
	b.emit(movzX(12, 0), strX(12, 31, 6), strX(12, 31, 7), addImmX(14, 31, 48))
	b.emit(movzX(13, 16), m8StrB(13, 14), addImmX(15, 14, 1), movzX(13, 2), m8StrB(13, 15))
	b.emit(addImmX(15, 14, 2), m10Lsr(13, 10, 8), m8StrB(13, 15))
	b.emit(addImmX(15, 14, 3), m8StrB(10, 15))
	b.emit(ldrX(9, 31, 5))
	for i := uint32(0); i < 4; i++ {
		if i != 0 {
			b.emit(addImmX(9, 9, 1))
		}
		b.emit(m8LdrB(12, 9), addImmX(15, 14, 4+i), m8StrB(12, 15))
	}
	b.emit(ldrX(0, 31, 4), addImmX(1, 31, 48), movzX(2, 16), movzX(16, sysno), svc(0x80))
	b.bc(2, prefix+".status")
	b.emit(movzX(0, 0))
	b.b(prefix + ".status")
	b.label(prefix + ".closed")
	b.emit(movzX(0, 9))
	b.b(prefix + ".status")
	b.label(prefix + ".invalid")
	b.emit(movzX(0, 22))
	b.label(prefix + ".status")
	b.bl("m14.socket.classify")
	b.emit(movX(1, 0), ldrX(0, 31, 3))
	b.bl("m14.status.byte")
	b.emit(addImmX(31, 31, 80))
	m14ReturnTagged(b, emptyTagged)
}

func socketDecimal(value uint16) string {
	if value < 10 {
		return string(rune('0' + value))
	}
	return string(rune('0'+value/10)) + string(rune('0'+value%10))
}
