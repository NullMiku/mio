// Package linuxamd64 generates Linux x86_64 (System V AMD64) native
// executables. It is an independent sibling of darwinarm64: nothing here
// touches the macOS ARM64 backend.
package linuxamd64

import (
	"encoding/binary"
	"fmt"
)

const (
	pageSize       uint64 = 0x1000
	imageBase      uint64 = 0x400000
	ehdrSize              = 64
	phdrSize              = 56
	shdrSize              = 64
	phdrCount             = 3 // PT_LOAD(RX), PT_LOAD(RW bss), PT_GNU_STACK
	codeFileOff           = 0x1000
	MaxGlobalSlots        = 1 << 20

	// dataBase is the fixed virtual address of the RW segment: runtime state
	// (4 KiB) followed by the global slots. A fixed address lets the
	// position-independent runtime reach its state without relocations.
	dataBase  uint64 = 0x10000000
	stateSize        = 4096
)

// Symbol names a function entry inside the text segment.
type Symbol struct {
	Name   string
	Offset int // offset inside code
	Size   int
}

// buildELF wraps code into an ELF64 ET_EXEC image. Layout:
//
//	0x000000 ELF header + program headers (inside the RX segment)
//	0x001000 code (entry point = code[entry])
//	...      .symtab/.strtab/.shstrtab/section headers (not loaded)
//	data     one RW PT_LOAD with filesz 0 and memsz = bssSize (globals)
func buildELF(codeBytes []byte, entry int, bssSize uint64, symbols []Symbol) ([]byte, uint64) {
	textVA := imageBase + codeFileOff
	textEnd := codeFileOff + uint64(len(codeBytes))
	loadSize := textEnd
	bssVA := dataBase
	if bssSize == 0 {
		bssSize = 0
	}

	// string tables
	shstr := []byte{0}
	addStr := func(tab *[]byte, s string) uint32 {
		off := uint32(len(*tab))
		*tab = append(*tab, s...)
		*tab = append(*tab, 0)
		return off
	}
	nText := addStr(&shstr, ".text")
	nBss := addStr(&shstr, ".bss")
	nSym := addStr(&shstr, ".symtab")
	nStr := addStr(&shstr, ".strtab")
	nShstr := addStr(&shstr, ".shstrtab")

	strtab := []byte{0}
	symtab := make([]byte, 24) // null symbol
	for _, s := range symbols {
		var ent [24]byte
		binary.LittleEndian.PutUint32(ent[0:], addStr(&strtab, s.Name))
		ent[4] = 0x12 // GLOBAL FUNC
		binary.LittleEndian.PutUint16(ent[6:], 1)
		binary.LittleEndian.PutUint64(ent[8:], textVA+uint64(s.Offset))
		binary.LittleEndian.PutUint64(ent[16:], uint64(s.Size))
		symtab = append(symtab, ent[:]...)
	}
	symOff := (textEnd + 7) &^ 7
	strOff := symOff + uint64(len(symtab))
	shstrOff := strOff + uint64(len(strtab))
	shOff := (shstrOff + uint64(len(shstr)) + 7) &^ 7
	const nSections = 6 // null,.text,.bss,.symtab,.strtab,.shstrtab
	total := shOff + nSections*shdrSize

	out := make([]byte, total)
	le := binary.LittleEndian
	copy(out, []byte{0x7f, 'E', 'L', 'F', 2, 1, 1, 0})
	le.PutUint16(out[16:], 2)  // ET_EXEC
	le.PutUint16(out[18:], 62) // EM_X86_64
	le.PutUint32(out[20:], 1)
	le.PutUint64(out[24:], textVA+uint64(entry))
	le.PutUint64(out[32:], ehdrSize)
	le.PutUint64(out[40:], shOff)
	le.PutUint16(out[52:], ehdrSize)
	le.PutUint16(out[54:], phdrSize)
	le.PutUint16(out[56:], phdrCount)
	le.PutUint16(out[58:], shdrSize)
	le.PutUint16(out[60:], nSections)
	le.PutUint16(out[62:], 5) // shstrndx

	ph := func(i int, typ, flags uint32, off, va, filesz, memsz, align uint64) {
		p := out[ehdrSize+i*phdrSize:]
		le.PutUint32(p[0:], typ)
		le.PutUint32(p[4:], flags)
		le.PutUint64(p[8:], off)
		le.PutUint64(p[16:], va)
		le.PutUint64(p[24:], va)
		le.PutUint64(p[32:], filesz)
		le.PutUint64(p[40:], memsz)
		le.PutUint64(p[48:], align)
	}
	ph(0, 1, 5, 0, imageBase, loadSize, loadSize, pageSize) // R+X
	ph(1, 1, 6, 0, bssVA, 0, bssSize, pageSize)             // R+W, zero filled
	ph(2, 0x6474e551, 6, 0, 0, 0, 0, 16)                    // GNU_STACK: RW, non-exec
	copy(out[codeFileOff:], codeBytes)
	copy(out[symOff:], symtab)
	copy(out[strOff:], strtab)
	copy(out[shstrOff:], shstr)

	sh := func(i int, name, typ uint32, flags, addr, off, size uint64, link, info uint32, align, entsize uint64) {
		p := out[shOff+uint64(i)*shdrSize:]
		le.PutUint32(p[0:], name)
		le.PutUint32(p[4:], typ)
		le.PutUint64(p[8:], flags)
		le.PutUint64(p[16:], addr)
		le.PutUint64(p[24:], off)
		le.PutUint64(p[32:], size)
		le.PutUint32(p[40:], link)
		le.PutUint32(p[44:], info)
		le.PutUint64(p[48:], align)
		le.PutUint64(p[56:], entsize)
	}
	sh(1, nText, 1, 6, textVA, codeFileOff, uint64(len(codeBytes)), 0, 0, 16, 0)
	sh(2, nBss, 8, 3, bssVA, textEnd, bssSize, 0, 0, 8, 0)
	sh(3, nSym, 2, 0, 0, symOff, uint64(len(symtab)), 4, 1, 8, 24)
	sh(4, nStr, 3, 0, 0, strOff, uint64(len(strtab)), 0, 0, 1, 0)
	sh(5, nShstr, 3, 0, 0, shstrOff, uint64(len(shstr)), 0, 0, 1, 0)
	return out, bssVA
}

func checkELFInputs(code []byte, globals int) error {
	if len(code) == 0 {
		return fmt.Errorf("empty x86_64 instruction stream")
	}
	if globals < 0 || globals > MaxGlobalSlots {
		return fmt.Errorf("AOT global slot count %d exceeds limit %d", globals, MaxGlobalSlots)
	}
	return nil
}
