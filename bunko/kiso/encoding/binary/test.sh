#!/usr/bin/env bash
CI_MODULE=kiso/encoding/binary
source "$(dirname "$0")/../../../../scripts/ci/common.sh"
ci_module() {
  ci_native native bunko/kiso/encoding/binary
}
ci_main "$@"
