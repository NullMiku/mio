#!/usr/bin/env bash
CI_MODULE=kiso/aot/macho
source "$(dirname "$0")/../../../../scripts/ci/common.sh"
ci_module() {
  ci_native_and_crosscheck native bunko/kiso/aot/macho independent "$PYTHON" scripts/ci/verify_native.py backend
}
ci_main "$@"
