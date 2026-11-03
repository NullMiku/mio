#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
./scripts/build-wasm.sh
MIO_WASM_BASELINE="$PWD/build/playground/native-results.json" go test -count=1 ./internal/playground ./internal/bunko ./internal/vm ./internal/mochi
# A separately running static server is required (scripts/serve-wasm.sh).
node scripts/test-wasm.cjs
