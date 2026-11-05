#!/usr/bin/env bash
CI_MODULE=kiso/aot/pe
source "$(dirname "$0")/../../../../scripts/ci/common.sh"
ci_module() {
  ci_native_and_crosscheck native bunko/kiso/aot/pe independent "$PYTHON" tests/pe-writer/run.py \
    --mio "$MIO_CI_MIO" --mode native --output "$MIO_CI_MODULE_DIR/pe-images"
}
ci_main "$@"
