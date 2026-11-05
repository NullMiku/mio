package aot

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"testing"
	"time"

	"Mio/internal/mochi"
	"Mio/internal/stdlib"
	"Mio/internal/vm"
)

// Pure-Mio Mochi -> Linux x86-64 lowering (kiso/aot/lowerlinux): the lowering itself runs in the
// Mochi VM only because that is the available host for Mio code; the machine code is produced
// entirely by Mio (lowerlinux -> x86_64 -> elf). Each program is run by the VM (expected) and as the
// produced native ELF (actual), and stdout and the exit status must agree.
const pureLowerDriver = `yobu "kiso/aot/lowerlinux";
yobu "kiso/encoding/mochi";
yobu "kiso/fs";
waza build(file: mochi.File) -> unit {
    kaku lowered = lowerlinux.compile_with_gc_threshold(file, THRESHOLD);
    moshi (lowered.error != "") { chant(lowered.error); kaesu; }
    kaku written = fs.write_all(OUTPUT, lowered.bytes);
    moshi (written.error != mu) { chant("write failed"); kaesu; }
    chant("ok");
}
kaku decoded = mochi.decode_file(INPUT);
kaku file = decoded.value;
moshi (decoded.error != mu) { chant("decode failed"); }
sore {
    moshi (file == mu) { chant("decode failed"); } sore { build(file); }
}
`

// pureLowerGCThreshold is the collection threshold of programs lowered by the test driver (bytes).
var pureLowerGCThreshold = 33554432

type pureLowerResult struct {
	stdout string
	stderr string
	exit   int
}

func pureLowerBuild(t *testing.T, root, source string) (elf string, report string) {
	t.Helper()
	dir := t.TempDir()
	program := m17CompileMio(t, root, source)
	var encoded bytes.Buffer
	if err := mochi.Encode(&encoded, program); err != nil {
		t.Fatalf("encode: %v", err)
	}
	input := filepath.Join(dir, "in.mochi")
	if err := os.WriteFile(input, encoded.Bytes(), 0o644); err != nil {
		t.Fatal(err)
	}
	elf = filepath.Join(dir, "out.elf")
	driver := bytes.NewBufferString(pureLowerDriver).String()
	driver = replaceOnce(driver, "INPUT", fmt.Sprintf("%q", input))
	driver = replaceOnce(driver, "OUTPUT", fmt.Sprintf("%q", elf))
	driver = replaceOnce(driver, "THRESHOLD", strconv.Itoa(pureLowerGCThreshold))
	registry, err := stdlib.NewRegistry()
	if err != nil {
		t.Fatal(err)
	}
	var log bytes.Buffer
	machine := vm.NewWithRegistryAndOutput(m17CompileMio(t, root, driver), registry, &log)
	if err := machine.RunWithOptions(vm.ExecutionOptions{InstructionLimit: 4_000_000_000}); err != nil {
		t.Fatalf("lowering driver failed: %v (%q)", err, log.String())
	}
	return elf, log.String()
}

func replaceOnce(s, old, new string) string {
	i := bytes.Index([]byte(s), []byte(old))
	if i < 0 {
		panic("missing " + old)
	}
	return s[:i] + new + s[i+len(old):]
}

func pureLowerRunVM(t *testing.T, root, source string) pureLowerResult {
	t.Helper()
	registry, err := stdlib.NewRegistry()
	if err != nil {
		t.Fatal(err)
	}
	var out bytes.Buffer
	machine := vm.NewWithRegistryAndOutput(m17CompileMio(t, root, source), registry, &out)
	if err := machine.RunWithOptions(vm.ExecutionOptions{InstructionLimit: 2_000_000_000}); err != nil {
		return pureLowerResult{stdout: out.String(), exit: 1}
	}
	return pureLowerResult{stdout: out.String()}
}

func pureLowerRunNative(t *testing.T, path string) pureLowerResult {
	t.Helper()
	if err := os.Chmod(path, 0o755); err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, path)
	var out, errOut bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &errOut
	err := cmd.Run()
	result := pureLowerResult{stdout: out.String(), stderr: errOut.String()}
	if err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			result.exit = exitErr.ExitCode()
		} else {
			t.Fatalf("native run: %v", err)
		}
	}
	return result
}

