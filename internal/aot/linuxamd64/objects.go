package linuxamd64

import (
	"encoding/binary"
	"fmt"
	"sort"
)

// Runtime operation numbers (must match runtime/rt.c).
const (
	opInit = iota
	opArrayLit
	opArrayMake
	opArrayWithCap
	opPush
	opReserve
	opClone
	opTruncate
	opAppendAll
	opStructNew
	opFail
	opCollect
	opStats
	opBoxNew
	opEnumNew
	opDump
	opCellNew
	opEnvNew
	opClosureNew
	opBytesFrom
	opStringFrom
)

// Runtime message ids (must match runtime/rt.c).
const (
	msgAlloc = iota
	msgIndex
	msgCapacity
	msgLength
	msgNil
	msgTrunc
	msgRoot
)

var runtimeMessages = []string{
	"M12 allocation failed\n",
	"M12 array index out of bounds\n",
	"M12 invalid array capacity\n",
	"M12 invalid array length\n",
	"M13 nullable value is nil\n",
	"M12 array length is out of range\n",
	"M19 invalid GC root slot (exact-root check failed)\n",
}

const (
	kindBox     = 106 // M13NullableTypeID (box header typeID)
	stateOrigin = 8   // offsetof(State, origin)
	stateBump   = 24  // offsetof(State, bump)
	stateGRA    = 328 // offsetof(State, g_ra)
	stateGRBP   = 336 // offsetof(State, g_rbp)
	stateShadow = 408 // offsetof(State, g_shadow)
)

type safepoint struct {
	at   int // code offset of the return address
	refs []int32
}

type poolItem struct {
	l    *label
	data []byte
}

// EnableHeap switches the image to the managed-heap runtime. Capacity is the
// managed heap size in bytes; stress forces a collection before every allocation.
func (e *Emitter) EnableHeap(capacity uint64, stress bool) {
	e.heap, e.heapCap, e.stress = true, capacity, stress
	e.rtStub, e.rtEntryL, e.failIndex, e.descL = e.newLabel(), e.newLabel(), e.newLabel(), e.newLabel()
	e.failNil = e.newLabel()
	e.globalRecL = e.newLabel()
}

// SetLegacyStackMaps selects the old return-address stack-map root mode at run
// time (comparison baseline only). The default is the shadow-frame contract.
func (e *Emitter) SetLegacyStackMaps(v bool) { e.legacyMaps = v }

// SetHeapDumpPath makes the program write its heap image to path at exit (ABI v1 structural tests).
func (e *Emitter) SetHeapDumpPath(p string) { e.dumpPath = p }

// SetMainRootCap sets the capacity (in values) of main's shadow record.
func (e *Emitter) SetMainRootCap(n int) { e.mainRootCap = n }

// Test hook: deliberately break the root protocol (mutation tests only).
func (e *Emitter) SetRootMutation(kind string) { e.rootMutation = kind }

// RecordSlots returns the number of 8-byte slots a shadow record with the given
// capacity occupies (two header words followed by the values).
func RecordSlots(rootCap int) int { return 2 + rootCap }

// SetGlobalRefs tells the collector which global slots hold references.
func (e *Emitter) SetGlobalRefs(refs []bool) { e.globalRefs = refs }

// Safepoint records the reference slots (rbp-relative byte offsets) that are
// live at the next call / runtime call emitted. Offsets: local i is -8*(i+1);
// operand stack index d is -8*(locals+d+1).
func (e *Emitter) Safepoint(refs []int32) { e.pending, e.hasPending = refs, true }

func (e *Emitter) takeSafepoint() []int32 {
	r := e.pending
	e.pending, e.hasPending = nil, false
	return r
}

func (e *Emitter) record(refs []int32) {
	e.safepoints = append(e.safepoints, safepoint{at: len(e.buf), refs: refs})
}

func (e *Emitter) pool(data []byte) *label {
	l := e.newLabel()
	e.pools = append(e.pools, poolItem{l: l, data: data})
	return l
}

// rtCall emits `mov edi, op; call rt_stub` (operands are already in rsi..r8)
// and records the safepoint at the return address.
func (e *Emitter) rtCall(op int) {
	refs := e.takeSafepoint()
	e.publishShadow(refs)
	e.b(0xBF)
	e.i32(int32(op))
	e.b(0xE8)
	e.rel32(e.rtStub)
	e.record(refs)
}

