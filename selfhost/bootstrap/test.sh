#!/usr/bin/env bash
CI_MODULE=bootstrap
source "$(dirname "$0")/../../scripts/ci/common.sh"
ci_module() {
  if [[ $2 == full || $2 == bootstrap ]]; then
    ci_native bootstrap-native selfhost/codegen
    local evidence="$CI_ROOT/build/m19ef-evidence/ci-abcd-$(basename "$(dirname "$MIO_CI_MODULE_DIR")")"
    mkdir -p "$CI_ROOT/build/m19ef-evidence"
    ci_check command bootstrap-independent bash tests/m19ef/bootstrap-abcd.sh build --seed "$MIO_CI_SEED" --out "$evidence"
    ci_check command bootstrap-recheck bash tests/m19ef/bootstrap-abcd.sh verify --out "$evidence"
  fi
}
ci_main "$@"
