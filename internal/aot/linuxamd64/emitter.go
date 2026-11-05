package linuxamd64

import (
	"encoding/binary"
	"fmt"
)

// MaxCallDepth mirrors the macOS backend's native call-depth guard.
const MaxCallDepth = 1024

// Condition codes for Compare (x86 setcc low nibble).
const (
	CondEQ = 0x4
	CondNE = 0x5
	CondLT = 0xC // signed <
	CondGE = 0xD
	CondLE = 0xE
	CondGT = 0xF
)

type label struct{ pos int }

type fixup struct {
	at    int // offset of rel32
	label *label
}

// Emitter is a stack-machine x86-64 encoder. The Mochi operand stack lives on
// the native stack; r12/r13/r14 hold the "last popped value" of main, r15 the
// call-depth counter. Calling convention for Mochi-to-Mochi calls: arguments
// pushed left-to-right on the stack, callee pops them with `ret imm16`, result
// in rax. (Runtime/syscall boundaries use System V AMD64: rdi,rsi,rdx,...)
type Emitter struct {
	buf                                []byte
	fixups                             []fixup
	dataFix                            []fixup // rip-relative references to global slots, label.pos = slot*8
	funcLabels                         []*label
	funcSyms                           []Symbol
	errExit                            *label
	printInt                           *label
	printBool                          *label
	haiLabel                           *label
	iieLabel                           *label
	needPInt                           bool
	needPBool                          bool
	needFloat                          bool
	needStr                            bool
	heap                               bool
	heapCap                            uint64
	stress                             bool
	pending                            []int32
	hasPending                         bool
	safepoints                         []safepoint
	pools                              []poolItem
	globalRefs                         []bool
	rtStub, rtEntryL, failIndex, descL *label
	failNil, printNil                  *label
	needNil                            bool
	curLocals                          int
	legacyMaps                         bool
	dumpPath                           string
	globalRecL                         *label
	mainRootCap                        int
	rootMutation                       string
	curRecordSlots                     int
	strings                            []string
	printStr, strLen, strEq, strTable  *label
	strView                            *label
	printFloat                         *label
	fmtBlob                            *label
	globals                            int
	opLabels                           map[int]*label
	curParams                          int
}

func New(globals, functions int) *Emitter {
	e := &Emitter{globals: globals, opLabels: map[int]*label{}}
	for i := 0; i < functions; i++ {
		e.funcLabels = append(e.funcLabels, &label{pos: -1})
	}
	e.errExit = &label{pos: -1}
	e.printInt = &label{pos: -1}
	e.printBool = &label{pos: -1}
	e.printFloat = &label{pos: -1}
	e.printStr, e.strLen, e.strEq, e.strTable = e.newLabel(), e.newLabel(), e.newLabel(), e.newLabel()
	e.printNil = e.newLabel()
	e.strView = e.newLabel()
	e.fmtBlob = &label{pos: -1}
	e.haiLabel = &label{pos: -1}
	e.iieLabel = &label{pos: -1}
	return e
}

func (e *Emitter) Offset() int  { return len(e.buf) }
func (e *Emitter) b(bs ...byte) { e.buf = append(e.buf, bs...) }
func (e *Emitter) i32(v int32) {
	e.buf = binary.LittleEndian.AppendUint32(e.buf, uint32(v))
}
func (e *Emitter) newLabel() *label { return &label{pos: -1} }
func (e *Emitter) bind(l *label)    { l.pos = len(e.buf) }
func (e *Emitter) rel32(l *label) {
	e.fixups = append(e.fixups, fixup{at: len(e.buf), label: l})
	e.i32(0)
}

// BytecodeLabel returns the label for a Mochi byte offset within the block
// currently being emitted.
func (e *Emitter) BytecodeLabel(off int) *label {
	l, ok := e.opLabels[off]
	if !ok {
		l = e.newLabel()
		e.opLabels[off] = l
	}
	return l
}

// BeginBlock resets the per-block bytecode-offset labels.
func (e *Emitter) BeginBlock() { e.opLabels = map[int]*label{} }

// MarkOffset binds the Mochi byte offset to the current native position.
func (e *Emitter) MarkOffset(off int) { e.bind(e.BytecodeLabel(off)) }