// publishShadow copies the live reference values into the current frame's
// shadow record and publishes their count (the formal root contract).
func (e *Emitter) publishShadow(refs []int32) {
	if !e.heap {
		return
	}
	switch e.rootMutation {
	case "drop-roots":
		refs = nil
	case "corrupt-header":
		if len(refs) > 0 { // clobber the typeID of the first published root's object header
			skip := e.newLabel()
			e.b(0x48, 0x8B, 0x85) // mov rax,[rbp+off]  (first root)
			e.i32(refs[0])
			e.b(0xA8, 0x01) // test al,1  (static string ids carry no header)
			e.jcc(0x5, skip)
			e.b(0x48, 0x85, 0xC0)
			e.jcc(0x4, skip)
			e.b(0xC7, 0x40, 0xF0) // mov dword [rax-16],9999
			e.i32(9999)
			e.bind(skip)
		}
	case "poison-root":
		if len(refs) > 0 {
			e.b(0x48, 0xC7, 0x83) // mov qword [rbx+16],0x1230  (an invalid, non-heap, 16-aligned value)
			e.i32(16)
			e.i32(0x1230)
			e.b(0x48, 0xC7, 0x83)
			e.i32(8)
			e.i32(int32(len(refs)))
			return
		}
	}
	for i, off := range refs {
		e.b(0x48, 0x8B, 0x85) // mov rax,[rbp+off]
		e.i32(off)
		e.b(0x48, 0x89, 0x83) // mov [rbx+16+8*i],rax
		e.i32(int32(16 + 8*i))
	}
	e.b(0x48, 0xC7, 0x83) // mov qword [rbx+8],count
	e.i32(8)
	e.i32(int32(len(refs)))
}

func (e *Emitter) movImm(reg byte, v int) { // reg: 0xBE esi, 0xBA edx, 0xB9 ecx
	e.b(reg)
	e.i32(int32(v))
}

func boolInt(b bool) int {
	if b {
		return 1
	}
	return 0
}

func (e *Emitter) popN(n int) {
	if n > 0 {
		e.b(0x48, 0x81, 0xC4)
		e.i32(int32(8 * n))
	}
}

// ArrayLiteral builds an array from the n topmost operands.
func (e *Emitter) ArrayLiteral(width int, ref bool, n int) {
	e.movImm(0xBE, width)
	e.movImm(0xBA, boolInt(ref))
	e.movImm(0xB9, n)
	e.b(0x49, 0x89, 0xE0) // mov r8,rsp
	e.rtCall(opArrayLit)
	e.popN(n)
	e.b(0x50)
}

// ArrayMake: length below, initial value on top.
func (e *Emitter) ArrayMake(width int, ref bool) {
	e.movImm(0xBE, width)
	e.movImm(0xBA, boolInt(ref))
	e.b(0x48, 0x8B, 0x4C, 0x24, 0x08) // mov rcx,[rsp+8]
	e.b(0x4C, 0x8B, 0x04, 0x24)       // mov r8,[rsp]
	e.rtCall(opArrayMake)
	e.popN(2)
	e.b(0x50)
}

func (e *Emitter) ArrayWithCapacity(width int, ref bool) {
	e.movImm(0xBE, width)
	e.movImm(0xBA, boolInt(ref))
	e.b(0x48, 0x8B, 0x0C, 0x24) // mov rcx,[rsp]
	e.rtCall(opArrayWithCap)
	e.popN(1)
	e.b(0x50)
}

func (e *Emitter) twoOperand(op int) { // array below, value on top, no result
	e.b(0x48, 0x8B, 0x74, 0x24, 0x08) // mov rsi,[rsp+8]
	e.b(0x48, 0x8B, 0x14, 0x24)       // mov rdx,[rsp]
	e.rtCall(op)
	e.popN(2)
}
func (e *Emitter) ArrayPush()      { e.twoOperand(opPush) }
func (e *Emitter) ArrayReserve()   { e.twoOperand(opReserve) }
func (e *Emitter) ArrayTruncate()  { e.twoOperand(opTruncate) }
func (e *Emitter) ArrayAppendAll() { e.twoOperand(opAppendAll) }

