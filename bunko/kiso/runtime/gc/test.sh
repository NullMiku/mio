#!/usr/bin/env bash
CI_MODULE=gc
source "$(dirname "$0")/../../../../scripts/ci/common.sh"
ci_module() {
  ci_native_and_crosscheck gc-native bunko/kiso/runtime/gc gc-independent "$PYTHON" scripts/ci/verify_native.py gc
}
ci_main "$@"
