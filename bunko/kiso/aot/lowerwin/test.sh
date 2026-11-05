#!/usr/bin/env bash
CI_MODULE=kiso/aot/lowerwin
source "$(dirname "$0")/../../../../scripts/ci/common.sh"
ci_module() {
  ci_native_and_crosscheck native bunko/kiso/aot/lowerwin independent "$PYTHON" tests/windows-amd64/run_cases.py \
    --mio "$MIO_CI_MIO" --output "$MIO_CI_MODULE_DIR/windows-cases"
}
ci_main "$@"
