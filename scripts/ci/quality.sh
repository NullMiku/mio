#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
cd "$root"
work=$(mktemp -d)
trap 'rm -f "$work/files" "$work/unformatted"; rmdir "$work"' EXIT
git ls-files -z -- '*.go' > "$work/files"
# BSD xargs lacks -r; the repository always has tracked Go sources.
xargs -0 gofmt -l < "$work/files" > "$work/unformatted"
if [[ -s $work/unformatted ]]; then cat "$work/unformatted"; exit 1; fi
go vet ./...
git diff --check
