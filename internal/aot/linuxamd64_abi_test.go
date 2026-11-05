package aot

import (
	"encoding/binary"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"testing"

	"Mio/internal/aot/darwinarm64"
)

// Frozen Mio Object ABI v1 as defined by the existing sources. Constants come from
// the macOS ARM64 package (exported) and from bunko/kiso/runtime/gc/layout.mio -
// nothing is guessed for Linux.
type abiV1 struct {
	headerBytes, alignment, metadataBytes, losThreshold, heapHeader int
	typeStruct, typeArray, typeStorage, typeBox, typeEnum           uint32
	payloadBase                                                     int
}

func loadABIv1(t testing.TB) abiV1 {
	t.Helper()
	text, err := os.ReadFile(filepath.Join("..", "..", "bunko", "kiso", "runtime", "gc", "layout.mio"))
	if err != nil {
		t.Fatal(err)
	}
	layout := func(name string) int {
		m := regexp.MustCompile(`teisu ` + name + ` = (\d+);`).FindSubmatch(text)
		if m == nil {
			t.Fatalf("layout.mio has no %s", name)
		}
		n, _ := strconv.Atoi(string(m[1]))
		return n
	}
	a := abiV1{
		headerBytes: layout("header_bytes"), alignment: layout("object_alignment"),
		metadataBytes: layout("metadata_bytes"), losThreshold: layout("default_los_threshold"),
		heapHeader: darwinarm64.M8HeapHeaderSize,
		typeStruct: darwinarm64.M12StructTypeID, typeArray: darwinarm64.M12ArrayTypeID,
		typeStorage: darwinarm64.M12StorageTypeID, typeBox: darwinarm64.M13NullableTypeID,
		typeEnum: darwinarm64.M13EnumTypeID, payloadBase: 32,
	}
	if a.headerBytes != darwinarm64.M8ObjectHeaderSize || a.alignment != darwinarm64.M8ObjectAlignment ||
		a.metadataBytes != darwinarm64.M8TelemetrySize {
		t.Fatalf("layout.mio and the ARM64 package disagree about the frozen ABI: %+v", a)
	}
	return a
}

type abiObject struct {
	typ, flags uint32
	payload    uint64
	words      []uint64 // first payload words (up to 8)
	large      bool
}

type abiDump struct {
	heapHeader, telemetry []byte
	objects               []abiObject
	free                  int
	large                 []abiObject
}

func parseDump(raw []byte, a abiV1) (*abiDump, error) {
	if len(raw) < 32 {
		return nil, fmt.Errorf("dump too short")
	}
	le := binary.LittleEndian
	sizes := [4]uint64{le.Uint64(raw), le.Uint64(raw[8:]), le.Uint64(raw[16:]), le.Uint64(raw[24:])}
	if sizes[0] != uint64(a.heapHeader) || sizes[2] != uint64(a.metadataBytes) {
		return nil, fmt.Errorf("heap header/telemetry sizes %d/%d, want %d/%d", sizes[0], sizes[2], a.heapHeader, a.metadataBytes)
	}
	off := uint64(32)
	d := &abiDump{}
	d.heapHeader = raw[off : off+sizes[0]]
	off += sizes[0]
	objs := raw[off : off+sizes[1]]
	off += sizes[1]
	d.telemetry = raw[off : off+sizes[2]]
	off += sizes[2]
	if le.Uint64(d.heapHeader) != 0x38504145484F494D {
		return nil, fmt.Errorf("heap magic %#x", le.Uint64(d.heapHeader))
	}
	readWords := func(b []byte, n int) []uint64 {
		var w []uint64
		for i := 0; i < n && 8*(i+1) <= len(b); i++ {
			w = append(w, le.Uint64(b[8*i:]))
		}
		return w
	}
	for p := uint64(0); p < uint64(len(objs)); {
		if p%uint64(a.alignment) != 0 {
			return nil, fmt.Errorf("object header at +%d is not %d-byte aligned", p, a.alignment)
		}
		if p+uint64(a.headerBytes) > uint64(len(objs)) {
			return nil, fmt.Errorf("truncated header at +%d", p)
		}
		o := abiObject{typ: le.Uint32(objs[p:]), flags: le.Uint32(objs[p+4:]), payload: le.Uint64(objs[p+8:])}
		span := (o.payload + uint64(a.headerBytes) + uint64(a.alignment) - 1) &^ (uint64(a.alignment) - 1)
		if span < uint64(a.headerBytes) || p+span > uint64(len(objs)) {
			return nil, fmt.Errorf("object at +%d has impossible payload size %d", p, o.payload)
		}
		if o.typ == 0 {
			if o.flags&4 == 0 {
				return nil, fmt.Errorf("free block at +%d lacks the free bit (flags %#x)", p, o.flags)
			}
			if o.payload != span-uint64(a.headerBytes) {
				return nil, fmt.Errorf("free block at +%d payloadSize %d != span-16", p, o.payload)
			}
			d.free++
		} else {
			o.words = readWords(objs[p+uint64(a.headerBytes):p+span], 8)
			if err := checkObjectLayout(o, a); err != nil {
				return nil, fmt.Errorf("object at +%d: %w", p, err)
			}
			d.objects = append(d.objects, o)
		}
		p += span
	}
	for i := uint64(0); i < sizes[3]; i++ {
		rec := raw[off : off+32+16+64]
		off += 32 + 16 + 64
		o := abiObject{typ: le.Uint32(rec[32:]), flags: le.Uint32(rec[36:]), payload: le.Uint64(rec[40:]), large: true}
		o.words = readWords(rec[48:], 8)
		mapping := le.Uint64(rec[8:])
		span := (o.payload + 16 + 15) &^ 15
		if mapping%4096 != 0 || mapping < 32+span || span < uint64(a.losThreshold) {
			return nil, fmt.Errorf("LOS node %d: mapping %d span %d threshold %d", i, mapping, span, a.losThreshold)
		}
		if err := checkObjectLayout(o, a); err != nil {
			return nil, fmt.Errorf("LOS node %d: %w", i, err)
		}
		d.large = append(d.large, o)
	}
	return d, nil
}

