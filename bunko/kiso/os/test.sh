#!/usr/bin/env bash
CI_MODULE=kiso/os
source "$(dirname "$0")/../../../scripts/ci/common.sh"
ci_module() {
  ci_native native bunko/kiso/os
}
ci_main "$@"
