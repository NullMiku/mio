package main

import (
	"bytes"
	"debug/elf"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"

	"Mio/internal/code"
	"Mio/internal/compiler"
	"Mio/internal/mochi"
	"Mio/internal/stdlib"
	"Mio/internal/value"
	"Mio/internal/vm"
)

// sumProgram prints 20 + 22.
func sumProgram() *compiler.Bytecode {
	return &compiler.Bytecode{
		Constants: []value.Value{value.NewInt(20), value.NewInt(22)},
		Instructions: code.Instructions{
			byte(code.OpConstant), 0, 0,
			byte(code.OpConstant), 0, 1,
			byte(code.OpAdd),
			byte(code.OpChant),
		},
	}
}

func writeMochi(t *testing.T, program *compiler.Bytecode) string {
	t.Helper()
	input := filepath.Join(t.TempDir(), "program.mochi")
	f, err := os.Create(input)
	if err != nil {
		t.Fatal(err)
	}
	if err = mochi.Encode(f, program); err != nil {
		f.Close()
		t.Fatal(err)
	}
	if err = f.Close(); err != nil {
		t.Fatal(err)
	}
	return input
}

// Host independent: the ELF is only written and inspected, never executed.
func TestRunLinuxAMD64WritesELF(t *testing.T) {
	input := writeMochi(t, sumProgram())
	output := filepath.Join(t.TempDir(), "program")
	var stdout, stderr bytes.Buffer
	if status := run([]string{"-target", "linux-amd64", "-o", output, input}, &stdout, &stderr); status != 0 {
		t.Fatalf("status=%d stderr=%s", status, stderr.String())
	}
	if !strings.Contains(stdout.String(), "wrote "+output) || !strings.Contains(stdout.String(), "ELF64 x86-64") {
		t.Fatalf("unexpected stdout:\n%s", stdout.String())
	}
	if strings.Contains(stdout.String(), "codesign") {
		t.Fatalf("the macOS signing hint must not be printed for linux-amd64:\n%s", stdout.String())
	}
	content, err := os.ReadFile(output)
	if err != nil {
		t.Fatal(err)
	}
	if len(content) < 4 || !bytes.Equal(content[:4], []byte{0x7f, 'E', 'L', 'F'}) {
		t.Fatalf("output is not an ELF image: %x", content[:min(4, len(content))])
	}
	f, err := elf.NewFile(bytes.NewReader(content))
	if err != nil {
		t.Fatalf("output does not parse as ELF: %v", err)
	}
	defer f.Close()
	if f.Class != elf.ELFCLASS64 || f.Machine != elf.EM_X86_64 || f.Type != elf.ET_EXEC {
		t.Fatalf("unexpected ELF header: class=%v machine=%v type=%v", f.Class, f.Machine, f.Type)
	}
	info, err := os.Stat(output)
	if err != nil || info.Mode()&0o111 == 0 {
		t.Fatalf("output is not executable: info=%v err=%v", info, err)
	}
}

func TestRunLinuxAMD64RejectsM11GC(t *testing.T) {
	input := writeMochi(t, sumProgram())
	output := filepath.Join(t.TempDir(), "program")
	var stdout, stderr bytes.Buffer
	if status := run([]string{"-target", "linux-amd64", "-m11-gc", "-o", output, input}, &stdout, &stderr); status != 1 {
		t.Fatalf("status=%d stderr=%q", status, stderr.String())
	}
	if !strings.Contains(stderr.String(), "usage") {
		t.Fatalf("unexpected stderr: %s", stderr.String())
	}
	if _, err := os.Stat(output); err == nil {
		t.Fatal("no output file may be written when the options are rejected")
	}
}

func TestRunRejectsUnknownTarget(t *testing.T) {
	input := writeMochi(t, sumProgram())
	output := filepath.Join(t.TempDir(), "program")
	var stdout, stderr bytes.Buffer
	if status := run([]string{"-target", "windows-amd64", "-o", output, input}, &stdout, &stderr); status != 1 {
		t.Fatalf("status=%d stderr=%q", status, stderr.String())
	}
	if _, err := os.Stat(output); err == nil {
		t.Fatal("no output file may be written for an unknown target")
	}
}

// The default target and an explicit -target darwin-arm64 both still produce the Mach-O image.
func TestRunDefaultTargetStaysDarwinARM64(t *testing.T) {
	input := writeMochi(t, sumProgram())
	for _, args := range [][]string{nil, {"-target", "darwin-arm64"}} {
		output := filepath.Join(t.TempDir(), "program")
		var stdout, stderr bytes.Buffer
		if status := run(append(append([]string{}, args...), "-o", output, input), &stdout, &stderr); status != 0 {
			t.Fatalf("args=%v status=%d stderr=%s", args, status, stderr.String())
		}
		content, err := os.ReadFile(output)
		if err != nil {
			t.Fatal(err)
		}
		if len(content) < 4 || !bytes.Equal(content[:4], []byte{0xcf, 0xfa, 0xed, 0xfe}) {
			t.Fatalf("args=%v: output is not a Mach-O image: %x", args, content[:min(4, len(content))])
		}
		if !strings.Contains(stdout.String(), "unsigned Mach-O arm64") || !strings.Contains(stdout.String(), "codesign") {
			t.Fatalf("args=%v: darwin output text changed:\n%s", args, stdout.String())
		}
	}
}

// Linux x86-64 only: run the produced ELF and compare with the VM.
func TestRunLinuxAMD64ExecutableMatchesVM(t *testing.T) {
	if runtime.GOOS != "linux" || runtime.GOARCH != "amd64" {
		t.Skipf("SKIP: requires linux/amd64 to execute the ELF (host is %s/%s)", runtime.GOOS, runtime.GOARCH)
	}
	program := sumProgram()
	input := writeMochi(t, program)
	output := filepath.Join(t.TempDir(), "program")
	var stdout, stderr bytes.Buffer
	if status := run([]string{"-target", "linux-amd64", "-o", output, input}, &stdout, &stderr); status != 0 {
		t.Fatalf("status=%d stderr=%s", status, stderr.String())
	}
	native, err := exec.Command(output).CombinedOutput()
	if err != nil {
		t.Fatalf("native run failed: %v\n%s", err, native)
	}
	registry, err := stdlib.NewRegistry()
	if err != nil {
		t.Fatal(err)
	}
	var want bytes.Buffer
	machine := vm.NewWithRegistryAndOutput(program, registry, &want)
	if err := machine.RunWithOptions(vm.ExecutionOptions{InstructionLimit: 1_000_000}); err != nil {
		t.Fatal(err)
	}
	if v, ok := machine.LastPoppedValue(); ok {
		if err := value.WriteLine(&want, v); err != nil {
			t.Fatal(err)
		}
	}
	if string(native) != "42\n" || !bytes.Equal(native, want.Bytes()) {
		t.Fatalf("native output %q, VM output %q, want \"42\\n\"", native, want.Bytes())
	}
}
