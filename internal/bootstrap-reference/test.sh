#!/usr/bin/env bash
CI_MODULE=go-bootstrap-reference
source "$(dirname "$0")/../../scripts/ci/common.sh"
# Go reference test of the pure-Mio bootstrap (Compiler A -> B -> C -> D in the reference VM). It takes about an
# hour on a GitHub-hosted runner, so it is a standalone module: `all` skips it and the Full workflow runs it in
# its own job. The test timeout is above the observed duration with margin; nothing here relaxes the test.
ci_module() {
  # The Go bootstrap test temporarily writes this source-side fixture. Restore it even when the runner times out.
  cp selfhost/bootstrap/bootstrap.config "$MIO_CI_MODULE_DIR/bootstrap.config.original"
  trap 'cp "$MIO_CI_MODULE_DIR/bootstrap.config.original" "$CI_ROOT/selfhost/bootstrap/bootstrap.config"' EXIT
  trap 'exit 143' TERM HUP
  trap 'exit 130' INT
  MIO_CI_CHECK_TIMEOUT=10800 ci_check go bootstrap-selfcompile go test -json -p 1 ./selfhost/bootstrap -count=1 -timeout 175m
}
ci_main "$@"
