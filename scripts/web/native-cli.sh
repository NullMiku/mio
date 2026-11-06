#!/usr/bin/env bash
# Builds the pure-Mio native CLI for linux-amd64, used by the Web CI only as a Mochi producer
# (`mio build --emit=mochi`). Stage A is go-hosted exactly as in scripts/ci/native_platforms.py:
# the Go reference front end compiles selfhost/linux-compiler to Mochi and the pure-Mio lowering
# runs in the reference VM. Compiler A then builds selfhost/cli. Nothing here is a fixed-point
# or seed verification; that remains the job of the native workflows.
set -euo pipefail
cd "$(dirname "$0")/../.."
out="$(mkdir -p "${1:-build/native-cli}" && cd "${1:-build/native-cli}" && pwd)"
go build -o "$out/refvm" ./tests/windows-amd64/refvm
"$out/refvm" bunko mochi selfhost/linux-compiler/main.mio "$out/linux-compiler.mochi"
mkdir -p "$out/lower"
printf '%s' "$out/linux-compiler.mochi" > "$out/lower/input.config"
printf '%s' "$out/compiler-A" > "$out/lower/output.config"
(cd "$out/lower" && "$out/refvm" "$OLDPWD/bunko" run "$OLDPWD/selfhost/native-aot-linux/main.mio") | grep -qx 'native-aot-linux: ok'
chmod +x "$out/compiler-A"
[[ "$(printf 'selfhost/cli\n%s\n' "$out/mio" | "$out/compiler-A")" == "linux-compiler: ok" ]]
chmod +x "$out/mio"
"$out/mio" --version
