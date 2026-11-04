#!/usr/bin/env bash
CI_MODULE=quality
source "$(dirname "$0")/common.sh"
ci_module() {
  ci_check command quality bash scripts/ci/quality.sh
  ci_check command infrastructure "$PYTHON" scripts/ci/selftest.py
  ci_check command release-isolation "$PYTHON" scripts/ci/release_isolation.py
}
ci_main "$@"
