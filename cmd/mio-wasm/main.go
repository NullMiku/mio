//go:build js && wasm

package main

import (
	"Mio/internal/playground"
	"embed"
	"encoding/json"
	"io/fs"
	"syscall/js"
)

//go:embed library
var library embed.FS

func main() {
	fn := js.FuncOf(func(this js.Value, args []js.Value) any {
		if len(args) != 2 {
			return `{"status":"error","error":"expected source and operation"}`
		}
		result := playground.Execute(args[0].String(), args[1].String(), bundled())
		data, _ := json.Marshal(result)
		return string(data)
	})
	js.Global().Set("mioExecute", fn)
	select {}
}

func bundled() fs.FS {
	sub, err := fs.Sub(library, "library")
	if err != nil {
		panic(err)
	}
	return sub
}