var pureLowerPrograms = map[string]string{
	"hello_constant": `chant(42);`,
	"arithmetic":     `chant(7 + 5 * 3 - 4); chant(100 / 7); chant(-100 / 7); chant(100 / -7); chant(0 - 9223372036854775807 - 1);`,
	"comparisons":    `chant(3 < 4); chant(4 < 3); chant(3 == 3); chant(3 != 3); chant(5 >= 5); chant(5 > 6); chant(!(1 < 2));`,
	"loop_globals": `kaku sum = 0; kaku i = 1;
aida (i <= 100) { sum = sum + i; i = i + 1; }
chant(sum);`,
	"branches": `kaku n = 10;
moshi (n > 5) { chant(1); } sore { chant(2); }
moshi (n > 50) { chant(3); } sore { chant(4); }`,
	"functions": `waza add(a: int64, b: int64) -> int64 { kaesu a + b; }
waza sub3(a: int64, b: int64, c: int64) -> int64 { kaesu a - b - c; }
chant(add(2, 3)); chant(sub3(100, 30, 5));`,
	"recursion": `waza fib(n: int64) -> int64 { moshi (n < 2) { kaesu n; } kaesu fib(n - 1) + fib(n - 2); }
waza fact(n: int64) -> int64 { moshi (n <= 1) { kaesu 1; } kaesu n * fact(n - 1); }
chant(fib(20)); chant(fact(15));`,
	"locals_and_loops": `waza collatz(start: int64) -> int64 {
    kaku value = start; kaku steps = 0;
    aida (value != 1) {
        moshi (value - (value / 2) * 2 == 0) { value = value / 2; } sore { value = value * 3 + 1; }
        steps = steps + 1;
    }
    kaesu steps;
}
chant(collatz(27)); chant(collatz(97));`,
	"negative_and_zero": `chant(0); chant(-1); chant(-9223372036854775807 - 1); chant(1000000007 * 1000000007);`,
	"strings": `yobu "kiso/string";
chant("hello"); chant(""); chant("a" == "a"); chant("a" == "b"); chant("abc" != "abd");
kaku s = "über"; chant(string.byte_len(s)); chant(s); chant(string.byte_len(""));`,
	"string_globals_functions": `kaku greeting = "hi";
waza pick(flag: bool) -> string { moshi (flag) { kaesu greeting; } kaesu "other"; }
chant(pick(hai)); chant(pick(iie)); chant(pick(hai) == greeting);`,
	"arrays": `yobu "kiso/array";
kaku a = [1, 2, 3]; chant(a[1]); a[1] = 20; chant(a[1]); chant(len(a));
kaku b: []int64 = []; kaku i = 0; aida (i < 10) { array.push(b, i * i); i = i + 1; }
chant(len(b)); chant(b[9]); array.truncate(b, 3); chant(len(b));
kaku c = array.clone(b); array.push(c, 99); chant(len(c)); chant(len(b)); chant(c[3]);
array.append_all(c, b); chant(len(c)); chant(c[6]);
kaku z = array.make[int64](5, 7); chant(z[4]);
kaku words = ["x", "yy"]; chant(words[1]); array.push(words, "zzz"); chant(words[2]);`,
	"bytes_and_strings": `yobu "kiso/string";
kaku data = string.to_bytes("héllo"); chant(len(data)); chant(data[1]);
kaku back = string.from_utf8(data); moshi (back != mu) { chant(back); }
kaku bad: []uint8 = [uint8(255), uint8(65)]; kaku r = string.from_utf8(bad); moshi (r == mu) { chant("invalid"); }
kaku cp = string.to_bytes("😀"); chant(len(cp));`,
	"structs_and_enums": `kata Point { x: int64; y: int64; name: string; }
sentaku Shape { Circle(int64); Rect(int64, int64); Empty; }
waza area(s: Shape) -> int64 {
    awase (s) {
        baai Circle(r) { kaesu r * r * 3; }
        baai Rect(w, h) { kaesu w * h; }
        baai Empty { kaesu 0; }
    }
    kaesu -1;
}
kaku p = Point { x: 3, y: 4, name: "pt" };
chant(p.x + p.y); chant(p.name);
kaku pts = [Point { x: 1, y: 2, name: "a" }, Point { x: 5, y: 6, name: "b" }];
chant(pts[1].y); chant(pts[0].name == "a");
chant(area(Shape.Circle(5))); chant(area(Shape.Rect(3, 4))); chant(area(Shape.Empty()));`,
	"fixed_width": `kaku a = uint8(250); kaku b = a + uint8(10); chant(b);
kaku c = int8(100); kaku d = c + int8(100); chant(d);
kaku e = uint32(4000000000); chant(e + uint32(500000000));
chant(int64(a) * 3); kaku n = int32(0) - int32(5); chant(n); chant(-n);`,
	"nil_and_nullable": `kata Node { value: int64; next: Node?; }
kaku tail = Node { value: 2, next: mu };
kaku head = Node { value: 1, next: tail };
waza total(n: Node?) -> int64 {
    moshi (n == mu) { kaesu 0; }
    kaesu n.value + total(n.next);
}
chant(total(head)); chant(total(mu));
kaku name: string? = "n"; moshi (name != mu) { chant(name); }
waza pick(flag: bool) -> string? { moshi (flag) { kaesu "yes"; } kaesu mu; }
kaku yes = pick(hai); moshi (yes != mu) { chant(yes == "yes"); } chant(pick(iie) == mu); chant(pick(hai) != mu);`,
	"closures": `waza counter() -> () -> int64 {
    kaku n = 0;
    kaesu waza () -> int64 { n = n + 1; kaesu n; };
}
waza apply(f: (int64) -> int64, x: int64) -> int64 { kaesu f(x); }
waza adder(k: int64) -> (int64) -> int64 { kaesu waza (x: int64) -> int64 { kaesu x + k; }; }
kaku c = counter(); chant(c()); chant(c()); chant(c());
kaku d = counter(); chant(d());
chant(apply(adder(10), 5));
kaku add3 = adder(3); chant(add3(4));
waza dbl(x: int64) -> int64 { kaesu x * 2; }
chant(apply(dbl, 21));
kaku fs = [adder(1), adder(2), adder(3)]; chant(fs[2](10));`,
	"floats": `yobu "kiso/math";
kaku a = 1.5; kaku b = 2.25; kaku c = a + b * 2.0 - 0.5 / 4.0;
chant(c > 5.0); chant(c < 5.0); chant(c == 5.875); chant(c != 5.875); chant(a <= b); chant(a >= b);
chant(int64(c * 100.0)); chant(int64(-c)); chant(int64(math.floor(-2.5))); chant(int64(math.ceil(2.1)));
chant(int64(math.trunc(-2.9))); chant(int64(math.sqrt(144.0))); chant(int64(math.round(2.5)));
kaku n = 7; chant(int64(float64(n) / 2.0 * 10.0));
chant(math.is_nan(0.0 / 0.0)); chant(math.is_inf(1.0 / 0.0)); chant(math.is_finite(a)); chant(math.is_finite(1.0 / 0.0));
kaku f: float32 = float32(1.5); kaku g = f + float32(2.25); chant(int64(float64(g) * 100.0)); chant(g > f);
chant(float64(f) == 1.5);`,
	"convert_numbers": `yobu "kiso/convert";
kaku values = ["0", "1", "42", "-17", "9223372036854775807", "007"];
kaku i = 0;
aida (i < len(values)) { kaku v = convert.parse_int(values[i]); moshi (v != mu) { chant(v); } sore { chant("bad"); } i = i + 1; }
chant(convert.format_int(-123456789)); chant(convert.format_int(0));
kaku fl = ["1.5", "0.1", "3.14159", "2", "-0.5", "1e3", "2.5e-3", "123456.789", "1.0", "0.0", "abc", ""];
kaku j = 0;
aida (j < len(fl)) {
    kaku x = convert.parse_float64(fl[j]);
    moshi (x != mu) { chant(convert.format_float64(x)); } sore { chant("bad"); }
    j = j + 1;
}
kaku y = convert.parse_float32("1.5"); moshi (y != mu) { chant(convert.format_float32(y)); }`,
	"nullable_scalars": `waza zero_int() -> int64? { kaesu 0; }
waza maybe(flag: bool) -> int64? { moshi (flag) { kaesu 0; } kaesu mu; }
waza maybe_float(flag: bool) -> float64? { moshi (flag) { kaesu 0.0; } kaesu mu; }
kaku b = zero_int(); chant(b != mu);
kaku c = maybe(hai); chant(c != mu); kaku d = maybe(iie); chant(d != mu);
moshi (c != mu) { chant(c == 0); chant(c + 5); }
kaku f = maybe_float(hai); kaku g = maybe_float(iie); chant(f != mu); chant(g == mu);
moshi (f != mu) { chant(f == 0.0); }
kaku nums: []int64? = [1, mu, 3]; chant(len(nums)); chant(nums[1] == mu); kaku third = nums[2]; moshi (third != mu) { chant(third + 1); }`,
	"gc_garbage": `yobu "kiso/array";
kata Cell { value: int64; label: string; next: Cell?; }
waza push_cell(value: int64, tail: Cell?) -> Cell { kaesu Cell { value: value, label: "c", next: tail }; }
waza make_chain(n: int64) -> Cell? {
    moshi (n == 0) { kaesu mu; }
    kaku head = push_cell(0, mu); kaku i = 1;
    aida (i < n) { head = push_cell(i, head); i = i + 1; }
    kaesu head;
}
waza chain_sum(c: Cell?) -> int64 {
    moshi (c == mu) { kaesu 0; }
    kaesu c.value + chain_sum(c.next);
}
// about 3.2 GB of short-lived arrays: impossible without reclamation in a 1 GiB heap
kaku keep = make_chain(400);
kaku sink = 0; kaku i = 0;
aida (i < 400000) {
    kaku scratch = array.make[int64](1000, i);
    sink = sink + scratch[999];
    moshi (i - (i / 50000) * 50000 == 0) { kaku extra = make_chain(300); sink = sink + chain_sum(extra); }
    i = i + 1;
}
chant(sink); chant(chain_sum(keep));`,
	"gc_keeps_live_data": `yobu "kiso/array";
yobu "kiso/string";
kata Row { id: int64; name: string; tags: []string; parent_index: int64; }
waza build(n: int64) -> []Row {
    kaku rows: []Row = []; kaku i = 0;
    aida (i < n) {
        kaku parent = 0; moshi (i > 0) { parent = i / 2; }
        array.push(rows, Row { id: i, name: string.concat("row-", string.concat("x", "y")), tags: ["a", "b"], parent_index: parent });
        i = i + 1;
    }
    kaesu rows;
}
waza depth(rows: []Row, at: int64) -> int64 {
    kaku d = 0; kaku cur = at;
    aida (cur > 0) { cur = rows[cur].parent_index; d = d + 1; }
    kaesu d;
}
waza counter(start: int64) -> () -> int64 { kaku n = start; kaesu waza () -> int64 { n = n + 1; kaesu n; }; }
kaku rows = build(30000); kaku tick = counter(100);
kaku churn = 0; kaku i = 0;
aida (i < 300000) {
    kaku junk = array.make[int64](2000, 1); churn = churn + junk[1999]; tick();
    i = i + 1;
}
kaku total = 0; kaku j = 0;
aida (j < len(rows)) { total = total + depth(rows, j) + len(rows[j].tags); j = j + 1; }
chant(churn); chant(total); chant(tick()); chant(rows[29999].name);`,
	"maps": `kaku ages = Map[string, int64]();
ages["ann"] = 31; ages["bob"] = 42; ages["ann"] = 32;
kaku a = ages["ann"]; moshi (a != mu) { chant(a); }
kaku b = ages["bob"]; moshi (b != mu) { chant(b); }
chant(ages["nobody"] == mu);
kaku names = Map[int64, string]();
kaku i = 0;
aida (i < 50) { names[i * 7] = "n"; i = i + 1; }
names[14] = "fourteen";
kaku n = names[14]; moshi (n != mu) { chant(n); }
chant(names[15] == mu);
kaku flags = Map[bool, int64](); flags[hai] = 1; flags[iie] = 0;
kaku t = flags[hai]; moshi (t != mu) { chant(t); }
kaku z = flags[iie]; moshi (z != mu) { chant(z); }
kaku key = "dy"; ages[string_join(key)] = 7;
waza string_join(s: string) -> string { kaesu s; }`,
	"gc_maps": `yobu "kiso/array";
kata Box { id: int64; name: string; }
kaku keep = Map[int64, Box]();
kaku i = 0;
aida (i < 300) { keep[i] = Box { id: i, name: "box" }; i = i + 1; }
kaku strings = Map[string, string](); strings["k"] = "kept";
kaku round = 0; kaku checksum = 0;
aida (round < 3000) {
    kaku temp = Map[int64, Box]();
    kaku j = 0;
    aida (j < 40) { temp[j] = Box { id: j + round, name: "temp" }; j = j + 1; }
    kaku junk = array.make[int64](500, round);
    kaku probe = temp[39]; moshi (probe != mu) { checksum = checksum + probe.id; }
    checksum = checksum + junk[499] - round;
    round = round + 1;
}
kaku sum = 0; kaku k = 0;
aida (k < 300) { kaku b = keep[k]; moshi (b != mu) { sum = sum + b.id; } k = k + 1; }
chant(checksum); chant(sum);
kaku kept = strings["k"]; moshi (kept != mu) { chant(kept); }`,
	// Type analysis regression: a self-referential nullable struct joined through recursive calls in nested branches
	// lost its nullability (a nested field join re-parented the class root), so the nil test folded to "not nil".
	"recursive_nullable_tree": `kata Tree { v: int64; left: Tree?; right: Tree?; }
waza ins(t: Tree?, v: int64) -> Tree {
    moshi (t == mu) { kaesu Tree { v: v, left: mu, right: mu }; }
    moshi (v < t.v) { kaesu Tree { v: t.v, left: ins(t.left, v), right: t.right }; }
    kaesu Tree { v: t.v, left: t.left, right: ins(t.right, v) };
}
waza total(t: Tree?) -> int64 { moshi (t == mu) { kaesu 0; } kaesu t.v + total(t.left) + total(t.right); }
kaku tree: Tree? = mu; kaku i = 0;
aida (i < 200) { tree = ins(tree, (i * 37) - ((i * 37) / 101) * 101); i = i + 1; }
chant(total(tree));`,
	// Type analysis regression: a global first seen as nil whose struct stores are analysed in a later block was
	// rejected at the first field read.
	"nil_global_struct_result": `kata Mixed { v: int64; next: Mixed?; }
waza mixed(i: int64, next: Mixed?) -> Mixed { kaesu Mixed { v: i, next: next }; }
kaku chain: Mixed? = mu;
chain = mixed(0, chain); chain = mixed(1, chain);
kaku t = mixed(7, mu); chant(t.v);`,
	"divide_by_zero": `kaku zero = 0; chant(1); chant(10 / zero); chant(2);`,
}

