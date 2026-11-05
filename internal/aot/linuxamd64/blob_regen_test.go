package linuxamd64

import (
	"bytes"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

// blobGCCVersion is the compiler the committed blobs were generated with. Machine code differs
// between compiler versions, so the comparison below only runs with this exact version.
const blobGCCVersion = "14.2.0"

// TestRuntimeBlobsMatchSources regenerates rt_blob.go and floatfmt_blob.go from the C sources
// with the committed scripts (which also reject relocations, libc calls and non-empty data
// sections, i.e. enforce that the blobs are freestanding) and requires byte-identical output.
// It is skipped, with the reason, when a tool is missing or gcc is not the recorded version.
func TestRuntimeBlobsMatchSources(t *testing.T) {
	for _, tool := range []string{"gcc", "objdump", "objcopy", "nm", "python3", "sh"} {
		if _, err := exec.LookPath(tool); err != nil {
			t.Skipf("SKIP: %s not found (needed to regenerate the blobs with gcc %s); blobs not regenerated, so not verified", tool, blobGCCVersion)
		}
	}
	out, err := exec.Command("gcc", "-dumpfullversion").Output()
	if err != nil {
		t.Skipf("SKIP: gcc -dumpfullversion failed (%v), expected gcc %s; blobs not regenerated, so not verified", err, blobGCCVersion)
	}
	if v := strings.TrimSpace(string(out)); v != blobGCCVersion {
		t.Skipf("SKIP: detected gcc %s, expected gcc %s (the version the blobs were generated with); blobs not regenerated, so not verified", v, blobGCCVersion)
	}
	tmp := t.TempDir()
	if err := os.MkdirAll(filepath.Join(tmp, "runtime"), 0o755); err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"rt.c", "floatfmt.c", "gen_rt.sh", "gen.sh"} {
		data, err := os.ReadFile(filepath.Join("runtime", name))
		if err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(tmp, "runtime", name), data, 0o755); err != nil {
			t.Fatal(err)
		}
	}
	for _, c := range []struct{ script, blob string }{{"gen_rt.sh", "rt_blob.go"}, {"gen.sh", "floatfmt_blob.go"}} {
		cmd := exec.Command("sh", filepath.Join(tmp, "runtime", c.script))
		if msg, err := cmd.CombinedOutput(); err != nil {
			t.Fatalf("%s failed: %v\n%s", c.script, err, msg)
		}
		got, err := os.ReadFile(filepath.Join(tmp, c.blob))
		if err != nil {
			t.Fatal(err)
		}
		want, err := os.ReadFile(c.blob)
		if err != nil {
			t.Fatal(err)
		}
		if !bytes.Equal(got, want) {
			t.Errorf("%s is stale: regenerating it from the C source gives different bytes (run runtime/%s)", c.blob, c.script)
		}
	}
}
