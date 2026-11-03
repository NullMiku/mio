package typecheck_test

import (
	mio "Mio"
	"bytes"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
)

// Optional exact before/after comparison against a frozen source tree. Unlike
// the Go/Mio tests, raw wire equality also checks node and diagnostic order.
func TestMioTypecheckerFrozenSnapshotDifferential(t *testing.T) {
	baseline := os.Getenv("MIO_TYPECHECK_BASELINE_ROOT")
	if baseline == "" {
		t.Skip("set MIO_TYPECHECK_BASELINE_ROOT to a frozen pre-optimization source tree")
	}
	sources := []string{
		`waza add(x: int64) -> int64 {kaesu x+1;} chant(add(41));`,
		`waza id<T: Number>(x: T) -> T {kaesu x;} chant(id(7));`,
		`waza use(x: int64?) -> int64 {moshi(x != mu){kaesu x;}kaesu 0;} chant(use(4));`,
		`kaku a: []int64=[1,2,3]; a[0]=4; chant(a[0]);`,
		`kaku m: Map<string,int64> = Map[string,int64](); m["x"]=3; chant(m["x"]);`,
		`kata Box<T> {value:T;} kaku b=Box[int64]{value:2}; chant(b.value);`,
		`kaku a: int32=1; kaku b: int64=2; chant(a+b); kaku c: uint8=256;`,
		`waza bad(x: int64?) -> int64 {kaesu x+1;}`,
		`waza id<T: Float>(x:T) -> T {kaesu x;} kaku a=id(1);`,
		`yobu "mio/sys/socket"; socket.status(1,[uint8(0)]); socket.open(1);`,
		`yobu "mio/fs/runtime"; runtime.close(123,456);`,
		`teisu a: int64=b+1; teisu b: int64=41; chant(a);`,
	}
	dir := t.TempDir()
	paths := make([]string, len(sources))
	for i, source := range sources {
		paths[i] = filepath.Join(dir, fmt.Sprintf("case%d.mio", i))
		if err := os.WriteFile(paths[i], []byte(source), 0600); err != nil {
			t.Fatal(err)
		}
	}
	harnessSource := "yobu \"selfhost/codegen\";\n" + typecheckHarness(paths)
	// Append Codegen's entire generated Mochi bytes, not just a summary/hash.
	harnessSource += `waza generated(path: string) -> unit {
 kaku loaded=fs.read_all(path);kaku parsed=parser.parse(loaded.data);
 kaku resolved=resolver.resolve_program("case",parsed);kaku checked=typecheck.check_program(resolved);
 kaku compiled=codegen.compile_program(resolved,checked);chant(compiled.success);chant(len(compiled.bytes));
 kaku i=0;aida(i<len(compiled.bytes)){chant(int64(compiled.bytes[i]));i=i+1;}
 chant(len(compiled.errors));i=0;aida(i<len(compiled.errors)){chant(compiled.errors[i].detail);i=i+1;}
}
`
	for _, path := range paths {
		harnessSource += "generated(" + strconv.Quote(path) + ");\n"
	}
	harness := filepath.Join(dir, "harness.mio")
	if err := os.WriteFile(harness, []byte(harnessSource), 0600); err != nil {
		t.Fatal(err)
	}
	run := func(root string) []byte {
		env, err := mio.NewStandardEnvironment()
		if err != nil {
			t.Fatal(err)
		}
		defer env.Close()
		program, err := env.CompileFile(harness, filepath.Join(root, "bunko"))
		if err != nil {
			t.Fatal(err)
		}
		var out bytes.Buffer
		if err := env.RunWithOptions(program, &out, mio.ExecutionOptions{InstructionLimit: 100_000_000_000}); err != nil {
			t.Fatal(err)
		}
		return out.Bytes()
	}
	before, after := run(baseline), run(typecheckRoot(t))
	if evidence := os.Getenv("MIO_TYPECHECK_EVIDENCE"); evidence != "" {
		for name, data := range map[string][]byte{"snapshot-before.stdout": before, "snapshot-after.stdout": after} {
			if err := os.WriteFile(filepath.Join(evidence, name), data, 0600); err != nil {
				t.Fatal(err)
			}
		}
	}
	if !bytes.Equal(before, after) {
		a, b := strings.Split(string(before), "\n"), strings.Split(string(after), "\n")
		for i := 0; i < len(a) && i < len(b); i++ {
			if a[i] != b[i] {
				t.Fatalf("first difference at wire line %d: before=%q after=%q", i+1, a[i], b[i])
			}
		}
		t.Fatalf("wire lengths differ: %d vs %d", len(before), len(after))
	}
	t.Logf("%d cases: ordered type results, full diagnostics and generated Mochi bytes equal (%d wire bytes)", len(sources), len(after))
}
