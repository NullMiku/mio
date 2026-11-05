package linuxamd64

import (
	"fmt"
	"strings"
	"testing"
)

// These tests check the machine code the emitter produces against GNU objdump, which is an
// independent decoder: the expected strings below are what objdump prints (Intel syntax, no raw
// bytes) for the bytes the emitter wrote, after reviewing that each sequence implements the
// operation named in the case. Only mnemonics and operands are compared. Addresses are
// normalised: branch targets inside a case become ".+N", targets with an exact symbol become
// "<symbol>", other targets "EXT"; rip-relative data operands become "[rip+DATA+0xN]".
//
// Without a GNU objdump the tests SKIP: in that case the emitted instructions are not
// independently verified (the differential tests in package aot still run the programs).
//
// The Mio encoder in kiso/aot/x86_64 is deliberately not used here.

// objdumpAliases lists spellings other binutils versions are known to use for the same
// instruction. It is explicit and exact: no pattern matching. Entries are only applied to the
// mnemonic. Tested with binutils 2.44 only; the table has not been exercised on other versions.
var objdumpAliases = map[string]string{
	"retq":   "ret",
	"callq":  "call",
	"jmpq":   "jmp",
	"leaveq": "leave",
}

func canonical(insn string) string {
	mnemonic, rest, found := strings.Cut(insn, " ")
	if alias, ok := objdumpAliases[mnemonic]; ok {
		mnemonic = alias
	}
	if !found {
		return mnemonic
	}
	return mnemonic + " " + rest
}

type emitCase struct {
	name string
	emit func(e *Emitter)
}

func compareCases(t *testing.T, cases []emitCase, names []string, got [][]string, want map[string][]string) {
	t.Helper()
	if len(got) < len(names) {
		t.Fatalf("objdump delimited %d cases, want at least %d", len(got), len(names))
	}
	if len(want) != len(names) {
		t.Fatalf("%d expectations for %d cases", len(want), len(names))
	}
	for i, name := range names {
		expect, ok := want[name]
		if !ok {
			t.Errorf("no expectation for case %q", name)
			continue
		}
		var actual []string
		for _, in := range got[i] {
			actual = append(actual, canonical(in))
		}
		if strings.Join(actual, "\n") != strings.Join(expect, "\n") {
			t.Errorf("case %q: emitter output decodes differently\n--- objdump says ---\n%s\n--- expected ---\n%s", name, strings.Join(actual, "\n"), strings.Join(expect, "\n"))
		}
	}
}

func marked(e *Emitter, body func()) {
	e.b(0xCC) // int3 delimits the case in the disassembly
	body()
	e.b(0xCC)
}

