package aot

import (
	"fmt"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

// Programs that keep references only in frames / operand stacks / globals while
// allocating heavily. GC stress collects before every allocation.
const shadowPreciseSrc = `yobu "kiso/array";
waza sum2(a: []int64, b: []int64) -> int64 { kaesu a[0] + b[99] + len(a) + len(b); }
waza deep(n: int64) -> int64 {
  kaku mine = array.make[int64](20, n);
  moshi (n == 0) { kaesu mine[0]; }
  kaku below = deep(n - 1);
  kaesu below + mine[19] + len(mine);
}
kaku i = 0;
kaku total = 0;
aida (i < 400) {
  total = total + sum2(array.make[int64](100, i), array.make[int64](100, i + 1));
  i = i + 1;
}
chant(total);
chant(deep(300));`

const shadowNestedSrc = `yobu "kiso/array";
kata Holder { items: []int64; tag: int64; }
kaku rows: [][]int64 = array.with_capacity[[]int64](64);
kaku r = 0;
aida (r < 64) { array.push(rows, array.make[int64](16, r)); r = r + 1; }
kaku holders: []Holder = array.with_capacity[Holder](8);
kaku h = 0;
aida (h < 8) { array.push(holders, Holder { items: array.make[int64](32, h * 100), tag: h }); h = h + 1; }
kaku seed = 12345;
kaku round = 0;
aida (round < 3000) {
  kaku next = seed * 1103515245 + 12345;
  seed = next - (next / 2147483648) * 2147483648;
  kaku row = seed - (seed / 64) * 64;
  rows[row] = array.make[int64](16, round);
  kaku junk = array.make[int64](50, seed);
  kaku slot = seed - (seed / 8) * 8;
  holders[slot] = Holder { items: array.make[int64](32, round), tag: slot };
  round = round + 1;
}
kaku total = 0;
r = 0;
aida (r < 64) { total = total + rows[r][0] + rows[r][15]; r = r + 1; }
h = 0;
aida (h < 8) { total = total + holders[h].items[0] + holders[h].items[31] + holders[h].tag; h = h + 1; }
chant(total); chant(len(rows)); chant(len(holders));`

// A reference-typed global that is only read by main after a call that collects.
// (Functions cannot access globals in the shared analysis, so main liveness is complete.)
const shadowGlobalSrc = `yobu "kiso/array";
kaku held = array.make[int64](8, 41);
waza churn() -> unit {
  kaku i = 0;
  aida (i < 200) { kaku junk = array.make[int64](64, i); i = i + 1; }
}
churn();
chant(held[0] + len(held));`

var shadowSources = []struct{ name, src string }{
	{"precise-stack-roots", shadowPreciseSrc},
	{"nested-arrays-structs", shadowNestedSrc},
	{"global-held-across-collections", shadowGlobalSrc},
}

// Shadow-frame mode (formal contract) and the legacy stack-map mode must both
// reproduce the VM exactly under GC stress.
func TestLinuxAMD64ShadowFrameAndLegacyStackMapAgree(t *testing.T) {
	for _, c := range shadowSources {
		for _, legacy := range []bool{false, true} {
			t.Run(fmt.Sprintf("%s/legacy=%v", c.name, legacy), func(t *testing.T) {
				requireLinuxSourceDifferentialOpts(t, c.src, LinuxAMD64Options{HeapCapacity: 128 << 10, GCStress: true, LegacyStackMaps: legacy})
			})
		}
	}
}

// Mutation: dropping the published roots must be detected (wrong output or crash)
// under stress. This proves the shadow records are the roots actually used.
func TestLinuxAMD64ShadowFrameRootDropIsDetected(t *testing.T) {
	if !isLinuxAMD64() {
		t.Skip("requires Linux x86_64")
	}
	root, _ := filepath.Abs(filepath.Join("..", ".."))
	for _, c := range shadowSources[:2] {
		t.Run(c.name, func(t *testing.T) {
			program := m17CompileMio(t, root, c.src)
			want := linuxVMOracle(t, program)
			out, err := runLinuxAMD64Options(t, program, LinuxAMD64Options{HeapCapacity: 128 << 10, GCStress: true, RootMutation: "drop-roots"})
			if err == nil && string(out) == string(want) {
				t.Fatalf("dropping every shadow root was not detected (output %q)", out)
			}
		})
	}
}

// Negative: a record naming a non-object value must be rejected by the exact-root
// check (exit 1 + diagnostic), never marked.
func TestLinuxAMD64ShadowFrameInvalidRootIsRejected(t *testing.T) {
	if !isLinuxAMD64() {
		t.Skip("requires Linux x86_64")
	}
	root, _ := filepath.Abs(filepath.Join("..", ".."))
	program := m17CompileMio(t, root, shadowPreciseSrc)
	out, err := runLinuxAMD64Options(t, program, LinuxAMD64Options{HeapCapacity: 128 << 10, GCStress: true, RootMutation: "poison-root"})
	exit, ok := err.(*exec.ExitError)
	if !ok || exit.ExitCode() != 1 || !strings.Contains(string(out), "invalid GC root") {
		t.Fatalf("want exit 1 with exact-root diagnostic, got err=%v output=%q", err, out)
	}
}

// Deep recursion keeps one shadow record per frame; the chain is walked at every
// allocation under stress. The call-depth guard (1024) stays the hard limit.
func TestLinuxAMD64ShadowFrameDeepRecursionAndLimit(t *testing.T) {
	deep := func(n int) string {
		return fmt.Sprintf(`yobu "kiso/array";
waza deep(n: int64) -> int64 {
  kaku mine = array.make[int64](4, n);
  moshi (n == 0) { kaesu mine[0]; }
  kaesu deep(n - 1) + mine[3] + len(mine);
}
chant(deep(%d));`, n)
	}
	requireLinuxSourceDifferentialOpts(t, deep(900), LinuxAMD64Options{HeapCapacity: 8 << 20, GCStress: true})
	if !isLinuxAMD64() {
		return
	}
	root, _ := filepath.Abs(filepath.Join("..", ".."))
	program := m17CompileMio(t, root, deep(5000))
	out, err := runLinuxAMD64Options(t, program, LinuxAMD64Options{HeapCapacity: 8 << 20, GCStress: true})
	exit, ok := err.(*exec.ExitError)
	if !ok || exit.ExitCode() != 1 {
		t.Fatalf("recursion beyond the depth guard must exit 1, got err=%v output=%q", err, out)
	}
}
