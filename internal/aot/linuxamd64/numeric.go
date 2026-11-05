package linuxamd64

import (
	"encoding/binary"
	"fmt"
	"math"
)

// Kinds stored in r14 for the top-level "last popped value" and for floats.
const (
	KindInt   = 0
	KindBool  = 1
	KindF32   = 3
	KindF64   = 4
	KindNil   = 7
	opAdd     = 2
	opSub     = 4
	opMul     = 5
	opDiv     = 6
	opEqual   = 11
	opNotEq   = 12
	opLess    = 13
	opLessEq  = 14
	opGreater = 15
	opGreatEq = 16
)

// Unsigned condition codes for Compare.
const (
	CondB  = 0x2
	CondAE = 0x3
	CondBE = 0x6
	CondA  = 0x7
)

func (e *Emitter) imm64rcx(v uint64) {
	e.b(0x48, 0xB9)
	e.buf = binary.LittleEndian.AppendUint64(e.buf, v)
}
func (e *Emitter) jcc(cc byte, l *label) { e.b(0x0F, 0x80|cc); e.rel32(l) }

// Normalize wraps rax-sized operand to the fixed integer width.
func (e *Emitter) Normalize(width uint32, signed bool) error {
	if width == 64 {
		return nil
	}
	e.b(0x58)
	switch {
	case width == 8 && signed:
		e.b(0x48, 0x0F, 0xBE, 0xC0)
	case width == 16 && signed:
		e.b(0x48, 0x0F, 0xBF, 0xC0)
	case width == 32 && signed:
		e.b(0x48, 0x63, 0xC0)
	case width == 8:
		e.b(0x0F, 0xB6, 0xC0)
	case width == 16:
		e.b(0x0F, 0xB7, 0xC0)
	case width == 32:
		e.b(0x89, 0xC0)
	default:
		return fmt.Errorf("invalid integer width %d", width)
	}
	e.b(0x50)
	return nil
}

// DivInt: division by zero exits 1; INT64_MIN / -1 wraps (no SIGFPE).
func (e *Emitter) DivInt(unsigned bool) {
	e.b(0x59, 0x58, 0x48, 0x85, 0xC9) // pop rcx; pop rax; test rcx,rcx
	e.jcc(0x4, e.errExit)
	if unsigned {
		e.b(0x31, 0xD2, 0x48, 0xF7, 0xF1) // xor edx,edx; div rcx
	} else {
		l1, l2 := e.newLabel(), e.newLabel()
		e.b(0x48, 0x83, 0xF9, 0xFF) // cmp rcx,-1
		e.jcc(0x5, l1)
		e.b(0x48, 0xF7, 0xD8) // neg rax
		e.b(0xE9)
		e.rel32(l2)
		e.bind(l1)
		e.b(0x48, 0x99, 0x48, 0xF7, 0xF9) // cqo; idiv rcx
		e.bind(l2)
	}
	e.b(0x50)
}

func (e *Emitter) toXmm(kind int, xmm int) { // rax/rcx -> xmm0/xmm1
	src := byte(0xC0) // rax
	if xmm == 1 {
		src = 0xC9 // rcx -> xmm1
	}
	if kind == KindF32 {
		e.b(0x66, 0x0F, 0x6E, src)
	} else {
		e.b(0x66, 0x48, 0x0F, 0x6E, src)
	}
}
func (e *Emitter) fromXmm0(kind int) {
	if kind == KindF32 {
		e.b(0x66, 0x0F, 0x7E, 0xC0)
	} else {
		e.b(0x66, 0x48, 0x0F, 0x7E, 0xC0)
	}
}

func (e *Emitter) FloatBinary(kind int, op int) error {
	var code byte
	switch op {
	case opAdd:
		code = 0x58
	case opSub:
		code = 0x5C
	case opMul:
		code = 0x59
	case opDiv:
		code = 0x5E
	default:
		return fmt.Errorf("unknown float opcode %d", op)
	}
	e.b(0x59, 0x58)
	e.toXmm(kind, 0)
	e.toXmm(kind, 1)
	if kind == KindF32 {
		e.b(0xF3, 0x0F, code, 0xC1)
	} else {
		e.b(0xF2, 0x0F, code, 0xC1)
	}
	e.fromXmm0(kind)
	e.b(0x50)
	return nil
}

func (e *Emitter) FloatNeg(kind int) {
	e.b(0x58)
	if kind == KindF32 {
		e.b(0x0F, 0xBA, 0xF8, 31) // btc eax,31
	} else {
		e.b(0x48, 0x0F, 0xBA, 0xF8, 63)
	}
	e.b(0x50)
}

