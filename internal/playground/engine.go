// Package playground hosts the real compiler and VM with a closed capability set.
package playground

import (
	"bytes"
	"fmt"
	"io/fs"
	"time"

	"Mio/internal/bunko"
	"Mio/internal/compiler"
	"Mio/internal/constant"
	"Mio/internal/mochi"
	"Mio/internal/resolver"
	"Mio/internal/typecheck"
	"Mio/internal/vm"
	"Mio/mma"
)

const MaxSourceBytes = 64 * 1024
const MaxOutputBytes = 64 * 1024
const InstructionLimit = 5_000_000

type Result struct {
	Status      string   `json:"status"`
	Stdout      string   `json:"stdout"`
	Diagnostics []string `json:"diagnostics"`
	Error       string   `json:"error,omitempty"`
	CompileMS   float64  `json:"compileMs"`
	RunMS       float64  `json:"runMs"`
}

type cappedOutput struct{ buffer bytes.Buffer }

func (w *cappedOutput) Write(p []byte) (int, error) {
	remaining := MaxOutputBytes - w.buffer.Len()
	if len(p) > remaining {
		w.buffer.Write(p[:remaining])
		return remaining, fmt.Errorf("output limit exceeded (%d bytes)", MaxOutputBytes)
	}
	return w.buffer.Write(p)
}

// Execute creates fresh compiler, registry and VM state for every request.
func Execute(source, operation string, library fs.FS) (result Result) {
	result.Diagnostics = []string{}
	result.Status = "error"
	defer func() {
		if p := recover(); p != nil {
			result.Error = fmt.Sprintf("internal error: %v", p)
		}
	}()
	if operation != "run" && operation != "check" {
		result.Error = "unsupported operation"
		return
	}
	if len(source) > MaxSourceBytes {
		result.Error = "source limit exceeded (65536 bytes)"
		return
	}
	start := time.Now()
	loaded, err := bunko.LoadSourceFS(source, library)
	if err == nil {
		err = constant.Fold(loaded.AST)
	}
	r := resolver.New()
	if err == nil {
		err = r.ResolveProgram(loaded.AST)
	}
	if err == nil {
		err = typecheck.NewWithResolver(r).CheckProgram(loaded.AST)
	}
	c := compiler.NewWithResolver(r)
	if err == nil {
		err = c.Compile(loaded.AST)
	}
	result.CompileMS = float64(time.Since(start).Microseconds()) / 1000
	if err != nil {
		result.Status = "diagnostic"
		result.Diagnostics = append(result.Diagnostics, err.Error())
		return
	}
	if operation == "check" {
		result.Status = "checked"
		return
	}
	// Exercise the actual Mochi encoder/decoder, supporting format versions through v14.
	var encoded bytes.Buffer
	if err = mochi.Encode(&encoded, c.Bytecode()); err != nil {
		result.Error = err.Error()
		return
	}
	bytecode, err := mochi.Decode(&encoded)
	if err != nil {
		result.Error = err.Error()
		return
	}
	output := &cappedOutput{}
	start = time.Now()
	err = vm.NewWithRegistryAndOutput(bytecode, mma.NewModuleRegistry(), output).RunWithOptions(vm.ExecutionOptions{InstructionLimit: InstructionLimit})
	result.RunMS = float64(time.Since(start).Microseconds()) / 1000
	result.Stdout = output.buffer.String()
	if err != nil {
		result.Error = err.Error()
		return
	}
	result.Status = "ok"
	return
}
