#!/usr/bin/env bash
CI_MODULE=kiso/math
source "$(dirname "$0")/../../../scripts/ci/common.sh"
ci_module() {
  ci_native native bunko/kiso/math
}
ci_main "$@"