func scalarCases() []emitCase {
	must := func(err error) {
		if err != nil {
			panic(err)
		}
	}
	return []emitCase{
		{"push-int64", func(e *Emitter) { e.PushInt64(-2) }},
		{"push-bool-true", func(e *Emitter) { e.PushBool(true) }},
		{"push-bool-false", func(e *Emitter) { e.PushBool(false) }},
		{"add", func(e *Emitter) { e.Add() }},
		{"sub", func(e *Emitter) { e.Sub() }},
		{"mul", func(e *Emitter) { e.Mul() }},
		{"neg", func(e *Emitter) { e.Neg() }},
		{"not", func(e *Emitter) { e.Not() }},
		{"cmp-eq", func(e *Emitter) { e.Compare(CondEQ) }},
		{"cmp-lt", func(e *Emitter) { e.Compare(CondLT) }},
		{"cmp-ae", func(e *Emitter) { e.Compare(CondAE) }},
		{"jump", func(e *Emitter) { e.Jump(1000); e.PushBool(true); e.MarkOffset(1000) }},
		{"jump-if-false", func(e *Emitter) { e.JumpIfFalse(1001); e.PushBool(true); e.MarkOffset(1001) }},
		{"set-global", func(e *Emitter) { must(e.SetGlobal(1)) }},
		{"get-global", func(e *Emitter) { must(e.GetGlobal(1)) }},
		{"get-local", func(e *Emitter) { e.GetLocal(2) }},
		{"set-local", func(e *Emitter) { e.SetLocal(2) }},
		{"discard", func(e *Emitter) { e.Discard() }},
		{"normalize-i8", func(e *Emitter) { must(e.Normalize(8, true)) }},
		{"normalize-i16", func(e *Emitter) { must(e.Normalize(16, true)) }},
		{"normalize-i32", func(e *Emitter) { must(e.Normalize(32, true)) }},
		{"normalize-u8", func(e *Emitter) { must(e.Normalize(8, false)) }},
		{"normalize-u16", func(e *Emitter) { must(e.Normalize(16, false)) }},
		{"normalize-u32", func(e *Emitter) { must(e.Normalize(32, false)) }},
		{"div-signed", func(e *Emitter) { e.DivInt(false) }},
		{"div-unsigned", func(e *Emitter) { e.DivInt(true) }},
		{"f64-add", func(e *Emitter) { must(e.FloatBinary(KindF64, opAdd)) }},
		{"f64-sub", func(e *Emitter) { must(e.FloatBinary(KindF64, opSub)) }},
		{"f64-mul", func(e *Emitter) { must(e.FloatBinary(KindF64, opMul)) }},
		{"f64-div", func(e *Emitter) { must(e.FloatBinary(KindF64, opDiv)) }},
		{"f32-add", func(e *Emitter) { must(e.FloatBinary(KindF32, opAdd)) }},
		{"f32-div", func(e *Emitter) { must(e.FloatBinary(KindF32, opDiv)) }},
		{"f64-neg", func(e *Emitter) { e.FloatNeg(KindF64) }},
		{"f32-neg", func(e *Emitter) { e.FloatNeg(KindF32) }},
		{"f64-eq", func(e *Emitter) { must(e.FloatCompare(KindF64, opEqual)) }},
		{"f64-ne", func(e *Emitter) { must(e.FloatCompare(KindF64, opNotEq)) }},
		{"f64-lt", func(e *Emitter) { must(e.FloatCompare(KindF64, opLess)) }},
		{"f64-le", func(e *Emitter) { must(e.FloatCompare(KindF64, opLessEq)) }},
		{"f64-gt", func(e *Emitter) { must(e.FloatCompare(KindF64, opGreater)) }},
		{"f64-ge", func(e *Emitter) { must(e.FloatCompare(KindF64, opGreatEq)) }},
		{"f32-lt", func(e *Emitter) { must(e.FloatCompare(KindF32, opLess)) }},
		{"int-to-f64", func(e *Emitter) { must(e.FloatConvert(OpIntToFloat64)) }},
		{"f64-to-int", func(e *Emitter) { must(e.FloatConvert(OpFloat64ToInt)) }},
		{"int-to-f32", func(e *Emitter) { must(e.FloatConvert(OpIntToFloat32)) }},
		{"f32-to-int", func(e *Emitter) { must(e.FloatConvert(OpFloat32ToInt)) }},
		{"f32-to-f64", func(e *Emitter) { must(e.FloatConvert(OpF32ToF64)) }},
		{"f64-to-f32", func(e *Emitter) { must(e.FloatConvert(OpF64ToF32)) }},
		{"sqrt-f64", func(e *Emitter) { must(e.MathFloatUnary(KindF64, 1)) }},
		{"floor-f64", func(e *Emitter) { must(e.MathFloatUnary(KindF64, 2)) }},
		{"ceil-f32", func(e *Emitter) { must(e.MathFloatUnary(KindF32, 3)) }},
		{"is-nan-f64", func(e *Emitter) { must(e.MathFloatPredicate(KindF64, 6)) }},
		{"chant-bool", func(e *Emitter) { e.Chant(true) }},
		{"call", func(e *Emitter) { e.Call(0, 2, true) }},
		{"main-epilogue", func(e *Emitter) { e.EmitMainEpilogue() }},
	}
}

