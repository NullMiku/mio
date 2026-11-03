package main

import (
	"bytes"
	"fmt"
	"io"
	"net"
	"os"
	"path/filepath"
	"runtime"
	"testing"
	"time"
)

func runTCPSource(t *testing.T, source string) (string, string, int) {
	t.Helper()
	path := filepath.Join(t.TempDir(), "main.mio")
	if err := os.WriteFile(path, []byte(source), 0o600); err != nil {
		t.Fatal(err)
	}
	var stdout, stderr bytes.Buffer
	exit := runCLI([]string{"run", path}, &stdout, &stderr)
	return stdout.String(), stderr.String(), exit
}

func TestKisoTCPClientRoundTrip(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("Windows socket primitive backend has not been implemented")
	}
	t.Setenv("MIO_BUNKO", mathBunkoRoot(t))
	listener, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer listener.Close()
	serverError := make(chan error, 1)
	go func() {
		conn, err := listener.Accept()
		if err != nil {
			serverError <- err
			return
		}
		defer conn.Close()
		if err := conn.SetDeadline(time.Now().Add(5 * time.Second)); err != nil {
			serverError <- err
			return
		}
		payload := make([]byte, 3)
		if _, err := io.ReadFull(conn, payload); err != nil {
			serverError <- err
			return
		}
		if !bytes.Equal(payload, []byte{2, 3, 4}) {
			serverError <- fmt.Errorf("unexpected request bytes: %v", payload)
			return
		}
		if _, err := conn.Write([]byte{9, 8, 7}); err != nil {
			serverError <- err
			return
		}
		if err := conn.(*net.TCPConn).CloseWrite(); err != nil {
			serverError <- err
			return
		}
		serverError <- nil
	}()
	address := listener.Addr().(*net.TCPAddr)
	source := fmt.Sprintf(`yobu "kiso/net/tcp";
yobu "kiso/io";
waza exercise(connection: tcp.Connection?) -> unit {
    moshi (connection == mu) { kaesu; }
    kaku invalid = tcp.write(connection, [1], 1, 1);
    chant(invalid.error != mu);
    kaku written = tcp.write_all(connection, [1, 2, 3, 4, 5], 1, 3);
    chant(written.count); chant(written.error == mu);
    kaku data: []uint8 = [0, 0, 0, 0, 0];
    kaku read_result = io.read_full(tcp.reader(connection), data, 1, 3);
    chant(read_result.count); chant(read_result.error == mu);
    chant(data[1]); chant(data[2]); chant(data[3]);
    kaku eof = tcp.read(connection, data, 0, 1);
    chant(eof.eof); chant(eof.error == mu);
    kaku closed = tcp.close(connection); chant(closed.error == mu);
    kaku after_close = tcp.read(connection, data, 0, 1);
    chant(after_close.error != mu);
}
kaku opened = tcp.connect(tcp.ipv4(uint8(127), uint8(0), uint8(0), uint8(1), %d));
chant(opened.error == mu);
exercise(opened.connection);
`, address.Port)
	stdout, stderr, exit := runTCPSource(t, source)
	if exit != 0 || stdout != "hai\nhai\n3\nhai\n3\nhai\n9\n8\n7\nhai\nhai\nhai\nhai\n" {
		t.Fatalf("exit=%d stdout=%q stderr=%q", exit, stdout, stderr)
	}
	if err := <-serverError; err != nil {
		t.Fatal(err)
	}
}

func TestKisoTCPServerAccept(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("Windows socket primitive backend has not been implemented")
	}
	t.Setenv("MIO_BUNKO", mathBunkoRoot(t))
	reserved, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	port := reserved.Addr().(*net.TCPAddr).Port
	reserved.Close()

	source := fmt.Sprintf(`yobu "kiso/net/tcp";
yobu "kiso/io";
waza exercise_client(client: tcp.Connection?) -> unit {
    moshi (client == mu) { kaesu; }
    kaku data: []uint8 = [0, 0];
    kaku received = io.read_full(tcp.reader(client), data, 0, 2);
    chant(received.count); chant(received.error == mu);
    chant(data[0]); chant(data[1]);
    kaku sent = tcp.write_all(client, [3, 4], 0, 2);
    chant(sent.error == mu);
    kaku closed = tcp.close(client); chant(closed.error == mu);
}
waza exercise_listener(listener: tcp.Listener?) -> unit {
    moshi (listener == mu) { kaesu; }
    kaku accepted = tcp.accept(listener);
    chant(accepted.error == mu);
    exercise_client(accepted.connection);
    kaku stopped = tcp.close_listener(listener); chant(stopped.error == mu);
}
kaku server = tcp.listen(tcp.ipv4(uint8(127), uint8(0), uint8(0), uint8(1), %d));
chant(server.error == mu);
exercise_listener(server.listener);
`, port)
	output := make(chan struct {
		stdout string
		stderr string
		exit   int
	}, 1)
	go func() {
		stdout, stderr, exit := runTCPSource(t, source)
		output <- struct {
			stdout string
			stderr string
			exit   int
		}{stdout, stderr, exit}
	}()
	var conn net.Conn
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		conn, err = net.DialTimeout("tcp4", fmt.Sprintf("127.0.0.1:%d", port), 150*time.Millisecond)
		if err == nil {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	if conn == nil {
		t.Fatalf("could not reach Mio listener: %v", err)
	}
	defer conn.Close()
	_ = conn.SetDeadline(time.Now().Add(5 * time.Second))
	if _, err := conn.Write([]byte{1, 2}); err != nil {
		t.Fatal(err)
	}
	response := make([]byte, 2)
	if _, err := io.ReadFull(conn, response); err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(response, []byte{3, 4}) {
		t.Fatalf("unexpected Mio response %v", response)
	}
	result := <-output
	if result.exit != 0 || result.stdout != "hai\nhai\n2\nhai\n1\n2\nhai\nhai\nhai\n" {
		t.Fatalf("exit=%d stdout=%q stderr=%q", result.exit, result.stdout, result.stderr)
	}
}
