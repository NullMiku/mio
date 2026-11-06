#!/usr/bin/env bash
# Builds the self-contained static playground into build/web (or $1).
# The output needs only a static file server; no request ever carries Mio source.
set -euo pipefail
cd "$(dirname "$0")/../.."
out="${1:-build/web}"
go run ./cmd/mio-wasm/stage bunko cmd/mio-wasm/library
rm -rf "$out"
mkdir -p "$out"
cp web/playground/index.html web/playground/style.css web/playground/app.js web/playground/client.js \
   web/playground/worker.js web/playground/examples.json "$out/"
GOOS=js GOARCH=wasm go build -trimpath -ldflags=-s -o "$out/mio.wasm" ./cmd/mio-wasm
runtime="$(go env GOROOT)/lib/wasm/wasm_exec.js"
[[ -f "$runtime" ]] || runtime="$(go env GOROOT)/misc/wasm/wasm_exec.js"
cp "$runtime" "$out/wasm_exec.js"
python3 - "$out" <<'PY'
import hashlib, json, os, subprocess, sys
out = sys.argv[1]
files = {name: hashlib.sha256(open(os.path.join(out, name), 'rb').read()).hexdigest()
         for name in sorted(os.listdir(out))}
manifest = dict(engine="go-reference-vm/js-wasm", note="Web reference VM; not a native AOT backend",
                go=subprocess.check_output(["go", "env", "GOVERSION"], text=True).strip(),
                source=subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
                files=files)
open(os.path.join(out, "manifest.json"), "w").write(json.dumps(manifest, indent=2) + "\n")
PY
echo "built $out ($(wc -c < "$out/mio.wasm") bytes mio.wasm)"
