package playground

import (
	"errors"
	"io/fs"
	"path"
	"strings"
)

// LibraryPackages is the reviewed closure of pure-Mio Bunko packages available in the
// browser. None of them imports a native MMA module; kiso/fs, kiso/io, kiso/os,
// kiso/net, kiso/runtime, kiso/aot, kiso/testing and kiso/encoding/mochi (which needs
// kiso/fs) are deliberately absent.
var LibraryPackages = []string{
	"kiso/array",
	"kiso/bytes",
	"kiso/convert",
	"kiso/crypto/sha256",
	"kiso/encoding/binary",
	"kiso/encoding/json",
	"kiso/math",
	"kiso/path",
	"kiso/regexp",
	"kiso/regexp/unicode_data",
	"kiso/string",
	"kiso/utf8",
}

// Library restricts root (a Bunko root such as os.DirFS("bunko") or an embedded copy) to
// the regular, non-test .mio files of LibraryPackages. Everything else reads as missing.
func Library(root fs.FS) fs.FS { return library{root} }

type library struct{ root fs.FS }

func allowedPackage(dir string) bool {
	for _, name := range LibraryPackages {
		if dir == name {
			return true
		}
	}
	return false
}

func allowedFile(name string) bool {
	if !fs.ValidPath(name) || !strings.HasSuffix(name, ".mio") || strings.HasSuffix(name, "_test.mio") {
		return false
	}
	return allowedPackage(path.Dir(name))
}

func (l library) Open(name string) (fs.File, error) {
	if !allowedFile(name) {
		return nil, &fs.PathError{Op: "open", Path: name, Err: fs.ErrNotExist}
	}
	return l.root.Open(name)
}

func (l library) ReadFile(name string) ([]byte, error) {
	if !allowedFile(name) {
		return nil, &fs.PathError{Op: "read", Path: name, Err: fs.ErrNotExist}
	}
	return fs.ReadFile(l.root, name)
}

func (l library) ReadDir(name string) ([]fs.DirEntry, error) {
	if !fs.ValidPath(name) || !allowedPackage(name) {
		return nil, &fs.PathError{Op: "readdir", Path: name, Err: fs.ErrNotExist}
	}
	entries, err := fs.ReadDir(l.root, name)
	if err != nil {
		return nil, err
	}
	kept := entries[:0]
	for _, entry := range entries {
		if entry.Type().IsRegular() && allowedFile(path.Join(name, entry.Name())) {
			kept = append(kept, entry)
		}
	}
	if len(kept) == 0 {
		return nil, &fs.PathError{Op: "readdir", Path: name, Err: errors.New("no sources")}
	}
	return kept, nil
}
