package aot

import (
	"bytes"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"

	"Mio/internal/compiler"
	"Mio/internal/mochi"
	"Mio/internal/stdlib"
	"Mio/internal/vm"
)

// Decision 7: the Go compiler (analyzeM6) and the pure-Mio compiler
// (kiso/aot/lower/types) must agree, for the SAME Mochi input, on which slots
// are heap references. Physical register numbers / stack offsets are not
// compared: only semantic roots (globals, locals, and the operand-stack entry
// state of every reachable instruction, i.e. every possible safepoint).

type rootFacts struct {
	globals map[int]int
	locals  map[[2]int]int   // {function id, slot}
	entries map[[2]int][]int // class per operand slot: 0 raw, 1 nullable-scalar box, 2 reference
	errText string
}

func goRootClass(a *m6Analysis, node int) int {
	switch {
	case m12ReferenceKind(a.u.get(node)):
		return 2
	case m13ReferenceNode(a.u, node):
		return 1
	}
	return 0
}

func goRootFacts(p *compiler.Bytecode) (*rootFacts, error) {
	a, err := analyzeM6(p)
	if err != nil {
		return nil, err
	}
	f := &rootFacts{globals: map[int]int{}, locals: map[[2]int]int{}, entries: map[[2]int][]int{}}
	for i, n := range a.globals {
		f.globals[i] = goRootClass(a, n)
	}
	for fid, nodes := range a.locals {
		for slot, n := range nodes {
			f.locals[[2]int{fid, slot}] = goRootClass(a, n)
		}
	}
	for bi, b := range a.blocks {
		for i, ins := range b.inst {
			if b.reach[i] == nil {
				continue
			}
			bits := make([]int, len(b.entry[i]))
			for k, n := range b.entry[i] {
				bits[k] = goRootClass(a, n)
			}
			f.entries[[2]int{bi, ins.offset}] = bits
		}
	}
	return f, nil
}

const rootDumpMio = `yobu "kiso/aot/lower/types";
yobu "kiso/encoding/mochi";
yobu "kiso/convert";
yobu "kiso/string";
waza num(n: int64) -> string { kaesu convert.format_int(n); }
waza bit(analysis: types.TypeAnalysis, node: int64) -> string {
  kaku kind = types.type_kind(analysis, node);
  moshi (kind == types.type_string_id || kind == types.type_array_ref || kind == types.type_struct_ref || kind == types.type_enum_ref || kind == types.type_function_ref || kind == types.type_map_ref) { kaesu "2"; }
  moshi (types.type_is_heap_reference(analysis, node)) { kaesu "1"; }
  kaesu "0";
}
waza dump(file: mochi.File) -> unit {
  kaku analysis = types.analyze_types(file);
  moshi (analysis.error_detail != 0) { chant(string.concat("ANALYSIS_ERROR ", num(analysis.error_detail))); kaesu; }
  kaku i = 0;
  aida (i < len(analysis.globals)) { chant(string.concat("G ", string.concat(num(i), string.concat(" ", bit(analysis, analysis.globals[i]))))); i = i + 1; }
  i = 0;
  aida (i < len(analysis.locals)) {
    kaku s = 0;
    aida (s < len(analysis.locals[i])) {
      chant(string.concat("L ", string.concat(num(i), string.concat(" ", string.concat(num(s), string.concat(" ", bit(analysis, analysis.locals[i][s]))))))); s = s + 1;
    }
    i = i + 1;
  }
  i = 0;
  aida (i < len(analysis.blocks)) {
    kaku block = analysis.blocks[i];
    kaku o = 0;
    aida (o < len(block.reachable)) {
      moshi (block.reachable[o]) {
        kaku bits = "";
        kaku k = 0;
        aida (k < len(block.entry[o])) { bits = string.concat(bits, bit(analysis, block.entry[o][k])); k = k + 1; }
        chant(string.concat("E ", string.concat(num(i), string.concat(" ", string.concat(num(o), string.concat(" ", bits))))));
      }
      o = o + 1;
    }
    i = i + 1;
  }
}
kaku decoded = mochi.decode_file(MOCHI_PATH);
kaku file = decoded.value;
moshi (decoded.error != mu) { chant("DECODE_FAILED"); }
sore { moshi (file == mu) { chant("DECODE_FAILED"); } sore { dump(file); } }
`

