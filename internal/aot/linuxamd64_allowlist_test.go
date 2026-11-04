package aot

import (
	"errors"
	"testing"
)

func TestLinuxNotImplementedAllowlistIsNarrow(t *testing.T) {
	allowed := errors.New(`linux-amd64: native file-system import "$mma::mio/fs/runtime::open::test" is not implemented yet`)
	if !isAllowedLinuxNotImplemented(allowed) {
		t.Fatal("native file-system imports must be skippable")
	}
	for _, msg := range []string{
		"linux-amd64: closures are not implemented yet",
		"linux-amd64: dynamic strings not yet implemented",
		"linux-amd64: unsupported opcode OpFoo at byte offset 3",
		"linux-amd64: native file-system import",
	} {
		if isAllowedLinuxNotImplemented(errors.New(msg)) {
			t.Errorf("%q must fail the test, not skip it", msg)
		}
	}
}
