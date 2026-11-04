#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
cd "$root"
"${PYTHON:-python3}" scripts/ci/format_go.py
go vet ./...
git diff --check
