#!/usr/bin/env bash
CI_MODULE=kiso/crypto/sha256
source "$(dirname "$0")/../../../../scripts/ci/common.sh"
ci_module() {
  ci_native native bunko/kiso/crypto/sha256
}
ci_main "$@"