func (e *Emitter) ArrayClone() {
	e.b(0x48, 0x8B, 0x34, 0x24) // mov rsi,[rsp]
	e.rtCall(opClone)
	e.popN(1)
	e.b(0x50)
}
func (e *Emitter) ArrayLen()      { e.b(0x58, 0x48, 0x8B, 0x40, 0x08, 0x50) } // pop rax; mov rax,[rax+8] (payload w1); push rax
func (e *Emitter) ArrayCapacity() { e.b(0x58, 0x48, 0x8B, 0x40, 0x10, 0x50) } // payload w2

func (e *Emitter) ArrayIndex(width int) {
	e.b(0x59, 0x58)             // pop rcx (index); pop rax (array)
	e.b(0x48, 0x3B, 0x48, 0x08) // cmp rcx,[rax+8]   (length, descriptor payload w1)
	e.jcc(0x3, e.failIndex)     // jae (also catches negative indexes)
	e.b(0x48, 0x8B, 0x50, 0x28) // mov rdx,[rax+40]  (storage, payload w5)
	if width == 1 {
		e.b(0x0F, 0xB6, 0x44, 0x0A, 0x20) // movzx eax,byte [rdx+rcx+32]
	} else {
		e.b(0x48, 0x8B, 0x44, 0xCA, 0x20) // mov rax,[rdx+rcx*8+32]
	}
	e.b(0x50)
}

func (e *Emitter) ArraySetIndex(width int, ref bool) {
	e.b(0x5A, 0x59, 0x58) // pop rdx (value); pop rcx (index); pop rax (array)
	e.b(0x48, 0x3B, 0x48, 0x08)
	e.jcc(0x3, e.failIndex)
	e.b(0x48, 0x8B, 0x40, 0x28) // mov rax,[rax+40]
	if width == 1 {
		e.b(0x88, 0x54, 0x08, 0x20) // mov [rax+rcx+32],dl
	} else {
		e.b(0x48, 0x89, 0x54, 0xC8, 0x20) // mov [rax+rcx*8+32],rdx
	}
}

// NewStruct builds a struct from the `count` topmost operands. bitmap marks
// reference fields (bit i = field i).
func (e *Emitter) NewStruct(count int, bitmap []uint64) {
	words := (count + 63) / 64
	if words == 0 {
		words = 1
	}
	data := make([]byte, 8*words)
	for i, w := range bitmap {
		binary.LittleEndian.PutUint64(data[8*i:], w)
	}
	pool := e.pool(data)
	e.movImm(0xBE, count)
	e.b(0x48, 0x8D, 0x15) // lea rdx,[rip+pool]
	e.rel32(pool)
	e.b(0x48, 0x89, 0xE1) // mov rcx,rsp
	e.rtCall(opStructNew)
	e.popN(count)
	e.b(0x50)
}

// GetField loads field `index` of a struct that has `count` fields.
func (e *Emitter) GetField(index, count int) {
	words := (count + 63) / 64
	e.b(0x58, 0x48, 0x8B, 0x80) // pop rax; mov rax,[rax+disp32]
	e.i32(int32(32 + 8*words + 8*index))
	e.b(0x50)
}

// Collect forces a collection (used by tests through the runtime op).
func (e *Emitter) Collect() { e.rtCall(opCollect) }

// emitHeapRuntime appends the stub, the runtime blob, the failure stubs and
// the descriptor/tables. Called from emitRuntime when the heap is enabled.
func (e *Emitter) emitHeapRuntime() error {
	// shared stub: record anchor, align, call mio_rt
	e.bind(e.rtStub)
	e.b(0x4C, 0x8B, 0x14, 0x24) // mov r10,[rsp]
	e.b(0x4C, 0x89, 0x14, 0x25) // mov [g_ra],r10
	e.i32(int32(dataBase) + stateGRA)
	e.b(0x48, 0x89, 0x2C, 0x25) // mov [g_rbp],rbp
	e.i32(int32(dataBase) + stateGRBP)
	e.b(0x48, 0x89, 0x1C, 0x25) // mov [g_shadow],rbx  (shadow-frame chain head)
	e.i32(int32(dataBase) + stateShadow)
	e.b(0x55, 0x48, 0x89, 0xE5, 0x48, 0x83, 0xE4, 0xF0) // push rbp; mov rbp,rsp; and rsp,-16
	e.b(0xE8)
	e.rel32(e.rtEntryL)
	e.b(0x48, 0x89, 0xEC, 0x5D, 0xC3) // mov rsp,rbp; pop rbp; ret
	e.bind(e.failIndex)
	e.b(0xBE)
	e.i32(msgIndex)
	e.rtCall(opFail)
	e.bind(e.failNil)
	e.b(0xBE)
	e.i32(msgNil)
	e.rtCall(opFail)
	e.alignCode(16)
	e.rtEntryL.pos = len(e.buf) + rtEntry
	e.buf = append(e.buf, rtBlob...)
	return nil
}