func heapCases() []emitCase {
	return []emitCase{
		{"array-literal", func(e *Emitter) { e.Safepoint(nil); e.ArrayLiteral(8, true, 2) }},
		{"array-make", func(e *Emitter) { e.Safepoint(nil); e.ArrayMake(1, false) }},
		{"array-push", func(e *Emitter) { e.Safepoint(nil); e.ArrayPush() }},
		{"array-len", func(e *Emitter) { e.ArrayLen() }},
		{"array-index-8", func(e *Emitter) { e.ArrayIndex(8) }},
		{"array-index-1", func(e *Emitter) { e.ArrayIndex(1) }},
		{"array-set-8", func(e *Emitter) { e.ArraySetIndex(8, false) }},
		{"array-set-1", func(e *Emitter) { e.ArraySetIndex(1, false) }},
		{"new-struct", func(e *Emitter) { e.Safepoint(nil); e.NewStruct(3, []uint64{5}) }},
		{"get-field", func(e *Emitter) { e.GetField(2, 3) }},
		{"call-value", func(e *Emitter) { e.Safepoint(nil); e.CallValue(2, true, nil) }},
		{"get-upvalue", func(e *Emitter) { e.GetUpvalue(-8, 1) }},
		{"box-top", func(e *Emitter) { e.Safepoint(nil); e.BoxTop() }},
		{"enum-tag", func(e *Emitter) { e.EnumTag() }},
	}
}

