#!/usr/bin/env bash
CI_MODULE=gc
source "$(dirname "$0")/../../../../scripts/ci/common.sh"
ci_module() {
  ci_native gc-native bunko/kiso/runtime/gc
  ci_check command gc-independent "$PYTHON" scripts/ci/verify_native.py gc
}
ci_main "$@"
