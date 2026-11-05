package aot

import (
	"fmt"

	"Mio/internal/aot/linuxamd64"
	"Mio/internal/code"
	"Mio/internal/compiler"
	"Mio/internal/mochi"
	"Mio/internal/value"
)

// CompileLinuxAMD64 compiles validated Mochi bytecode to a Linux x86_64
// ELF64 executable. Unsupported programs fail explicitly (no VM fallback).
// Current slice: int64/bool, globals, control flow, native functions.
func CompileLinuxAMD64(program *compiler.Bytecode) ([]byte, error) {
	return CompileLinuxAMD64WithOptions(program, LinuxAMD64Options{})
}

// LinuxAMD64Options mirrors DarwinARM64Options. HeapCapacity is the managed
// heap size in bytes (default 1 MiB, hard limit 1 GiB). GCStress collects
// before every allocation.
type LinuxAMD64Options struct {
	HeapCapacity uint64
	GCStress     bool
	// LegacyStackMaps selects the old return-address stack-map root mode. It is a
	// comparison baseline for the migration to the shadow-frame contract only.
	LegacyStackMaps bool
	// RootMutation breaks the root protocol on purpose (mutation tests only).
	RootMutation string
	// HeapDumpPath makes the program write its ABI v1 heap image at exit (structural tests).
	HeapDumpPath string
}

func CompileLinuxAMD64WithOptions(program *compiler.Bytecode, opts LinuxAMD64Options) ([]byte, error) {
	if opts.HeapCapacity > 1<<30 {
		return nil, fmt.Errorf("AOT heap capacity %d exceeds hard limit %d", opts.HeapCapacity, 1<<30)
	}
	if err := mochi.Validate(program); err != nil {
		return nil, fmt.Errorf("invalid Mochi bytecode: %w", err)
	}
	if needsM6(program) || usesOpDiv(program) {
		return compileLinuxAMD64Scalar(program, opts)
	}
	if program.GlobalsCount < 0 || program.GlobalsCount > linuxamd64.MaxGlobalSlots {
		return nil, fmt.Errorf("linux-amd64: global slot count %d out of range", program.GlobalsCount)
	}
	for id, v := range program.Constants {
		if v.Kind() != value.KindInt {
			return nil, fmt.Errorf("linux-amd64: constant %d has unsupported type %s", id, v.Kind())
		}
	}
	for id, fn := range program.Functions {
		if fn.ID != id {
			return nil, fmt.Errorf("linux-amd64: function id mismatch: index=%d id=%d", id, fn.ID)
		}
		if fn.ParameterCount < 0 || fn.LocalCount < fn.ParameterCount || fn.LocalCount > 4096 {
			return nil, fmt.Errorf("linux-amd64: function %q exceeds frame limits", fn.Name)
		}
	}
	e := linuxamd64.New(program.GlobalsCount, len(program.Functions))
	e.EmitEntry()
	if err := lowerAMD64Block(e, program, nil, program.Instructions); err != nil {
		return nil, err
	}
	e.EmitMainEpilogue()
	for i := range program.Functions {
		fn := &program.Functions[i]
		e.BeginFunction(i, fn.ParameterCount, fn.LocalCount, fn.Name, 0)
		if err := lowerAMD64Block(e, program, fn, fn.Instructions); err != nil {
			return nil, err
		}
		e.EndFunction()
	}
	return e.Finish()
}

func lowerAMD64Block(e *linuxamd64.Emitter, program *compiler.Bytecode, fn *compiler.CompiledFunction, source code.Instructions) error {
	ins, boundaries, err := decodeM4Block(source)
	if err != nil {
		return err
	}
	states, err := analyzeM4Block(program, fn, ins, boundaries)
	if err != nil {
		return err
	}
	if fn == nil {
		e.BeginBlock()
	}
	for i, in := range ins {
		e.MarkOffset(in.offset)
		st := states[i]
		if st == nil {
			continue
		}
		top := func() bool { return st.stack[len(st.stack)-1] == m3Bool }
		var err error
		switch in.op {
		case code.OpConstant:
			n, _ := program.Constants[in.operands[0]].Int64()
			e.PushInt64(n)
		case code.OpSetGlobal:
			err = e.SetGlobal(in.operands[0])
		case code.OpGetGlobal:
			err = e.GetGlobal(in.operands[0])
		case code.OpSetLocal, code.OpDefineLocal:
			e.SetLocal(in.operands[0])
		case code.OpGetLocal:
			e.GetLocal(in.operands[0])
		case code.OpAdd:
			e.Add()
		case code.OpSub:
			e.Sub()
		case code.OpMul:
			e.Mul()
		case code.OpNeg:
			e.Neg()
		case code.OpTrue:
			e.PushBool(true)
		case code.OpFalse:
			e.PushBool(false)
		case code.OpNot:
			e.Not()
		case code.OpEqual:
			e.Compare(linuxamd64.CondEQ)
		case code.OpNotEqual:
			e.Compare(linuxamd64.CondNE)
		case code.OpLess:
			e.Compare(linuxamd64.CondLT)
		case code.OpLessEqual:
			e.Compare(linuxamd64.CondLE)
		case code.OpGreater:
			e.Compare(linuxamd64.CondGT)
		case code.OpGreaterEqual:
			e.Compare(linuxamd64.CondGE)
		case code.OpJump:
			e.Jump(in.operands[0])
		case code.OpJumpIfFalse:
			e.JumpIfFalse(in.operands[0])
		case code.OpChant:
			e.Chant(top())
		case code.OpPop:
			if fn != nil {
				e.Discard()
			} else {
				e.PopMain(top())
			}
		case code.OpCall:
			callee := program.Functions[in.operands[0]]
			e.Call(in.operands[0], callee.ParameterCount, callee.ReturnsValue)
		case code.OpReturn:
			e.ReturnUnit()
		case code.OpReturnValue:
			e.ReturnValue()
		default:
			return fmt.Errorf("linux-amd64: unsupported opcode %s at byte offset %d", in.name, in.offset)
		}
		if err != nil {
			return fmt.Errorf("linux-amd64 at byte offset %d: %w", in.offset, err)
		}
	}
	e.MarkOffset(len(source))
	return nil
}

// usesOpDiv reports whether any block divides; the simple M4 analysis has no
// division, the M6 scalar path implements checked integer and IEEE division.
func usesOpDiv(p *compiler.Bytecode) bool {
	blocks := []code.Instructions{p.Instructions}
	for _, fn := range p.Functions {
		blocks = append(blocks, fn.Instructions)
	}
	for _, src := range blocks {
		ins, _, err := decodeM4Block(src)
		if err != nil {
			continue
		}
		for _, in := range ins {
			if in.op == code.OpDiv {
				return true
			}
		}
	}
	return false
}