func mioRootFacts(t *testing.T, root string, p *compiler.Bytecode) (*rootFacts, error) {
	t.Helper()
	dir := t.TempDir()
	path := filepath.Join(dir, "input.mochi")
	var buf bytes.Buffer
	if err := mochi.Encode(&buf, p); err != nil {
		return nil, fmt.Errorf("encode: %w", err)
	}
	if err := os.WriteFile(path, buf.Bytes(), 0o644); err != nil {
		return nil, err
	}
	program := m17CompileMio(t, root, strings.Replace(rootDumpMio, "MOCHI_PATH", fmt.Sprintf("%q", path), 1))
	registry, err := stdlib.NewRegistry()
	if err != nil {
		return nil, err
	}
	var out bytes.Buffer
	machine := vm.NewWithRegistryAndOutput(program, registry, &out)
	if err := machine.RunWithOptions(vm.ExecutionOptions{InstructionLimit: 4_000_000_000}); err != nil {
		return nil, fmt.Errorf("mio analysis: %w", err)
	}
	f := &rootFacts{globals: map[int]int{}, locals: map[[2]int]int{}, entries: map[[2]int][]int{}}
	for _, line := range strings.Split(strings.TrimSpace(out.String()), "\n") {
		fields := strings.Fields(line)
		switch {
		case len(fields) == 0:
		case fields[0] == "DECODE_FAILED" || fields[0] == "ANALYSIS_ERROR":
			f.errText = line
		case fields[0] == "G" && len(fields) == 3:
			var i int
			fmt.Sscan(fields[1], &i)
			f.globals[i] = int(fields[2][0] - '0')
		case fields[0] == "L" && len(fields) == 4:
			var fid, slot int
			fmt.Sscan(fields[1], &fid)
			fmt.Sscan(fields[2], &slot)
			f.locals[[2]int{fid, slot}] = int(fields[3][0] - '0')
		case fields[0] == "E":
			var b, o int
			fmt.Sscan(fields[1], &b)
			fmt.Sscan(fields[2], &o)
			bits := []int{}
			if len(fields) == 4 {
				for _, c := range fields[3] {
					bits = append(bits, int(c-'0'))
				}
			}
			f.entries[[2]int{b, o}] = bits
		}
	}
	return f, nil
}

// compareRoots classifies every disagreement:
//
//	hard:  the two compilers disagree about a true heap reference (string, array,
//	       struct, enum, function) - a possibly missing root. Always a failure.
//	boxing: they disagree only on whether a nullable SCALAR is boxed (0 vs 1).
//	       Each compiler is self-consistent (it boxes and unboxes with its own
//	       analysis), so this is a representation difference, not a missing root.
func compareRoots(goF, mioF *rootFacts) (hard, boxing []string, compared int) {
	note := func(what string, g, m int) {
		if g == m {
			return
		}
		line := fmt.Sprintf("%s: go=%d mio=%d", what, g, m)
		if g == 2 || m == 2 {
			hard = append(hard, line)
		} else {
			boxing = append(boxing, line)
		}
	}
	for i, g := range goF.globals {
		if m, ok := mioF.globals[i]; ok {
			compared++
			note(fmt.Sprintf("global %d", i), g, m)
		}
	}
	for k, g := range goF.locals {
		if m, ok := mioF.locals[k]; ok {
			compared++
			note(fmt.Sprintf("local fn%d slot%d", k[0], k[1]), g, m)
		}
	}
	for k, g := range goF.entries {
		m, ok := mioF.entries[k]
		if !ok {
			continue // reachability differs: informational only
		}
		compared++
		if len(g) != len(m) {
			hard = append(hard, fmt.Sprintf("entry block%d@%d depth go=%d mio=%d", k[0], k[1], len(g), len(m)))
			continue
		}
		for i := range g {
			note(fmt.Sprintf("entry block%d@%d slot%d", k[0], k[1], i), g[i], m[i])
		}
	}
	sort.Strings(hard)
	sort.Strings(boxing)
	return
}

var rootDiffPrograms = []struct{ name, src string }{
	{"precise-stack-roots", shadowPreciseSrc},
	{"nested-arrays-structs", shadowNestedSrc},
	{"global-held", shadowGlobalSrc},
	{"nullable-and-enum", `yobu "kiso/array";
sentaku Shape { Empty; Num(int64); Name(string); Pair([]int64, int64?); }
waza classify(s: Shape) -> int64 {
  kaku result = 0;
  awase (s) {
    baai Empty { result = 0; }
    baai Num(n) { result = n; }
    baai Name(name) { result = 1000; }
    baai Pair(items, extra) { kaku total = len(items); moshi (extra != mu) { total = total + extra; } result = total; }
  }
  kaesu result;
}
waza maybe(n: int64) -> int64? { moshi (n - (n / 3) * 3 == 0) { kaesu mu; } kaesu n * 2; }
kaku shapes: []Shape = array.with_capacity[Shape](8);
array.push(shapes, Shape.Empty()); array.push(shapes, Shape.Num(41)); array.push(shapes, Shape.Name("mio"));
kaku i = 0;
aida (i < 30) { array.push(shapes, Shape.Pair(array.make[int64](i + 1, i), maybe(i))); i = i + 1; }
kaku sum = 0; i = 0;
aida (i < len(shapes)) { sum = sum + classify(shapes[i]); i = i + 1; }
chant(sum);`},
	{"floats-and-strings", `kaku a: float64 = 0.1; kaku s: string = "hello"; kaku b = a + 0.2; chant(b); chant(s);
waza twice(x: float64) -> float64 { kaesu x * 2.0; } chant(twice(b));`},
	{"closures", `waza make(n: int64) -> int64 { kaku inner = waza (x: int64) -> int64 { kaesu x + n; }; kaesu inner(1); }
waza twice(n: int64) -> int64 { kaku f = waza (x: int64) -> int64 { kaesu x * 2 + n; }; kaesu f(f(3)); }
chant(make(41)); chant(twice(5));`},
	{"kiso-string-and-array-libraries", `yobu "kiso/string"; yobu "kiso/array"; yobu "kiso/convert";
kaku parts: []string = array.with_capacity[string](4);
array.push(parts, "a"); array.push(parts, convert.format_int(42));
chant(string.concat(parts[0], parts[1]));`},
}

