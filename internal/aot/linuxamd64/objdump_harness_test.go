package linuxamd64

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"testing"
)

// requireGNUObjdump skips the test, with a reason, unless a GNU objdump is on PATH. A skipped
// test means the emitted instructions were NOT independently checked.
func requireGNUObjdump(t *testing.T) {
	t.Helper()
	path, err := exec.LookPath("objdump")
	if err != nil {
		t.Skip("SKIP: GNU objdump not found (objdump is not on PATH); emitted instructions not independently verified")
	}
	out, err := exec.Command(path, "--version").Output()
	first := ""
	if err == nil {
		first, _, _ = strings.Cut(string(out), "\n")
	}
	if err != nil || !strings.Contains(first, "GNU objdump") {
		t.Skipf("SKIP: GNU objdump not found (%s is %q); emitted instructions not independently verified", path, first)
	}
}

// disInsn is one disassembled instruction.
type disInsn struct {
	addr uint64
	text string // "mnemonic operands", single spaces, no comment
	note string // objdump's trailing "# addr <sym>" comment, if any
}

var (
	disLine   = regexp.MustCompile(`^\s*([0-9a-f]+):\t(.*)$`)
	spaceRuns = regexp.MustCompile(`\s+`)
)

// disassemble writes image to a temporary file and returns objdump -d -M intel output for .text.
func disassemble(t *testing.T, image []byte) []disInsn {
	t.Helper()
	path := filepath.Join(t.TempDir(), "image.elf")
	if err := os.WriteFile(path, image, 0o755); err != nil {
		t.Fatal(err)
	}
	out, err := exec.Command("objdump", "-d", "-M", "intel", "--no-show-raw-insn", path).CombinedOutput()
	if err != nil {
		t.Fatalf("objdump failed: %v\n%s", err, out)
	}
	var insns []disInsn
	for _, line := range strings.Split(string(out), "\n") {
		m := disLine.FindStringSubmatch(line)
		if m == nil {
			continue
		}
		addr, _ := strconv.ParseUint(m[1], 16, 64)
		body, note, _ := strings.Cut(m[2], "#")
		insns = append(insns, disInsn{addr: addr, text: strings.TrimSpace(spaceRuns.ReplaceAllString(body, " ")), note: strings.TrimSpace(note)})
	}
	return insns
}

var (
	branchOp   = regexp.MustCompile(`^(jmp|call|j[a-z]+) ([0-9a-f]+)(?: <([^>]+)>)?$`)
	ripOperand = regexp.MustCompile(`\[rip\+0x[0-9a-f]+\]`)
)

// normalize makes an instruction independent of where the code was placed: branch targets inside
// [lo,hi) become ".+N" (offset from the first instruction of the case), targets with a symbol
// become "<symbol>", other targets "EXT"; rip-relative operands become "[rip+DATA+0xN]" using
// the target address objdump reports in its comment (the data segment starts at 0x10000000).
func normalize(in disInsn, lo, hi uint64) string {
	if m := branchOp.FindStringSubmatch(in.text); m != nil {
		target, _ := strconv.ParseUint(m[2], 16, 64)
		switch {
		case target >= lo && target < hi:
			return fmt.Sprintf("%s .+%d", m[1], target-lo)
		case target == hi:
			return fmt.Sprintf("%s .+%d", m[1], target-lo)
		case m[3] != "" && !strings.Contains(m[3], "+"):
			return fmt.Sprintf("%s <%s>", m[1], m[3])
		default:
			return m[1] + " EXT"
		}
	}
	if ripOperand.MatchString(in.text) {
		fields := strings.Fields(in.note)
		if len(fields) > 0 {
			if target, err := strconv.ParseUint(fields[0], 16, 64); err == nil && target >= uint64(dataBase) {
				return ripOperand.ReplaceAllString(in.text, fmt.Sprintf("[rip+DATA+0x%x]", target-uint64(dataBase)))
			}
		}
		return ripOperand.ReplaceAllString(in.text, "[rip+EXT]")
	}
	return in.text
}

// extractCases returns, for each pair of int3 markers, the normalized instructions between them.
func extractCases(insns []disInsn) [][]string {
	var cases [][]string
	for i := 0; i < len(insns); i++ {
		if insns[i].text != "int3" {
			continue
		}
		j := i + 1
		for j < len(insns) && insns[j].text != "int3" {
			j++
		}
		if j >= len(insns) {
			break
		}
		lo := insns[i+1].addr
		hi := insns[j].addr
		var c []string
		for _, in := range insns[i+1 : j] {
			c = append(c, normalize(in, lo, hi))
		}
		cases = append(cases, c)
		i = j
	}
	return cases
}

func dumpCases(t *testing.T, names []string, got [][]string) {
	for i, c := range got {
		t.Logf("CASE %s\n\t%s", names[i], strings.Join(c, "\n\t"))
	}
}
