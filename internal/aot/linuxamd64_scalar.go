package aot

import (
	"fmt"
	"math"

	"Mio/internal/aot/linuxamd64"
	"Mio/internal/code"
	"Mio/internal/compiler"
	"Mio/internal/value"
)

func amd64FloatKind(k m6Kind) (int, bool) {
	switch k {
	case m6Float32:
		return linuxamd64.KindF32, true
	case m6Float64:
		return linuxamd64.KindF64, true
	}
	return 0, false
}

// compileLinuxAMD64Scalar lowers programs that need the M6 type analysis but
// only use scalar values: all fixed-width integers, bool, float32/float64,
// conversions, Math primitives, globals, locals and static function calls.
// Strings, arrays, structs, enums, nullables, closures and native-FS imports
// fail explicitly until their Linux runtime exists.
func compileLinuxAMD64Scalar(p *compiler.Bytecode, opts LinuxAMD64Options) ([]byte, error) {
	objects := usesM12Objects(p)
	for _, fn := range p.Functions {
		if _, ok := m14NativeName(fn.Name); ok {
			return nil, fmt.Errorf("linux-amd64: native file-system import %q is not implemented yet", fn.Name)
		}
	}
	a, err := analyzeM6(p)
	if err != nil {
		return nil, err
	}
	e := linuxamd64.New(p.GlobalsCount, len(p.Functions))
	if objects {
		capacity := opts.HeapCapacity
		if capacity == 0 {
			capacity = 1 << 20
		}
		e.EnableHeap(capacity, opts.GCStress)
		e.SetLegacyStackMaps(opts.LegacyStackMaps)
		e.SetRootMutation(opts.RootMutation)
		e.SetHeapDumpPath(opts.HeapDumpPath)
		e.SetMainRootCap(amd64RootCap(p, a.blocks[0]))
		refs := make([]bool, p.GlobalsCount)
		for i := range refs {
			refs[i] = m13ReferenceNode(a.u, a.globals[i])
		}
		e.SetGlobalRefs(refs)
	}
	stringIDs := make(map[int]int)
	var stringTable []string
	seen := make(map[string]int)
	for i, c := range p.Constants {
		if c.Kind() != value.KindString {
			continue
		}
		text, _ := c.Text()
		id, ok := seen[text]
		if !ok {
			id = len(stringTable)
			seen[text] = id
			stringTable = append(stringTable, text)
		}
		stringIDs[i] = id
	}
	e.SetStrings(stringTable)
	e.EmitEntry()
	for bi, b := range a.blocks {
		if bi == 0 {
			e.BeginBlock()
		} else {
			fn := b.fn
			rootCap := amd64RootCap(p, b)
			if !a.reachableFunctions[bi-1] {
				rootCap = 0
			}
			layout := amd64ClosureLayoutOf(p, b)
			e.BeginFunction(bi-1, fn.ParameterCount, fn.LocalCount+layout.hidden, fn.Name, rootCap)
			if a.reachableFunctions[bi-1] && layout.env >= 0 {
				e.SaveEnvironment(layout.env)
			}
			if !a.reachableFunctions[bi-1] {
				e.ReturnZeroStub()
				e.EndFunction()
				continue
			}
		}
		if err := lowerAMD64M6Block(e, p, a, bi, b, stringIDs, objects); err != nil {
			return nil, err
		}
		if bi == 0 {
			e.EmitMainEpilogue()
		} else {
			e.EndFunction()
		}
	}
	return e.Finish()
}