// notComparableAllowlist maps a program name to the exact error text for which the Go analysis
// may reject it, in which case the comparison is skipped (and the skip reason is logged). It is
// empty on purpose: every program in rootDiffPrograms is currently comparable. A new rejection, or
// a different error for a listed program, fails the test instead of hiding behind a SKIP.
var notComparableAllowlist = map[string]string{}

func TestLinuxAMD64RootSetsAgreeBetweenGoAndPureMio(t *testing.T) {
	if testing.Short() {
		t.Skip("slow: runs the pure-Mio analyser in the VM")
	}
	root, err := filepath.Abs(filepath.Join("..", ".."))
	if err != nil {
		t.Fatal(err)
	}
	for _, c := range rootDiffPrograms {
		t.Run(c.name, func(t *testing.T) {
			p := m17CompileMio(t, root, c.src)
			goF, err := goRootFacts(p)
			if err != nil {
				if reason, ok := notComparableAllowlist[c.name]; ok && strings.Contains(err.Error(), reason) {
					t.Skipf("NOT-COMPARABLE (allowlisted: %s): Go analysis rejects this input (%v)", reason, err)
				}
				t.Fatalf("Go analysis rejects this input (%v); if this is a known limitation add it, with its error text, to notComparableAllowlist", err)
			}
			mioF, err := mioRootFacts(t, root, p)
			if err != nil {
				t.Fatal(err)
			}
			if mioF.errText != "" {
				t.Fatalf("pure-Mio analysis failed: %s", mioF.errText)
			}
			hard, boxing, compared := compareRoots(goF, mioF)
			t.Logf("compared %d semantic facts; hard disagreements=%d nullable-boxing differences=%d", compared, len(hard), len(boxing))
			if compared == 0 {
				t.Fatal("nothing compared")
			}
			if len(hard) != 0 {
				max := len(hard)
				if max > 25 {
					max = 25
				}
				t.Fatalf("Go and pure-Mio disagree about true heap references:\n%s", strings.Join(hard[:max], "\n"))
			}
		})
	}
}

// The comparator must actually flag a missing/extra root: mutate one fact.
func TestRootComparatorDetectsMutations(t *testing.T) {
	base := func() *rootFacts {
		return &rootFacts{globals: map[int]int{0: 2, 1: 0}, locals: map[[2]int]int{{0, 0}: 2}, entries: map[[2]int][]int{{0, 5}: {0, 2, 1}}}
	}
	if hard, boxing, n := compareRoots(base(), base()); len(hard)+len(boxing) != 0 || n != 4 {
		t.Fatalf("identical facts must agree: %v %v %d", hard, boxing, n)
	}
	m := base()
	m.entries[[2]int{0, 5}][1] = 0 // Mio would not root a real reference
	if hard, _, _ := compareRoots(base(), m); len(hard) != 1 {
		t.Fatalf("missing reference root not flagged: %v", hard)
	}
	m = base()
	m.globals[1] = 2 // Mio roots something Go treats as raw
	if hard, _, _ := compareRoots(base(), m); len(hard) != 1 {
		t.Fatalf("extra reference root not flagged: %v", hard)
	}
	m = base()
	m.entries[[2]int{0, 5}][2] = 0 // nullable boxing only
	if hard, boxing, _ := compareRoots(base(), m); len(hard) != 0 || len(boxing) != 1 {
		t.Fatalf("boxing difference misclassified: %v %v", hard, boxing)
	}
	m = base()
	m.entries[[2]int{0, 5}] = []int{0, 2}
	if hard, _, _ := compareRoots(base(), m); len(hard) != 1 {
		t.Fatalf("depth mismatch not flagged: %v", hard)
	}
}