var wantScalarInstructions = map[string][]string{
	"entry": {
		"xor r12,r12",
		"xor r13,r13",
		"xor r14,r14",
		"xor r15,r15",
	},
	"push-int64": {
		"movabs rax,0xfffffffffffffffe",
		"push rax",
	},
	"push-bool-true": {
		"push 0x1",
	},
	"push-bool-false": {
		"push 0x0",
	},
	"add": {
		"pop rcx",
		"pop rax",
		"add rax,rcx",
		"push rax",
	},
	"sub": {
		"pop rcx",
		"pop rax",
		"sub rax,rcx",
		"push rax",
	},
	"mul": {
		"pop rcx",
		"pop rax",
		"imul rax,rcx",
		"push rax",
	},
	"neg": {
		"pop rax",
		"neg rax",
		"push rax",
	},
	"not": {
		"pop rax",
		"xor rax,0x1",
		"push rax",
	},
	"cmp-eq": {
		"pop rcx",
		"pop rax",
		"cmp rax,rcx",
		"sete al",
		"movzx eax,al",
		"push rax",
	},
	"cmp-lt": {
		"pop rcx",
		"pop rax",
		"cmp rax,rcx",
		"setl al",
		"movzx eax,al",
		"push rax",
	},
	"cmp-ae": {
		"pop rcx",
		"pop rax",
		"cmp rax,rcx",
		"setae al",
		"movzx eax,al",
		"push rax",
	},
	"jump": {
		"jmp .+7",
		"push 0x1",
	},
	"jump-if-false": {
		"pop rax",
		"test rax,rax",
		"je .+12",
		"push 0x1",
	},
	"set-global": {
		"pop rax",
		"mov QWORD PTR [rip+DATA+0x8],rax",
	},
	"get-global": {
		"mov rax,QWORD PTR [rip+DATA+0x8]",
		"push rax",
	},
	"get-local": {
		"mov rax,QWORD PTR [rbp-0x18]",
		"push rax",
	},
	"set-local": {
		"pop rax",
		"mov QWORD PTR [rbp-0x18],rax",
	},
	"discard": {
		"add rsp,0x8",
	},
	"normalize-i8": {
		"pop rax",
		"movsx rax,al",
		"push rax",
	},
	"normalize-i16": {
		"pop rax",
		"movsx rax,ax",
		"push rax",
	},
	"normalize-i32": {
		"pop rax",
		"movsxd rax,eax",
		"push rax",
	},
	"normalize-u8": {
		"pop rax",
		"movzx eax,al",
		"push rax",
	},
	"normalize-u16": {
		"pop rax",
		"movzx eax,ax",
		"push rax",
	},
	"normalize-u32": {
		"pop rax",
		"mov eax,eax",
		"push rax",
	},
	"div-signed": {
		"pop rcx",
		"pop rax",
		"test rcx,rcx",
		"je EXT",
		"cmp rcx,0xffffffffffffffff",
		"jne .+29",
		"neg rax",
		"jmp .+34",
		"cqo",
		"idiv rcx",
		"push rax",
	},
	"div-unsigned": {
		"pop rcx",
		"pop rax",
		"test rcx,rcx",
		"je EXT",
		"xor edx,edx",
		"div rcx",
		"push rax",
	},
	"f64-add": {
		"pop rcx",
		"pop rax",
		"movq xmm0,rax",
		"movq xmm1,rcx",
		"addsd xmm0,xmm1",
		"movq rax,xmm0",
		"push rax",
	},
	"f64-sub": {
		"pop rcx",
		"pop rax",
		"movq xmm0,rax",
		"movq xmm1,rcx",
		"subsd xmm0,xmm1",
		"movq rax,xmm0",
		"push rax",
	},
	"f64-mul": {
		"pop rcx",
		"pop rax",
		"movq xmm0,rax",
		"movq xmm1,rcx",
		"mulsd xmm0,xmm1",
		"movq rax,xmm0",
		"push rax",
	},
	"f64-div": {
		"pop rcx",
		"pop rax",
		"movq xmm0,rax",
		"movq xmm1,rcx",
		"divsd xmm0,xmm1",
		"movq rax,xmm0",
		"push rax",
	},
	"f32-add": {
		"pop rcx",
		"pop rax",
		"movd xmm0,eax",
		"movd xmm1,ecx",
		"addss xmm0,xmm1",
		"movd eax,xmm0",
		"push rax",
	},
	"f32-div": {
		"pop rcx",
		"pop rax",
		"movd xmm0,eax",
		"movd xmm1,ecx",
		"divss xmm0,xmm1",
		"movd eax,xmm0",
		"push rax",
	},
	"f64-neg": {
		"pop rax",
		"btc rax,0x3f",
		"push rax",
	},
	"f32-neg": {
		"pop rax",
		"btc eax,0x1f",
		"push rax",
	},
	"f64-eq": {
		"pop rcx",
		"pop rax",
		"movq xmm0,rax",
		"movq xmm1,rcx",
		"ucomisd xmm0,xmm1",
		"sete al",
		"setnp cl",
		"and al,cl",
		"movzx eax,al",
		"push rax",
	},
	"f64-ne": {
		"pop rcx",
		"pop rax",
		"movq xmm0,rax",
		"movq xmm1,rcx",
		"ucomisd xmm0,xmm1",
		"setne al",
		"setp cl",
		"or al,cl",
		"movzx eax,al",
		"push rax",
	},
	"f64-lt": {
		"pop rcx",
		"pop rax",
		"movq xmm0,rax",
		"movq xmm1,rcx",
		"ucomisd xmm1,xmm0",
		"seta al",
		"movzx eax,al",
		"push rax",
	},
	"f64-le": {
		"pop rcx",
		"pop rax",
		"movq xmm0,rax",
		"movq xmm1,rcx",
		"ucomisd xmm1,xmm0",
		"setae al",
		"movzx eax,al",
		"push rax",
	},
	"f64-gt": {
		"pop rcx",
		"pop rax",
		"movq xmm0,rax",
		"movq xmm1,rcx",
		"ucomisd xmm0,xmm1",
		"seta al",
		"movzx eax,al",
		"push rax",
	},
	"f64-ge": {
		"pop rcx",
		"pop rax",
		"movq xmm0,rax",
		"movq xmm1,rcx",
		"ucomisd xmm0,xmm1",
		"setae al",
		"movzx eax,al",
		"push rax",
	},
	"f32-lt": {
		"pop rcx",
		"pop rax",
		"movd xmm0,eax",
		"movd xmm1,ecx",
		"ucomiss xmm1,xmm0",
		"seta al",
		"movzx eax,al",
		"push rax",
	},
	"int-to-f64": {
		"pop rax",
		"cvtsi2sd xmm0,rax",
		"movq rax,xmm0",
		"push rax",
	},
	"f64-to-int": {
		"pop rax",
		"movq xmm0,rax",
		"ucomisd xmm0,xmm0",
		"jp EXT",
		"movabs rcx,0x43e0000000000000",
		"movq xmm1,rcx",
		"ucomisd xmm0,xmm1",
		"jae EXT",
		"movabs rcx,0xc3e0000000000000",
		"movq xmm1,rcx",
		"ucomisd xmm0,xmm1",
		"jb EXT",
		"cvttsd2si rax,xmm0",
		"push rax",
	},
	"int-to-f32": {
		"pop rax",
		"cvtsi2ss xmm0,rax",
		"movd eax,xmm0",
		"push rax",
	},
	"f32-to-int": {
		"pop rax",
		"movq xmm0,rax",
		"movd xmm0,eax",
		"cvtss2sd xmm0,xmm0",
		"ucomisd xmm0,xmm0",
		"jp EXT",
		"movabs rcx,0x43e0000000000000",
		"movq xmm1,rcx",
		"ucomisd xmm0,xmm1",
		"jae EXT",
		"movabs rcx,0xc3e0000000000000",
		"movq xmm1,rcx",
		"ucomisd xmm0,xmm1",
		"jb EXT",
		"cvttsd2si rax,xmm0",
		"push rax",
	},
	"f32-to-f64": {
		"pop rax",
		"movd xmm0,eax",
		"cvtss2sd xmm0,xmm0",
		"movq rax,xmm0",
		"push rax",
	},
	"f64-to-f32": {
		"pop rax",
		"movq xmm0,rax",
		"cvtsd2ss xmm0,xmm0",
		"movd eax,xmm0",
		"push rax",
	},
	"sqrt-f64": {
		"pop rax",
		"movq xmm0,rax",
		"sqrtsd xmm0,xmm0",
		"movq rax,xmm0",
		"push rax",
	},
	"floor-f64": {
		"pop rax",
		"movq xmm0,rax",
		"roundsd xmm0,xmm0,0x9",
		"movq rax,xmm0",
		"push rax",
	},
	"ceil-f32": {
		"pop rax",
		"movd xmm0,eax",
		"roundss xmm0,xmm0,0xa",
		"movd eax,xmm0",
		"push rax",
	},
	"is-nan-f64": {
		"pop rax",
		"shl rax,1",
		"movabs rcx,0xffe0000000000000",
		"cmp rax,rcx",
		"seta al",
		"movzx eax,al",
		"push rax",
	},
	"chant-bool": {
		"pop rdi",
		"call EXT",
	},
	"call": {
		"inc r15",
		"cmp r15,0x400",
		"ja EXT",
		"call <f0>",
		"dec r15",
		"push rax",
	},
	"main-epilogue": {
		"test r13,r13",
		"je .+107",
		"mov rdi,r12",
		"cmp r14,0x1",
		"je .+62",
		"cmp r14,0x5",
		"je .+82",
		"cmp r14,0x7",
		"je .+72",
		"cmp r14,0x3",
		"jge .+92",
		"call EXT",
		"jmp .+107",
		"call EXT",
		"jmp .+107",
		"call EXT",
		"jmp .+107",
		"call EXT",
		"jmp .+107",
		"xor esi,esi",
		"cmp r14,0x3",
		"sete sil",
		"call EXT",
		"xor edi,edi",
		"mov eax,0xe7",
		"syscall",
	},
	"return-value": {
		"pop rax",
		"leave",
		"ret 0x10",
	},
}

