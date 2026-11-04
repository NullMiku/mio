#!/usr/bin/env bash
CI_MODULE=kiso/aot/lower
source "$(dirname "$0")/../../../../scripts/ci/common.sh"
ci_module() {
  ci_native native bunko/kiso/aot/lower
}
ci_main "$@"