func TestLinuxAMD64PureMioLoweringMatchesVM(t *testing.T) {
	if runtime.GOOS != "linux" || runtime.GOARCH != "amd64" {
		t.Skip("requires Linux x86_64")
	}
	root, err := filepath.Abs(filepath.Join("..", ".."))
	if err != nil {
		t.Fatal(err)
	}
	for name, source := range pureLowerPrograms {
		name, source := name, source
		t.Run(name, func(t *testing.T) {
			want := pureLowerRunVM(t, root, source)
			elf, report := pureLowerBuild(t, root, source)
			if report != "ok\n" {
				t.Fatalf("lowering reported %q", report)
			}
			got := pureLowerRunNative(t, elf)
			if got.stdout != want.stdout {
				t.Fatalf("stdout differs:\n native %q (exit %d, stderr %q)\n vm     %q", got.stdout, got.exit, got.stderr, want.stdout)
			}
			if (got.exit == 0) != (want.exit == 0) {
				t.Fatalf("exit status differs: native %d, vm %d", got.exit, want.exit)
			}
		})
	}
}

// Unsupported programs must fail closed with a named error, never fall back or be ignored.
func TestLinuxAMD64PureMioLoweringRejectsUnsupported(t *testing.T) {
	if runtime.GOOS != "linux" || runtime.GOARCH != "amd64" {
		t.Skip("requires Linux x86_64")
	}
	root, _ := filepath.Abs(filepath.Join("..", ".."))
	for name, source := range map[string]string{"float": `chant(1.5 + 2.5);`} {
		_, report := pureLowerBuild(t, root, source)
		if report == "ok\n" || report == "" {
			t.Fatalf("%s: expected a rejection, got %q", name, report)
		}
		t.Logf("%s rejected: %s", name, report)
	}
}

