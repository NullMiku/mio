package aot

import (
	"bytes"
	"debug/elf"
	"fmt"
	"math"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"testing"

	"Mio/internal/code"
	"Mio/internal/compiler"
	"Mio/internal/value"
)

func runLinuxAMD64(t *testing.T, p *compiler.Bytecode) (string, int) {
	t.Helper()
	image, err := CompileLinuxAMD64(p)
	if err != nil {
		t.Fatal(err)
	}
	f, err := elf.NewFile(bytes.NewReader(image))
	if err != nil {
		t.Fatalf("not a valid ELF: %v", err)
	}
	if f.Machine != elf.EM_X86_64 || f.Class != elf.ELFCLASS64 || f.Type != elf.ET_EXEC {
		t.Fatalf("unexpected ELF header %v %v %v", f.Machine, f.Class, f.Type)
	}
	f.Close()
	if runtime.GOOS != "linux" || runtime.GOARCH != "amd64" {
		t.Skip("requires Linux x86_64 to execute")
	}
	path := filepath.Join(t.TempDir(), "prog")
	if err := os.WriteFile(path, image, 0o755); err != nil {
		t.Fatal(err)
	}
	var out bytes.Buffer
	cmd := exec.Command(path)
	cmd.Stdout = &out
	err = cmd.Run()
	status := 0
	if ee, ok := err.(*exec.ExitError); ok {
		status = ee.ExitCode()
	} else if err != nil {
		t.Fatal(err)
	}
	return out.String(), status
}

func ints(v ...int64) []value.Value {
	r := make([]value.Value, len(v))
	for i, n := range v {
		r[i] = value.NewInt(n)
	}
	return r
}

func TestLinuxAMD64ExitAndEmpty(t *testing.T) {
	out, st := runLinuxAMD64(t, &compiler.Bytecode{})
	if out != "" || st != 0 {
		t.Fatalf("got %q status %d", out, st)
	}
}

func TestLinuxAMD64ArithmeticAndBool(t *testing.T) {
	a := newM3TestAsm()
	for _, c := range []int{0, 1} {
		a.emit(code.OpConstant, c)
		a.emit(code.OpChant)
	}
	a.emit(code.OpConstant, 2) // 7
	a.emit(code.OpConstant, 3) // 5
	a.emit(code.OpSub)
	a.emit(code.OpConstant, 4) // -3
	a.emit(code.OpMul)
	a.emit(code.OpChant) // -6
	a.emit(code.OpConstant, 5)
	a.emit(code.OpConstant, 6)
	a.emit(code.OpAdd) // wraps
	a.emit(code.OpChant)
	a.emit(code.OpConstant, 5)
	a.emit(code.OpNeg)
	a.emit(code.OpChant)
	a.emit(code.OpConstant, 7) // MinInt64
	a.emit(code.OpChant)
	a.emit(code.OpConstant, 2)
	a.emit(code.OpConstant, 3)
	a.emit(code.OpGreater)
	a.emit(code.OpChant)
	a.emit(code.OpConstant, 2)
	a.emit(code.OpConstant, 3)
	a.emit(code.OpLessEqual)
	a.emit(code.OpNot)
	a.emit(code.OpChant)
	a.emit(code.OpConstant, 2)
	a.emit(code.OpPop) // trailing value is printed at exit
	p := &compiler.Bytecode{Constants: ints(0, 123456789, 7, 5, -3, math.MaxInt64, 1, math.MinInt64), Instructions: a.build()}
	out, st := runLinuxAMD64(t, p)
	want := "0\n123456789\n-6\n-9223372036854775808\n-9223372036854775807\n-9223372036854775808\nhai\nhai\n7\n"
	if out != want || st != 0 {
		t.Fatalf("got %q status %d, want %q", out, st, want)
	}
}

