package darwinarm64

import "testing"

func TestM14NativeSocketRuntimeIsOptIn(t *testing.T) {
	without, oldEntries, _, err := appendM14NativeFSRuntime(1, false)
	if err != nil {
		t.Fatal(err)
	}
	if _, exists := oldEntries["socket_open"]; exists {
		t.Fatal("filesystem-only program must not expose socket entry points")
	}
	with, newEntries, _, err := appendM14NativeFSRuntime(1, true)
	if err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"socket_open", "socket_status", "socket_bind_ipv4", "socket_connect_ipv4", "socket_listen", "socket_accept", "socket_read", "socket_write", "socket_close"} {
		if _, exists := newEntries[name]; !exists {
			t.Fatalf("missing native socket entry %s", name)
		}
	}
	if len(with) <= len(without) {
		t.Fatalf("socket runtime should add code only when imported: %d <= %d", len(with), len(without))
	}
}