func lowerAMD64M6Block(e *linuxamd64.Emitter, p *compiler.Bytecode, a *m6Analysis, bi int, b *m6Block, stringIDs map[int]int, objects bool) error {
	locals := 0
	layout := amd64ClosureLayoutOf(p, b)
	if b.fn != nil {
		locals = b.fn.LocalCount + layout.hidden
	}
	// Hidden slots (environment, cells) are always published as roots: they are nil or live objects.
	hiddenRefs := func() []int32 {
		var out []int32
		if b.fn == nil {
			return out
		}
		for slot := b.fn.LocalCount; slot < locals; slot++ {
			out = append(out, int32(-8*(slot+1)))
		}
		return out
	}
	// Frame layout (rbp-relative): locals, then the shadow record, then the
	// operand stack. Operand slot d lives at -8*(frameBase+d+1).
	frameBase := locals
	if objects {
		frameBase += linuxamd64.RecordSlots(amd64RootCap(p, b))
	}
	for i, ins := range b.inst {
		e.MarkOffset(ins.offset)
		if b.reach[i] == nil {
			continue
		}
		// Operand slots unboxed in place by this instruction hold raw scalars now:
		// they are no longer references and must not appear in its stack map.
		rawSlots := map[int]bool{}
		// Call safepoints: the arguments belong to the callee (it copies them into its
		// own locals before any safepoint), exactly like the ARM64 caller record.
		skipTop := 0
		refs := func() []int32 {
			var out []int32
			if bi > 0 {
				for slot := 0; slot < locals && slot < len(a.locals[bi-1]); slot++ {
					if m13ReferenceNode(a.u, a.locals[bi-1][slot]) {
						out = append(out, int32(-8*(slot+1)))
					}
				}
			}
			out = append(out, hiddenRefs()...)
			for d, node := range b.entry[i][:len(b.entry[i])-skipTop] {
				if m13ReferenceNode(a.u, node) && !rawSlots[d] {
					out = append(out, int32(-8*(frameBase+d+1)))
				}
			}
			return out
		}
		st := b.endKind[i]
		k := m6Unknown
		if len(st) != 0 {
			k = st[len(st)-1]
		}
		var err error
		// Nullable scalars are GC boxes (as on ARM64); consumers unbox in place.
		unbox := func(slot int) {
			node := b.entry[i][slot]
			top := len(b.entry[i]) - 1 - slot
			if a.u.isNullable(node) && m13BoxedKind(a.u.get(node)) {
				e.UnboxNullable(top)
				rawSlots[slot] = true
			} else if m13BoxedKind(a.u.get(node)) {
				e.UnboxScalar(top)
			}
		}
		if objects {
			n := len(b.entry[i])
			switch ins.op {
			case code.OpNot, code.OpNeg, code.OpIntToFloat, code.OpFloatToInt,
				code.OpIntToFloat32, code.OpFloat32ToInt, code.OpFloat32ToFloat64,
				code.OpFloat64ToFloat32, code.OpIntegerConvert, code.OpMath,
				code.OpJumpIfFalse, code.OpChant, code.OpLen, code.OpIndex,
				code.OpArrayWithCapacity, code.OpArrayReserve, code.OpArrayTruncate:
				unbox(n - 1)
			case code.OpArrayMake, code.OpSetIndex, code.OpSetNullableIndex:
				unbox(n - 2)
			case code.OpAdd, code.OpSub, code.OpMul, code.OpDiv, code.OpEqual,
				code.OpNotEqual, code.OpLess, code.OpLessEqual, code.OpGreater, code.OpGreaterEqual:
				unbox(n - 2)
				unbox(n - 1)
			}
		}
		boxesResult := objects && len(b.exit[i]) != 0 && m13RawProducer(ins.op) &&
			a.u.isNullable(b.exit[i][len(b.exit[i])-1]) && m13BoxedKind(a.u.get(b.exit[i][len(b.exit[i])-1]))
		switch ins.op {
		case code.OpConstant:
			v := p.Constants[ins.operands[0]]
			switch m6ValueKind(v) {
			case m6Int, m6Int8, m6Int16, m6Int32, m6Uint8, m6Uint16, m6Uint32:
				n, _ := v.IntegerBits()
				e.PushInt64(int64(n))
			case m6Float64:
				n, _ := v.Float64()
				e.PushInt64(int64(math.Float64bits(n)))
			case m6Float32:
				n, _ := v.Float32()
				e.PushInt64(int64(math.Float32bits(n)))
			case m6Bool:
				n, _ := v.Bool()
				e.PushBool(n)
			case m6String:
				e.PushStringID(stringIDs[ins.operands[0]])
			default:
				err = fmt.Errorf("constant of type %s is not implemented yet", v.Kind())
			}
		case code.OpTrue:
			e.PushBool(true)
		case code.OpFalse:
			e.PushBool(false)
		case code.OpSetGlobal:
			err = e.SetGlobal(ins.operands[0])
		case code.OpGetGlobal:
			err = e.GetGlobal(ins.operands[0])
		case code.OpSetLocal, code.OpDefineLocal:
			if cell, captured := layout.cells[ins.operands[0]]; captured {
				if ins.op == code.OpDefineLocal {
					e.DefineCapturedLocal(ins.operands[0], cell)
				} else {
					e.SetCapturedLocal(ins.operands[0], cell, m13ReferenceNode(a.u, a.locals[bi-1][ins.operands[0]]))
				}
			} else {
				e.SetLocal(ins.operands[0])
			}
		case code.OpGetLocal:
			if cell, captured := layout.cells[ins.operands[0]]; captured {
				e.GetCapturedLocal(ins.operands[0], cell)
			} else {
				e.GetLocal(ins.operands[0])
			}
		case code.OpGetUpvalue:
			if layout.env < 0 {
				err = fmt.Errorf("upvalue %d outside a closure", ins.operands[0])
			} else {
				e.GetUpvalue(layout.env, ins.operands[0])
			}
		case code.OpSetUpvalue:
			if layout.env < 0 {
				err = fmt.Errorf("upvalue %d outside a closure", ins.operands[0])
			} else {
				e.SetUpvalue(layout.env, ins.operands[0], m13ReferenceNode(a.u, a.captures[bi-1][ins.operands[0]]))
			}
		case code.OpFunction, code.OpClosure:
			target := ins.operands[0]
			captures := make([]linuxamd64.Capture, len(p.Functions[target].Captures))
			for ci, capture := range p.Functions[target].Captures {
				captures[ci] = linuxamd64.Capture{Local: capture.Local, Index: capture.Index, Reference: m13ReferenceNode(a.u, a.captures[target][ci])}
			}
			e.NewClosure(target, p.Functions[target].ParameterCount, p.Functions[target].ReturnsValue, captures,
				layout.cells, layout.env, refs(), int32(-8*(frameBase+len(b.entry[i])+1)))
		case code.OpCallValue:
			params := ins.operands[0]
			targets := a.u.functionTargets(b.entry[i][len(b.entry[i])-params-1])
			if len(targets) == 0 {
				err = fmt.Errorf("unknown function value")
				break
			}
			skipTop = params + 1
			callRefs := refs()
			skipTop = 0
			e.CallValue(params, p.Functions[targets[0]].ReturnsValue, callRefs)
		case code.OpNot:
			e.Not()
		case code.OpAdd, code.OpSub, code.OpMul, code.OpDiv:
			if m6IntegerKind(k) {
				switch ins.op {
				case code.OpAdd:
					e.Add()
				case code.OpSub:
					e.Sub()
				case code.OpMul:
					e.Mul()
				case code.OpDiv:
					e.DivInt(m6UnsignedKind(k))
				}
				err = e.Normalize(m6IntegerWidth(k), !m6UnsignedKind(k))
			} else if fk, ok := amd64FloatKind(k); ok {
				err = e.FloatBinary(fk, int(ins.op))
			} else {
				err = fmt.Errorf("%s on %s is not implemented yet", ins.name, k)
			}
		case code.OpNeg:
			if m6IntegerKind(k) {
				e.Neg()
				err = e.Normalize(m6IntegerWidth(k), true)
			} else if fk, ok := amd64FloatKind(k); ok {
				e.FloatNeg(fk)
			} else {
				err = fmt.Errorf("neg on %s is not implemented yet", k)
			}
		case code.OpEqual, code.OpNotEqual, code.OpLess, code.OpLessEqual, code.OpGreater, code.OpGreaterEqual:
			left := st[len(st)-2]
			if fk, ok := amd64FloatKind(left); ok {
				err = e.FloatCompare(fk, int(ins.op))
				break
			}
			if left == m6String {
				if ins.op != code.OpEqual && ins.op != code.OpNotEqual {
					err = fmt.Errorf("ordering comparison of strings is not implemented yet")
					break
				}
				e.StringCompare(ins.op == code.OpNotEqual)
				break
			}
			uns := m6UnsignedKind(left)
			var cond byte
			switch ins.op {
			case code.OpEqual:
				cond = linuxamd64.CondEQ
			case code.OpNotEqual:
				cond = linuxamd64.CondNE
			case code.OpLess:
				cond = pick(uns, linuxamd64.CondB, linuxamd64.CondLT)
			case code.OpLessEqual:
				cond = pick(uns, linuxamd64.CondBE, linuxamd64.CondLE)
			case code.OpGreater:
				cond = pick(uns, linuxamd64.CondA, linuxamd64.CondGT)
			case code.OpGreaterEqual:
				cond = pick(uns, linuxamd64.CondAE, linuxamd64.CondGE)
			}
			e.Compare(cond)
		case code.OpIntToFloat, code.OpIntToFloat32, code.OpFloatToInt,
			code.OpFloat32ToInt, code.OpFloat32ToFloat64, code.OpFloat64ToFloat32:
			err = e.FloatConvert(int(ins.op))
		case code.OpIntegerConvert:
			if k == m6Float32 || k == m6Float64 {
				op := linuxamd64.OpFloat64ToInt
				if k == m6Float32 {
					op = linuxamd64.OpFloat32ToInt
				}
				err = e.FloatConvert(op)
			}
			if err == nil {
				err = e.IntegerConvert(m6UnsignedKind(k), ins.operands[0])
			}
		case code.OpMath:
			err = lowerAMD64Math(e, ins.operands[0], k)
		case code.OpLen:
			if k == m6String {
				e.StringLen()
			} else {
				e.ArrayLen()
			}
		case code.OpArray, code.OpArrayTyped:
			count := ins.operands[0]
			elementKind := m6Unknown
			nullable := ins.op == code.OpArrayTyped && ins.operands[1]&0x80 != 0
			if count > 0 {
				node := b.entry[i][len(st)-count]
				elementKind, nullable = a.u.get(node), a.u.isNullable(node)
			} else if ins.op == code.OpArrayTyped {
				elementKind = m12DescriptorKind(ins.operands[1])
			}
			if elementKind == m6Unknown {
				elementKind = m6Int
			}
			e.Safepoint(refs())
			e.ArrayLiteral(m13ElementBytes(elementKind, nullable), m13StoredReference(elementKind, nullable), count)
		case code.OpArrayMake:
			elementKind := m12DescriptorKind(ins.operands[0])
			nullable := ins.operands[0]&0x80 != 0
			if elementKind == m6Unknown {
				node := b.entry[i][len(st)-1]
				elementKind, nullable = a.u.get(node), a.u.isNullable(node)
			}
			err = lowerAMD64ArrayOp(e, code.OpArrayMake, elementKind, nullable, refs)
		case code.OpArrayWithCapacity:
			elementKind := m12DescriptorKind(ins.operands[0])
			nullable := ins.operands[0]&0x80 != 0
			if elementKind == m6Unknown {
				next := b.boundaries[ins.next]
				if next < len(b.entry) && len(b.entry[next]) != 0 {
					elementKind = a.u.arrayElementKind(b.entry[next][len(b.entry[next])-1])
				}
				if elementKind == m6Unknown {
					elementKind = m6Int
				}
			}
			if len(b.exit[i]) != 0 {
				nullable = a.u.arrayElementNullable(b.exit[i][len(b.exit[i])-1])
			}
			err = lowerAMD64ArrayOp(e, code.OpArrayWithCapacity, elementKind, nullable, refs)
		case code.OpArrayPush, code.OpArrayReserve, code.OpArrayTruncate, code.OpArrayAppendAll:
			node := b.entry[i][len(b.entry[i])-2]
			err = lowerAMD64ArrayOpOn(e, a, ins.op, node, refs)
		case code.OpArrayCapacity, code.OpArrayClone:
			node := b.entry[i][len(b.entry[i])-1]
			err = lowerAMD64ArrayOpOn(e, a, ins.op, node, refs)
		case code.OpIndex:
			node := b.entry[i][len(b.entry[i])-2]
			kind, nullable := a.u.arrayElementKind(node), a.u.arrayElementNullable(node)
			if kind == m6Unknown {
				err = fmt.Errorf("unknown array element type")
				break
			}
			e.ArrayIndex(m13ElementBytes(kind, nullable))
		case code.OpSetIndex, code.OpSetNullableIndex:
			node := b.entry[i][len(b.entry[i])-3]
			kind, nullable := a.u.arrayElementKind(node), a.u.arrayElementNullable(node)
			if kind == m6Unknown {
				err = fmt.Errorf("unknown array element type")
				break
			}
			e.ArraySetIndex(m13ElementBytes(kind, nullable), m13StoredReference(kind, nullable))
		case code.OpStruct:
			count := ins.operands[0]
			bitmap := make([]uint64, (count+63)/64)
			for field, node := range b.entry[i][len(st)-count:] {
				if m13ReferenceNode(a.u, node) {
					bitmap[field/64] |= uint64(1) << uint(field%64)
				}
			}
			e.Safepoint(refs())
			e.NewStruct(count, bitmap)
		case code.OpGetField:
			node := b.entry[i][len(b.entry[i])-1]
			if a.u.isNullable(node) {
				e.NilCheckTop()
			}
			e.GetField(ins.operands[0], a.u.structFieldCount(node))
		case code.OpNil:
			e.PushInt64(0)
		case code.OpIsNil:
			node := b.entry[i][len(b.entry[i])-1]
			e.IsNil(a.u.get(node) == m6Nil || a.u.isNullable(node))
		case code.OpEnum:
			count := ins.operands[1]
			bitmap := make([]uint64, (count+63)/64)
			for payload, node := range b.entry[i][len(st)-count:] {
				if m13ReferenceNode(a.u, node) {
					bitmap[payload/64] |= uint64(1) << uint(payload%64)
				}
			}
			e.Safepoint(refs())
			e.NewEnum(ins.operands[0], count, bitmap)
		case code.OpEnumTag:
			node := b.entry[i][len(b.entry[i])-1]
			if a.u.isNullable(node) {
				e.NilCheckTop()
			}
			e.EnumTag()
		case code.OpGetEnumValue:
			enumNode := b.entry[i][len(b.entry[i])-1]
			tag := -1
			if narrowed, ok := b.enumTags[ins.offset]; ok {
				tag = narrowed
			}
			_, count, fieldErr := a.u.enumValue(enumNode, tag, ins.operands[0])
			if fieldErr != nil {
				err = fieldErr
				break
			}
			if a.u.isNullable(enumNode) {
				e.NilCheckTop()
			}
			e.GetEnumValue(ins.operands[0], count)
		case code.OpJump:
			e.Jump(ins.operands[0])
		case code.OpJumpIfFalse:
			e.JumpIfFalse(ins.operands[0])
		case code.OpChant:
			if k == m6Nil {
				e.ChantNil()
			} else if k == m6String {
				e.ChantString()
			} else if fk, ok := amd64FloatKind(k); ok {
				e.ChantFloat(fk)
			} else if k == m6Bool || m6IntegerKind(k) || k == m6Int {
				e.Chant(k == m6Bool)
			} else if k == m6Array || k == m6Struct || k == m6Enum {
				err = fmt.Errorf("M12 cannot chant composite value")
			} else {
				err = fmt.Errorf("chant of %s is not implemented yet", k)
			}
		case code.OpPop:
			node := b.entry[i][len(b.entry[i])-1]
			switch {
			case bi != 0:
				e.Discard()
			case k == m6Nil:
				e.PopMainNil()
			case a.u.isNullable(node) && m13BoxedKind(k):
				e.PopNullableMain(m13OutputKind(k))
			case k == m6String:
				e.PopMainKind(linuxamd64.KindString)
			case k == m6Float32:
				e.PopMainKind(linuxamd64.KindF32)
			case k == m6Float64:
				e.PopMainKind(linuxamd64.KindF64)
			case k == m6Bool:
				e.PopMainKind(linuxamd64.KindBool)
			case m6IntegerKind(k) || k == m6Int:
				e.PopMainKind(linuxamd64.KindInt)
			case k == m6Array || k == m6Struct || k == m6Enum:
				err = fmt.Errorf("M12 cannot print composite expression result")
			default:
				err = fmt.Errorf("pop of %s is not implemented yet", k)
			}
		case code.OpCall:
			target := ins.operands[0]
			if prim, generic := a.genericMathWrapper[target]; generic {
				err = lowerAMD64Math(e, prim, a.u.get(b.entry[i][len(b.entry[i])-1]))
			} else {
				if op, wrapper := a.genericArrayWrapper[target]; wrapper {
					err = lowerAMD64ArrayWrapper(e, a, b, i, op, refs)
					break
				}
				callee := p.Functions[target]
				skipTop = callee.ParameterCount
				e.Safepoint(refs())
				skipTop = 0
				e.Call(target, callee.ParameterCount, callee.ReturnsValue)
			}
		case code.OpDataConvert:
			switch ins.operands[0] {
			case code.DataStringToBytes:
				e.StringToBytes(refs())
			case code.DataBytesToString:
				e.BytesToString(refs())
			default:
				err = fmt.Errorf("unknown data conversion %d", ins.operands[0])
			}
		case code.OpReturn:
			e.ReturnUnit()
		case code.OpReturnValue:
			e.ReturnValue()
		default:
			err = fmt.Errorf("opcode %s is not implemented yet", ins.name)
		}
		if err == nil && boxesResult {
			exit := b.exit[i]
			var out []int32
			if bi > 0 {
				for slot := 0; slot < locals && slot < len(a.locals[bi-1]); slot++ {
					if m13ReferenceNode(a.u, a.locals[bi-1][slot]) {
						out = append(out, int32(-8*(slot+1)))
					}
				}
			}
			out = append(out, hiddenRefs()...)
			for d, node := range exit[:len(exit)-1] { // the raw top slot is not a reference yet
				if m13ReferenceNode(a.u, node) {
					out = append(out, int32(-8*(frameBase+d+1)))
				}
			}
			e.Safepoint(out)
			e.BoxTop()
		}
		if err != nil {
			return fmt.Errorf("linux-amd64 %s at byte offset %d: %w", b.name, ins.offset, err)
		}
	}
	end := len(p.Instructions)
	if b.fn != nil {
		end = len(b.fn.Instructions)
	}
	e.MarkOffset(end)
	return nil
}