func TestLinuxAMD64LoopAndGlobals(t *testing.T) {
	a := newM3TestAsm()
	a.emit(code.OpConstant, 0)
	a.emit(code.OpSetGlobal, 0)
	a.label("head")
	a.emit(code.OpGetGlobal, 0)
	a.emit(code.OpConstant, 1)
	a.emit(code.OpLess)
	a.jump(code.OpJumpIfFalse, "done")
	a.emit(code.OpGetGlobal, 0)
	a.emit(code.OpConstant, 2)
	a.emit(code.OpAdd)
	a.emit(code.OpSetGlobal, 0)
	a.jump(code.OpJump, "head")
	a.label("done")
	a.emit(code.OpGetGlobal, 0)
	a.emit(code.OpChant)
	a.emit(code.OpGetGlobal, 0)
	a.emit(code.OpConstant, 1)
	a.emit(code.OpEqual)
	a.emit(code.OpChant)
	p := &compiler.Bytecode{GlobalsCount: 1, Constants: ints(0, 1000000, 1), Instructions: a.build()}
	out, _ := runLinuxAMD64(t, p)
	if out != "1000000\nhai\n" {
		t.Fatalf("got %q", out)
	}
}

// fib(n) = n<2 ? n : fib(n-1)+fib(n-2); params/locals in native frames.
func fibProgram(n int64) *compiler.Bytecode {
	f := newM3TestAsm()
	f.emit(code.OpGetLocal, 0)
	f.emit(code.OpConstant, 1)
	f.emit(code.OpLess)
	f.jump(code.OpJumpIfFalse, "rec")
	f.emit(code.OpGetLocal, 0)
	f.emit(code.OpReturnValue)
	f.label("rec")
	f.emit(code.OpGetLocal, 0)
	f.emit(code.OpConstant, 2)
	f.emit(code.OpSub)
	f.emit(code.OpCall, 0)
	f.emit(code.OpGetLocal, 0)
	f.emit(code.OpConstant, 1)
	f.emit(code.OpSub)
	f.emit(code.OpCall, 0)
	f.emit(code.OpAdd)
	f.emit(code.OpReturnValue)
	m := newM3TestAsm()
	m.emit(code.OpConstant, 3)
	m.emit(code.OpCall, 0)
	m.emit(code.OpChant)
	return &compiler.Bytecode{
		Constants:    ints(0, 2, 1, n),
		Functions:    []compiler.CompiledFunction{{ID: 0, Name: "fib", ParameterCount: 1, LocalCount: 1, ReturnsValue: true, Instructions: f.build()}},
		Instructions: m.build(),
	}
}

func TestLinuxAMD64RecursionAndABI(t *testing.T) {
	out, st := runLinuxAMD64(t, fibProgram(27))
	if out != "196418\n" || st != 0 {
		t.Fatalf("got %q status %d", out, st)
	}
}

func TestLinuxAMD64MultiArgOrderAndUnitReturn(t *testing.T) {
	// sub3(a,b,c)=a-b*c ; unit function prints its arg.
	f := newM3TestAsm()
	f.emit(code.OpGetLocal, 0)
	f.emit(code.OpGetLocal, 1)
	f.emit(code.OpGetLocal, 2)
	f.emit(code.OpMul)
	f.emit(code.OpSub)
	f.emit(code.OpReturnValue)
	g := newM3TestAsm()
	g.emit(code.OpGetLocal, 0)
	g.emit(code.OpChant)
	g.emit(code.OpReturn)
	m := newM3TestAsm()
	m.emit(code.OpConstant, 0)
	m.emit(code.OpConstant, 1)
	m.emit(code.OpConstant, 2)
	m.emit(code.OpCall, 0)
	m.emit(code.OpCall, 1)
	m.emit(code.OpConstant, 3)
	m.emit(code.OpChant)
	p := &compiler.Bytecode{
		Constants: ints(100, 6, 7, 9),
		Functions: []compiler.CompiledFunction{
			{ID: 0, Name: "sub3", ParameterCount: 3, LocalCount: 3, ReturnsValue: true, Instructions: f.build()},
			{ID: 1, Name: "show", ParameterCount: 1, LocalCount: 1, Instructions: g.build()},
		},
		Instructions: m.build(),
	}
	out, _ := runLinuxAMD64(t, p)
	if out != "58\n9\n" {
		t.Fatalf("got %q", out)
	}
}

