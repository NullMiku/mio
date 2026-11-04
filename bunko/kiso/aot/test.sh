#!/usr/bin/env bash
CI_MODULE=aot
source "$(dirname "$0")/../../../scripts/ci/common.sh"
ci_module() {
  ci_native aot-native bunko/kiso/aot/...
  ci_check command aot-independent "$PYTHON" scripts/ci/verify_native.py core
}
ci_main "$@"
