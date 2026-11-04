#!/usr/bin/env bash
CI_MODULE=kiso/regexp
source "$(dirname "$0")/../../../scripts/ci/common.sh"
ci_module() {
  ci_native native bunko/kiso/regexp
}
ci_main "$@"
