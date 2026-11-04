#!/usr/bin/env bash
CI_MODULE=go-reference
source "$(dirname "$0")/../scripts/ci/common.sh"
ci_module() {
  case "$2" in
    quick|unit) ci_check go core-unit go test -json -p 2 ./internal/lexer ./internal/parser ./internal/resolver ./internal/typecheck ./internal/compiler ./internal/code ./internal/vm ./internal/mochi ./internal/tester ./cmd/mio -count=1 -timeout 10m ;;
    full)
      ci_check go vm-regression go test -json -p 2 ./internal/vm/... ./internal/mochi/... -count=1 -timeout 30m
      ci_check go repository go test -json -p 2 ./... -count=1 -timeout 30m ;;
  esac
  ci_check command vm-independent "$PYTHON" scripts/ci/verify.py vm
}
ci_main "$@"
