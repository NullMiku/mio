#!/usr/bin/env bash
CI_MODULE=go-aot-linux-amd64
source "$(dirname "$0")/../../../scripts/ci/common.sh"
# Supplementary Go tests of the Linux AMD64 backend (reference engine; they do not replace Mio native tests).
# `backend` is the ordinary Go check: VM-versus-native differential tests, the Object ABI checker and the CLI
# tests; it keeps per-test SKIP details (macOS-only tests, native file-system imports, and the blob
# regeneration comparison, which only runs with gcc 14.2.0).
# The checks below must really run, so go-required turns any SKIP or empty run into NOT_RUN:
# the blob/source hash check (no tools needed) and the three comparisons of emitted code with GNU objdump.
ci_module() {
  local result=0 name
  ci_check go backend go test -json -p 1 ./internal/aot/... ./cmd/mochi-aot -count=1 -timeout 30m || result=$?
  ci_check go-required blob-source-hashes go test -json -p 1 ./internal/aot/linuxamd64 \
    -run '^TestRuntimeBlobsRecordCurrentSourceHashes$' -count=1 -timeout 5m || result=$?
  ci_check go-required objdump-scalar go test -json -p 1 ./internal/aot/linuxamd64 \
    -run '^TestEmitterScalarInstructionsMatchObjdump$' -count=1 -timeout 5m || result=$?
  ci_check go-required objdump-heap go test -json -p 1 ./internal/aot/linuxamd64 \
    -run '^TestEmitterHeapInstructionsMatchObjdump$' -count=1 -timeout 5m || result=$?
  ci_check go-required objdump-decode go test -json -p 1 ./internal/aot/linuxamd64 \
    -run '^TestEmittedScalarCodeDecodesWithoutGaps$' -count=1 -timeout 5m || result=$?
  if [[ $2 == full ]]; then
    ci_check go backend-race go test -json -p 1 -race ./internal/aot/... ./cmd/mochi-aot -count=1 -timeout 30m || result=$?
  fi
  return "$result"
}
ci_main "$@"