func (e *Emitter) alignCode(n int) {
	for len(e.buf)%n != 0 {
		e.b(0xCC)
	}
}

// emitHeapTables appends pools, messages, globals bitmap, stack maps and the
// runtime descriptor, then resolves the descriptor references.
func (e *Emitter) emitHeapTables() error {
	e.alignCode(8)
	for _, p := range e.pools {
		e.bind(p.l)
		e.buf = append(e.buf, p.data...)
		e.alignCode(8)
	}
	textVA := imageBase + codeFileOff
	abs := func(off int) uint64 { return uint64(textVA) + uint64(off) }

	// messages: {off,len}[n] then text; offsets relative to table start
	msgOff := len(e.buf)
	head := 8 * len(runtimeMessages)
	text := []byte{}
	for _, m := range runtimeMessages {
		var ent [8]byte
		binary.LittleEndian.PutUint32(ent[0:], uint32(head+len(text)))
		binary.LittleEndian.PutUint32(ent[4:], uint32(len(m)))
		e.buf = append(e.buf, ent[:]...)
		text = append(text, m...)
	}
	e.buf = append(e.buf, text...)
	e.alignCode(8)

	// globals bitmap
	bmOff := len(e.buf)
	bm := make([]uint64, (e.globals+63)/64+1)
	for i, r := range e.globalRefs {
		if r {
			bm[i/64] |= 1 << uint(i%64)
		}
	}
	for _, w := range bm {
		e.buf = binary.LittleEndian.AppendUint64(e.buf, w)
	}

	// stack maps: table of {u32 ra_va, u32 map_off_from_table}, then maps
	sort.Slice(e.safepoints, func(i, j int) bool { return e.safepoints[i].at < e.safepoints[j].at })
	tabOff := len(e.buf)
	maps := []byte{}
	mapsBase := 8 * len(e.safepoints)
	var tab []byte
	for _, sp := range e.safepoints {
		var ent [8]byte
		binary.LittleEndian.PutUint32(ent[0:], uint32(abs(sp.at)))
		binary.LittleEndian.PutUint32(ent[4:], uint32(mapsBase+len(maps)))
		tab = append(tab, ent[:]...)
		maps = binary.LittleEndian.AppendUint32(maps, uint32(len(sp.refs)))
		for _, r := range sp.refs {
			maps = binary.LittleEndian.AppendUint32(maps, uint32(r))
		}
	}
	e.buf = append(e.buf, tab...)
	e.buf = append(e.buf, maps...)
	e.alignCode(8)

	// static global-root record: {previous=0, count|indirect<<32, &slot...}. Global
	// root slots are dereferenced by the collector at GC time (contract's indirect
	// entries), so every reference-typed global is always a root.
	e.alignCode(8)
	e.bind(e.globalRecL)
	var globalAddrs []uint64
	for i, r := range e.globalRefs {
		if r {
			globalAddrs = append(globalAddrs, dataBase+stateSize+8*uint64(i))
		}
	}
	n := uint64(len(globalAddrs))
	e.buf = binary.LittleEndian.AppendUint64(e.buf, 0)
	e.buf = binary.LittleEndian.AppendUint64(e.buf, n|n<<32)
	for _, a := range globalAddrs {
		e.buf = binary.LittleEndian.AppendUint64(e.buf, a)
	}

	var dumpAbs uint64
	if e.dumpPath != "" {
		dumpAbs = abs(len(e.buf))
		e.buf = append(e.buf, e.dumpPath...)
		e.buf = append(e.buf, 0)
		e.alignCode(8)
	}
	// descriptor (must match runtime Desc)
	e.bind(e.descL)
	flags := uint64(0)
	if e.stress {
		flags |= 1
	}
	if !e.legacyMaps {
		flags |= 2 // shadow-frame root mode
	}
	if e.rootMutation == "no-barrier" {
		flags |= 8 // mutation test: the C helpers skip their barrier too
	}
	globalsAddr := dataBase + stateSize
	for _, v := range []uint64{e.heapCap, flags, globalsAddr, uint64(e.globals), abs(bmOff), abs(tabOff), uint64(len(e.safepoints)), abs(msgOff), dumpAbs, 0, 0, 0, 0, 0, 0} {
		e.buf = binary.LittleEndian.AppendUint64(e.buf, v)
	}
	if abs(len(e.buf)) >= 1<<32 {
		return fmt.Errorf("image too large for 32-bit stack-map addresses")
	}
	return nil
}

