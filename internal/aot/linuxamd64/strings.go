package linuxamd64

import "encoding/binary"

// KindString is the r14 output kind of a top-level popped string.
const KindString = 5

// SetStrings installs the static string table. A string value is the tagged
// id (id<<1)|1; an aligned (low bit 0) value is reserved for heap strings.
func (e *Emitter) SetStrings(table []string) { e.strings = table }

// PushStringID pushes the tagged static string value.
func (e *Emitter) PushStringID(id int) { e.PushInt64(int64(id)<<1 | 1) }

func (e *Emitter) ChantString() {
	e.b(0x5F, 0xE8)
	e.rel32(e.printStr)
	e.needStr = true
}

func (e *Emitter) StringLen() {
	e.b(0x5F, 0xE8)
	e.rel32(e.strLen)
	e.b(0x50)
	e.needStr = true
}

// StringCompare handles == and !=.
func (e *Emitter) StringCompare(notEqual bool) {
	e.b(0x5E, 0x5F, 0xE8) // pop rsi; pop rdi; call str_eq
	e.rel32(e.strEq)
	if notEqual {
		e.b(0x83, 0xF0, 0x01) // xor eax,1
	}
	e.b(0x50)
	e.needStr = true
}

// emitStringRuntime appends the helpers and the table (called from emitRuntime).
// A string value is either a tagged static id ((id<<1)|1) or, with the low bit clear, the byte-array
// descriptor of a dynamic string (length at +8, storage at +40, bytes at storage+32).
func (e *Emitter) emitStringRuntime() {
	// str_view: rdi = string value -> rax = first byte, rdx = length. Clobbers rcx and rdi.
	e.bind(e.strView)
	dyn := e.newLabel()
	e.b(0x40, 0xF6, 0xC7, 0x01) // test dil,1
	e.jcc(0x4, dyn)
	e.b(0x48, 0xD1, 0xEF) // shr rdi,1
	e.b(0x48, 0x8D, 0x0D) // lea rcx,[rip+table]
	e.rel32(e.strTable)
	e.b(0x8B, 0x04, 0xF9)       // mov eax,[rcx+rdi*8]
	e.b(0x8B, 0x54, 0xF9, 0x04) // mov edx,[rcx+rdi*8+4]
	e.b(0x48, 0x01, 0xC8)       // add rax,rcx
	e.b(0xC3)
	e.bind(dyn)
	e.b(0x48, 0x8B, 0x57, 0x08) // mov rdx,[rdi+8]
	e.b(0x48, 0x8B, 0x47, 0x28) // mov rax,[rdi+40]
	e.b(0x48, 0x83, 0xC0, 0x20) // add rax,32
	e.b(0xC3)

	e.bind(e.printStr)
	static := e.newLabel()
	e.b(0x40, 0xF6, 0xC7, 0x01) // test dil,1
	e.jcc(0x5, static)
	e.b(0xE8) // dynamic string: call str_view; write(bytes); write("\n")
	e.rel32(e.strView)
	e.b(0x48, 0x89, 0xC6)                   // mov rsi,rax
	e.b(0xBF, 1, 0, 0, 0, 0xB8, 1, 0, 0, 0) // mov edi,1; mov eax,1
	e.b(0x0F, 0x05)                         // syscall
	e.b(0x6A, 0x0A, 0x48, 0x89, 0xE6)       // push 10; mov rsi,rsp
	e.b(0xBA, 1, 0, 0, 0, 0xBF, 1, 0, 0, 0, 0xB8, 1, 0, 0, 0)
	e.b(0x0F, 0x05, 0x59, 0xC3) // syscall; pop rcx; ret
	e.bind(static)
	e.b(0x48, 0xD1, 0xEF) // shr rdi,1
	e.b(0x48, 0x8D, 0x0D) // lea rcx,[rip+table]
	e.rel32(e.strTable)
	e.b(0x8B, 0x04, 0xF9)       // mov eax,[rcx+rdi*8]
	e.b(0x8B, 0x54, 0xF9, 0x04) // mov edx,[rcx+rdi*8+4]
	e.b(0x48, 0x8D, 0x34, 0x01) // lea rsi,[rcx+rax]
	e.b(0xFF, 0xC2)             // inc edx (trailing newline is stored)
	e.b(0xB8, 1, 0, 0, 0, 0xBF, 1, 0, 0, 0, 0x0F, 0x05, 0xC3)

	e.bind(e.strLen)
	e.b(0xE8) // call str_view; mov rax,rdx; ret
	e.rel32(e.strView)
	e.b(0x48, 0x89, 0xD0, 0xC3)

	e.bind(e.strEq)
	yes, no := e.newLabel(), e.newLabel()
	e.b(0x48, 0x39, 0xF7) // cmp rdi,rsi
	e.jcc(0x4, yes)
	e.b(0xE8) // first operand: r9 = bytes, r10 = length
	e.rel32(e.strView)
	e.b(0x49, 0x89, 0xC1, 0x49, 0x89, 0xD2) // mov r9,rax; mov r10,rdx
	e.b(0x48, 0x89, 0xF7)                   // mov rdi,rsi
	e.b(0xE8)
	e.rel32(e.strView)
	e.b(0x49, 0x39, 0xD2) // cmp r10,rdx
	e.jcc(0x5, no)
	e.b(0x48, 0x89, 0xC6) // mov rsi,rax
	e.b(0x4C, 0x89, 0xCF) // mov rdi,r9
	e.b(0x48, 0x89, 0xD1) // mov rcx,rdx
	e.b(0x39, 0xC0)       // cmp eax,eax (ZF=1 for empty strings)
	e.b(0xF3, 0xA6)       // repe cmpsb
	e.b(0x0F, 0x94, 0xC0, 0x0F, 0xB6, 0xC0, 0xC3)
	e.bind(yes)
	e.b(0xB8, 1, 0, 0, 0, 0xC3)
	e.bind(no)
	e.b(0x31, 0xC0, 0xC3)

	e.bind(e.strTable)
	for len(e.buf)%8 != 0 {
		e.b(0xCC)
	}
	e.bind(e.strTable)
	head := len(e.strings) * 8
	data := []byte{}
	for i, s := range e.strings {
		var ent [8]byte
		binary.LittleEndian.PutUint32(ent[0:], uint32(head+len(data)))
		binary.LittleEndian.PutUint32(ent[4:], uint32(len(s)))
		e.buf = append(e.buf, ent[:]...)
		_ = i
		data = append(data, s...)
		data = append(data, '\n')
	}
	e.buf = append(e.buf, data...)
}

// StringToBytes converts the string on top into a fresh byte array (OpDataConvert string-to-bytes).
// The string stays on the operand stack (and in refs) while the array is allocated.
func (e *Emitter) StringToBytes(refs []int32) {
	e.b(0x48, 0x8B, 0x3C, 0x24) // mov rdi,[rsp]
	e.b(0xE8)
	e.rel32(e.strView)
	e.b(0x48, 0x89, 0xC6) // mov rsi,rax  (source address); rdx = length
	e.Safepoint(refs)
	e.rtCall(opBytesFrom)
	e.popN(1)
	e.b(0x50)
	e.needStr = true
}

// BytesToString converts the byte array on top into a dynamic string, or nil when it is not valid UTF-8.
func (e *Emitter) BytesToString(refs []int32) {
	e.b(0x48, 0x8B, 0x34, 0x24) // mov rsi,[rsp]
	e.Safepoint(refs)
	e.rtCall(opStringFrom)
	e.popN(1)
	e.b(0x50)
}
