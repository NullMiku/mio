#!/usr/bin/env bash
CI_MODULE=legacy-bootstrap
source "$(dirname "$0")/../common.sh"
ci_module() {
  local result=0
  case "$2" in
    bootstrap) ci_check command legacy-bcd "$PYTHON" scripts/ci/legacy_bootstrap.py ;;
    fixed-point)
      ci_check command legacy-m18 "$PYTHON" scripts/check-native-aot-fixed-point.py --evidence build/m18-ci --gc-witness
      export MIO_M18_EVIDENCE_DIR="$CI_ROOT/build/m18-ci"
      ci_check go legacy-m18-reference go test -json -p 1 ./internal/aot -run '^TestM18' -count=1 -timeout 30m ;;
    full)
      ci_check command legacy-bcd "$PYTHON" scripts/ci/legacy_bootstrap.py || result=$?
      ci_check command legacy-m18 "$PYTHON" scripts/check-native-aot-fixed-point.py --evidence "$MIO_CI_MODULE_DIR/m18" --gc-witness || result=$?
      export MIO_M18_EVIDENCE_DIR="$MIO_CI_MODULE_DIR/m18"
      ci_check go legacy-m18-reference go test -json -p 1 ./internal/aot -run '^TestM18' -count=1 -timeout 30m || result=$?
      return "$result" ;;
  esac
}
ci_main "$@"