// The backend driver (selfhost/native-aot-linux) is the first self-hosting target: it must lower
// with the pure-Mio backend itself.
func TestLinuxAMD64PureMioLowersItsOwnDriver(t *testing.T) {
	if runtime.GOOS != "linux" || runtime.GOARCH != "amd64" {
		t.Skip("requires Linux x86_64")
	}
	root, _ := filepath.Abs(filepath.Join("..", ".."))
	source, err := os.ReadFile(filepath.Join(root, "selfhost/native-aot-linux/main.mio"))
	if err != nil {
		t.Fatal(err)
	}
	elf, report := pureLowerBuild(t, root, string(source))
	if report != "ok\n" {
		t.Fatalf("lowering the driver reported %q", report)
	}
	info, err := os.Stat(elf)
	if err != nil {
		t.Fatal(err)
	}
	t.Logf("driver ELF: %d bytes", info.Size())
}

// Native fixed point of the backend driver: the seed-built ELF A (lowering run by the Mochi VM) compiles the
// driver's Mochi into B, B into C, and C into D. All four stages after the seed are Linux x86-64 executables
// run directly by the kernel; B = C = D must hold byte for byte, and B must also equal A because the seed
// and the native image implement the same lowering.
func TestLinuxAMD64PureMioDriverNativeFixedPoint(t *testing.T) {
	if runtime.GOOS != "linux" || runtime.GOARCH != "amd64" {
		t.Skip("requires Linux x86_64")
	}
	root, _ := filepath.Abs(filepath.Join("..", ".."))
	source, err := os.ReadFile(filepath.Join(root, "selfhost/native-aot-linux/main.mio"))
	if err != nil {
		t.Fatal(err)
	}
	program := m17CompileMio(t, root, string(source))
	var encoded bytes.Buffer
	if err := mochi.Encode(&encoded, program); err != nil {
		t.Fatal(err)
	}
	dir := t.TempDir()
	input := filepath.Join(dir, "driver.mochi")
	if err := os.WriteFile(input, encoded.Bytes(), 0o644); err != nil {
		t.Fatal(err)
	}
	seed, report := pureLowerBuild(t, root, string(source))
	if report != "ok\n" {
		t.Fatalf("seed lowering: %q", report)
	}
	stages := []string{"A", "B", "C", "D"}
	os.Chmod(seed, 0o755)
	paths := map[string]string{"A": seed}
	for i := 1; i < len(stages); i++ {
		compiler, name := paths[stages[i-1]], stages[i]
		work := filepath.Join(dir, "work-"+name)
		if err := os.MkdirAll(work, 0o755); err != nil {
			t.Fatal(err)
		}
		output := filepath.Join(dir, "compiler-"+name)
		os.WriteFile(filepath.Join(work, "input.config"), []byte(input), 0o644)
		os.WriteFile(filepath.Join(work, "output.config"), []byte(output), 0o644)
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
		cmd := exec.CommandContext(ctx, compiler)
		cmd.Dir = work
		var stdout, stderr bytes.Buffer
		cmd.Stdout, cmd.Stderr = &stdout, &stderr
		start := time.Now()
		err := cmd.Run()
		cancel()
		if err != nil || stdout.String() != "native-aot-linux: ok\n" {
			t.Fatalf("stage %s (compiler %s): err=%v stdout=%q stderr=%q", name, stages[i-1], err, stdout.String(), stderr.String())
		}
		os.Chmod(output, 0o755)
		paths[name] = output
		t.Logf("stage %s built by %s natively in %v", name, stages[i-1], time.Since(start).Round(time.Millisecond))
	}
	read := func(name string) []byte {
		data, err := os.ReadFile(paths[name])
		if err != nil {
			t.Fatal(err)
		}
		return data
	}
	a, b, c, d := read("A"), read("B"), read("C"), read("D")
	hash := func(data []byte) string { sum := sha256.Sum256(data); return hex.EncodeToString(sum[:8]) }
	t.Logf("A=%s B=%s C=%s D=%s (%d bytes)", hash(a), hash(b), hash(c), hash(d), len(b))
	if !bytes.Equal(b, c) || !bytes.Equal(c, d) {
		t.Fatalf("fixed point violated: B, C and D differ")
	}
	if !bytes.Equal(a, b) {
		t.Fatalf("native image differs from the seed's lowering: A != B")
	}
}

