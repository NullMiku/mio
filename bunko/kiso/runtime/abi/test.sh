#!/usr/bin/env bash
CI_MODULE=kiso/runtime/abi
source "$(dirname "$0")/../../../../scripts/ci/common.sh"
ci_module() {
  ci_native native bunko/kiso/runtime/abi
}
ci_main "$@"
