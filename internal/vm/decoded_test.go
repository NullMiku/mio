package vm

import (
	"context"
	"errors"
	"reflect"
	"testing"

	"Mio/internal/code"
	"Mio/internal/compiler"
	"Mio/internal/value"
)

// Cached decoding must preserve byte offsets and one budget unit per Mochi
// instruction, including when a progress callback cancels a running loop.
func TestVMDecodedProgressAndCancellation(t *testing.T) {
	machine := New(&compiler.Bytecode{Instructions: code.Instructions{
		byte(code.OpTrue), byte(code.OpPop), byte(code.OpJump), 0, 0,
	}})
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	var count uint64
	var offsets []int
	err := machine.RunWithOptions(ExecutionOptions{
		Context: ctx, InstructionLimit: 20, InstructionCount: &count,
		ProgressInterval: 1, Progress: func(p ExecutionProgress) {
			offsets = append(offsets, p.Offset)
			if p.Instructions == 5 {
				cancel()
			}
		},
	})
	if !errors.Is(err, context.Canceled) || count != 5 || !reflect.DeepEqual(offsets, []int{0, 1, 2, 0, 1}) {
		t.Fatalf("err=%v count=%d offsets=%v", err, count, offsets)
	}
	// Reuse a cache after an interrupted execution with a different budget.
	err = machine.RunWithOptions(ExecutionOptions{InstructionLimit: 3, InstructionCount: &count})
	if err == nil || count != 3 {
		t.Fatalf("err=%v count=%d", err, count)
	}
}

func TestVMDecodedCacheFollowsProgram(t *testing.T) {
	machine := New(&compiler.Bytecode{Instructions: code.Instructions{byte(code.OpTrue), byte(code.OpPop)}})
	if err := machine.Run(); err != nil {
		t.Fatal(err)
	}
	machine.bytecode = &compiler.Bytecode{
		Instructions: code.Instructions{byte(code.OpConstant), 0, 0, byte(code.OpPop)},
		Constants:    []value.Value{value.NewInt(42)},
	}
	if err := machine.Run(); err != nil {
		t.Fatal(err)
	}
	if got, ok := machine.LastPoppedStackElem(); !ok || got != 42 {
		t.Fatalf("got %d present=%v", got, ok)
	}
}

func TestVMDecodedCacheDetectsInstructionEdits(t *testing.T) {
	program := &compiler.Bytecode{
		Instructions: code.Instructions{byte(code.OpCall), 0, 0, byte(code.OpPop)},
		Functions:    []compiler.CompiledFunction{{ID: 0, ReturnsValue: true, Instructions: code.Instructions{byte(code.OpConstant), 0, 0, byte(code.OpReturnValue)}}},
		Constants:    []value.Value{value.NewInt(11), value.NewInt(22)},
	}
	machine := New(program)
	for _, index := range []byte{0, 1, 0} {
		program.Functions[0].Instructions[2] = index
		if err := machine.Run(); err != nil {
			t.Fatal(err)
		}
		got, _ := machine.LastPoppedStackElem()
		want, _ := program.Constants[index].Int64()
		if got != want {
			t.Fatalf("got %d want %d", got, want)
		}
	}
	program.Instructions[0] = 255
	if err := machine.Run(); err == nil {
		t.Fatal("edited invalid opcode accepted")
	}
	program.Instructions[0] = byte(code.OpCall)
	if err := machine.Run(); err != nil {
		t.Fatal(err)
	}
}
