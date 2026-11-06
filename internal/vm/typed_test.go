package vm

import (
	"bytes"
	"strings"
	"testing"

	"Mio/internal/code"
	"Mio/internal/compiler"
)

func typedInstructions(t *testing.T, parts ...[]int) code.Instructions {
	t.Helper()
	var out code.Instructions
	for _, part := range parts {
		instruction, err := code.Make(code.Opcode(part[0]), part[1:]...)
		if err != nil {
			t.Fatal(err)
		}
		out = append(out, instruction...)
	}
	return out
}

// OpTypeConstraint leaves the value unchanged and OpCallTyped calls like OpCallValue.
func TestVMTypedCallAndConstraint(t *testing.T) {
	bytecode := &compiler.Bytecode{
		Instructions: typedInstructions(t,
			[]int{int(code.OpFunction), 0}, []int{int(code.OpTypeConstraint), 11},
			[]int{int(code.OpTrue)}, []int{int(code.OpTypeConstraint), 4},
			[]int{int(code.OpCallTyped), 1, 1}, []int{int(code.OpChant)},
			[]int{int(code.OpFunction), 1}, []int{int(code.OpCallTyped), 0, 0}),
		Functions: []compiler.CompiledFunction{
			{ID: 0, Name: "negate", ParameterCount: 1, LocalCount: 1, ReturnsValue: true, Instructions: typedInstructions(t,
				[]int{int(code.OpGetLocal), 0}, []int{int(code.OpNot)}, []int{int(code.OpReturnValue)})},
			{ID: 1, Name: "say", Instructions: typedInstructions(t,
				[]int{int(code.OpFalse)}, []int{int(code.OpChant)}, []int{int(code.OpReturn)})},
		},
	}
	var output bytes.Buffer
	if err := NewWithOutput(bytecode, &output).Run(); err != nil {
		t.Fatal(err)
	}
	if output.String() != "iie\niie\n" {
		t.Fatalf("output=%q", output.String())
	}
}

// A typed call whose result flag disagrees with the callee stops with a runtime error.
func TestVMTypedCallResultMismatch(t *testing.T) {
	bytecode := &compiler.Bytecode{
		Instructions: typedInstructions(t, []int{int(code.OpFunction), 0}, []int{int(code.OpCallTyped), 0, 0}),
		Functions: []compiler.CompiledFunction{{ID: 0, Name: "value", ReturnsValue: true, Instructions: typedInstructions(t,
			[]int{int(code.OpTrue)}, []int{int(code.OpReturnValue)})}},
	}
	err := New(bytecode).Run()
	if err == nil || !strings.Contains(err.Error(), "typed function value call result mismatch") {
		t.Fatalf("err=%v", err)
	}
}
