#!/usr/bin/env bash
CI_MODULE=go-aot-reference
source "$(dirname "$0")/../../scripts/ci/common.sh"
ci_module() {
  case "$2" in
    quick) ci_check go native-regression go test -json -p 1 ./internal/aot -run '^TestM(15aParameterCountsDifferential|11AutomaticGCReusesUnreachableObjects)$' -count=1 -timeout 10m ;;
    full|unit) ci_check go aot go test -json -p 1 ./internal/aot/... -count=1 -timeout 30m ;;
    race) ci_check go aot-race go test -json -p 1 -race ./internal/aot/... -count=1 -timeout 30m ;;
  esac
  ci_check command native-independent "$PYTHON" scripts/ci/verify.py native
}
ci_main "$@"
