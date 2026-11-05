package aot

import (
	"Mio/internal/compiler"
	"Mio/internal/stdlib"
	"Mio/internal/value"
	"Mio/internal/vm"
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

// Source-level differential: the Mochi VM is the oracle, the Linux x86_64
// native binary must print byte-identical output (including exit behaviour
// for programs that finish normally).
func requireLinuxSourceDifferential(t *testing.T, source string) {
	t.Helper()
	requireLinuxSourceDifferentialOpts(t, source, LinuxAMD64Options{})
}

func requireLinuxSourceDifferentialOpts(t *testing.T, source string, opts LinuxAMD64Options) {
	t.Helper()
	if !isLinuxAMD64() {
		t.Skip("requires Linux x86_64")
	}
	root, err := filepath.Abs(filepath.Join("..", ".."))
	if err != nil {
		t.Fatal(err)
	}
	program := m17CompileMio(t, root, source)
	want := linuxVMOracle(t, program)
	got, err := runLinuxAMD64Options(t, program, opts)
	if err != nil {
		t.Fatalf("native failed: %v output=%q", err, got)
	}
	if !bytes.Equal(got, want) {
		t.Fatalf("native output differs\n--- native ---\n%s\n--- VM ---\n%s", got, want)
	}
}

func TestLinuxAMD64ExampleSourcesDifferential(t *testing.T) {
	root := filepath.Join("..", "..", "examples")
	for _, name := range []string{
		"aot_m6/floating.mio", "aot_m6b/floating_output.mio", "aot_m6b/mixed_pop.mio",
		"recursion.mio", "functions.mio", "local_scope.mio", "variables_and_conditionals.mio", "hello_world.mio",
	} {
		t.Run(name, func(t *testing.T) {
			src, err := os.ReadFile(filepath.Join(root, name))
			if err != nil {
				t.Fatal(err)
			}
			requireLinuxSourceDifferential(t, string(src))
		})
	}
}

func TestLinuxAMD64FloatSourceDifferential(t *testing.T) {
	requireLinuxSourceDifferential(t, `
kaku a: float64 = 0.1;
kaku b: float64 = 0.2;
chant(a + b);
chant(a * 3.0);
chant(1.0 / 3.0);
chant(123456789.0);
chant(1e21);
chant(1e-7);
chant(-2.5e-10);
chant(float32(0.1) + float32(0.2));
chant(float32(16777216.0) + float32(1.0));
chant(float64(float32(0.1)));
chant(int64(1e15));
chant(int64(-7.9));
chant(5e-324);
chant(1.7976931348623157e308);
chant(2.0 < 3.0);
chant(0.0 / 0.0);
chant(-1.0 / 0.0);
kaku total: float64 = 0.0;
kaku i: int64 = 0;
aida (i < 100) {
    total = total + float64(i) * 0.5;
    i = i + 1;
}
chant(total);
total;
`)
}

// linuxVMOracle runs the Mochi VM and appends the value of the last executed
// top-level pop, which is the documented contract that native images implement
// ("the final expression value is printed at program end").
func linuxVMOracle(t *testing.T, program *compiler.Bytecode) []byte {
	t.Helper()
	registry, err := stdlib.NewRegistry()
	if err != nil {
		t.Fatal(err)
	}
	var out bytes.Buffer
	machine := vm.NewWithRegistryAndOutput(program, registry, &out)
	if err := machine.RunWithOptions(vm.ExecutionOptions{InstructionLimit: 100_000_000}); err != nil {
		t.Fatal(err)
	}
	if v, ok := machine.LastPoppedValue(); ok {
		if err := value.WriteLine(&out, v); err != nil {
			t.Fatal(err)
		}
	}
	return out.Bytes()
}

func TestLinuxAMD64StaticStringSourceDifferential(t *testing.T) {
	requireLinuxSourceDifferential(t, `
kaku a: string = "hello";
kaku b: string = "hello";
kaku c: string = "猫🙂 world";
kaku e: string = "";
chant(a);
chant(c);
chant(e);
chant(a == b);
chant(a != b);
chant(a == c);
chant(e == "");
waza pick(flag: bool) -> string {
    moshi (flag) { kaesu "yes"; }
    kaesu "no";
}
chant(pick(hai));
chant(pick(iie) == "no");
c;
`)
}

// GC tests: the heap is far smaller than the total bytes allocated, so a
// program can only succeed if unreachable objects are really reclaimed and
// reachable ones (arrays, struct fields, nested arrays) survive every cycle.
func TestLinuxAMD64GCReclaimsAndKeepsReachable(t *testing.T) {
	src := `yobu "kiso/array";
kata Box { value: int64; }
waza churn() -> unit {
 kaku a = array.make[uint8](40000,uint8(219));
 kaku b = array.make[uint8](20000,uint8(17));
 moshi (a[39999] != uint8(219) || b[19999] != uint8(17)) { chant(-1); }
}
kaku refs = array.with_capacity[Box](3000);
kaku i=0; aida (i<3000) { array.push(refs,Box { value:i }); i=i+1; }
kaku j=0; aida (j<100) { churn(); j=j+1; }
i=0; kaku sum=0; aida (i<3000) { sum=sum+refs[i].value; i=i+1; }
chant(sum); chant(len(refs));`
	for _, stress := range []bool{false, true} {
		t.Run(fmt.Sprintf("stress=%v", stress), func(t *testing.T) {
			requireLinuxSourceDifferentialOpts(t, src, LinuxAMD64Options{HeapCapacity: 320 << 10, GCStress: stress})
		})
	}
}

// Sizes are tuned to the Linux object layout (the ARM64 boundary values depend on
// its 16-byte headers): the dead interior (500 x 176 B) is ~88 KB, the bump tail is
// ~43 KB, so the 80 KB array fits only after adjacent dead blocks are coalesced.
func TestLinuxAMD64GCCoalescesAndSplits(t *testing.T) {
	requireLinuxSourceDifferentialOpts(t, `yobu "kiso/array";
kata Marker { value: int64; }
waza make_hole() -> Marker {
 kaku i=0; aida (i<500) { kaku garbage=array.make[uint8](96,uint8(211)); i=i+1; }
 kaesu Marker { value:771 };
}
kaku marker=make_hole();
kaku large=array.make[uint8](80000,uint8(143));
kaku second=array.make[uint8](10000,uint8(29));
chant(marker.value); chant(len(large)); chant(large[79999]); chant(second[9999]);`, LinuxAMD64Options{HeapCapacity: 128 << 10})
}

func TestLinuxAMD64GCNestedArraysAndStructsSurvive(t *testing.T) {
	// Deterministic LCG (fixed seed): every round replaces a random row of a
	// matrix with a fresh array, while garbage rows are produced and dropped.
	src := `yobu "kiso/array";
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
  kaku fresh = array.make[int64](16, round);
  rows[row] = fresh;
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
chant(total);
chant(len(rows)); chant(len(holders));`
	for _, stress := range []bool{false, true} {
		t.Run(fmt.Sprintf("stress=%v", stress), func(t *testing.T) {
			requireLinuxSourceDifferentialOpts(t, src, LinuxAMD64Options{HeapCapacity: 192 << 10, GCStress: stress})
		})
	}
}

func TestLinuxAMD64OutOfMemoryAndBoundsExitOne(t *testing.T) {
	if !isLinuxAMD64() {
		t.Skip("requires Linux x86_64")
	}
	root, _ := filepath.Abs(filepath.Join("..", ".."))
	cases := []struct{ name, src, want string }{
		{"live-data-exceeds-heap", `yobu "kiso/array";
kaku keep: [][]int64 = array.with_capacity[[]int64](4);
kaku i = 0;
aida (i < 100) { array.push(keep, array.make[int64](4096, i)); i = i + 1; }
chant(len(keep));`, "allocation failed"},
		{"index-out-of-bounds", `yobu "kiso/array";
kaku a = array.make[int64](3, 1);
chant(a[3]);`, "out of bounds"},
		{"negative-index", `yobu "kiso/array";
kaku a = array.make[int64](3, 1);
kaku i = 0 - 1;
chant(a[i]);`, "out of bounds"},
		{"negative-length", `yobu "kiso/array";
kaku n = 0 - 5;
kaku a = array.make[int64](n, 1);
chant(len(a));`, "invalid array length"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			program := m17CompileMio(t, root, c.src)
			out, err := runLinuxAMD64Options(t, program, LinuxAMD64Options{HeapCapacity: 256 << 10})
			exit, ok := err.(*exec.ExitError)
			if !ok || exit.ExitCode() != 1 || !strings.Contains(string(out), c.want) {
				t.Fatalf("want exit 1 containing %q, got err=%v output=%q", c.want, err, out)
			}
		})
	}
}

