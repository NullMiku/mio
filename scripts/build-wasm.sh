#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Copy only this reviewed pure-source closure; never include native FS/MMA packages.
rm -rf cmd/mio-wasm/library
for module in math array string bytes utf8; do
  mkdir -p "cmd/mio-wasm/library/kiso/$module"
  for source in bunko/kiso/"$module"/*.mio; do
    case "$source" in *_test.mio) continue;; esac
    cp "$source" "cmd/mio-wasm/library/kiso/$module/"
  done
done
mkdir -p build/playground
cp web/playground/* build/playground/
GOOS=js GOARCH=wasm go build -trimpath -o build/playground/mio.wasm ./cmd/mio-wasm
runtime="$(go env GOROOT)/lib/wasm/wasm_exec.js"
if [[ ! -f "$runtime" ]]; then runtime="$(go env GOROOT)/misc/wasm/wasm_exec.js"; fi
cp "$runtime" build/playground/wasm_exec.js
go version > build/playground/toolchain.txt
wc -c build/playground/mio.wasm
