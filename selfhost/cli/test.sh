#!/usr/bin/env bash
CI_MODULE=core
source "$(dirname "$0")/../../scripts/ci/common.sh"
ci_module() {
  ci_native core-native selfhost/pipeline
  ci_check command core-independent "$PYTHON" scripts/ci/verify_native.py core
}
ci_main "$@"
