#!/usr/bin/env bash
CI_MODULE=go-linux-native
source "$(dirname "$0")/../../../scripts/ci/common.sh"
# Pure-Mio Linux AMD64 backend (kiso/aot/lowerlinux). Nothing here replaces the trusted macOS Native Seed
# verification; the seed of these checks is the experimental Go-hosted one, and none of them may SKIP silently
# (go-required turns a skipped test into NOT_RUN).
#   quick  encoder / ELF / runtime packages in the reference VM, GNU objdump cross-check, VM-vs-native differential
#   unit   + the same programs under a 16 KiB collection threshold
#   full   + A->B->C->D fixed points of the backend driver, the compiler and the CLI, and native `mio test` cases
ci_module() {
  local result=0
  ci_check command encoder-and-runtime-vm bash -c '
    set -e
    for package in bunko/kiso/aot/x86_64 bunko/kiso/aot/elf bunko/kiso/runtime/cpu/amd64 bunko/kiso/runtime/os/linux; do
      MIO_BUNKO="$PWD/bunko" go run ./cmd/mio test "$package"
    done' || result=$?
  ci_check command objdump "$PYTHON" bunko/kiso/aot/x86_64/check_with_objdump.py || result=$?
  ci_check go-required lowering-differential go test -json -p 1 ./internal/aot \
    -run '^TestLinuxAMD64PureMio(LoweringMatchesVM|LoweringRejectsUnsupported|LowersItsOwnDriver|RuntimeChainExecutesNatively)$' -count=1 -timeout 20m || result=$?
  if [[ $2 == unit || $2 == full ]]; then
    ci_check go-required gc-stress go test -json -p 1 ./internal/aot -run '^TestLinuxAMD64PureMioLoweringUnderGCStress$' -count=1 -timeout 20m || result=$?
  fi
  if [[ $2 == full ]]; then
    ci_check go-required native-fixed-points go test -json -p 1 ./internal/aot \
      -run '^TestLinuxAMD64(PureMioDriverNativeFixedPoint|NativeCompilerFixedPoint|NativeCLIFixedPoint)$' -count=1 -timeout 60m || result=$?
  fi
  return "$result"
}
ci_main "$@"