func (e *Emitter) EmitEntry() {
	// _start: zero the main-state registers; stack is 16-byte aligned by the kernel.
	e.b(0x4D, 0x31, 0xE4) // xor r12,r12
	e.b(0x4D, 0x31, 0xED) // xor r13,r13
	e.b(0x4D, 0x31, 0xF6) // xor r14,r14
	e.b(0x4D, 0x31, 0xFF) // xor r15,r15
	if e.heap {
		e.b(0x31, 0xED, 0x55, 0x48, 0x89, 0xE5) // xor ebp,ebp; push rbp; mov rbp,rsp (main frame, chain end)
		e.curRecordSlots = RecordSlots(e.mainRootCap)
		e.b(0x48, 0x81, 0xEC) // sub rsp, record bytes
		e.i32(int32(8 * e.curRecordSlots))
		e.b(0x48, 0x8D, 0x05) // lea rax,[rip+global root record]  (static, indirect global slots)
		e.rel32(e.globalRecL)
		e.b(0x48, 0x89, 0x04, 0x24)       // mov [rsp],rax  (previous)
		e.b(0x48, 0xC7, 0x44, 0x24, 0x08) // mov qword [rsp+8],0
		e.i32(0)
		e.b(0x48, 0x89, 0xE3) // mov rbx,rsp  (shadow head)
		e.b(0x48, 0x8D, 0x35) // lea rsi,[rip+desc]
		e.rel32(e.descL)
		e.rtCall(opInit)
	}
}

// EmitMainEpilogue prints the last top-level popped value (if any) and exits 0.
func (e *Emitter) EmitMainEpilogue() {
	done, isBool, isFloat, isStr, isNil := e.newLabel(), e.newLabel(), e.newLabel(), e.newLabel(), e.newLabel()
	e.b(0x4D, 0x85, 0xED) // test r13,r13
	e.jcc(0x4, done)
	e.b(0x4C, 0x89, 0xE7)       // mov rdi,r12
	e.b(0x49, 0x83, 0xFE, 0x01) // cmp r14,1
	e.jcc(0x4, isBool)
	e.b(0x49, 0x83, 0xFE, KindString) // cmp r14,5
	e.jcc(0x4, isStr)
	e.b(0x49, 0x83, 0xFE, KindNil) // cmp r14,7
	e.jcc(0x4, isNil)
	e.b(0x49, 0x83, 0xFE, 0x03) // cmp r14,3
	e.jcc(0xD, isFloat)         // jge
	e.b(0xE8)
	e.rel32(e.printInt)
	e.needPInt = true
	e.b(0xE9)
	e.rel32(done)
	e.bind(isBool)
	e.b(0xE8)
	e.rel32(e.printBool)
	e.needPBool = true
	e.b(0xE9)
	e.rel32(done)
	e.bind(isNil)
	e.b(0xE8)
	e.rel32(e.printNil)
	e.needNil = true
	e.b(0xE9)
	e.rel32(done)
	e.bind(isStr)
	e.b(0xE8)
	e.rel32(e.printStr)
	e.needStr = true
	e.b(0xE9)
	e.rel32(done)
	e.bind(isFloat)
	e.b(0x31, 0xF6)             // xor esi,esi
	e.b(0x49, 0x83, 0xFE, 0x03) // cmp r14,3
	e.b(0x40, 0x0F, 0x94, 0xC6) // sete sil
	e.b(0xE8)
	e.rel32(e.printFloat)
	e.needFloat = true
	e.bind(done)
	if e.heap && e.dumpPath != "" {
		e.rtCall(opDump)
	}
	e.b(0x31, 0xFF)                   // xor edi,edi
	e.b(0xB8, 0xE7, 0x00, 0x00, 0x00) // mov eax,231 (exit_group)
	e.b(0x0F, 0x05)
}

