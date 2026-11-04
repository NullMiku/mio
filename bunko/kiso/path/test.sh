#!/usr/bin/env bash
CI_MODULE=kiso/path
source "$(dirname "$0")/../../../scripts/ci/common.sh"
ci_module() {
  ci_native native bunko/kiso/path
}
ci_main "$@"
