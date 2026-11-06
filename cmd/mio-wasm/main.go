//go:build js && wasm

// Command mio-wasm is the Web reference VM: the Go reference front end, the Mochi codec
// and the Go reference VM compiled to js/wasm for the browser playground. It is not a
// native AOT backend. It exposes exactly one function, mioExecute, to its Worker.
package main

import (
	"embed"
	"encoding/json"
	"io/fs"
	"runtime/debug"
	"syscall/js"

	"Mio/internal/playground"
)

// library is filled by scripts/web/build.sh with the allowlisted Bunko packages.
//
//go:embed library
var library embed.FS

func main() {
	// A soft limit makes the collector work harder long before wasm32's 4 GiB address space
	// is exhausted. A program that keeps more than that alive ends the Go runtime, which the
	// Worker reports; the controller then replaces the Worker.
	debug.SetMemoryLimit(1 << 30)
	root, err := fs.Sub(library, "library")
	if err != nil {
		panic(err)
	}
	closed := playground.Library(root)
	// mioExecute(requestJSON, done) returns immediately; the request runs on an ordinary
	// goroutine and done(resultJSON) is called when it finishes. Running the VM inside the
	// JS callback itself would starve the garbage collector's background workers (js/wasm
	// has no asynchronous preemption), so a long allocation-heavy run would exhaust memory.
	requests := make(chan pending, 1)
	js.Global().Set("mioExecute", js.FuncOf(func(this js.Value, args []js.Value) any {
		if len(args) != 2 || args[0].Type() != js.TypeString || args[1].Type() != js.TypeFunction {
			return "expected a JSON request and a completion callback"
		}
		requests <- pending{request: args[0].String(), done: args[1]}
		return nil
	}))
	for item := range requests {
		item.done.Invoke(handle(item.request, closed))
	}
}

type pending struct {
	request string
	done    js.Value
}

func handle(input string, closed fs.FS) string {
	var result playground.Result
	var request playground.Request
	if err := json.Unmarshal([]byte(input), &request); err != nil {
		result = playground.Result{Status: playground.StatusRejected, ExitCode: 1, Error: "malformed request: " + err.Error()}
	} else {
		result = playground.Execute(request, closed)
	}
	if result.Diagnostics == nil {
		result.Diagnostics = []playground.Diagnostic{}
	}
	data, _ := json.Marshal(result)
	return string(data)
}