func (e *Emitter) PushInt64(n int64) {
	e.b(0x48, 0xB8) // mov rax, imm64
	e.buf = binary.LittleEndian.AppendUint64(e.buf, uint64(n))
	e.b(0x50)
}
func (e *Emitter) PushBool(v bool) {
	if v {
		e.b(0x6A, 0x01)
	} else {
		e.b(0x6A, 0x00)
	}
}
func (e *Emitter) Add() { e.b(0x59, 0x58, 0x48, 0x01, 0xC8, 0x50) } // pop rcx; pop rax; add rax,rcx; push rax
func (e *Emitter) Sub() { e.b(0x59, 0x58, 0x48, 0x29, 0xC8, 0x50) }
func (e *Emitter) Mul() { e.b(0x59, 0x58, 0x48, 0x0F, 0xAF, 0xC1, 0x50) }
func (e *Emitter) Neg() { e.b(0x58, 0x48, 0xF7, 0xD8, 0x50) }
func (e *Emitter) Not() { e.b(0x58, 0x48, 0x83, 0xF0, 0x01, 0x50) } // xor rax,1
func (e *Emitter) Compare(cond byte) {
	e.b(0x59, 0x58, 0x48, 0x39, 0xC8) // cmp rax,rcx
	e.b(0x0F, 0x90|cond, 0xC0)        // setcc al
	e.b(0x0F, 0xB6, 0xC0)             // movzx eax,al
	e.b(0x50)
}
func (e *Emitter) Jump(target int) {
	e.b(0xE9)
	e.rel32(e.BytecodeLabel(target))
}
func (e *Emitter) JumpIfFalse(target int) {
	e.b(0x58, 0x48, 0x85, 0xC0) // pop rax; test rax,rax
	e.b(0x0F, 0x84)
	e.rel32(e.BytecodeLabel(target))
}

func (e *Emitter) globalRef(slot int) error {
	if slot < 0 || slot >= e.globals {
		return fmt.Errorf("global slot %d out of range", slot)
	}
	e.dataFix = append(e.dataFix, fixup{at: len(e.buf), label: &label{pos: slot * 8}})
	e.i32(0)
	return nil
}
func (e *Emitter) SetGlobal(slot int) error {
	e.b(0x58, 0x48, 0x89, 0x05) // pop rax; mov [rip+d],rax
	return e.globalRef(slot)
}
func (e *Emitter) GetGlobal(slot int) error {
	e.b(0x48, 0x8B, 0x05) // mov rax,[rip+d]
	if err := e.globalRef(slot); err != nil {
		return err
	}
	e.b(0x50)
	return nil
}
func (e *Emitter) localDisp(slot int) int32 { return int32(-8 * (slot + 1)) }
func (e *Emitter) GetLocal(slot int) {
	e.b(0x48, 0x8B, 0x85)
	e.i32(e.localDisp(slot))
	e.b(0x50)
}
func (e *Emitter) SetLocal(slot int) {
	e.b(0x58, 0x48, 0x89, 0x85)
	e.i32(e.localDisp(slot))
}

func (e *Emitter) Chant(isBool bool) {
	e.b(0x5F) // pop rdi
	e.b(0xE8)
	if isBool {
		e.rel32(e.printBool)
		e.needPBool = true
	} else {
		e.rel32(e.printInt)
		e.needPInt = true
	}
}

// PopMain implements the top-level "last expression value is printed at exit" rule.
func (e *Emitter) PopMain(isBool bool) {
	k := byte(KindInt)
	if isBool {
		k = KindBool
	}
	e.PopMainKind(k)
}
func (e *Emitter) Discard() { e.b(0x48, 0x83, 0xC4, 0x08) } // add rsp,8

func (e *Emitter) Call(id, params int, returnsValue bool) {
	e.b(0x49, 0xFF, 0xC7) // inc r15
	e.b(0x49, 0x81, 0xFF) // cmp r15,MaxCallDepth
	e.i32(MaxCallDepth)
	e.b(0x0F, 0x87) // ja errExit
	e.rel32(e.errExit)
	refs := e.takeSafepoint()
	e.publishShadow(refs)
	e.b(0xE8)
	e.rel32(e.funcLabels[id])
	if e.heap {
		e.record(refs)
	}
	e.b(0x49, 0xFF, 0xCF) // dec r15
	if returnsValue {
		e.b(0x50)
	}
}