func (e *Emitter) ucomis(kind int, swap bool) {
	modrm := byte(0xC1) // xmm0, xmm1
	if swap {
		modrm = 0xC8
	}
	if kind == KindF32 {
		e.b(0x0F, 0x2E, modrm)
	} else {
		e.b(0x66, 0x0F, 0x2E, modrm)
	}
}

// FloatCompare follows IEEE semantics: every ordered comparison with NaN is
// false, and != is true.
func (e *Emitter) FloatCompare(kind int, op int) error {
	e.b(0x59, 0x58)
	e.toXmm(kind, 0)
	e.toXmm(kind, 1)
	switch op {
	case opEqual:
		e.ucomis(kind, false)
		e.b(0x0F, 0x94, 0xC0, 0x0F, 0x9B, 0xC1, 0x20, 0xC8) // sete al; setnp cl; and al,cl
	case opNotEq:
		e.ucomis(kind, false)
		e.b(0x0F, 0x95, 0xC0, 0x0F, 0x9A, 0xC1, 0x08, 0xC8) // setne al; setp cl; or al,cl
	case opLess:
		e.ucomis(kind, true)
		e.b(0x0F, 0x97, 0xC0)
	case opLessEq:
		e.ucomis(kind, true)
		e.b(0x0F, 0x93, 0xC0)
	case opGreater:
		e.ucomis(kind, false)
		e.b(0x0F, 0x97, 0xC0)
	case opGreatEq:
		e.ucomis(kind, false)
		e.b(0x0F, 0x93, 0xC0)
	default:
		return fmt.Errorf("invalid float comparison opcode %d", op)
	}
	e.b(0x0F, 0xB6, 0xC0, 0x50)
	return nil
}

const (
	OpIntToFloat64 = 28
	OpFloat64ToInt = 29
	OpIntToFloat32 = 50
	OpFloat32ToInt = 51
	OpF32ToF64     = 52
	OpF64ToF32     = 53
)

func (e *Emitter) FloatConvert(op int) error {
	e.b(0x58)
	switch op {
	case OpIntToFloat64:
		e.b(0xF2, 0x48, 0x0F, 0x2A, 0xC0)
		e.fromXmm0(KindF64)
	case OpIntToFloat32:
		e.b(0xF3, 0x48, 0x0F, 0x2A, 0xC0)
		e.fromXmm0(KindF32)
	case OpF32ToF64:
		e.toXmm(KindF32, 0)
		e.b(0xF3, 0x0F, 0x5A, 0xC0)
		e.fromXmm0(KindF64)
	case OpF64ToF32:
		e.toXmm(KindF64, 0)
		e.b(0xF2, 0x0F, 0x5A, 0xC0)
		e.fromXmm0(KindF32)
	case OpFloat64ToInt, OpFloat32ToInt:
		e.toXmm(KindF64, 0)
		if op == OpFloat32ToInt {
			e.toXmm(KindF32, 0)
			e.b(0xF3, 0x0F, 0x5A, 0xC0)
		}
		// NaN, +-Inf and out-of-int64-range values are conversion errors (exit 1).
		e.b(0x66, 0x0F, 0x2E, 0xC0) // ucomisd xmm0,xmm0
		e.jcc(0xA, e.errExit)       // jp
		e.imm64rcx(math.Float64bits(0x1p63))
		e.toXmm(KindF64, 1)
		e.ucomis(KindF64, false)
		e.jcc(0x3, e.errExit) // jae
		e.imm64rcx(math.Float64bits(-0x1p63))
		e.toXmm(KindF64, 1)
		e.ucomis(KindF64, false)
		e.jcc(0x2, e.errExit)             // jb
		e.b(0xF2, 0x48, 0x0F, 0x2C, 0xC0) // cvttsd2si rax,xmm0
	default:
		return fmt.Errorf("unsupported conversion opcode %d", op)
	}
	e.b(0x50)
	return nil
}

const (
	TargetInt8 = iota + 1
	TargetInt16
	TargetInt32
	TargetInt64
	TargetUint8
	TargetUint16
	TargetUint32
)

// IntegerConvert is the checked conversion: out of range exits 1.
func (e *Emitter) IntegerConvert(sourceUnsigned bool, target int) error {
	var min int64
	var max uint64
	unsignedTarget := false
	switch target {
	case TargetInt8:
		min, max = math.MinInt8, math.MaxInt8
	case TargetInt16:
		min, max = math.MinInt16, math.MaxInt16
	case TargetInt32:
		min, max = math.MinInt32, math.MaxInt32
	case TargetInt64:
		min, max = math.MinInt64, math.MaxInt64
	case TargetUint8:
		unsignedTarget, max = true, math.MaxUint8
	case TargetUint16:
		unsignedTarget, max = true, math.MaxUint16
	case TargetUint32:
		unsignedTarget, max = true, math.MaxUint32
	default:
		return fmt.Errorf("unknown integer target %d", target)
	}
	e.b(0x58)
	cmpMax := func(cc byte) {
		e.imm64rcx(max)
		e.b(0x48, 0x39, 0xC8) // cmp rax,rcx
		e.jcc(cc, e.errExit)
	}
	switch {
	case sourceUnsigned:
		if target != TargetInt64 {
			cmpMax(0x7) // ja
		}
	case unsignedTarget:
		e.b(0x48, 0x85, 0xC0)
		e.jcc(0x8, e.errExit) // js
		cmpMax(0xF)           // jg
	case target != TargetInt64:
		e.imm64rcx(uint64(min))
		e.b(0x48, 0x39, 0xC8)
		e.jcc(0xC, e.errExit) // jl
		cmpMax(0xF)
	}
	e.b(0x50)
	return nil
}