func pick(unsigned bool, u, s byte) byte {
	if unsigned {
		return u
	}
	return s
}

func lowerAMD64Math(e *linuxamd64.Emitter, primitive int, k m6Kind) error {
	switch primitive {
	case code.MathSqrt, code.MathFloor, code.MathCeil, code.MathRoundEven, code.MathTrunc:
		fk, ok := amd64FloatKind(k)
		if !ok {
			return fmt.Errorf("math primitive %d requires float32/float64, got %s", primitive, k)
		}
		return e.MathFloatUnary(fk, primitive)
	case code.MathIsNaN, code.MathIsInf, code.MathIsFinite:
		fk, ok := amd64FloatKind(k)
		if !ok {
			return fmt.Errorf("math predicate %d on %s (polymorphic float) is not implemented yet", primitive, k)
		}
		return e.MathFloatPredicate(fk, primitive)
	case code.MathIsNegative, code.MathNegOverflows:
		floating := k == m6Float32 || k == m6Float64
		width := m6IntegerWidth(k)
		if floating {
			width = 64
			if k == m6Float32 {
				width = 32
			}
		}
		e.MathSign(width, !m6UnsignedKind(k), floating, primitive == code.MathNegOverflows)
		return nil
	case code.MathError:
		e.MathError()
		return nil
	}
	return fmt.Errorf("unsupported math primitive %d", primitive)
}

