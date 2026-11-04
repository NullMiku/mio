#!/usr/bin/env bash
CI_MODULE=selfhost
source "$(dirname "$0")/../scripts/ci/common.sh"
ci_module() {
  ci_native selfhost-native selfhost/...
}
ci_main "$@"