// Math primitive numbers (code.Math*).
func (e *Emitter) MathFloatUnary(kind int, primitive int) error {
	if kind != KindF32 && kind != KindF64 {
		return fmt.Errorf("floating primitive requires float32 or float64")
	}
	e.b(0x58)
	e.toXmm(kind, 0)
	if primitive == 1 { // sqrt
		if kind == KindF32 {
			e.b(0xF3, 0x0F, 0x51, 0xC0)
		} else {
			e.b(0xF2, 0x0F, 0x51, 0xC0)
		}
	} else {
		imm, ok := map[int]byte{2: 0x09, 3: 0x0A, 4: 0x08, 5: 0x0B}[primitive] // floor, ceil, rint-even, trunc
		if !ok {
			return fmt.Errorf("unknown floating unary primitive %d", primitive)
		}
		op := byte(0x0B) // roundsd
		if kind == KindF32 {
			op = 0x0A // roundss
		}
		e.b(0x66, 0x0F, 0x3A, op, 0xC0, imm)
	}
	e.fromXmm0(kind)
	e.b(0x50)
	return nil
}

// MathFloatPredicate: is_nan(6), is_inf(7), is_finite(8), exact bit tests.
func (e *Emitter) MathFloatPredicate(kind int, primitive int) error {
	var cc byte
	switch primitive {
	case 6:
		cc = 0x97 // seta: |x| bits > inf
	case 7:
		cc = 0x94 // sete
	case 8:
		cc = 0x92 // setb
	default:
		return fmt.Errorf("unknown floating predicate %d", primitive)
	}
	e.b(0x58)
	switch kind {
	case KindF32:
		e.b(0xD1, 0xE0, 0x3D)
		e.i32(int32(-0x1000000)) // cmp eax,0xFF000000
	case KindF64:
		e.b(0x48, 0xD1, 0xE0)
		e.imm64rcx(0xFFE0000000000000)
		e.b(0x48, 0x39, 0xC8)
	default:
		return fmt.Errorf("floating predicate requires float32 or float64")
	}
	e.b(0x0F, cc, 0xC0, 0x0F, 0xB6, 0xC0, 0x50)
	return nil
}

func (e *Emitter) MathSign(width uint32, signed, floating, overflow bool) {
	e.b(0x58)
	switch {
	case overflow:
		if !signed || floating {
			e.b(0x31, 0xC0)
		} else {
			e.imm64rcx(uint64(int64(-1) << (width - 1)))
			e.b(0x48, 0x39, 0xC8, 0x0F, 0x94, 0xC0, 0x0F, 0xB6, 0xC0)
		}
	case floating:
		e.b(0x48, 0xC1, 0xE8, byte(width-1), 0x83, 0xE0, 0x01)
	case signed:
		e.b(0x48, 0x85, 0xC0, 0x0F, 0x98, 0xC0, 0x0F, 0xB6, 0xC0)
	default:
		e.b(0x31, 0xC0)
	}
	e.b(0x50)
}

// MathError never returns (exit 1), like the checked-runtime failure exit.
func (e *Emitter) MathError() {
	e.b(0x58, 0xE9)
	e.rel32(e.errExit)
}

func (e *Emitter) ChantFloat(kind int) {
	e.b(0x5F, 0xBE) // pop rdi; mov esi,imm32
	if kind == KindF32 {
		e.i32(1)
	} else {
		e.i32(0)
	}
	e.b(0xE8)
	e.rel32(e.printFloat)
	e.needFloat = true
}

// PopMainKind records the top-level last popped value with its output kind.
func (e *Emitter) PopMainKind(kind byte) {
	e.b(0x41, 0x5C, 0x49, 0xC7, 0xC5, 1, 0, 0, 0)
	e.b(0x49, 0xC7, 0xC6, kind, 0, 0, 0)
}

// ReturnZeroStub is the body used for functions the analysis proved unreachable.
func (e *Emitter) ReturnZeroStub() {
	e.b(0x31, 0xC0)
	e.ret()
}