var wantHeapInstructions = map[string][]string{
	"entry-heap": {
		"xor r12,r12",
		"xor r13,r13",
		"xor r14,r14",
		"xor r15,r15",
		"xor ebp,ebp",
		"push rbp",
		"mov rbp,rsp",
		"sub rsp,0x10",
		"lea rax,[rip+EXT]",
		"mov QWORD PTR [rsp],rax",
		"mov QWORD PTR [rsp+0x8],0x0",
		"mov rbx,rsp",
		"lea rsi,[rip+EXT]",
		"mov QWORD PTR [rbx+0x8],0x0",
		"mov edi,0x0",
		"call EXT",
	},
	"array-literal": {
		"mov esi,0x8",
		"mov edx,0x1",
		"mov ecx,0x2",
		"mov r8,rsp",
		"mov QWORD PTR [rbx+0x8],0x0",
		"mov edi,0x1",
		"call EXT",
		"add rsp,0x10",
		"push rax",
	},
	"array-make": {
		"mov esi,0x1",
		"mov edx,0x0",
		"mov rcx,QWORD PTR [rsp+0x8]",
		"mov r8,QWORD PTR [rsp]",
		"mov QWORD PTR [rbx+0x8],0x0",
		"mov edi,0x2",
		"call EXT",
		"add rsp,0x10",
		"push rax",
	},
	"array-push": {
		"mov rsi,QWORD PTR [rsp+0x8]",
		"mov rdx,QWORD PTR [rsp]",
		"mov QWORD PTR [rbx+0x8],0x0",
		"mov edi,0x4",
		"call EXT",
		"add rsp,0x10",
	},
	"array-len": {
		"pop rax",
		"mov rax,QWORD PTR [rax+0x8]",
		"push rax",
	},
	"array-index-8": {
		"pop rcx",
		"pop rax",
		"cmp rcx,QWORD PTR [rax+0x8]",
		"jae EXT",
		"mov rdx,QWORD PTR [rax+0x28]",
		"mov rax,QWORD PTR [rdx+rcx*8+0x20]",
		"push rax",
	},
	"array-index-1": {
		"pop rcx",
		"pop rax",
		"cmp rcx,QWORD PTR [rax+0x8]",
		"jae EXT",
		"mov rdx,QWORD PTR [rax+0x28]",
		"movzx eax,BYTE PTR [rdx+rcx*1+0x20]",
		"push rax",
	},
	"array-set-8": {
		"pop rdx",
		"pop rcx",
		"pop rax",
		"cmp rcx,QWORD PTR [rax+0x8]",
		"jae EXT",
		"mov rax,QWORD PTR [rax+0x28]",
		"mov QWORD PTR [rax+rcx*8+0x20],rdx",
	},
	"array-set-1": {
		"pop rdx",
		"pop rcx",
		"pop rax",
		"cmp rcx,QWORD PTR [rax+0x8]",
		"jae EXT",
		"mov rax,QWORD PTR [rax+0x28]",
		"mov BYTE PTR [rax+rcx*1+0x20],dl",
	},
	"new-struct": {
		"mov esi,0x3",
		"lea rdx,[rip+EXT]",
		"mov rcx,rsp",
		"mov QWORD PTR [rbx+0x8],0x0",
		"mov edi,0x9",
		"call EXT",
		"add rsp,0x18",
		"push rax",
	},
	"get-field": {
		"pop rax",
		"mov rax,QWORD PTR [rax+0x38]",
		"push rax",
	},
	"call-value": {
		"mov rax,QWORD PTR [rsp+0x10]",
		"test rax,rax",
		"je EXT",
		"inc r15",
		"cmp r15,0x400",
		"ja EXT",
		"mov QWORD PTR [rbx+0x8],0x0",
		"mov rax,QWORD PTR [rsp+0x10]",
		"mov r10,QWORD PTR [rax+0x28]",
		"call QWORD PTR [rax+0x20]",
		"dec r15",
		"add rsp,0x8",
		"push rax",
	},
	"get-upvalue": {
		"mov rax,QWORD PTR [rbp+0x38]",
		"mov rax,QWORD PTR [rax+0x18]",
		"mov rax,QWORD PTR [rax+0x8]",
		"push rax",
	},
	"box-top": {
		"mov rsi,QWORD PTR [rsp]",
		"mov QWORD PTR [rbx+0x8],0x0",
		"mov edi,0xd",
		"call EXT",
		"mov QWORD PTR [rsp],rax",
	},
	"enum-tag": {
		"pop rax",
		"mov rax,QWORD PTR [rax+0x8]",
		"push rax",
	},
	"return-value-heap": {
		"pop rax",
		"mov rbx,QWORD PTR [rbx]",
		"leave",
		"ret 0x10",
	},
}