var _ = value.KindInt

func lowerAMD64ArrayOpOn(e *linuxamd64.Emitter, a *m6Analysis, op code.Opcode, arrayNode int, refs func() []int32) error {
	kind := a.u.arrayElementKind(arrayNode)
	if kind == m6Unknown {
		return fmt.Errorf("unknown array element type")
	}
	return lowerAMD64ArrayOp(e, op, kind, a.u.arrayElementNullable(arrayNode), refs)
}

func lowerAMD64ArrayOp(e *linuxamd64.Emitter, op code.Opcode, kind m6Kind, nullable bool, refs func() []int32) error {
	width, ref := m13ElementBytes(kind, nullable), m13StoredReference(kind, nullable)
	if op != code.OpArrayCapacity {
		e.Safepoint(refs())
	}
	switch op {
	case code.OpArrayMake:
		e.ArrayMake(width, ref)
	case code.OpArrayWithCapacity:
		e.ArrayWithCapacity(width, ref)
	case code.OpArrayPush:
		e.ArrayPush()
	case code.OpArrayReserve:
		e.ArrayReserve()
	case code.OpArrayTruncate:
		e.ArrayTruncate()
	case code.OpArrayAppendAll:
		e.ArrayAppendAll()
	case code.OpArrayCapacity:
		e.ArrayCapacity()
	case code.OpArrayClone:
		e.ArrayClone()
	default:
		return fmt.Errorf("unsupported array operation %d", op)
	}
	return nil
}