// References that live only on the operand stack (call arguments evaluated
// before the next allocation) and in the locals of many recursive frames must be
// found by the stack maps; GC stress collects before every allocation.
func TestLinuxAMD64GCPreciseStackRoots(t *testing.T) {
	src := `yobu "kiso/array";
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
	for _, stress := range []bool{false, true} {
		t.Run(fmt.Sprintf("stress=%v", stress), func(t *testing.T) {
			requireLinuxSourceDifferentialOpts(t, src, LinuxAMD64Options{HeapCapacity: 128 << 10, GCStress: stress})
		})
	}
}

// Nullable scalars (boxes), nullable references, enums with reference payloads,
// all kept alive across collections: GC stress collects before every allocation.
func TestLinuxAMD64NullableAndEnumGCDifferential(t *testing.T) {
	src := `yobu "kiso/array";
sentaku Shape { Empty; Num(int64); Name(string); Pair([]int64, int64?); }
waza classify(s: Shape) -> int64 {
  kaku result = 0;
  awase (s) {
    baai Empty { result = 0; }
    baai Num(n) { result = n; }
    baai Name(name) { result = 1000; }
    baai Pair(items, extra) {
      kaku total = len(items);
      moshi (extra != mu) { total = total + extra; }
      result = total;
    }
  }
  kaesu result;
}
waza maybe(n: int64) -> int64? {
  moshi (n - (n / 3) * 3 == 0) { kaesu mu; }
  kaesu n * 2;
}
kaku shapes: []Shape = array.with_capacity[Shape](8);
array.push(shapes, Shape.Empty());
array.push(shapes, Shape.Num(41));
array.push(shapes, Shape.Name("mio"));
kaku i = 0;
aida (i < 60) {
  kaku boxed = maybe(i);
  array.push(shapes, Shape.Pair(array.make[int64](i + 1, i), boxed));
  i = i + 1;
}
kaku sum = 0;
i = 0;
aida (i < len(shapes)) { sum = sum + classify(shapes[i]); i = i + 1; }
chant(sum);
kaku values: []int64? = array.with_capacity[int64?](4);
i = 0;
aida (i < 30) { array.push(values, maybe(i)); i = i + 1; }
kaku nils = 0; kaku live = 0;
i = 0;
aida (i < len(values)) {
  kaku v = values[i];
  moshi (v == mu) { nils = nils + 1; } sore { live = live + v; }
  i = i + 1;
}
chant(nils); chant(live);`
	for _, stress := range []bool{false, true} {
		t.Run(fmt.Sprintf("stress=%v", stress), func(t *testing.T) {
			requireLinuxSourceDifferentialOpts(t, src, LinuxAMD64Options{HeapCapacity: 128 << 10, GCStress: stress})
		})
	}
}
