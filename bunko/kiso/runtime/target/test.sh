#!/usr/bin/env bash
CI_MODULE=kiso/runtime/target
source "$(dirname "$0")/../../../../scripts/ci/common.sh"
ci_module() {
  ci_native native bunko/kiso/runtime/target
}
ci_main "$@"
