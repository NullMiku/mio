#!/usr/bin/env bash
CI_MODULE=legacy-bootstrap
source "$(dirname "$0")/../common.sh"
ci_module() {
  case "$2" in
    bootstrap) ci_check command legacy-bcd bash scripts/check-native-bootstrap.sh ;;
    fixed-point)
      ci_check command legacy-m18 "$PYTHON" scripts/check-native-aot-fixed-point.py --evidence build/m18-ci --gc-witness
      export MIO_M18_EVIDENCE_DIR="$CI_ROOT/build/m18-ci"
      ci_check go legacy-m18-reference go test -json -p 1 ./internal/aot -run '^TestM18' -count=1 -timeout 30m ;;
  esac
}
ci_main "$@"
