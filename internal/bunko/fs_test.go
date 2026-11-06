package bunko

import (
	"strings"
	"testing"
	"testing/fstest"
)

func TestClosedSourceFS(t *testing.T) {
	if _, err := LoadSourceFS(`chant("hello");`, nil); err == nil {
		t.Fatal("nil filesystem accepted")
	}
	library := fstest.MapFS{
		"demo/value.mio":       {Data: []byte(`koukai waza answer() -> int64 { kaesu 42; }`)},
		"demo/broken_test.mio": {Data: []byte(`not a program`)},
	}
	if _, err := LoadSourceFS(`yobu "demo"; chant(demo.answer());`, library); err != nil {
		t.Fatal(err)
	}
	// Existing on-disk packages cannot be imported through the closed FS.
	if _, err := LoadSourceFS(`yobu "kiso/math";`, library); err == nil || !strings.Contains(err.Error(), "unsupported") {
		t.Fatalf("disk fallback: %v", err)
	}
	for _, path := range []string{"../demo", "/demo", "demo/../demo", "bunko/demo"} {
		if _, err := (&Loader{sourceFS: library}).Load(path); err == nil {
			t.Fatalf("accepted %q", path)
		}
	}
}
