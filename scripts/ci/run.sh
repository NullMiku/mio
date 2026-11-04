#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
exec "${PYTHON:-python3}" "$root/scripts/ci/runner.py" run "$@"