func TestEmitterScalarInstructionsMatchObjdump(t *testing.T) {
	requireGNUObjdump(t)
	e := New(4, 1)
	cases := scalarCases()
	names := []string{"entry"}
	marked(e, e.EmitEntry)
	e.BeginBlock()
	for _, c := range cases {
		names = append(names, c.name)
		marked(e, func() { c.emit(e) })
	}
	e.BeginFunction(0, 2, 3, "f0", 0)
	marked(e, e.ReturnValue)
	names = append(names, "return-value")
	image, err := e.Finish()
	if err != nil {
		t.Fatal(err)
	}
	compareCases(t, cases, names, extractCases(disassemble(t, image)), wantScalarInstructions)
}

func TestEmitterHeapInstructionsMatchObjdump(t *testing.T) {
	requireGNUObjdump(t)
	e := New(2, 1)
	e.EnableHeap(1<<20, false)
	e.SetGlobalRefs([]bool{false, false})
	cases := heapCases()
	names := []string{"entry-heap"}
	marked(e, e.EmitEntry)
	e.BeginBlock()
	for _, c := range cases {
		names = append(names, c.name)
		marked(e, func() { c.emit(e) })
	}
	e.EmitMainEpilogue()
	e.BeginFunction(0, 2, 3, "f0", 2)
	marked(e, e.ReturnValue)
	names = append(names, "return-value-heap")
	image, err := e.Finish()
	if err != nil {
		t.Fatal(err)
	}
	compareCases(t, cases, names, extractCases(disassemble(t, image)), wantHeapInstructions)
}

