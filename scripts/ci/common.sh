#!/usr/bin/env bash
# Module scripts source this file and define their checks in ci_module().
set -euo pipefail
CI_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
ci_check() {
  "${PYTHON:-python3}" "$CI_ROOT/scripts/ci/runner.py" check "$@"
}
ci_native() {
  local name=$1 package=$2
  ci_check mio "$name" "$MIO_CI_MIO" test "$package" --bunko-root "$CI_ROOT/bunko" --format=json --lang=en-US
}
ci_native_and_crosscheck() {
  local native_name=$1 package=$2 independent_name=$3 native_result=0 independent_result=0
  shift 3
  ci_native "$native_name" "$package" || native_result=$?
  ci_check command "$independent_name" "$@" || independent_result=$?
  if (( native_result > independent_result )); then return "$native_result"; fi
  return "$independent_result"
}
ci_main() {
  if [[ ${MIO_CI_ACTIVE:-} != 1 ]]; then
    if (( $# < 1 || $# > 2 )); then
      echo "usage: test.sh <target> [suite]" >&2
      return 2
    fi
    exec bash "$CI_ROOT/scripts/ci/run.sh" "${1:-}" "$CI_MODULE" "${2:-quick}"
  fi
  cd "$CI_ROOT"
  ci_module "$1" "$2"
}