// pureLowerSeed lowers the Mio program in `source` (compiled by the Go reference compiler) with the pure-Mio
// backend running in the Mochi VM and returns the ELF path.
func pureLowerSeed(t *testing.T, root, source string) string {
	t.Helper()
	elf, report := pureLowerBuild(t, root, source)
	if report != "ok\n" {
		t.Fatalf("seed lowering: %q", report)
	}
	if err := os.Chmod(elf, 0o755); err != nil {
		t.Fatal(err)
	}
	return elf
}

// runLinuxCompiler runs a native Linux compiler ELF from the repository root with the request on stdin.
func runLinuxCompiler(t *testing.T, root, compiler, entry, output string) (string, string, error) {
	return runLinuxCompilerIn(t, root, compiler, entry, output)
}

func runLinuxCompilerIn(t *testing.T, root, compiler, entry, output string) (string, string, error) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Minute)
	defer cancel()
	cmd := exec.CommandContext(ctx, compiler)
	cmd.Dir = root
	cmd.Stdin = bytes.NewBufferString(entry + "\n" + output + "\n")
	var stdout, stderr bytes.Buffer
	cmd.Stdout, cmd.Stderr = &stdout, &stderr
	err := cmd.Run()
	return stdout.String(), stderr.String(), err
}

// The complete pure-Mio compiler (parser, resolver, type checker, code generator, Linux lowering) as a native
// Linux program: the seed is built by the VM-hosted backend, then A -> B -> C -> D natively.
func TestLinuxAMD64NativeCompilerFixedPoint(t *testing.T) {
	if runtime.GOOS != "linux" || runtime.GOARCH != "amd64" {
		t.Skip("requires Linux x86_64")
	}
	root, _ := filepath.Abs(filepath.Join("..", ".."))
	source, err := os.ReadFile(filepath.Join(root, "selfhost/linux-compiler/main.mio"))
	if err != nil {
		t.Fatal(err)
	}
	dir := t.TempDir()
	started := time.Now()
	paths := map[string]string{"A": pureLowerSeed(t, root, string(source))}
	t.Logf("seed ELF built by the VM-hosted backend in %v (%d bytes)", time.Since(started).Round(time.Millisecond), fileSize(t, paths["A"]))
	order := []string{"A", "B", "C", "D"}
	for i := 1; i < len(order); i++ {
		name := order[i]
		output := filepath.Join(dir, "compiler-"+name)
		started := time.Now()
		stdout, stderr, err := runLinuxCompiler(t, root, paths[order[i-1]], "selfhost/linux-compiler", output)
		if err != nil || stdout != "linux-compiler: ok\n" {
			t.Fatalf("stage %s (compiler %s): err=%v stdout=%q stderr=%q", name, order[i-1], err, stdout, stderr)
		}
		if err := os.Chmod(output, 0o755); err != nil {
			t.Fatal(err)
		}
		paths[name] = output
		t.Logf("stage %s built natively by %s in %v", name, order[i-1], time.Since(started).Round(time.Millisecond))
	}
	read := func(name string) []byte {
		data, err := os.ReadFile(paths[name])
		if err != nil {
			t.Fatal(err)
		}
		return data
	}
	a, b, c, d := read("A"), read("B"), read("C"), read("D")
	hash := func(data []byte) string { sum := sha256.Sum256(data); return hex.EncodeToString(sum[:8]) }
	t.Logf("A=%s B=%s C=%s D=%s (%d bytes)", hash(a), hash(b), hash(c), hash(d), len(b))
	if keep := os.Getenv("MIO_LINUX_ARTIFACT_DIR"); keep != "" {
		os.MkdirAll(keep, 0o755)
		for name, data := range map[string][]byte{"compiler-A": a, "compiler-B": b, "compiler-C": c, "compiler-D": d} {
			os.WriteFile(filepath.Join(keep, name), data, 0o755)
		}
	}
	if !bytes.Equal(b, c) || !bytes.Equal(c, d) {
		t.Fatalf("fixed point violated: B, C and D differ")
	}
	// A is lowered from the Go reference compiler's Mochi, B from the Mio code generator's Mochi, so A != B is
	// expected (different function numbering); the fixed point is B = C = D.
	t.Logf("seed A and native B differ as expected: %v", !bytes.Equal(a, b))

	// The native compiler B must also produce working programs: compile every differential program with it
	// (sources in a scratch project that shares the repository's bunko) and compare with the VM.
	project := t.TempDir()
	if err := os.Symlink(filepath.Join(root, "bunko"), filepath.Join(project, "bunko")); err != nil {
		t.Fatal(err)
	}
	names := make([]string, 0, len(pureLowerPrograms))
	for name := range pureLowerPrograms {
		names = append(names, name)
	}
	sort.Strings(names)
	for _, name := range names {
		source := pureLowerPrograms[name]
		dirName := "prog_" + name
		if err := os.MkdirAll(filepath.Join(project, dirName), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(project, dirName, "main.mio"), []byte(source), 0o644); err != nil {
			t.Fatal(err)
		}
		output := filepath.Join(project, "out_"+name)
		stdout, stderr, err := runLinuxCompilerIn(t, project, paths["B"], dirName, output)
		if err != nil || stdout != "linux-compiler: ok\n" {
			t.Errorf("%s: native compile failed: err=%v stdout=%q stderr=%q", name, err, stdout, stderr)
			continue
		}
		want := pureLowerRunVM(t, root, source)
		got := pureLowerRunNative(t, output)
		if got.stdout != want.stdout || (got.exit == 0) != (want.exit == 0) {
			t.Errorf("%s: native-compiled program differs from the VM:\n native %q (exit %d, stderr %q)\n vm     %q", name, got.stdout, got.exit, got.stderr, want.stdout)
		}
	}
}