func TestLinuxAMD64CallDepthGuardExitsOne(t *testing.T) {
	f := newM3TestAsm()
	f.emit(code.OpGetLocal, 0)
	f.emit(code.OpCall, 0)
	f.emit(code.OpReturnValue)
	m := newM3TestAsm()
	m.emit(code.OpConstant, 0)
	m.emit(code.OpCall, 0)
	m.emit(code.OpChant)
	p := &compiler.Bytecode{Constants: ints(1),
		Functions:    []compiler.CompiledFunction{{ID: 0, Name: "inf", ParameterCount: 1, LocalCount: 1, ReturnsValue: true, Instructions: f.build()}},
		Instructions: m.build()}
	out, st := runLinuxAMD64(t, p)
	if out != "" || st != 1 {
		t.Fatalf("got %q status %d, want empty/1", out, st)
	}
}

func TestLinuxAMD64UnsupportedFailsExplicitly(t *testing.T) {
	// Arrays need the (not yet ported) heap runtime: must fail loudly, never fall back to the VM.
	p := &compiler.Bytecode{Constants: ints(1),
		Instructions: code.Instructions{byte(code.OpConstant), 0, 0, byte(code.OpArray), 1, 0, byte(code.OpPop)}}
	if _, err := CompileLinuxAMD64(p); err == nil {
		t.Fatal("array programs must be rejected explicitly until implemented")
	}
}

func TestLinuxAMD64StringLenAndCompareBytecode(t *testing.T) {
	a := newM3TestAsm()
	for _, c := range []int{0, 1, 2} {
		a.emit(code.OpConstant, c)
		a.emit(code.OpLen)
		a.emit(code.OpChant)
	}
	a.emit(code.OpConstant, 0)
	a.emit(code.OpConstant, 0)
	a.emit(code.OpEqual)
	a.emit(code.OpChant)
	a.emit(code.OpConstant, 0)
	a.emit(code.OpConstant, 1)
	a.emit(code.OpNotEqual)
	a.emit(code.OpChant)
	a.emit(code.OpConstant, 3) // same content as constant 0 but a distinct pool entry
	a.emit(code.OpConstant, 0)
	a.emit(code.OpEqual)
	a.emit(code.OpChant)
	p := &compiler.Bytecode{Constants: []value.Value{value.NewString("hello"), value.NewString("猫🙂"), value.NewString(""), value.NewString("hello")}, Instructions: a.build()}
	requireM12Differential(t, p)
}

