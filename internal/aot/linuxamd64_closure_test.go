package aot

import (
	"Mio/internal/compiler"
	"fmt"
	"path/filepath"
	"testing"
)

// Closures on Linux x86-64 (cells, environments, indirect calls) checked against the Mochi VM,
// with and without GC stress, under the generational collector.

// A reference cell that becomes Old must be remembered when a closure (OpSetUpvalue) or the enclosing
// function (OpSetLocal through the cell) stores a Young array into it.
const closureOldCellSrc = `yobu "kiso/array";
waza run() -> unit {
  kaku cur = array.make[int64](8, 1);
  kaku set = waza(v: int64) -> int64 { cur = array.make[int64](8, v); kaesu v; };
  kaku get = waza(unused: int64) -> int64 { kaesu cur[0] + cur[7]; };
  kaku round = 0; kaku sum = 0;
  aida (round < 900) {
    kaku done = set(round);
    kaku garbage = array.make[int64](24, round);
    sum = sum + get(0);
    cur = array.make[int64](8, round * 2);
    kaku garbage2 = array.make[int64](24, round);
    sum = sum + get(0);
    round = round + 1;
  }
  chant(sum);
}
run();`

// Closures outlive the frame that created them; each keeps its own cells and a reference capture.
const closureCountersSrc = `yobu "kiso/array";
waza make_counter(start: int64) -> (int64) -> int64 {
  kaku n = start; kaku label = array.make[int64](4, start);
  kaesu waza(step: int64) -> int64 { n = n + step; kaesu n + label[3]; };
}
waza run() -> unit {
  kaku a = make_counter(10); kaku b = make_counter(100);
  kaku i = 0; kaku sum = 0;
  aida (i < 500) { kaku garbage = array.make[int64](16, i); sum = sum + a(1) + b(2); i = i + 1; }
  chant(sum); chant(a(0)); chant(b(0));
}
run();`

func TestLinuxAMD64ClosuresDifferential(t *testing.T) {
	for name, src := range map[string]string{"old-cell": closureOldCellSrc, "counters": closureCountersSrc} {
		for _, stress := range []bool{false, true} {
			t.Run(fmt.Sprintf("%s/stress=%v", name, stress), func(t *testing.T) {
				requireLinuxSourceDifferentialOpts(t, src, LinuxAMD64Options{HeapCapacity: 256 << 10, GCStress: stress})
			})
		}
	}
}

// Dropping the published roots (including the hidden environment and cell slots) must also be caught.
func TestLinuxAMD64ClosureRootRemovalIsDetected(t *testing.T) {
	if !isLinuxAMD64() {
		t.Skip("requires Linux x86_64")
	}
	root, _ := filepath.Abs(filepath.Join("..", ".."))
	program := m17CompileMio(t, root, closureCountersSrc)
	want := linuxVMOracle(t, program)
	requireUnmutatedMatches(t, program, want)
	out, err := runLinuxAMD64Options(t, program, LinuxAMD64Options{HeapCapacity: 256 << 10, GCStress: true, RootMutation: "drop-roots"})
	if err == nil && string(out) == string(want) {
		t.Fatalf("dropping closure roots was not detected (output %q)", out)
	}
}

// A mutation test is only meaningful if the same program passes without the mutation.
func requireUnmutatedMatches(t *testing.T, program *compiler.Bytecode, want []byte) {
	t.Helper()
	out, err := runLinuxAMD64Options(t, program, LinuxAMD64Options{HeapCapacity: 256 << 10, GCStress: true})
	if err != nil || string(out) != string(want) {
		t.Fatalf("unmutated program does not match the VM: err=%v native=%q vm=%q", err, out, want)
	}
}
