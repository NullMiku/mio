package linuxamd64

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"os"
	"path/filepath"
	"testing"
)

// sourceSHA256 hashes a C source with CRLF line endings normalised to LF, exactly like
// runtime/gen_rt.sh and runtime/gen.sh do, so the result does not depend on the checkout's
// line-ending settings.
func sourceSHA256(t *testing.T, name string) string {
	t.Helper()
	data, err := os.ReadFile(filepath.Join("runtime", name))
	if err != nil {
		t.Fatal(err)
	}
	sum := sha256.Sum256(bytes.ReplaceAll(data, []byte("\r\n"), []byte("\n")))
	return hex.EncodeToString(sum[:])
}

// TestRuntimeBlobsRecordCurrentSourceHashes needs no compiler: it fails when rt.c or floatfmt.c
// was edited without regenerating the committed blob (the blob records the hash of the source it
// was built from). It does not prove the blob equals what gcc produces; that is
// TestRuntimeBlobsMatchSources, which only runs with the recorded gcc version.
func TestRuntimeBlobsRecordCurrentSourceHashes(t *testing.T) {
	for _, c := range []struct{ source, recorded string }{
		{"rt.c", rtSourceSHA256},
		{"floatfmt.c", floatFmtSourceSHA256},
	} {
		if got := sourceSHA256(t, c.source); got != c.recorded {
			t.Errorf("runtime/%s has SHA-256 %s but its generated blob records %s: regenerate the blob (runtime/gen_rt.sh or runtime/gen.sh)", c.source, got, c.recorded)
		}
	}
}