func (e *Emitter) BeginFunction(id, params, locals int, name string, rootCap int) {
	e.BeginBlock()
	e.bind(e.funcLabels[id])
	e.funcSyms = append(e.funcSyms, Symbol{Name: name, Offset: len(e.buf)})
	e.curParams = params
	e.b(0x55, 0x48, 0x89, 0xE5) // push rbp; mov rbp,rsp
	e.curLocals = locals
	if locals > 0 {
		e.b(0x48, 0x81, 0xEC) // sub rsp, 8*locals
		e.i32(int32(8 * locals))
		if e.heap { // precise roots: no stale pointers in uninitialised locals
			e.b(0x48, 0x89, 0xE7) // mov rdi,rsp
			e.b(0xB9)             // mov ecx,locals
			e.i32(int32(locals))
			e.b(0x31, 0xC0, 0xF3, 0x48, 0xAB) // xor eax,eax; rep stosq
		}
	}
	if e.heap { // shadow record: {previous, 0, values...}; rbx becomes the chain head
		e.curRecordSlots = RecordSlots(rootCap)
		e.b(0x48, 0x81, 0xEC)
		e.i32(int32(8 * e.curRecordSlots))
		e.b(0x48, 0x89, 0x1C, 0x24) // mov [rsp],rbx
		e.b(0x48, 0xC7, 0x44, 0x24, 0x08)
		e.i32(0)
		e.b(0x48, 0x89, 0xE3) // mov rbx,rsp
	}
	for i := 0; i < params; i++ { // arg i sits at [rbp+16+8*(n-1-i)]
		e.b(0x48, 0x8B, 0x85)
		e.i32(int32(16 + 8*(params-1-i)))
		e.b(0x48, 0x89, 0x85)
		e.i32(e.localDisp(i))
	}
}
func (e *Emitter) EndFunction() {
	last := &e.funcSyms[len(e.funcSyms)-1]
	last.Size = len(e.buf) - last.Offset
}
func (e *Emitter) ret() {
	if e.heap {
		e.b(0x48, 0x8B, 0x1B) // mov rbx,[rbx]  (unlink this frame's shadow record)
	}
	e.b(0xC9, 0xC2) // leave; ret imm16
	e.buf = binary.LittleEndian.AppendUint16(e.buf, uint16(8*e.curParams))
}
func (e *Emitter) ReturnUnit() { e.ret() }
func (e *Emitter) ReturnValue() {
	e.b(0x58) // pop rax
	e.ret()
}

