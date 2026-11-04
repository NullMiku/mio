#!/usr/bin/env bash
CI_MODULE=kiso/encoding/mochi
source "$(dirname "$0")/../../../../scripts/ci/common.sh"
ci_module() {
  ci_native native bunko/kiso/encoding/mochi
}
ci_main "$@"
