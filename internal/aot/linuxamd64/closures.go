package linuxamd64

// Closures (Object ABI v1 types 103..105), mirroring the Darwin M15b layout.
//
//	closure payload (48 B): {4, function id, parameters, returns, code address, environment}
//	environment payload   : {5, count, cell...}
//	cell payload (16 B)   : {6 | reference<<8, value}
//
// A local captured by an inner function lives in a hidden frame slot (its cell slot, 0 until the first
// capture). While the cell slot is 0 the local is read and written in its ordinary slot; from the first
// capture on, every access goes through the shared cell. OpDefineLocal resets the cell slot so each
// loop iteration gets an independent cell. A function with upvalues receives its environment in r10
// (set by CallValue) and keeps it in a hidden slot; the environment, cell slots and every operand are
// published as precise roots like any other reference.

// Capture describes one entry of a function's capture list after type analysis.
type Capture struct {
	Local     bool
	Index     int
	Reference bool
}

func (e *Emitter) disp32(slot int) { e.i32(e.localDisp(slot)) }

// SaveEnvironment stores the incoming environment (r10) in the hidden slot.
func (e *Emitter) SaveEnvironment(slot int) {
	e.b(0x4C, 0x89, 0x95) // mov [rbp+slot],r10
	e.disp32(slot)
}

func (e *Emitter) jmpLabel(l *label) { e.b(0xE9); e.rel32(l) }

// GetCapturedLocal pushes local `local`, reading through its cell once one exists.
func (e *Emitter) GetCapturedLocal(local, cell int) {
	raw, done := e.newLabel(), e.newLabel()
	e.b(0x48, 0x8B, 0x85) // mov rax,[rbp+cell]
	e.disp32(cell)
	e.b(0x48, 0x85, 0xC0) // test rax,rax
	e.jcc(0x4, raw)
	e.b(0x48, 0x8B, 0x40, 0x08) // mov rax,[rax+8]
	e.jmpLabel(done)
	e.bind(raw)
	e.b(0x48, 0x8B, 0x85) // mov rax,[rbp+local]
	e.disp32(local)
	e.bind(done)
	e.b(0x50)
}

// SetCapturedLocal pops a value into local `local` (through its cell when one exists).
func (e *Emitter) SetCapturedLocal(local, cell int, ref bool) {
	raw, done := e.newLabel(), e.newLabel()
	e.b(0x5A)             // pop rdx
	e.b(0x48, 0x8B, 0x85) // mov rax,[rbp+cell]
	e.disp32(cell)
	e.b(0x48, 0x85, 0xC0)
	e.jcc(0x4, raw)
	e.b(0x48, 0x89, 0x50, 0x08) // mov [rax+8],rdx
	e.jmpLabel(done)
	e.bind(raw)
	e.b(0x48, 0x89, 0x95) // mov [rbp+local],rdx
	e.disp32(local)
	e.bind(done)
}

// DefineCapturedLocal pops a value into a fresh binding: the old cell (if any) stays with the
// closures that captured it, and the next capture creates a new one.
func (e *Emitter) DefineCapturedLocal(local, cell int) {
	e.b(0x5A)             // pop rdx
	e.b(0x48, 0xC7, 0x85) // mov qword [rbp+cell],0
	e.disp32(cell)
	e.i32(0)
	e.b(0x48, 0x89, 0x95) // mov [rbp+local],rdx
	e.disp32(local)
}

// GetUpvalue / SetUpvalue access capture `index` of the running closure through its environment.
func (e *Emitter) GetUpvalue(env, index int) {
	e.b(0x48, 0x8B, 0x85) // mov rax,[rbp+env]
	e.disp32(env)
	e.b(0x48, 0x8B, 0x80) // mov rax,[rax+16+8*index]  (cell)
	e.i32(int32(16 + 8*index))
	e.b(0x48, 0x8B, 0x40, 0x08) // mov rax,[rax+8]
	e.b(0x50)
}

func (e *Emitter) SetUpvalue(env, index int, ref bool) {
	e.b(0x5A)
	e.b(0x48, 0x8B, 0x85)
	e.disp32(env)
	e.b(0x48, 0x8B, 0x80)
	e.i32(int32(16 + 8*index))
	e.b(0x48, 0x89, 0x50, 0x08) // mov [rax+8],rdx
}

