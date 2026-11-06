package playground

import (
	"bytes"
	"os"
	"path/filepath"
	"testing"

	"Mio/internal/bunko"
	"Mio/internal/compiler"
	"Mio/internal/constant"
	"Mio/internal/mochi"
	"Mio/internal/resolver"
	"Mio/internal/stdlib"
	"Mio/internal/typecheck"
)

// referenceBuild compiles source exactly like the reference `mio build` (host Bunko, native registry).
func referenceBuild(t *testing.T, source string) []byte {
	t.Helper()
	path := filepath.Join(t.TempDir(), "main.mio")
	if err := os.WriteFile(path, []byte(source), 0o644); err != nil {
		t.Fatal(err)
	}
	registry, err := stdlib.NewRegistry()
	if err != nil {
		t.Fatal(err)
	}
	loaded, err := bunko.LoadProgramWithRegistry(path, "../../bunko", registry)
	if err != nil {
		t.Fatal(err)
	}
	if err := constant.Fold(loaded.AST); err != nil {
		t.Fatal(err)
	}
	r := resolver.New()
	if err := r.ResolveProgram(loaded.AST); err != nil {
		t.Fatal(err)
	}
	if err := typecheck.NewWithResolver(r).CheckProgram(loaded.AST); err != nil {
		t.Fatal(err)
	}
	c := compiler.NewWithResolver(r)
	if err := c.Compile(loaded.AST); err != nil {
		t.Fatal(err)
	}
	var out bytes.Buffer
	if err := mochi.Encode(&out, c.Bytecode()); err != nil {
		t.Fatal(err)
	}
	return out.Bytes()
}
