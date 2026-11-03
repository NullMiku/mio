#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
./scripts/build-wasm.sh
exec python3 -m http.server "${1:-8787}" --bind 127.0.0.1 --directory build/playground
