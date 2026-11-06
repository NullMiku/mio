// Command stage copies the allowlisted Bunko packages (playground.LibraryPackages) into
// the directory that cmd/mio-wasm embeds. Only files visible through playground.Library
// are copied, so the embedded set and the run-time allowlist cannot drift apart.
package main

import (
	"fmt"
	"io/fs"
	"os"
	"path/filepath"

	"Mio/internal/playground"
)

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "usage: stage <bunko-root> <output-directory>")
		os.Exit(2)
	}
	library := playground.Library(os.DirFS(os.Args[1]))
	if err := os.RemoveAll(os.Args[2]); err != nil {
		fail(err)
	}
	files := 0
	for _, pkg := range playground.LibraryPackages {
		entries, err := fs.ReadDir(library, pkg)
		if err != nil {
			fail(err)
		}
		for _, entry := range entries {
			name := pkg + "/" + entry.Name()
			data, err := fs.ReadFile(library, name)
			if err != nil {
				fail(err)
			}
			target := filepath.Join(os.Args[2], filepath.FromSlash(name))
			if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
				fail(err)
			}
			if err := os.WriteFile(target, data, 0o644); err != nil {
				fail(err)
			}
			files++
		}
	}
	fmt.Printf("staged %d sources from %d packages\n", files, len(playground.LibraryPackages))
}

func fail(err error) {
	fmt.Fprintln(os.Stderr, "stage:", err)
	os.Exit(1)
}