func checkObjectLayout(o abiObject, a abiV1) error {
	w := o.words
	need := func(n int) error {
		if len(w) < n {
			return fmt.Errorf("type %d payload too short", o.typ)
		}
		return nil
	}
	switch o.typ {
	case a.typeStruct, a.typeEnum:
		if err := need(4); err != nil {
			return err
		}
		count, countIdx, kind := w[1], 1, uint64(1)
		if o.typ == a.typeEnum {
			count, countIdx, kind = w[2], 2, 8
		}
		if w[0] != kind || (o.typ == a.typeStruct && w[1] != w[2]) {
			return fmt.Errorf("type %d kind/count words %v", o.typ, w[:4])
		}
		if w[3] != (count+63)/64 {
			return fmt.Errorf("bitmap word count %d for %d fields (word %d)", w[3], count, countIdx)
		}
		if o.payload != uint64(a.payloadBase)+8*w[3]+8*count {
			return fmt.Errorf("payloadSize %d, want %d", o.payload, uint64(a.payloadBase)+8*w[3]+8*count)
		}
	case a.typeArray:
		if err := need(6); err != nil {
			return err
		}
		width := w[0] >> 8 & 0xff
		if w[0]&0xff != 2 || (width != 1 && width != 8) || w[3] != 1 || w[4] != 1 || o.payload != 48 || w[1] > w[2] {
			return fmt.Errorf("array descriptor words %v payload %d", w[:6], o.payload)
		}
	case a.typeStorage:
		if err := need(4); err != nil {
			return err
		}
		width := w[0] >> 8 & 0xff
		if w[0]&0xff != 3 || (width != 1 && width != 8) || w[2] != 1 || w[3] != w[0]>>16&1 {
			return fmt.Errorf("storage words %v", w[:4])
		}
		if o.payload != uint64(a.payloadBase)+w[1]*width {
			return fmt.Errorf("storage payloadSize %d, want %d", o.payload, uint64(a.payloadBase)+w[1]*width)
		}
	case a.typeBox:
		if err := need(2); err != nil {
			return err
		}
		if w[0] != 7 || o.payload != 16 {
			return fmt.Errorf("nullable box words %v payload %d", w[:2], o.payload)
		}
	default:
		return fmt.Errorf("unknown typeID %d", o.typ)
	}
	if o.flags&^uint32(0x1ff) != 0 || o.flags&(1|2) != 0 {
		return fmt.Errorf("flags %#x carry a stale mark/scan bit or unknown bits", o.flags)
	}
	return nil
}

const abiProbeSrc = `yobu "kiso/array";
kata Pair { left: []int64; right: int64; }
sentaku Choice { Empty; Number(int64); Many([]int64, int64?); }
kaku bytes = array.make[uint8](100, uint8(7));
kaku wide = array.make[int64](10, 3);
kaku pair = Pair { left: wide, right: 9 };
waza maybe(n: int64) -> int64? { moshi (n == 0) { kaesu mu; } kaesu n * 2; }
kaku choice = Choice.Many(wide, maybe(4));
kaku boxed = maybe(21);
kaku missing = maybe(0);
kaku none = Choice.Empty();
kaku nested: [][]int64 = array.with_capacity[[]int64](4);
array.push(nested, wide); array.push(nested, array.make[int64](3, 1));
kaku huge = array.make[uint8](200000, uint8(1));
waza churn() -> unit { kaku i = 0; aida (i < 300) { kaku junk = array.make[int64](40, i); i = i + 1; } }
churn();
chant(len(bytes) + len(wide) + pair.right + len(nested) + len(huge));`

