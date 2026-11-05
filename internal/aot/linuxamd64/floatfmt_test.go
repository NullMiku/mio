package linuxamd64

import (
	"bytes"
	"math"
	"math/rand"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"testing"
)

// harness: reads 9-byte records (bits LE u64, is32 byte) from stdin, prints
// each formatted value via the embedded mio_fmt_float routine.
func formatHarness(t *testing.T) string {
	e := New(0, 0)
	exit := e.newLabel()
	loop := e.newLabel()
	e.b(0x48, 0x83, 0xEC, 0x20) // sub rsp,32
	e.bind(loop)
	e.b(0x31, 0xC0, 0x31, 0xFF)             // xor eax,eax; xor edi,edi
	e.b(0x48, 0x89, 0xE6, 0xBA, 9, 0, 0, 0) // mov rsi,rsp; mov edx,9
	e.b(0x0F, 0x05, 0x48, 0x83, 0xF8, 0x09) // syscall; cmp rax,9
	e.b(0x0F, 0x85)                         // jne exit
	e.rel32(exit)
	e.b(0x48, 0x8B, 0x3C, 0x24, 0x0F, 0xB6, 0x74, 0x24, 0x08) // mov rdi,[rsp]; movzx esi,byte [rsp+8]
	e.b(0xE8)
	e.rel32(e.printFloat)
	e.needFloat = true
	e.b(0xE9)
	e.rel32(loop)
	e.bind(exit)
	e.b(0x31, 0xFF, 0xB8, 0xE7, 0, 0, 0, 0x0F, 0x05)
	img, err := e.Finish()
	if err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(t.TempDir(), "fmt")
	if err := os.WriteFile(path, img, 0o755); err != nil {
		t.Fatal(err)
	}
	return path
}

func TestFloatFormatMatchesStrconv(t *testing.T) {
	if runtime.GOOS != "linux" || runtime.GOARCH != "amd64" {
		t.Skip("requires Linux x86_64")
	}
	bin := formatHarness(t)
	r := rand.New(rand.NewSource(20261103)) // fixed seed
	type rec struct {
		bits uint64
		f32  bool
	}
	var recs []rec
	special64 := []float64{0, math.Copysign(0, -1), 1, -1, 0.1, 0.5, 1.5, 100, 123456, 1234567, 1e5, 1e6, 1e20, 1e21, 1e-4, 1e-5, 0.000123,
		math.MaxFloat64, math.SmallestNonzeroFloat64, 5e-324, 2.2250738585072014e-308, math.Inf(1), math.Inf(-1), math.NaN(),
		9007199254740993, 4.35, 0.3, 1.0 / 3, 2.0 / 3, math.Pi, math.E, 1e23, 8.41e21, 5e-5, 123456789.0, 1 << 53, 1 << 63, 1e100}
	for _, f := range special64 {
		recs = append(recs, rec{math.Float64bits(f), false})
		recs = append(recs, rec{uint64(math.Float32bits(float32(f))), true})
	}
	for _, b := range []uint32{1, 0x7f7fffff, 0x00800000, 0x007fffff, 0x4b800000, 0x33800000} {
		recs = append(recs, rec{uint64(b), true})
	}
	for i := 0; i < 250000; i++ {
		recs = append(recs, rec{r.Uint64(), false})
		recs = append(recs, rec{uint64(r.Uint32()), true})
	}
	// every power of two, and neighbours (boundary cases)
	for e := 0; e < 2046; e++ {
		b := uint64(e) << 52
		recs = append(recs, rec{b, false}, rec{b | 1, false}, rec{b - 1, false})
	}
	for e := 0; e < 254; e++ {
		b := uint64(e) << 23
		recs = append(recs, rec{b, true}, rec{b | 1, true}, rec{b - 1, true})
	}
	var in bytes.Buffer
	var want strings.Builder
	for _, x := range recs {
		var buf [9]byte
		for i := 0; i < 8; i++ {
			buf[i] = byte(x.bits >> (8 * i))
		}
		if x.f32 {
			buf[8] = 1
			want.WriteString(strconv.FormatFloat(float64(math.Float32frombits(uint32(x.bits))), 'g', -1, 32))
		} else {
			want.WriteString(strconv.FormatFloat(math.Float64frombits(x.bits), 'g', -1, 64))
		}
		want.WriteByte('\n')
		in.Write(buf[:])
	}
	cmd := exec.Command(bin)
	cmd.Stdin = &in
	var out bytes.Buffer
	cmd.Stdout = &out
	if err := cmd.Run(); err != nil {
		t.Fatal(err)
	}
	got := strings.Split(out.String(), "\n")
	exp := strings.Split(want.String(), "\n")
	if len(got) != len(exp) {
		t.Fatalf("line count %d != %d", len(got), len(exp))
	}
	bad := 0
	for i := range exp {
		if got[i] != exp[i] {
			if bad < 10 {
				t.Errorf("record %d bits=%#x f32=%v: got %q want %q", i, recs[i].bits, recs[i].f32, got[i], exp[i])
			}
			bad++
		}
	}
	if bad != 0 {
		t.Fatalf("%d/%d mismatches", bad, len(exp))
	}
	t.Logf("%d values identical to strconv.FormatFloat 'g' -1", len(recs))
}
