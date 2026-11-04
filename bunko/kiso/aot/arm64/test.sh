#!/usr/bin/env bash
CI_MODULE=kiso/aot/arm64
source "$(dirname "$0")/../../../../scripts/ci/common.sh"
ci_module() {
  ci_native native bunko/kiso/aot/arm64
}
ci_main "$@"