// ---- nullable scalars (boxes), nil, enums --------------------------------

// BoxTop replaces the raw scalar on top of the operand stack by a GC box.
// The caller must have installed a safepoint that excludes the raw top slot.
func (e *Emitter) BoxTop() {
	e.b(0x48, 0x8B, 0x34, 0x24) // mov rsi,[rsp]
	e.rtCall(opBoxNew)
	e.b(0x48, 0x89, 0x04, 0x24) // mov [rsp],rax
}

// operand returns the displacement of the operand `fromTop` slots below the top.
func operandDisp(fromTop int) int32 { return int32(8 * fromTop) }

// UnboxNullable loads the payload of a non-nil box in place; nil (or a value
// that is not a box) takes the common checked failure path, never scalar zero.
func (e *Emitter) UnboxNullable(fromTop int) {
	e.b(0x48, 0x8B, 0x84, 0x24) // mov rax,[rsp+disp32]
	e.i32(operandDisp(fromTop))
	e.b(0x48, 0x85, 0xC0) // test rax,rax
	e.jcc(0x4, e.failNil)
	e.b(0x8B, 0x48, 0xF0)    // mov ecx,[rax-16]  (typeID)
	e.b(0x83, 0xF9, kindBox) // cmp ecx,106
	e.jcc(0x5, e.failNil)
	e.b(0x48, 0x83, 0x78, 0xF8, 0x10) // cmp qword [rax-8],16 (payloadSize)
	e.jcc(0x5, e.failNil)
	e.b(0x48, 0x8B, 0x40, 0x08) // mov rax,[rax+8]
	e.b(0x48, 0x89, 0x84, 0x24)
	e.i32(operandDisp(fromTop))
}

// UnboxScalar tolerates a flow-narrowed scalar whose representation still comes
// from a nullable predecessor: the candidate is validated against the live heap
// and the box header before it is dereferenced, so ordinary integers stay raw.
func (e *Emitter) UnboxScalar(fromTop int) {
	raw := e.newLabel()
	e.b(0x48, 0x8B, 0x84, 0x24)
	e.i32(operandDisp(fromTop))
	e.b(0x48, 0x85, 0xC0) // test rax,rax
	e.jcc(0x4, raw)
	e.b(0x48, 0x8B, 0x0C, 0x25) // mov rcx,[object origin]
	e.i32(int32(dataBase) + stateOrigin)
	e.b(0x48, 0x83, 0xC1, 0x10) // add rcx,16  (first payload)
	e.b(0x48, 0x39, 0xC8)       // cmp rax,rcx
	e.jcc(0x2, raw)             // jb
	e.b(0x48, 0x8B, 0x0C, 0x25) // mov rcx,[bump]
	e.i32(int32(dataBase) + stateBump)
	e.b(0x48, 0x39, 0xC8)
	e.jcc(0x3, raw) // jae
	e.b(0xA8, 0x0F) // test al,15
	e.jcc(0x5, raw)
	e.b(0x8B, 0x48, 0xF0)    // mov ecx,[rax-16]  (typeID)
	e.b(0x83, 0xF9, kindBox) // cmp ecx,106
	e.jcc(0x5, raw)
	e.b(0x48, 0x83, 0x78, 0xF8, 0x10) // cmp qword [rax-8],16
	e.jcc(0x5, raw)
	e.b(0x48, 0x8B, 0x40, 0x08) // mov rax,[rax+8]
	e.b(0x48, 0x89, 0x84, 0x24)
	e.i32(operandDisp(fromTop))
	e.bind(raw)
}

