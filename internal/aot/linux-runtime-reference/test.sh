#!/usr/bin/env bash
CI_MODULE=linux-runtime-reference
source "$(dirname "$0")/../../../scripts/ci/common.sh"
# Supplementary Go check that runs the whole pure-Mio Linux runtime chain (IR -> cpu/amd64 -> x86_64 -> elf, with
# os/linux) in the reference VM and executes the produced ELF. It must not be skipped, so go-required turns a SKIP
# into NOT_RUN. It does not replace the Mio native tests of the packages.
ci_module() {
  ci_check go-required runtime-chain go test -json -p 1 ./internal/aot \
    -run '^TestLinuxAMD64PureMioRuntimeChainExecutesNatively$' -count=1 -timeout 2m
}
ci_main "$@"
