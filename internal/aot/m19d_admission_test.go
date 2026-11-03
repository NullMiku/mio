package aot

import (
	"bytes"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"testing"
	"time"
)

// The same Mio decision core runs in the Go VM, Go ARM64 AOT, and Mio ARM64
// lowering. Synthetic clock/snapshot/latency input is intentional, not HTTP load.
func TestM19dAdmissionDifferential(t *testing.T) {
	root, err := filepath.Abs("../..")
	if err != nil {
		t.Fatal(err)
	}
	source, err := os.ReadFile(filepath.Join(root, "tests/m19d/scenarios.mio"))
	if err != nil {
		t.Fatal(err)
	}
	p := m17CompileMio(t, root, string(source))
	want := []byte("50\n30\n10\n10\nPASS\n")
	if out := m17RunVM(t, p, 100_000_000); !bytes.Equal(out, want) {
		t.Fatalf("VM scenario assertions: %s", out)
	}
	if runtime.GOOS != "darwin" || runtime.GOARCH != "arm64" {
		t.Skip("native portion requires Darwin ARM64")
	}
	for _, engine := range []string{"go", "mio"} {
		for _, stress := range []bool{false, true} {
			name := engine
			if stress {
				name += "-gcstress"
			}
			t.Run(name, func(t *testing.T) {
				started := time.Now()
				var image []byte
				if engine == "go" {
					var err error
					image, err = CompileDarwinARM64WithOptions(p, DarwinARM64Options{HeapCapacity: 8 << 20, AdaptiveHeap: true, GCTelemetry: true, GCStress: stress})
					if err != nil {
						t.Fatal(err)
					}
				} else {
					image = m19MioImage(t, p, 8<<20, stress, true, false, true)
				}
				compiled := time.Now()
				out, diag, err := m19Run(t, image)
				if err != nil || !bytes.Equal(out, want) {
					t.Fatalf("native %v output %s\n%s", err, out, diag)
				}
				m := m19Metrics(t, diag)
				m19CheckMetrics(t, m)
				m19bCheckMetrics(t, m)
				if m["pressure_sequence"] == 0 || m["pressure_sequence"]%2 != 0 {
					t.Fatal("unpublished real runtime pressure")
				}
				if m["los_live_bytes"]+m["los_reclaimed_bytes"] == 0 {
					t.Fatal("missing real LOS roots test")
				}
				if directory := os.Getenv("MIO_M19D_EVIDENCE_DIR"); directory != "" {
					if err := os.MkdirAll(directory, 0700); err != nil {
						t.Fatal(err)
					}
					record := map[string]any{"engine": engine, "gcstress": stress, "unsigned_image_sha256": fmt.Sprintf("%x", sha256.Sum256(image)), "compile_seconds": compiled.Sub(started).Seconds(), "sign_and_execute_seconds": time.Since(compiled).Seconds(), "metrics": m, "synthetic_dispatch_counts": []int{50, 30, 10, 10}, "real_http_metrics": false}
					data, err := json.MarshalIndent(record, "", "  ")
					if err != nil {
						t.Fatal(err)
					}
					for suffix, content := range map[string][]byte{".json": data, ".unsigned": image, ".stdout": out, ".telemetry": diag} {
						path := filepath.Join(directory, name+suffix)
						f, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
						if err != nil {
							t.Fatal(err)
						}
						_, err = f.Write(content)
						closeErr := f.Close()
						if err != nil {
							t.Fatal(err)
						}
						if closeErr != nil {
							t.Fatal(closeErr)
						}
					}
				}
				t.Logf("real GC metrics: minor=%d major=%d los_reclaimed=%d", m["minor_gc_count"], m["major_gc_count"], m["los_reclaimed_bytes"])
			})
		}
	}
}
