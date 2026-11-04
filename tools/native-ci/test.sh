#!/usr/bin/env bash
CI_MODULE=native-release
source "$(dirname "$0")/../../scripts/ci/common.sh"
ci_module() {
  ci_native release-native tools/native-ci
  local temporary output
  # production.sb denies writing anywhere under SOURCE, including build/.
  # Keep the retained production output outside the checkout, as release.yml does.
  temporary=$(mktemp -d "${TMPDIR:-/tmp}/mio-ci-release.XXXXXX")
  output="$temporary/production"
  printf '%s\n' "$output" > "$MIO_CI_MODULE_DIR/production-path.txt"
  local revision
  revision=$(git rev-parse HEAD)
  # This reproduces the existing production workflow. The child cannot execute
  # Python, Go, Shell, or our external test driver in the production sandbox.
  ci_check command release-build env PATH= MIO_BUNKO= /usr/bin/sandbox-exec \
    -D "SEED=$MIO_CI_SEED" -D "SOURCE=$CI_ROOT" -D "OUT=$output" \
    -f tools/native-ci/production.sb "$MIO_CI_SEED" run tools/native-ci \
    --bunko-root "$CI_ROOT/bunko" -- ci "$CI_ROOT" "$MIO_CI_SEED" "$output" "$revision"
  ci_check command release-independent "$PYTHON" scripts/ci/release_isolation.py --archive "$output/mio-2.0.0-dev-darwin-arm64.tar.gz"
}
ci_main "$@"