func fileSize(t *testing.T, path string) int64 {
	info, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	return info.Size()
}

// Every differential program again with a 16 KiB collection threshold, so that collections run at almost every
// poll and any missing root, wrong stack map or bad sweep shows up as a difference from the VM.
func TestLinuxAMD64PureMioLoweringUnderGCStress(t *testing.T) {
	if runtime.GOOS != "linux" || runtime.GOARCH != "amd64" {
		t.Skip("requires Linux x86_64")
	}
	root, _ := filepath.Abs(filepath.Join("..", ".."))
	previous := pureLowerGCThreshold
	pureLowerGCThreshold = 16384
	defer func() { pureLowerGCThreshold = previous }()
	names := make([]string, 0, len(pureLowerPrograms))
	for name := range pureLowerPrograms {
		if name != "gc_garbage" && name != "gc_keeps_live_data" {
			names = append(names, name)
		}
	}
	sort.Strings(names)
	for _, name := range names {
		name := name
		t.Run(name, func(t *testing.T) {
			source := pureLowerPrograms[name]
			want := pureLowerRunVM(t, root, source)
			elf, report := pureLowerBuild(t, root, source)
			if report != "ok\n" {
				t.Fatalf("lowering reported %q", report)
			}
			got := pureLowerRunNative(t, elf)
			if got.stdout != want.stdout || (got.exit == 0) != (want.exit == 0) {
				t.Fatalf("differs under GC stress:\n native %q (exit %d, stderr %q)\n vm     %q", got.stdout, got.exit, got.stderr, want.stdout)
			}
		})
	}
}

