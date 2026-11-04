package aot

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"testing"
	"time"

	"Mio/internal/stdlib"
	"Mio/internal/vm"
)

// irWord packs up to 8 ASCII bytes little-endian: the 64-bit word the IR stores to build a message.
// Longer strings would silently lose their tail, so they are rejected.
func irWord(s string) int64 {
	if len(s) > 8 {
		panic("irWord: more than 8 bytes cannot be packed into one 64-bit IR constant: " + strconv.Quote(s))
	}
	var w uint64
	for i := 0; i < len(s); i++ {
		w |= uint64(s[i]) << (8 * i)
	}
	return int64(w)
}

// The whole Linux x86-64 runtime chain is pure Mio: IR -> kiso/runtime/cpu/amd64
// -> kiso/aot/x86_64 -> kiso/aot/elf, with OS services from kiso/runtime/os/linux.
// This test runs that builder in the Mochi VM, writes the produced ELF and
// executes it natively; no Go code generates any machine code here.
func TestLinuxAMD64PureMioRuntimeChainExecutesNatively(t *testing.T) {
	if runtime.GOOS != "linux" || runtime.GOARCH != "amd64" {
		t.Skip("requires Linux x86_64")
	}
	root, err := filepath.Abs(filepath.Join("..", ".."))
	if err != nil {
		t.Fatal(err)
	}
	messages := []string{"hello\n", "sum\n", "clock\n", "memory\n", "futex\n", "divide\n", "args7\n", "atomic\n", "rules\n", "done\n"}
	var say strings.Builder
	for _, m := range messages {
		name := strings.TrimSuffix(m, "\n")
		fmt.Fprintf(&say, `
kaku say_%[1]s = ir.function("say_%[1]s");
ir.put(say_%[1]s, ir.scratch_address, 1, 0, 0, 0); ir.put(say_%[1]s, ir.constant, 2, 0, 0, %[2]d);
ir.put(say_%[1]s, ir.store, 0, 1, 2, 0); ir.put(say_%[1]s, ir.constant, 3, 0, 0, %[3]d);
ir.call(say_%[1]s, 103, 4, [1, 3]); ir.put(say_%[1]s, ir.result, 0, 4, 0, 0);
array.push(functions, say_%[1]s);
`, name, irWord(m), len(m))
	}
	source := `yobu "kiso/runtime/ir";
yobu "kiso/runtime/os/linux";
yobu "kiso/runtime/gc";
yobu "kiso/array";
yobu "kiso/fs";
kaku functions = linux.platform_program();
` + say.String() + `
// weighted(a0..a6) = a0 + 10*a1 + 100*a2 + ... exercises all seven argument registers.
kaku weighted = ir.function("weighted");
kaku w = 1; kaku wi = 0; kaku acc = 7;
ir.put(weighted, ir.constant, acc, 0, 0, 0);
aida (wi < 7) {
  ir.put(weighted, ir.constant, 10, 0, 0, w); ir.put(weighted, ir.multiply, 11, wi, 10, 0); ir.put(weighted, ir.add, acc, acc, 11, 0);
  w = w * 10; wi = wi + 1;
}
ir.put(weighted, ir.result, 0, acc, 0, 0);
array.push(functions, weighted);

kaku main = ir.function("main");
waza fail(f: ir.Function, code: int64, label: string) -> unit {
  ir.branch(f, ir.label, 0, label); ir.put(f, ir.constant, 30, 0, 0, code); ir.put(f, ir.result, 0, 30, 0, 0);
}
ir.invoke_function(main, "say_hello", 1, []);
// ---- sum 1..100 with a counted loop
ir.put(main, ir.constant, 1, 0, 0, 0); ir.put(main, ir.constant, 2, 0, 0, 1); ir.put(main, ir.constant, 3, 0, 0, 101); ir.put(main, ir.constant, 5, 0, 0, 1);
ir.branch(main, ir.label, 0, "loop"); ir.put(main, ir.less_unsigned, 4, 2, 3, 0); ir.branch(main, ir.zero, 4, "loop_done");
ir.put(main, ir.add, 1, 1, 2, 0); ir.put(main, ir.add, 2, 2, 5, 0); ir.branch(main, ir.jump, 0, "loop");
ir.branch(main, ir.label, 0, "loop_done"); ir.put(main, ir.constant, 6, 0, 0, 5050); ir.put(main, ir.equal, 7, 1, 6, 0); ir.branch(main, ir.zero, 7, "fail_sum");
ir.invoke_function(main, "say_sum", 8, []);
// ---- monotonic clock never goes backwards and is non-zero
ir.invoke_function(main, "platform_now", 9, []); ir.invoke_function(main, "platform_now", 10, []);
ir.put(main, ir.less_unsigned, 11, 10, 9, 0); ir.branch(main, ir.nonzero, 11, "fail_clock"); ir.branch(main, ir.zero, 9, "fail_clock");
ir.invoke_function(main, "say_clock", 8, []);
// ---- virtual memory: reserve, commit, write/read, decommit (reads zero), release
ir.put(main, ir.constant, 12, 0, 0, 1048576); ir.invoke_function(main, "platform_reserve", 13, [12]);
ir.put(main, ir.constant, 14, 0, 0, -4096); ir.put(main, ir.less_unsigned, 15, 13, 14, 0); ir.branch(main, ir.zero, 15, "fail_memory");
ir.invoke_function(main, "platform_commit", 16, [13, 12]); ir.branch(main, ir.nonzero, 16, "fail_memory");
ir.put(main, ir.constant, 17, 0, 0, 11259375); ir.put(main, ir.store, 0, 13, 17, 4096); ir.put(main, ir.load, 18, 13, 0, 4096);
ir.put(main, ir.equal, 19, 17, 18, 0); ir.branch(main, ir.zero, 19, "fail_memory");
ir.invoke_function(main, "platform_decommit", 16, [13, 12]); ir.branch(main, ir.nonzero, 16, "fail_memory");
ir.invoke_function(main, "platform_commit", 16, [13, 12]); ir.branch(main, ir.nonzero, 16, "fail_memory");
ir.put(main, ir.load, 18, 13, 0, 4096); ir.branch(main, ir.nonzero, 18, "fail_memory");
ir.invoke_function(main, "platform_release", 16, [13, 12]); ir.branch(main, ir.nonzero, 16, "fail_memory");
ir.invoke_function(main, "say_memory", 8, []);
// ---- futex: changed value returns at once (0); unchanged value times out (1) after >= 20 ms
ir.put(main, ir.scratch_address, 20, 0, 0, 8); ir.put(main, ir.constant, 21, 0, 0, 5); ir.put(main, ir.store, 0, 20, 21, 0);
ir.put(main, ir.constant, 22, 0, 0, 6); ir.put(main, ir.constant, 23, 0, 0, 20000000);
ir.invoke_function(main, "platform_futex_wait", 24, [20, 22, 23]); ir.branch(main, ir.nonzero, 24, "fail_futex");
ir.invoke_function(main, "platform_now", 9, []);
ir.invoke_function(main, "platform_futex_wait", 24, [20, 21, 23]); ir.put(main, ir.constant, 25, 0, 0, 1); ir.put(main, ir.equal, 26, 24, 25, 0); ir.branch(main, ir.zero, 26, "fail_futex");
ir.invoke_function(main, "platform_now", 10, []); ir.put(main, ir.subtract, 27, 10, 9, 0); ir.put(main, ir.less_unsigned, 28, 27, 23, 0); ir.branch(main, ir.nonzero, 28, "fail_futex");
ir.invoke_function(main, "say_futex", 8, []);
// ---- unsigned divide: 100/7 = 14, divide by zero yields 0 (same as AArch64 UDIV)
ir.put(main, ir.constant, 1, 0, 0, 100); ir.put(main, ir.constant, 2, 0, 0, 7); ir.put(main, ir.constant, 3, 0, 0, 0);
ir.put(main, ir.divide_unsigned, 4, 1, 2, 0); ir.put(main, ir.constant, 5, 0, 0, 14); ir.put(main, ir.equal, 6, 4, 5, 0); ir.branch(main, ir.zero, 6, "fail_divide");
ir.put(main, ir.divide_unsigned, 4, 1, 3, 0); ir.branch(main, ir.nonzero, 4, "fail_divide");
ir.invoke_function(main, "say_divide", 8, []);
// ---- seven-argument call (7th argument travels in r10)
kaku ai = 0; kaku args: []int64 = [];
aida (ai < 7) { ir.put(main, ir.constant, 10 + ai, 0, 0, ai + 1); array.push(args, 10 + ai); ai = ai + 1; }
ir.invoke_function(main, "weighted", 1, args); ir.put(main, ir.constant, 2, 0, 0, 7654321); ir.put(main, ir.equal, 3, 1, 2, 0); ir.branch(main, ir.zero, 3, "fail_args");
ir.invoke_function(main, "say_args7", 8, []);
// ---- atomics: fetch_add returns the old value; CAS returns the observed value and stores only on match
ir.put(main, ir.scratch_address, 20, 0, 0, 16); ir.put(main, ir.constant, 21, 0, 0, 10); ir.put(main, ir.store, 0, 20, 21, 0);
ir.put(main, ir.constant, 22, 0, 0, 5);
array.push(main.steps, ir.Step { kind: ir.fetch_add, destination: 23, left: 20, right: 22, immediate: 0, name: "", arguments: [], order: gc.seq_cst, failure_order: gc.relaxed });
ir.put(main, ir.equal, 24, 23, 21, 0); ir.branch(main, ir.zero, 24, "fail_atomic");
ir.put(main, ir.constant, 25, 0, 0, 99); ir.put(main, ir.constant, 26, 0, 0, 15);
array.push(main.steps, ir.Step { kind: ir.compare_exchange, destination: 27, left: 20, right: 25, immediate: 0, name: "", arguments: [26], order: gc.seq_cst, failure_order: gc.relaxed });
ir.put(main, ir.equal, 28, 27, 26, 0); ir.branch(main, ir.zero, 28, "fail_atomic");
ir.put(main, ir.load, 29, 20, 0, 0); ir.put(main, ir.equal, 28, 29, 25, 0); ir.branch(main, ir.zero, 28, "fail_atomic");
ir.put(main, ir.constant, 31, 0, 0, 7);
array.push(main.steps, ir.Step { kind: ir.compare_exchange, destination: 27, left: 20, right: 21, immediate: 0, name: "", arguments: [31], order: gc.seq_cst, failure_order: gc.relaxed });
ir.put(main, ir.equal, 28, 27, 25, 0); ir.branch(main, ir.zero, 28, "fail_atomic");
ir.put(main, ir.load, 29, 20, 0, 0); ir.put(main, ir.equal, 28, 29, 25, 0); ir.branch(main, ir.zero, 28, "fail_atomic");
ir.invoke_function(main, "say_atomic", 8, []);
// ---- platform contracts (futex word width, zero timeout, wake with no waiter, errno results)
ir.put(main, ir.scratch_address, 1, 0, 0, 24);
ir.put(main, ir.constant, 2, 0, 0, 5); ir.put(main, ir.store, 0, 1, 2, 0); ir.put(main, ir.constant, 3, 0, 0, 0); ir.put(main, ir.constant, 5, 0, 0, 1);
// a zero timeout on a matching word returns "timed out" (1) at once: it never waits forever
ir.invoke_function(main, "platform_futex_wait", 4, [1, 2, 3]); ir.put(main, ir.equal, 6, 4, 5, 0); ir.branch(main, ir.zero, 6, "fail_contract");
// only the low 32 bits are compared: word 2^32+5 still matches expected 5 ...
ir.put(main, ir.constant, 7, 0, 0, 4294967301); ir.put(main, ir.store, 0, 1, 7, 0);
ir.invoke_function(main, "platform_futex_wait", 4, [1, 2, 3]); ir.put(main, ir.equal, 6, 4, 5, 0); ir.branch(main, ir.zero, 6, "fail_contract");
// ... and expected 2^32+5 matches word 5
ir.put(main, ir.store, 0, 1, 2, 0);
ir.invoke_function(main, "platform_futex_wait", 4, [1, 7, 3]); ir.put(main, ir.equal, 6, 4, 5, 0); ir.branch(main, ir.zero, 6, "fail_contract");
// a different low half is "value changed" (0) although the high halves are equal
ir.put(main, ir.constant, 8, 0, 0, 4294967302);
ir.invoke_function(main, "platform_futex_wait", 4, [1, 8, 3]); ir.branch(main, ir.nonzero, 4, "fail_contract");
// waking with nobody waiting wakes zero waiters (and is not an error)
ir.invoke_function(main, "platform_futex_wake_all", 4, [1]); ir.branch(main, ir.nonzero, 4, "fail_contract");
ir.put(main, ir.constant, 9, 0, 0, 1); ir.invoke_function(main, "platform_futex_wake", 4, [1, 9]); ir.branch(main, ir.nonzero, 4, "fail_contract");
// platform_reserve with an absurd length fails with a negated errno, never with an address
ir.put(main, ir.constant, 10, 0, 0, 4611686018427387904); ir.invoke_function(main, "platform_reserve", 11, [10]);
ir.put(main, ir.constant, 12, 0, 0, -4095); ir.put(main, ir.less_unsigned, 13, 11, 12, 0); ir.branch(main, ir.nonzero, 13, "fail_contract");
// platform_release of an unaligned address is -EINVAL (-22)
ir.put(main, ir.constant, 14, 0, 0, 1); ir.put(main, ir.constant, 15, 0, 0, 4096); ir.invoke_function(main, "platform_release", 16, [14, 15]);
ir.put(main, ir.constant, 17, 0, 0, -22); ir.put(main, ir.equal, 18, 16, 17, 0); ir.branch(main, ir.zero, 18, "fail_contract");
ir.invoke_function(main, "say_rules", 8, []);
ir.invoke_function(main, "say_done", 8, []);
ir.put(main, ir.constant, 30, 0, 0, 0); ir.put(main, ir.result, 0, 30, 0, 0);
fail(main, 11, "fail_sum"); fail(main, 12, "fail_clock"); fail(main, 13, "fail_memory"); fail(main, 14, "fail_futex");
fail(main, 15, "fail_divide"); fail(main, 16, "fail_args"); fail(main, 17, "fail_atomic"); fail(main, 18, "fail_contract");
array.push(functions, main);
kaku image = linux.executable(functions, linux.bindings(), "main", 0);
moshi (image.error != "") { chant(image.error); }
sore { kaku written = fs.write_all(OUTPUT, image.bytes); moshi (written.error != mu) { chant("write failed"); } sore { chant(len(image.bytes)); } }
`
	out := filepath.Join(t.TempDir(), "puremio.elf")
	source = strings.Replace(source, "OUTPUT", fmt.Sprintf("%q", out), 1)
	program := m17CompileMio(t, root, source)
	registry, err := stdlib.NewRegistry()
	if err != nil {
		t.Fatal(err)
	}
	var log bytes.Buffer
	machine := vm.NewWithRegistryAndOutput(program, registry, &log)
	buildStart := time.Now()
	if err := machine.RunWithOptions(vm.ExecutionOptions{InstructionLimit: 2_000_000_000}); err != nil {
		t.Fatalf("builder failed: %v (output %q)", err, log.String())
	}
	buildTime := time.Since(buildStart)
	// The builder prints the image size on success and an error name on failure.
	size, convErr := strconv.Atoi(strings.TrimSpace(log.String()))
	if convErr != nil || size <= 0 {
		t.Fatalf("builder did not report an image size: %q", log.String())
	}
	info, err := os.Stat(out)
	if err != nil {
		t.Fatalf("no image written: builder said %q", log.String())
	}
	if info.Size() != int64(size) {
		t.Fatalf("image file is %d bytes but the builder reported %d", info.Size(), size)
	}
	if err := os.Chmod(out, 0o755); err != nil {
		t.Fatal(err)
	}
	// The futex section sleeps for 20 ms; anything beyond a few seconds is a hang.
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, out)
	var stdout bytes.Buffer
	cmd.Stdout = &stdout
	runStart := time.Now()
	err = cmd.Run()
	runTime := time.Since(runStart)
	if errors.Is(ctx.Err(), context.DeadlineExceeded) {
		t.Fatalf("native image did not finish within 30s (output so far %q)", stdout.String())
	}
	want := strings.Join(messages, "")
	if err != nil || stdout.String() != want {
		t.Fatalf("native run: err=%v stdout=%q want %q", err, stdout.String(), want)
	}
	t.Logf("image %d bytes; building it in the Mochi VM took %v, running it natively %v", size, buildTime.Round(time.Millisecond), runTime.Round(time.Millisecond))
}
