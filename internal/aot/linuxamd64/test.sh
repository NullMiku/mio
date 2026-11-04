#!/usr/bin/env bash
CI_MODULE=go-aot-linux-amd64
source "$(dirname "$0")/../../../scripts/ci/common.sh"
# Supplementary Go tests of the Linux AMD64 backend: VM-versus-native differential tests, the Object ABI
# checker, and the comparison of emitted instructions with GNU objdump (that part reports SKIP when no GNU
# objdump is installed; the Go report keeps the per-test status). They do not replace the Mio native tests.
ci_module() {
  local result=0
  case "$2" in
    quick) ci_check go linux-amd64-aot go test -json -p 1 ./internal/aot/linuxamd64 ./cmd/mochi-aot -count=1 -timeout 10m || result=$? ;;
    unit|full) ci_check go linux-amd64-aot go test -json -p 1 ./internal/aot/... ./cmd/mochi-aot -count=1 -timeout 30m || result=$? ;;
  esac
  if [[ $2 == full ]]; then
    ci_check go linux-amd64-aot-race go test -json -p 1 -race ./internal/aot/... ./cmd/mochi-aot -count=1 -timeout 30m || result=$?
  fi
  return "$result"
}
ci_main "$@"
