package aot

import (
	"bytes"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"

	"Mio/internal/compiler"
)

func isLinuxAMD64() bool { return runtime.GOOS == "linux" && runtime.GOARCH == "amd64" }

// isAllowedLinuxNotImplemented is the allowlist of features the Linux backend knowingly does not
// support yet: native file-system imports. Any other "not implemented" compile error is returned
// to the caller and fails the test, so a regression cannot hide behind a SKIP.
func isAllowedLinuxNotImplemented(err error) bool {
	msg := err.Error()
	return strings.Contains(msg, "native file-system import") && strings.Contains(msg, "is not implemented yet")
}

// runLinuxAMD64Differential compiles with the Linux backend and executes the
// ELF natively. Only an allowlisted "not implemented yet" error (native file-system
// imports) turns the test into a SKIP with the reason (never a PASS); every other
// compile or runtime failure is returned to the caller and fails the test.
func runLinuxAMD64Differential(t *testing.T, program *compiler.Bytecode) ([]byte, error) {
	t.Helper()
	return runLinuxAMD64Options(t, program, LinuxAMD64Options{})
}

func runLinuxAMD64Options(t *testing.T, program *compiler.Bytecode, opts LinuxAMD64Options) ([]byte, error) {
	t.Helper()
	image, err := CompileLinuxAMD64WithOptions(program, opts)
	if err != nil {
		if isAllowedLinuxNotImplemented(err) {
			t.Skipf("NOT-IMPLEMENTED linux-amd64: %v", err)
		}
		return nil, err
	}
	if dump := os.Getenv("MIO_DUMP_IMAGE"); dump != "" {
		_ = os.WriteFile(dump, image, 0o755)
	}
	path := filepath.Join(t.TempDir(), "native")
	if err := os.WriteFile(path, image, 0o755); err != nil {
		return nil, err
	}
	var out bytes.Buffer
	cmd := exec.Command(path)
	cmd.Stdout, cmd.Stderr = &out, &out
	err = cmd.Run()
	return out.Bytes(), err
}
