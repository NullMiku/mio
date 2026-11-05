#!/usr/bin/env bash
CI_MODULE=kiso/runtime/cpu/aarch64
source "$(dirname "$0")/../../../../../scripts/ci/common.sh"
ci_module() {
  ci_native_and_crosscheck native bunko/kiso/runtime/cpu/aarch64 independent "$PYTHON" scripts/ci/verify_native.py core
}
ci_main "$@"