// IsNil: only nil-capable representations inspect zero; others are always false.
func (e *Emitter) IsNil(nilCapable bool) {
	if !nilCapable {
		e.b(0x48, 0xC7, 0x04, 0x24) // mov qword [rsp],0
		e.i32(0)
		return
	}
	e.b(0x58, 0x48, 0x85, 0xC0, 0x0F, 0x94, 0xC0, 0x0F, 0xB6, 0xC0, 0x50) // pop; test; sete al; movzx; push
}

// NilCheckTop fails (checked failure, exit 1) when the top operand is nil.
func (e *Emitter) NilCheckTop() {
	e.b(0x48, 0x83, 0x3C, 0x24, 0x00) // cmp qword [rsp],0
	e.jcc(0x4, e.failNil)
}

func (e *Emitter) ChantNil() {
	e.popN(1)
	e.b(0xE8)
	e.rel32(e.printNil)
	e.needNil = true
}

// PopMainNil / PopNullableMain record the final top-level value.
func (e *Emitter) PopMainNil() {
	e.popN(1)
	e.b(0x45, 0x31, 0xE4) // xor r12d,r12d
	e.b(0x49, 0xC7, 0xC5, 1, 0, 0, 0)
	e.b(0x49, 0xC7, 0xC6, KindNil, 0, 0, 0)
}
func (e *Emitter) PopNullableMain(outputKind byte) {
	nilCase, done := e.newLabel(), e.newLabel()
	e.b(0x58, 0x48, 0x85, 0xC0) // pop rax; test rax,rax
	e.jcc(0x4, nilCase)
	e.b(0x4C, 0x8B, 0x60, 0x08) // mov r12,[rax+8]  (box payload w1)
	e.b(0x49, 0xC7, 0xC6, outputKind, 0, 0, 0)
	e.b(0xE9)
	e.rel32(done)
	e.bind(nilCase)
	e.b(0x45, 0x31, 0xE4)
	e.b(0x49, 0xC7, 0xC6, KindNil, 0, 0, 0)
	e.bind(done)
	e.b(0x49, 0xC7, 0xC5, 1, 0, 0, 0)
}

// NewEnum builds an enum object (tag + payload) from the `count` topmost operands.
func (e *Emitter) NewEnum(tag, count int, bitmap []uint64) {
	words := (count + 63) / 64
	if words == 0 {
		words = 1
	}
	data := make([]byte, 8*words)
	for i, w := range bitmap {
		binary.LittleEndian.PutUint64(data[8*i:], w)
	}
	pool := e.pool(data)
	e.movImm(0xBE, count)
	e.b(0x48, 0x8D, 0x15)
	e.rel32(pool)
	e.b(0x48, 0x89, 0xE1) // mov rcx,rsp
	e.b(0x41, 0xB8)       // mov r8d,tag
	e.i32(int32(tag))
	e.rtCall(opEnumNew)
	e.popN(count)
	e.b(0x50)
}

func (e *Emitter) EnumTag() {
	e.b(0x58, 0x48, 0x8B, 0x40, 0x08, 0x50) // pop rax; mov rax,[rax+8] (tag, payload w1); push
}

func (e *Emitter) GetEnumValue(index, count int) {
	words := (count + 63) / 64
	e.b(0x58, 0x48, 0x8B, 0x80)
	e.i32(int32(32 + 8*words + 8*index))
	e.b(0x50)
}

func (e *Emitter) emitNilPrinter() {
	e.bind(e.printNil)
	e.b(0x48, 0x83, 0xEC, 0x10, 0xC7, 0x04, 0x24, 0x6D, 0x75, 0x0A, 0x00) // sub rsp,16; mov dword [rsp],"mu\n"
	e.b(0xB8, 1, 0, 0, 0, 0xBF, 1, 0, 0, 0, 0x48, 0x89, 0xE6, 0xBA, 3, 0, 0, 0, 0x0F, 0x05)
	e.b(0x48, 0x83, 0xC4, 0x10, 0xC3)
}
