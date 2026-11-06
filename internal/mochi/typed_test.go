package mochi

import (
	"bytes"
	"encoding/binary"
	"strings"
	"testing"

	"Mio/internal/code"
	"Mio/internal/compiler"
)

// typedProgram mirrors what the pure-Mio front end emits in typed mode
// (`mio build --emit=mochi`): a v15 type constraint and a v16 typed function value call.
func typedProgram(t *testing.T, returns int) *compiler.Bytecode {
	t.Helper()
	return &compiler.Bytecode{
		Constants:    nil,
		GlobalsCount: 0,
		Instructions: joinInstructions(t,
			mustInstruction(t, code.OpFunction, 0),
			mustInstruction(t, code.OpTypeConstraint, 11),
			mustInstruction(t, code.OpCallTyped, 0, returns),
			mustInstruction(t, code.OpPop),
		),
		Functions: []compiler.CompiledFunction{{ID: 0, Name: "answer", ReturnsValue: true, Instructions: joinInstructions(t,
			mustInstruction(t, code.OpTrue), mustInstruction(t, code.OpReturnValue))}},
	}
}

// Mochi v16 (pure-Mio typed mode) round-trips with its header version intact.
func TestMochiV16TypedRoundTrip(t *testing.T) {
	decoded, encoded := roundTrip(t, typedProgram(t, 1))
	if version := binary.BigEndian.Uint16(encoded[5:7]); version != VersionV16 {
		t.Fatalf("version=%d, want %d", version, VersionV16)
	}
	if !bytes.Equal(decoded.Instructions, typedProgram(t, 1).Instructions) {
		t.Fatalf("instructions=%v", decoded.Instructions)
	}
}

// A type constraint alone selects v15; programs without typed opcodes keep their old version.
func TestMochiV15AndOlderVersionsUnchanged(t *testing.T) {
	bytecode := &compiler.Bytecode{Instructions: joinInstructions(t, mustInstruction(t, code.OpTrue), mustInstruction(t, code.OpTypeConstraint, 4), mustInstruction(t, code.OpPop))}
	_, encoded := roundTrip(t, bytecode)
	if version := binary.BigEndian.Uint16(encoded[5:7]); version != VersionV15 {
		t.Fatalf("version=%d, want %d", version, VersionV15)
	}
	plain := &compiler.Bytecode{Instructions: joinInstructions(t, mustInstruction(t, code.OpTrue), mustInstruction(t, code.OpPop))}
	_, encoded = roundTrip(t, plain)
	if version := binary.BigEndian.Uint16(encoded[5:7]); version != VersionV2 {
		t.Fatalf("plain version=%d, want %d", version, VersionV2)
	}
}

// The typed opcodes follow bunko/kiso/encoding/mochi: version gates and operand checks.
func TestRejectInvalidTypedInstructions(t *testing.T) {
	tests := []struct {
		name    string
		mutate  func(*compiler.Bytecode)
		version uint16
		want    string
	}{
		{"call typed below v16", func(*compiler.Bytecode) {}, VersionV15, "requires Mochi v16"},
		{"constraint below v15", func(b *compiler.Bytecode) {
			b.Instructions = joinInstructions(t, mustInstruction(t, code.OpTrue), mustInstruction(t, code.OpTypeConstraint, 4), mustInstruction(t, code.OpPop))
		}, VersionV14, "requires Mochi v15"},
		{"result flag", func(b *compiler.Bytecode) { b.Instructions[8] = 2 }, VersionV16, "invalid typed call result flag 2"},
		{"zero descriptor", func(b *compiler.Bytecode) { b.Instructions[4] = 0 }, VersionV16, "invalid type constraint descriptor 0"},
		{"nil descriptor", func(b *compiler.Bytecode) { b.Instructions[4] = 6 }, VersionV16, "invalid type constraint descriptor 6"},
		{"nullable flag descriptor", func(b *compiler.Bytecode) { b.Instructions[4] = 0x81 }, VersionV16, "invalid type constraint descriptor 129"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			bytecode := typedProgram(t, 1)
			test.mutate(bytecode)
			err := validateVersion(bytecode, test.version)
			if err == nil || !strings.Contains(err.Error(), test.want) {
				t.Fatalf("err=%v, want %q", err, test.want)
			}
		})
	}
}

// Decode accepts v16 headers and still rejects versions above it.
func TestDecodeVersionRange(t *testing.T) {
	_, encoded := roundTrip(t, typedProgram(t, 1))
	future := append([]byte(nil), encoded...)
	binary.BigEndian.PutUint16(future[5:7], VersionV16+1)
	if _, err := Decode(bytes.NewReader(future)); err == nil || !strings.Contains(err.Error(), "unsupported format version 17") {
		t.Fatalf("err=%v", err)
	}
	downgraded := append([]byte(nil), encoded...)
	binary.BigEndian.PutUint16(downgraded[5:7], VersionV14)
	if _, err := Decode(bytes.NewReader(downgraded)); err == nil || !strings.Contains(err.Error(), "requires Mochi v15") {
		t.Fatalf("err=%v", err)
	}
}