// lowerAMD64ArrayWrapper lowers the generic kiso/array forwarding functions at
// each static call site, exactly like the equivalent bytecode instruction.
func lowerAMD64ArrayWrapper(e *linuxamd64.Emitter, a *m6Analysis, b *m6Block, i int, op code.Opcode, refs func() []int32) error {
	switch op {
	case code.OpArrayMake:
		element := b.entry[i][len(b.entry[i])-1]
		return lowerAMD64ArrayOp(e, op, a.u.get(element), a.u.isNullable(element), refs)
	case code.OpArrayWithCapacity:
		return lowerAMD64ArrayOpOn(e, a, op, b.exit[i][len(b.exit[i])-1], refs)
	case code.OpArrayPush, code.OpArrayReserve, code.OpArrayTruncate, code.OpArrayAppendAll:
		return lowerAMD64ArrayOpOn(e, a, op, b.entry[i][len(b.entry[i])-2], refs)
	default:
		return lowerAMD64ArrayOpOn(e, a, op, b.entry[i][len(b.entry[i])-1], refs)
	}
}

// amd64RootCap bounds the number of frame roots one safepoint can publish:
// every local plus the deepest reachable operand stack. Globals are covered by
// the static indirect global record and never occupy frame space.
func amd64RootCap(p *compiler.Bytecode, b *m6Block) int {
	locals, depth := 0, 0
	if b.fn != nil {
		locals = b.fn.LocalCount + amd64ClosureLayoutOf(p, b).hidden
	}
	for _, st := range b.reach {
		if st != nil && st.depth > depth {
			depth = st.depth
		}
	}
	return locals + depth
}

// amd64ClosureLayout describes the hidden frame slots of a function that has upvalues or whose
// locals are captured by inner closures: the environment slot first, then one cell slot per
// captured local (slot numbers continue after the ordinary locals).
type amd64ClosureLayout struct {
	env    int
	cells  map[int]int
	hidden int
}

func amd64ClosureLayoutOf(p *compiler.Bytecode, b *m6Block) amd64ClosureLayout {
	l := amd64ClosureLayout{env: -1, cells: map[int]int{}}
	if b.fn == nil {
		return l
	}
	next := b.fn.LocalCount
	if len(b.fn.Captures) != 0 {
		l.env = next
		next++
	}
	for _, local := range m15CapturedLocals(p, b) {
		l.cells[local] = next
		next++
	}
	l.hidden = next - b.fn.LocalCount
	return l
}