// binaryOp builds `chant(a OP b)` for each pair using typed constants; the VM is the oracle.
func TestLinuxAMD64FixedWidthIntegerDifferential(t *testing.T) {
	type tc struct {
		a, b value.Value
	}
	cases := []tc{
		{value.NewInt8(100), value.NewInt8(27)}, {value.NewInt8(-128), value.NewInt8(-1)}, {value.NewInt8(127), value.NewInt8(2)},
		{value.NewInt16(30000), value.NewInt16(30000)}, {value.NewInt16(-32768), value.NewInt16(3)},
		{value.NewInt32(2147483647), value.NewInt32(2)}, {value.NewInt32(-2147483648), value.NewInt32(-1)},
		{value.NewUint8(200), value.NewUint8(100)}, {value.NewUint8(3), value.NewUint8(7)},
		{value.NewUint16(65535), value.NewUint16(65535)},
		{value.NewUint32(4000000000), value.NewUint32(3)}, {value.NewUint32(4000000000), value.NewUint32(4000000000)},
		{value.NewInt(math.MaxInt64), value.NewInt(2)}, {value.NewInt(math.MinInt64), value.NewInt(-1)},
		{value.NewInt(-7), value.NewInt(2)}, {value.NewInt(7), value.NewInt(-2)},
	}
	for ci, c := range cases {
		for _, op := range []code.Opcode{code.OpAdd, code.OpSub, code.OpMul, code.OpDiv,
			code.OpLess, code.OpLessEqual, code.OpGreater, code.OpGreaterEqual, code.OpEqual, code.OpNotEqual} {
			a := newM3TestAsm()
			a.emit(code.OpConstant, 0)
			a.emit(code.OpConstant, 1)
			a.emit(op)
			a.emit(code.OpChant)
			switch c.a.Kind() {
			case value.KindUint8, value.KindUint16, value.KindUint32: // VM rejects negating unsigned values
			default:
				a.emit(code.OpConstant, 0)
				a.emit(code.OpNeg)
				a.emit(code.OpChant)
			}
			p := &compiler.Bytecode{Constants: []value.Value{c.a, c.b}, Instructions: a.build()}
			t.Run(fmt.Sprintf("case%d/op%d", ci, op), func(t *testing.T) {
				requireM12Differential(t, p)
			})
		}
	}
}

func TestLinuxAMD64CheckedFailuresExitOne(t *testing.T) {
	type tc struct {
		name   string
		consts []value.Value
		build  func(a *m3TestAssembler)
	}
	cases := []tc{
		{"int-div-by-zero", ints(1, 0), func(a *m3TestAssembler) {
			a.emit(code.OpConstant, 0)
			a.emit(code.OpConstant, 1)
			a.emit(code.OpDiv)
		}},
		{"nan-to-int", []value.Value{value.NewFloat(math.NaN())}, func(a *m3TestAssembler) {
			a.emit(code.OpConstant, 0)
			a.emit(code.OpFloatToInt)
		}},
		{"inf-to-int", []value.Value{value.NewFloat(math.Inf(1))}, func(a *m3TestAssembler) {
			a.emit(code.OpConstant, 0)
			a.emit(code.OpFloatToInt)
		}},
		{"2^63-to-int", []value.Value{value.NewFloat(0x1p63)}, func(a *m3TestAssembler) {
			a.emit(code.OpConstant, 0)
			a.emit(code.OpFloatToInt)
		}},
		{"int-to-uint8-range", ints(256), func(a *m3TestAssembler) {
			a.emit(code.OpConstant, 0)
			a.emit(code.OpIntegerConvert, code.IntegerUint8)
		}},
		{"negative-to-uint32", ints(-1), func(a *m3TestAssembler) {
			a.emit(code.OpConstant, 0)
			a.emit(code.OpIntegerConvert, code.IntegerUint32)
		}},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			a := newM3TestAsm()
			a.emit(code.OpConstant, 0)
			a.emit(code.OpChant) // proves execution started: printed before the failure
			c.build(a)
			a.emit(code.OpChant)
			consts := append([]value.Value{}, c.consts...)
			p := &compiler.Bytecode{Constants: consts, Instructions: a.build()}
			out, st := runLinuxAMD64(t, p)
			if st != 1 {
				t.Fatalf("exit status %d (output %q), want 1", st, out)
			}
		})
	}
	// Valid edge: -2^63 converts, truncation toward zero.
	a := newM3TestAsm()
	a.emit(code.OpConstant, 0)
	a.emit(code.OpFloatToInt)
	a.emit(code.OpChant)
	a.emit(code.OpConstant, 1)
	a.emit(code.OpFloatToInt)
	a.emit(code.OpChant)
	out, st := runLinuxAMD64(t, &compiler.Bytecode{Constants: []value.Value{value.NewFloat(-0x1p63), value.NewFloat(-2.9)}, Instructions: a.build()})
	if st != 0 || out != "-9223372036854775808\n-2\n" {
		t.Fatalf("got %q status %d", out, st)
	}
}
