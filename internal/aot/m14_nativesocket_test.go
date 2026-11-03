package aot

import (
	"bytes"
	"fmt"
	"io"
	"net"
	"path/filepath"
	"runtime"
	"testing"
	"time"
)

// Native TCP primitives must lower into actual Darwin ARM64 code. A regular
// MMA binding with no native body would otherwise compile into an empty stub.
func TestM14NativeSocketCompilesPureMioTCP(t *testing.T) {
	root, err := filepath.Abs(filepath.Join("..", ".."))
	if err != nil {
		t.Fatal(err)
	}
	sources := []string{
		`yobu "mio/sys/socket";
kaku handle = socket.open();
kaku status: []uint8 = [0];
socket.status(handle, status);
socket.bind_ipv4(handle, [uint8(127), uint8(0), uint8(0), uint8(1)], 0, status);
socket.listen(handle, 8, status);
socket.close(handle, status);
`,
		`yobu "kiso/net/tcp";
kaku address = tcp.ipv4(uint8(127), uint8(0), uint8(0), uint8(1), 8080);
kaku result = tcp.connect(address);
chant(result.error == mu);
`,
	}
	for _, source := range sources {
		program := m17CompileMio(t, root, source)
		image, err := CompileDarwinARM64(program)
		if err != nil {
			t.Fatalf("Darwin ARM64 native socket lowering: %v", err)
		}
		if len(image) < 4096 || !bytes.Equal(image[:4], []byte{0xcf, 0xfa, 0xed, 0xfe}) {
			t.Fatalf("expected a nonempty Mach-O executable, got %d bytes", len(image))
		}
	}
}

// Runs only on the target OS. The Linux CI compile test above cannot validate
// Darwin's actual socket syscall ABI, sockaddr layout, or kernel behavior.
func TestM14NativeSocketDarwinLoopback(t *testing.T) {
	if runtime.GOOS != "darwin" || runtime.GOARCH != "arm64" {
		t.Skip("native TCP loopback requires macOS ARM64")
	}
	server, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer server.Close()
	serverError := make(chan error, 1)
	go func() {
		conn, err := server.Accept()
		if err != nil {
			serverError <- err
			return
		}
		defer conn.Close()
		if err := conn.SetDeadline(time.Now().Add(5 * time.Second)); err != nil {
			serverError <- err
			return
		}
		request := make([]byte, 2)
		if _, err := io.ReadFull(conn, request); err != nil {
			serverError <- err
			return
		}
		if !bytes.Equal(request, []byte{17, 18}) {
			serverError <- fmt.Errorf("unexpected native request: %v", request)
			return
		}
		_, err = conn.Write([]byte{19, 20})
		serverError <- err
	}()
	root, err := filepath.Abs(filepath.Join("..", ".."))
	if err != nil {
		t.Fatal(err)
	}
	port := server.Addr().(*net.TCPAddr).Port
	source := fmt.Sprintf(`yobu "kiso/net/tcp";
yobu "kiso/io";
waza exercise(connection: tcp.Connection?) -> unit {
    moshi (connection == mu) { kaesu; }
    kaku sent = tcp.write_all(connection, [uint8(17), uint8(18)], 0, 2);
    chant(sent.count); chant(sent.error == mu);
    kaku data: []uint8 = [0, 0];
    kaku received = io.read_full(tcp.reader(connection), data, 0, 2);
    chant(received.count); chant(received.error == mu);
    chant(data[0]); chant(data[1]);
    kaku closed = tcp.close(connection); chant(closed.error == mu);
}
kaku opened = tcp.connect(tcp.ipv4(uint8(127), uint8(0), uint8(0), uint8(1), %d));
chant(opened.error == mu);
exercise(opened.connection);
`, port)
	program := m17CompileMio(t, root, source)
	output, err := runM12Native(t, program)
	if err != nil {
		t.Fatalf("native TCP execution: %v output=%q", err, output)
	}
	if string(output) != "hai\n2\nhai\n2\nhai\n19\n20\nhai\n" {
		t.Fatalf("unexpected native TCP output: %q", output)
	}
	if err := <-serverError; err != nil {
		t.Fatal(err)
	}
}
