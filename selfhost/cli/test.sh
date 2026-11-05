#!/usr/bin/env bash
CI_MODULE=core
source "$(dirname "$0")/../../scripts/ci/common.sh"
ci_module() {
  ci_native_and_crosscheck core-native selfhost/pipeline core-independent "$PYTHON" scripts/ci/verify_native.py core
}
ci_main "$@"