// A scalar image (no managed heap) holds only code in .text (the float formatter and the print
// helpers included), except for the two 4-byte messages "hai\n" and "iie\n" that the emitter
// places between helpers (haiLabel, iieLabel). The whole section must decode without "(bad)" or
// ".byte" outside that known data window (plus the few bytes an instruction overlapping it can
// swallow). Images with a managed heap interleave pools, stack maps and descriptors with code and
// are not checked this way: their data ranges are not identified by one pair of labels.
func TestEmittedScalarCodeDecodesWithoutGaps(t *testing.T) {
	requireGNUObjdump(t)
	e := New(4, 1)
	e.EmitEntry()
	e.BeginBlock()
	for _, c := range scalarCases() {
		c.emit(e)
	}
	if err := e.FloatBinary(KindF64, opAdd); err != nil {
		t.Fatal(err)
	}
	e.ChantFloat(KindF64)
	e.PopMainKind(KindF64)
	e.EmitMainEpilogue()
	e.BeginFunction(0, 2, 3, "f0", 0)
	e.ReturnValue()
	e.EndFunction()
	image, err := e.Finish()
	if err != nil {
		t.Fatal(err)
	}
	const textBase = 0x401000 // imageBase + codeFileOff
	dataLo := uint64(textBase + e.haiLabel.pos)
	dataHi := uint64(textBase+e.iieLabel.pos) + 4 + 5
	if e.haiLabel.pos < 0 || e.iieLabel.pos < e.haiLabel.pos {
		t.Fatalf("message labels not bound: hai=%d iie=%d", e.haiLabel.pos, e.iieLabel.pos)
	}
	insns := disassemble(t, image)
	if len(insns) < 1000 {
		t.Fatalf("only %d instructions decoded; the float formatter should be included", len(insns))
	}
	for _, in := range insns {
		if in.addr >= dataLo && in.addr < dataHi {
			continue
		}
		if strings.Contains(in.text, "(bad)") || strings.HasPrefix(in.text, ".byte") {
			t.Fatalf("undecodable bytes at %#x: %q", in.addr, in.text)
		}
	}
	t.Log(fmt.Sprintf("%d instructions decoded cleanly", len(insns)))
}
