package aot

import (
	"bytes"
	"fmt"
	"path/filepath"
	"testing"
)

// Dynamic strings (heap-backed byte arrays) on Linux x86-64, checked against the Mochi VM with and
// without GC stress: UTF-8 validation, empty strings, mixed static/dynamic comparison, concatenation,
// printing and the string library built on to_bytes/from_utf8.
const dynStringSrc = `yobu "kiso/array"; yobu "kiso/string";
kata Label { text: string; }
waza show(value: string?) -> unit { moshi (value != mu) { chant(value); } sore { chant("nil"); } }
waza run() -> unit {
 kaku hello = string.concat("héllo, ", "世界");
 chant(hello); chant(string.byte_len(hello)); chant(string.rune_count(hello));
 chant(hello == "héllo, 世界"); chant(hello != "héllo, 世界"); chant(hello == "other");
 kaku empty = string.concat("", ""); chant(string.byte_len(empty)); chant(empty == ""); chant(empty);
 kaku bytes = string.to_bytes("abc"); bytes[1] = uint8(120); show(string.from_utf8(bytes));
 kaku bad = array.make[uint8](2, uint8(255)); show(string.from_utf8(bad));
 kaku overlong = array.with_capacity[uint8](3); array.push(overlong, uint8(192)); array.push(overlong, uint8(128)); show(string.from_utf8(overlong));
 kaku surrogate = array.with_capacity[uint8](3); array.push(surrogate, uint8(237)); array.push(surrogate, uint8(160)); array.push(surrogate, uint8(128)); show(string.from_utf8(surrogate));
 kaku truncated = array.with_capacity[uint8](2); array.push(truncated, uint8(226)); array.push(truncated, uint8(130)); show(string.from_utf8(truncated));
 kaku four = string.to_bytes("😀"); chant(len(four)); show(string.from_utf8(four));
 kaku label = Label { text: string.concat("kept-", "alive") };
 kaku i = 0; kaku total = 0;
 aida (i < 300) {
  kaku garbage = string.concat("g", string.concat("-", string.concat("x", "y")));
  total = total + string.byte_len(garbage);
  i = i + 1;
 }
 chant(total); chant(label.text); chant(label.text == "kept-alive"); chant(string.contains(label.text, "alive")); chant(string.index(hello, "世"));
}
run();`

func TestLinuxAMD64DynamicStringsDifferential(t *testing.T) {
	for _, stress := range []bool{false, true} {
		t.Run(fmt.Sprintf("stress=%v", stress), func(t *testing.T) {
			requireLinuxSourceDifferentialOpts(t, dynStringSrc, LinuxAMD64Options{HeapCapacity: 512 << 10, GCStress: stress})
		})
	}
}

// The differential above compares two byte streams; make sure they are not both empty or wrong in
// the same way: the oracle must show the converted strings and exactly four nil results
// (0xFF 0xFF, overlong C0 80, surrogate ED A0 80, truncated E2 82).
func TestLinuxAMD64DynamicStringsOracleIsMeaningful(t *testing.T) {
	root, _ := filepath.Abs(filepath.Join("..", ".."))
	out := linuxVMOracle(t, m17CompileMio(t, root, dynStringSrc))
	for _, want := range []string{"héllo, 世界\n", "axc\n", "😀\n", "kept-alive\n"} {
		if !bytes.Contains(out, []byte(want)) {
			t.Fatalf("oracle output lacks %q:\n%s", want, out)
		}
	}
	if n := bytes.Count(out, []byte("nil\n")); n != 4 {
		t.Fatalf("expected 4 nil results, got %d:\n%s", n, out)
	}
}