// captureLocalCell makes sure the cell of `local` exists (copying the current value).
func (e *Emitter) captureLocalCell(local, cell int, ref bool, refs []int32) {
	done := e.newLabel()
	e.b(0x48, 0x83, 0xBD) // cmp qword [rbp+cell],0
	e.disp32(cell)
	e.b(0x00)
	e.jcc(0x5, done)
	e.b(0x48, 0x8B, 0xB5) // mov rsi,[rbp+local]
	e.disp32(local)
	e.movImm(0xBA, boolInt(ref)) // mov edx,ref
	e.Safepoint(refs)
	e.rtCall(opCellNew)
	e.b(0x48, 0x89, 0x85) // mov [rbp+cell],rax
	e.disp32(cell)
	e.bind(done)
}

// NewClosure pushes a closure for function `id`. refs lists the live references at this point
// (including hidden slots); envOperand is the frame offset of the operand slot the environment
// temporarily occupies. cellSlots maps captured locals to their hidden cell slots; env is the
// hidden slot holding the running closure's environment (-1 when it has none).
func (e *Emitter) NewClosure(id, params int, returns bool, caps []Capture, cellSlots map[int]int, env int, refs []int32, envOperand int32) {
	for _, c := range caps {
		if c.Local {
			e.captureLocalCell(c.Index, cellSlots[c.Index], c.Reference, refs)
		}
	}
	withEnv := refs
	if len(caps) > 0 {
		for _, c := range caps {
			if c.Local {
				e.b(0x48, 0x8B, 0x85) // mov rax,[rbp+cell]
				e.disp32(cellSlots[c.Index])
			} else {
				e.b(0x48, 0x8B, 0x85) // mov rax,[rbp+env]
				e.disp32(env)
				e.b(0x48, 0x8B, 0x80) // mov rax,[rax+16+8*index]
				e.i32(int32(16 + 8*c.Index))
			}
			e.b(0x50)
		}
		e.movImm(0xBE, len(caps)) // mov esi,count
		e.b(0x48, 0x89, 0xE2)     // mov rdx,rsp
		e.Safepoint(refs)
		e.rtCall(opEnvNew)
		e.popN(len(caps))
		e.b(0x50) // the environment now occupies the next operand slot
		withEnv = append(append([]int32(nil), refs...), envOperand)
		e.b(0x4C, 0x8B, 0x04, 0x24) // mov r8,[rsp]
	} else {
		e.b(0x6A, 0x00)       // push 0
		e.b(0x4D, 0x31, 0xC0) // xor r8,r8
	}
	e.movImm(0xBE, id)                          // mov esi,function id
	e.movImm(0xBA, params|boolInt(returns)<<16) // mov edx,params|returns<<16
	e.b(0x48, 0x8D, 0x0D)                       // lea rcx,[rip+function]
	e.rel32(e.funcLabels[id])
	e.Safepoint(withEnv)
	e.rtCall(opClosureNew)
	e.popN(1) // drop the environment slot
	e.b(0x50) // push the closure
}

// CallValue calls the closure below `params` arguments. refs must exclude the closure and the
// arguments (the callee owns the arguments; it holds the environment in its own frame).
func (e *Emitter) CallValue(params int, returns bool, refs []int32) {
	e.b(0x48, 0x8B, 0x84, 0x24) // mov rax,[rsp+8*params]  (the closure)
	e.i32(int32(8 * params))
	e.b(0x48, 0x85, 0xC0) // test rax,rax
	e.jcc(0x4, e.failNil)
	e.b(0x49, 0xFF, 0xC7) // inc r15
	e.b(0x49, 0x81, 0xFF) // cmp r15,MaxCallDepth
	e.i32(MaxCallDepth)
	e.b(0x0F, 0x87) // ja errExit
	e.rel32(e.errExit)
	e.publishShadow(refs) // clobbers rax: reload the closure
	e.b(0x48, 0x8B, 0x84, 0x24)
	e.i32(int32(8 * params))
	e.b(0x4C, 0x8B, 0x50, 0x28) // mov r10,[rax+40]  (environment)
	e.b(0xFF, 0x50, 0x20)       // call [rax+32]
	if e.heap {
		e.record(refs)
	}
	e.b(0x49, 0xFF, 0xCF) // dec r15
	e.popN(1)             // the closure operand (the callee removed the arguments)
	if returns {
		e.b(0x50)
	}
}