// The native Mio CLI (selfhost/cli) for Linux x86-64: built by the native compiler chain, then used as
// `mio build --target=linux-amd64` to build itself three more times. CLI2 = CLI3 = CLI4 is the fixed point of the CLI;
// CLI1 (built through the bootstrap-style driver) and CLI2 (built through the full frontend) may legitimately differ.
func TestLinuxAMD64NativeCLIFixedPoint(t *testing.T) {
	if runtime.GOOS != "linux" || runtime.GOARCH != "amd64" {
		t.Skip("requires Linux x86_64")
	}
	if testing.Short() {
		t.Skip("builds the CLI five times")
	}
	root, _ := filepath.Abs(filepath.Join("..", ".."))
	source, err := os.ReadFile(filepath.Join(root, "selfhost/linux-compiler/main.mio"))
	if err != nil {
		t.Fatal(err)
	}
	dir := t.TempDir()
	compiler := pureLowerSeed(t, root, string(source))
	for _, stage := range []string{"B", "C"} {
		output := filepath.Join(dir, "compiler-"+stage)
		stdout, stderr, err := runLinuxCompiler(t, root, compiler, "selfhost/linux-compiler", output)
		if err != nil || stdout != "linux-compiler: ok\n" {
			t.Fatalf("compiler %s: err=%v stdout=%q stderr=%q", stage, err, stdout, stderr)
		}
		os.Chmod(output, 0o755)
		compiler = output
	}
	cli := filepath.Join(dir, "mio-1")
	started := time.Now()
	if stdout, stderr, err := runLinuxCompiler(t, root, compiler, "selfhost/cli", cli); err != nil || stdout != "linux-compiler: ok\n" {
		t.Fatalf("native compiler cannot build the CLI: err=%v stdout=%q stderr=%q", err, stdout, stderr)
	}
	os.Chmod(cli, 0o755)
	t.Logf("CLI1 built by the native compiler in %v (%d bytes)", time.Since(started).Round(time.Millisecond), fileSize(t, cli))
	run := func(binary string, args ...string) (string, string, error) {
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Minute)
		defer cancel()
		cmd := exec.CommandContext(ctx, binary, args...)
		cmd.Dir = root
		cmd.Env = append(os.Environ(), "MIO_BUNKO="+filepath.Join(root, "bunko"))
		var out, errOut bytes.Buffer
		cmd.Stdout, cmd.Stderr = &out, &errOut
		err := cmd.Run()
		return out.String(), errOut.String(), err
	}
	if out, _, err := run(cli, "--version"); err != nil || !strings.HasPrefix(out, "mio v2.0.0-dev") {
		t.Fatalf("--version: err=%v out=%q", err, out)
	}
	// a program built by the CLI runs natively
	project := t.TempDir()
	os.WriteFile(filepath.Join(project, "main.mio"), []byte("chant(\"hello from the native Linux CLI\");\nkaku n = 0; kaku i = 1; aida (i <= 100) { n = n + i; i = i + 1; }\nchant(n);\n"), 0o644)
	hello := filepath.Join(dir, "hello")
	if _, stderr, err := run(cli, "build", project, "--target=linux-amd64", "-o", hello); err != nil {
		t.Fatalf("build hello: %v %s", err, stderr)
	}
	if out, _, err := run(hello); err != nil || out != "hello from the native Linux CLI\n5050\n" {
		t.Fatalf("hello: err=%v out=%q", err, out)
	}
	// `mio test` runs Linux ELF test images through spawn_test: pass, assertion failure, filter, hang, compile error, abnormal exit
	for _, c := range []struct {
		name, source string
		args         []string
		exit         int
		contains     []string
		absent       []string
	}{
		{"pass", "yobu \"kiso/testing\";\nwaza test_a() -> unit { testing.expect(1 + 1 == 2, \"ok\"); }\nwaza test_b() -> unit { testing.expect(hai, \"ok\"); }\n", nil, 0, []string{"PASS: test_a", "PASS: test_b", "2 passed, 0 failed"}, nil},
		{"fail", "yobu \"kiso/testing\";\nwaza test_ok() -> unit { testing.expect(hai, \"ok\"); }\nwaza test_bad() -> unit { testing.expect(1 == 2, \"one is not two\"); testing.expect(3 == 4, \"three is not four\"); }\n", nil, 1, []string{"PASS: test_ok", "FAIL: test_bad", "assertion failed: one is not two", "assertion failed: three is not four", "1 passed, 1 failed"}, nil},
		{"filter", "yobu \"kiso/testing\";\nwaza test_alpha() -> unit { testing.expect(hai, \"a\"); }\nwaza test_beta() -> unit { testing.expect(iie, \"must not run\"); }\n", []string{"--run=alpha"}, 0, []string{"PASS: test_alpha", "1 passed, 0 failed"}, []string{"test_beta"}},
		{"hang", "yobu \"kiso/testing\";\nwaza test_spin() -> unit { kaku i = 0; aida (hai) { i = i + 1; } }\nwaza test_after() -> unit { testing.expect(hai, \"ok\"); }\n", nil, 1, []string{"FAIL: test_spin", "resource limit", "PASS: test_after"}, nil},
		{"compile", "yobu \"kiso/testing\";\nwaza test_bad() -> unit { kaku x: int64 = \"text\"; }\n", nil, 1, []string{"E0301", "0 passed, 1 failed"}, []string{"PASS"}},
		{"abnormal", "yobu \"kiso/testing\";\nyobu \"kiso/os\";\nwaza test_exit() -> unit { os.exit(3); }\nwaza test_crash() -> unit { kaku a: []int64 = []; testing.expect(a[5] == 0, \"unreachable\"); }\n", nil, 1, []string{"FAIL: test_exit", "status=3", "FAIL: test_crash", "status=1", "0 passed, 2 failed"}, []string{"PASS"}},
		{"gc", "yobu \"kiso/testing\";\nyobu \"kiso/array\";\nwaza test_garbage() -> unit {\n    kaku keep = array.make[int64](100, 7); kaku i = 0; kaku sink = 0;\n    aida (i < 300000) { kaku g = array.make[int64](1000, i); sink = sink + g[999]; i = i + 1; }\n    testing.expect(keep[50] == 7, \"live\"); testing.expect(sink == 44999850000, \"sum\");\n}\n", nil, 0, []string{"PASS: test_garbage"}, nil},
	} {
		dirName := filepath.Join(project, "test_"+c.name)
		os.MkdirAll(dirName, 0o755)
		os.WriteFile(filepath.Join(dirName, "a_test.mio"), []byte(c.source), 0o644)
		args := append([]string{"test", dirName}, c.args...)
		for repeat := 0; repeat < 2; repeat++ {
			out, errOut, err := run(cli, args...)
			code := 0
			if exitErr, ok := err.(*exec.ExitError); ok {
				code = exitErr.ExitCode()
			} else if err != nil {
				t.Fatalf("mio test %s: %v", c.name, err)
			}
			if code != c.exit {
				t.Errorf("mio test %s: exit %d, want %d\n%s%s", c.name, code, c.exit, out, errOut)
			}
			out += errOut
			for _, want := range c.contains {
				if !strings.Contains(out, want) {
					t.Errorf("mio test %s: output lacks %q:\n%s", c.name, want, out)
				}
			}
			for _, bad := range c.absent {
				if strings.Contains(out, bad) {
					t.Errorf("mio test %s: output unexpectedly has %q:\n%s", c.name, bad, out)
				}
			}
		}
	}
	if leftovers, _ := filepath.Glob("/tmp/mio-test-*"); len(leftovers) > 0 {
		t.Logf("note: temporary test files left behind: %v", leftovers)
	}
	// the native `mio test` runs real package suites: sockets, the encoder / ELF / runtime packages, and the platform skip
	for _, suite := range []struct {
		target  string
		skipped string
	}{{"bunko/kiso/net/tcp", ""}, {"bunko/kiso/aot/x86_64", ""}, {"bunko/kiso/aot/elf", ""}, {"bunko/kiso/runtime/cpu/amd64", ""}, {"bunko/kiso/runtime/os/linux", ""}, {"selfhost/pipeline", "Tests skipped: 1"}} {
		out, errOut, err := run(cli, "test", suite.target)
		if err != nil || !strings.Contains(out, " 0 failed") {
			t.Errorf("native mio test %s: err=%v\n%s%s", suite.target, err, out, errOut)
		}
		if suite.skipped != "" && !strings.Contains(out, suite.skipped) {
			t.Errorf("native mio test %s: expected %q:\n%s", suite.target, suite.skipped, out)
		}
		if suite.skipped == "" && strings.Contains(out, "SKIP") {
			t.Errorf("native mio test %s: unexpected skip:\n%s", suite.target, out)
		}
	}
	// the CLI builds itself repeatedly
	previous := cli
	var built [][]byte
	for stage := 2; stage <= 4; stage++ {
		output := filepath.Join(dir, fmt.Sprintf("mio-%d", stage))
		started := time.Now()
		if _, stderr, err := run(previous, "build", "selfhost/cli", "--target=linux-amd64", "-o", output); err != nil {
			t.Fatalf("CLI%d -> CLI%d: %v %s", stage-1, stage, err, stderr)
		}
		data, err := os.ReadFile(output)
		if err != nil {
			t.Fatal(err)
		}
		built = append(built, data)
		t.Logf("CLI%d built by CLI%d in %v (%d bytes, %x)", stage, stage-1, time.Since(started).Round(time.Millisecond), len(data), sha256.Sum256(data))
		previous = output
	}
	if !bytes.Equal(built[0], built[1]) || !bytes.Equal(built[1], built[2]) {
		t.Fatalf("CLI fixed point violated: CLI2, CLI3 and CLI4 differ")
	}
	if keep := os.Getenv("MIO_LINUX_ARTIFACT_DIR"); keep != "" {
		os.MkdirAll(keep, 0o755)
		os.WriteFile(filepath.Join(keep, "mio-linux"), built[2], 0o755)
	}
}
