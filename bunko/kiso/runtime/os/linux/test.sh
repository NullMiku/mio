#!/usr/bin/env bash
CI_MODULE=kiso/runtime/os/linux
source "$(dirname "$0")/../../../../../scripts/ci/common.sh"
ci_module() {
  ci_native_and_crosscheck native bunko/kiso/runtime/os/linux independent "$PYTHON" bunko/kiso/runtime/os/linux/check_chain.py
}
ci_main "$@"
