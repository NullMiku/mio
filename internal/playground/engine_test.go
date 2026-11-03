package playground

import (
	mio "Mio"
	"bytes"
	"encoding/json"
	"os"
	"strings"
	"testing"
	"testing/fstest"
)

type example struct {
	Name       string `json:"name"`
	Source     string `json:"source"`
	Stdout     string `json:"stdout"`
	Diagnostic bool   `json:"diagnostic"`
	Limited    bool   `json:"limited"`
}

func TestExamplesAndNativeParity(t *testing.T) {
	data, err := os.ReadFile("../../web/playground/examples.json")
	if err != nil {
		t.Fatal(err)
	}
	var examples []example
	if err = json.Unmarshal(data, &examples); err != nil {
		t.Fatal(err)
	}
	baseline := map[string]Result{}
	for _, ex := range examples {
		t.Run(ex.Name, func(t *testing.T) {
			result := Execute(ex.Source, "run", os.DirFS("../../bunko"))
			baseline[ex.Name] = result
			if ex.Diagnostic {
				if result.Status != "diagnostic" || len(result.Diagnostics) == 0 {
					t.Fatalf("%+v", result)
				}
				sourcePath := t.TempDir() + "/bad.mio"
				if err := os.WriteFile(sourcePath, []byte(ex.Source), 0600); err != nil {
					t.Fatal(err)
				}
				env := mio.NewEnvironment(nil)
				defer env.Close()
				_, err := env.CompileFile(sourcePath, "../../bunko")
				if err == nil || err.Error() != result.Diagnostics[0] {
					t.Fatalf("native diagnostic %v != %v", err, result.Diagnostics)
				}
				return
			}
			if ex.Limited {
				if !strings.Contains(result.Error, "instruction limit") {
					t.Fatalf("%+v", result)
				}
				return
			}
			if result.Status != "ok" || result.Stdout != ex.Stdout {
				t.Fatalf("%+v; expected %q", result, ex.Stdout)
			}
			// Independent existing public embedding API, disk loader and VM as parity oracle.
			dir := t.TempDir()
			path := dir + "/main.mio"
			if err := os.WriteFile(path, []byte(ex.Source), 0600); err != nil {
				t.Fatal(err)
			}
			env := mio.NewEnvironment(nil)
			defer env.Close()
			program, err := env.CompileFile(path, "../../bunko")
			if err != nil {
				t.Fatal(err)
			}
			var output bytes.Buffer
			if err = env.Run(program, &output); err != nil {
				t.Fatal(err)
			}
			if output.String() != result.Stdout {
				t.Fatalf("native=%q playground=%q", output.String(), result.Stdout)
			}
		})
	}
	if destination := os.Getenv("MIO_WASM_BASELINE"); destination != "" {
		data, _ := json.MarshalIndent(baseline, "", "  ")
		if err := os.WriteFile(destination, data, 0600); err != nil {
			t.Fatal(err)
		}
	}
}

func TestLimitsIsolationAndCheck(t *testing.T) {
	library := fstest.MapFS{}
	checks := []struct{ source, op, status, contains string }{
		{`chant("never executed");`, "check", "checked", ""},
		{`aida (hai) { chant("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"); }`, "run", "error", "output limit exceeded"},
		{`yobu "kiso/fs";`, "run", "diagnostic", "unsupported"},
		{`yobu "../secrets";`, "run", "diagnostic", "invalid Bunko"},
		{strings.Repeat(" ", MaxSourceBytes+1), "run", "error", "source limit"},
		{`chant("ok");`, "run", "ok", ""},
		{`chant(missing);`, "run", "diagnostic", ""},
		{`chant("ok");`, "invalid", "error", "unsupported operation"},
	}
	for _, check := range checks {
		got := Execute(check.source, check.op, library)
		if got.Status != check.status || !strings.Contains(got.Error+strings.Join(got.Diagnostics, ""), check.contains) {
			t.Fatalf("%s: status=%s error=%s diagnostics=%v outputBytes=%d", check.source[:min(len(check.source), 100)], got.Status, got.Error, got.Diagnostics, len(got.Stdout))
		}
		if len(got.Stdout) > MaxOutputBytes {
			t.Fatal("output cap exceeded")
		}
		if check.op == "check" && got.Stdout != "" {
			t.Fatal("check ran source")
		}
	}
	first := Execute(`kaku private_value = 42;`, "run", library)
	second := Execute(`chant(private_value);`, "run", library)
	if first.Status != "ok" || second.Status != "diagnostic" {
		t.Fatalf("state leaked: %+v %+v", first, second)
	}
}
