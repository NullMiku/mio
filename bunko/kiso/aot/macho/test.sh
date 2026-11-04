#!/usr/bin/env bash
CI_MODULE=kiso/aot/macho
source "$(dirname "$0")/../../../../scripts/ci/common.sh"
ci_module() {
  ci_native native bunko/kiso/aot/macho
}
ci_main "$@"