func TestLinuxAMD64ObjectABIv1StructureAndSemantics(t *testing.T) {
	if !isLinuxAMD64() {
		t.Skip("requires Linux x86_64")
	}
	a := loadABIv1(t)
	root, _ := filepath.Abs(filepath.Join("..", ".."))
	program := m17CompileMio(t, root, abiProbeSrc)
	want := linuxVMOracle(t, program)
	for _, stress := range []bool{false, true} {
		t.Run(fmt.Sprintf("stress=%v", stress), func(t *testing.T) {
			dumpPath := filepath.Join(t.TempDir(), "heap.bin")
			out, err := runLinuxAMD64Options(t, program, LinuxAMD64Options{HeapCapacity: 1 << 20, GCStress: stress, HeapDumpPath: dumpPath})
			if err != nil || string(out) != string(want) {
				t.Fatalf("run: err=%v out=%q want %q", err, out, want)
			}
			raw, err := os.ReadFile(dumpPath)
			if err != nil {
				t.Fatal(err)
			}
			d, err := parseDump(raw, a)
			if err != nil {
				t.Fatalf("Object ABI v1 structure check failed: %v", err)
			}
			count := map[uint32]int{}
			for _, o := range d.objects {
				count[o.typ]++
			}
			for _, o := range d.large {
				count[o.typ]++
			}
			// The probe keeps 1 struct, 2 enums (Choice.Many has a payload; Empty/boxes are objects too),
			// array descriptors + their storages and boxes alive.
			if count[a.typeStruct] < 1 || count[a.typeEnum] < 2 || count[a.typeArray] < 5 || count[a.typeStorage] < 5 || count[a.typeBox] < 2 {
				t.Fatalf("expected live structs/enums/arrays/storages/boxes, got %v", count)
			}
			if len(d.large) != 1 || d.large[0].typ != a.typeStorage || d.large[0].payload != uint64(a.payloadBase)+200000 {
				t.Fatalf("200000-byte storage must be exactly one LOS object, got %+v", d.large)
			}
			le := binary.LittleEndian
			tel := func(i int) uint64 { return le.Uint64(d.telemetry[8*i:]) }
			if tel(323) != 1 || tel(324) != uint64(a.losThreshold) || tel(320) == 0 {
				t.Fatalf("LOS telemetry head=%#x count=%d threshold=%d", tel(320), tel(323), tel(324))
			}
			if stress && d.free == 0 {
				t.Log("note: no free blocks left after stress run")
			}
			t.Logf("ABI v1 ok: %v ordinary objects, %d LOS, %d free blocks, %d collections", len(d.objects), len(d.large), d.free, tel(2))
		})
	}
}

// The checker itself must reject corrupted headers and metadata.
func TestLinuxAMD64ObjectABIv1CheckerRejectsCorruption(t *testing.T) {
	if !isLinuxAMD64() {
		t.Skip("requires Linux x86_64")
	}
	a := loadABIv1(t)
	root, _ := filepath.Abs(filepath.Join("..", ".."))
	program := m17CompileMio(t, root, abiProbeSrc)
	dumpPath := filepath.Join(t.TempDir(), "heap.bin")
	if _, err := runLinuxAMD64Options(t, program, LinuxAMD64Options{HeapCapacity: 1 << 20, HeapDumpPath: dumpPath}); err != nil {
		t.Fatal(err)
	}
	good, _ := os.ReadFile(dumpPath)
	if _, err := parseDump(good, a); err != nil {
		t.Fatalf("baseline dump invalid: %v", err)
	}
	le := binary.LittleEndian
	objStart := 32 + a.heapHeader
	mutations := map[string]func([]byte){
		"unknown typeID":     func(b []byte) { le.PutUint32(b[objStart:], 9999) },
		"stale mark bit":     func(b []byte) { le.PutUint32(b[objStart+4:], le.Uint32(b[objStart+4:])|1) },
		"impossible size":    func(b []byte) { le.PutUint64(b[objStart+8:], 1<<40) },
		"bad heap magic":     func(b []byte) { b[32] ^= 0xff },
		"misaligned payload": func(b []byte) { le.PutUint64(b[objStart+8:], le.Uint64(b[objStart+8:])+1) },
	}
	for name, mutate := range mutations {
		t.Run(name, func(t *testing.T) {
			bad := append([]byte(nil), good...)
			mutate(bad)
			if _, err := parseDump(bad, a); err == nil {
				t.Fatal("corruption not detected")
			}
		})
	}
}

// Runtime side: a corrupted live header must stop the collector (exit 1, diagnostic),
// never be traversed.
func TestLinuxAMD64CorruptHeaderIsRejectedByCollector(t *testing.T) {
	if !isLinuxAMD64() {
		t.Skip("requires Linux x86_64")
	}
	root, _ := filepath.Abs(filepath.Join("..", ".."))
	program := m17CompileMio(t, root, shadowPreciseSrc)
	out, err := runLinuxAMD64Options(t, program, LinuxAMD64Options{HeapCapacity: 128 << 10, GCStress: true, RootMutation: "corrupt-header"})
	exit, ok := err.(*exec.ExitError)
	if !ok || exit.ExitCode() != 1 || !strings.Contains(string(out), "invalid GC root") {
		t.Fatalf("want exit 1 + exact-root diagnostic, got err=%v out=%q", err, out)
	}
}
