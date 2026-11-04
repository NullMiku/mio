#!/usr/bin/env bash
CI_MODULE=kiso/runtime/os/darwin
source "$(dirname "$0")/../../../../../scripts/ci/common.sh"
ci_module() {
  ci_native native bunko/kiso/runtime/os/darwin
}
ci_main "$@"