// emitRuntime appends shared helper routines (System V: first arg in rdi).
func (e *Emitter) emitRuntime() error {
	e.bind(e.errExit)
	e.b(0xBF, 1, 0, 0, 0)    // mov edi,1
	e.b(0xB8, 0xE7, 0, 0, 0) // mov eax,231
	e.b(0x0F, 0x05)
	if e.needPInt {
		e.bind(e.printInt)
		loop, pos, skip := e.newLabel(), e.newLabel(), e.newLabel()
		e.b(0x55, 0x48, 0x89, 0xE5, 0x48, 0x83, 0xEC, 0x30) // push rbp; mov rbp,rsp; sub rsp,48
		e.b(0x48, 0x89, 0xF8)                               // mov rax,rdi
		e.b(0xC6, 0x45, 0xFF, 0x0A)                         // mov byte [rbp-1],'\n'
		e.b(0x48, 0x8D, 0x75, 0xFF)                         // lea rsi,[rbp-1]
		e.b(0x49, 0x89, 0xC0)                               // mov r8,rax
		e.b(0x48, 0x85, 0xC0)                               // test rax,rax
		e.b(0x0F, 0x89)                                     // jns pos
		e.rel32(pos)
		e.b(0x48, 0xF7, 0xD8) // neg rax (INT64_MIN stays 2^63, divided unsigned)
		e.bind(pos)
		e.b(0xB9, 10, 0, 0, 0) // mov ecx,10
		e.bind(loop)
		e.b(0x31, 0xD2)       // xor edx,edx
		e.b(0x48, 0xF7, 0xF1) // div rcx
		e.b(0x80, 0xC2, 0x30) // add dl,'0'
		e.b(0x48, 0xFF, 0xCE) // dec rsi
		e.b(0x88, 0x16)       // mov [rsi],dl
		e.b(0x48, 0x85, 0xC0) // test rax,rax
		e.b(0x0F, 0x85)       // jnz loop
		e.rel32(loop)
		e.b(0x4D, 0x85, 0xC0) // test r8,r8
		e.b(0x0F, 0x89)       // jns skip
		e.rel32(skip)
		e.b(0x48, 0xFF, 0xCE) // dec rsi
		e.b(0xC6, 0x06, 0x2D) // mov byte [rsi],'-'
		e.bind(skip)
		e.b(0x48, 0x89, 0xEA)       // mov rdx,rbp
		e.b(0x48, 0x29, 0xF2)       // sub rdx,rsi
		e.b(0xB8, 1, 0, 0, 0)       // mov eax,1 (write)
		e.b(0xBF, 1, 0, 0, 0)       // mov edi,1
		e.b(0x0F, 0x05, 0xC9, 0xC3) // syscall; leave; ret
	}
	if e.heap {
		if err := e.emitHeapRuntime(); err != nil {
			return err
		}
	}
	if e.needStr {
		e.emitStringRuntime()
	}
	if e.needNil {
		e.emitNilPrinter()
	}
	if e.needFloat {
		// print_float(rdi=bits, esi=is32): align stack, format into a 64-byte buffer, write.
		e.bind(e.printFloat)
		e.b(0x55, 0x48, 0x89, 0xE5, 0x48, 0x83, 0xE4, 0xF0, 0x48, 0x83, 0xEC, 0x40) // push rbp; mov rbp,rsp; and rsp,-16; sub rsp,64
		e.b(0x48, 0x89, 0xE2)                                                       // mov rdx,rsp
		e.b(0xE8)
		e.rel32(e.fmtBlob)
		e.b(0xC6, 0x04, 0x04, 0x0A) // mov byte [rsp+rax],'\n'
		e.b(0x48, 0x8D, 0x50, 0x01) // lea rdx,[rax+1]
		e.b(0x48, 0x89, 0xE6)       // mov rsi,rsp
		e.b(0xB8, 1, 0, 0, 0)       // mov eax,1
		e.b(0xBF, 1, 0, 0, 0)       // mov edi,1
		e.b(0x0F, 0x05, 0xC9, 0xC3) // syscall; leave; ret
		e.bind(e.fmtBlob)
		e.buf = append(e.buf, floatFmtBlob...)
	}
	if e.needPBool {
		e.bind(e.printBool)
		ok := e.newLabel()
		e.b(0x48, 0x85, 0xFF) // test rdi,rdi
		e.b(0x48, 0x8D, 0x35) // lea rsi,[rip+hai]
		e.rel32(e.haiLabel)
		e.b(0x0F, 0x85) // jnz ok
		e.rel32(ok)
		e.b(0x48, 0x8D, 0x35) // lea rsi,[rip+iie]
		e.rel32(e.iieLabel)
		e.bind(ok)
		e.b(0xBA, 4, 0, 0, 0) // mov edx,4
		e.b(0xB8, 1, 0, 0, 0) // mov eax,1
		e.b(0xBF, 1, 0, 0, 0) // mov edi,1
		e.b(0x0F, 0x05, 0xC3) // syscall; ret
		e.bind(e.haiLabel)
		e.b('h', 'a', 'i', '\n')
		e.bind(e.iieLabel)
		e.b('i', 'i', 'e', '\n')
	}
	return nil
}

// Finish resolves fixups and returns a complete ELF64 executable.
func (e *Emitter) Finish() ([]byte, error) {
	if err := e.emitRuntime(); err != nil {
		return nil, err
	}
	if e.heap {
		if err := e.emitHeapTables(); err != nil {
			return nil, err
		}
	}
	for _, f := range e.fixups {
		if f.label.pos < 0 {
			return nil, fmt.Errorf("unresolved x86_64 label at offset %d", f.at)
		}
		binary.LittleEndian.PutUint32(e.buf[f.at:], uint32(int32(f.label.pos-(f.at+4))))
	}
	if err := checkELFInputs(e.buf, e.globals); err != nil {
		return nil, err
	}
	// Data address depends on code size only, so compute it with a dry layout.
	bssVA := dataBase
	if e.heap {
		bssVA += stateSize
	}
	textVA := imageBase + codeFileOff
	for _, f := range e.dataFix {
		target := bssVA + uint64(f.label.pos)
		next := textVA + uint64(f.at+4)
		d := int64(target) - int64(next)
		binary.LittleEndian.PutUint32(e.buf[f.at:], uint32(int32(d)))
	}
	syms := append([]Symbol{{Name: "_start", Offset: 0, Size: 0}}, e.funcSyms...)
	bss := uint64(e.globals) * 8
	if e.heap {
		bss += stateSize
	}
	img, _ := buildELF(e.buf, 0, bss, syms)
	return img, nil
}
