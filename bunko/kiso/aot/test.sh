#!/usr/bin/env bash
CI_MODULE=aot
source "$(dirname "$0")/../../../scripts/ci/common.sh"
ci_module() {
  ci_native_and_crosscheck aot-native bunko/kiso/aot/... aot-independent "$PYTHON" scripts/ci/verify_native.py backend
}
ci_main "$@"
