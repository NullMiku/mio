#!/usr/bin/env bash
set -euo pipefail
M19E_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd -- "$M19E_ROOT"
exec python3 tests/m19ef/run_native_e5.py "$@"
