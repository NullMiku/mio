#!/usr/bin/env bash
CI_MODULE=legacy-bootstrap
source "$(dirname "$0")/../common.sh"
# Mio-2.1 was created by a history migration, so the default CI ancestor of check-native-aot-fixed-point.py
# (8b53a25) is not reachable from HEAD. f398065 is the same commit in the migrated history (same author, time and
# subject; ancestor of Mio-2.1). The script documents this override for exactly that situation.
M18_ANCESTOR=f398065
ci_module() {
  local result=0
  case "$2" in
    bootstrap) ci_check command legacy-bcd "$PYTHON" scripts/ci/legacy_bootstrap.py ;;
    fixed-point)
      ci_check command legacy-m18 "$PYTHON" scripts/check-native-aot-fixed-point.py --evidence build/m18-ci --gc-witness --ci-ancestor "$M18_ANCESTOR" || result=$?
      export MIO_M18_EVIDENCE_DIR="$CI_ROOT/build/m18-ci"
      m18_reference "$result" build/m18-ci || result=$?
      return "$result" ;;
    full)
      ci_check command legacy-bcd "$PYTHON" scripts/ci/legacy_bootstrap.py || result=$?
      local m18=0
      ci_check command legacy-m18 "$PYTHON" scripts/check-native-aot-fixed-point.py --evidence "$MIO_CI_MODULE_DIR/m18" --gc-witness --ci-ancestor "$M18_ANCESTOR" || m18=$?
      export MIO_M18_EVIDENCE_DIR="$MIO_CI_MODULE_DIR/m18"
      m18_reference "$m18" "$MIO_CI_MODULE_DIR/m18" || result=$?
      if (( m18 > result )); then result=$m18; fi
      return "$result" ;;
  esac
}
# The Go M18 tests read the evidence that legacy-m18 generates. When legacy-m18 did not succeed that evidence does not
# exist, so running them only reports "file not found" noise: leave the check unexecuted (the runner records it as
# NOT_RUN) and let the legacy-m18 failure carry the module result.
m18_reference() {
  if [[ $1 != 0 ]]; then
    echo "NOT_RUN: legacy-m18-reference (needs the evidence of legacy-m18, which exited with $1)" >&2
    return 0
  fi
  ci_check go legacy-m18-reference go test -json -p 1 ./internal/aot -run '^TestM18' -count=1 -timeout 30m
}
ci_main "$@"
