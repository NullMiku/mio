# PR #4–#7 测试接入方案

审计日期：2026-11-04。这里只提供贡献者可应用的方案；没有修改 PR 分支，也没有加入任何未合并实现。下面模板的语言测试执行状态均为 **NOT_RUN**。路径相对于各 PR 的仓库根目录。

## #4 / #5：原生模块入口

已核对 PR head：#4 `015b0f8`，#5 `2347ce6`。两者都没有 `test.sh` 或 `ci-module.json`。#5 的差异中包含 #4 的文件，必须先合入 #4，再更新 #5 并重新验证。

四个包都能在 macOS ARM64 用当前源码 Mio 编译器运行字节/IR 单元测试；生成的是 AMD64 字节不意味着运行测试的编译器已经是 Linux 原生编译器。Linux ELF 执行必须另列验证。

| 目录 | CI_MODULE / module | common.sh 相对路径 |
| --- | --- | --- |
| bunko/kiso/aot/x86_64 | kiso/aot/x86_64 | ../../../../scripts/ci/common.sh |
| bunko/kiso/aot/elf | kiso/aot/elf | ../../../../scripts/ci/common.sh |
| bunko/kiso/runtime/cpu/amd64 | kiso/runtime/cpu/amd64 | ../../../../../scripts/ci/common.sh |
| bunko/kiso/runtime/os/linux | kiso/runtime/os/linux | ../../../../../scripts/ci/common.sh |

每个目录放置独立的 `test.sh`，以下为 x86_64 的完整入口；其余三个按表替换模块 ID、source 路径及测试包路径：

```bash
#!/usr/bin/env bash
CI_MODULE=kiso/aot/x86_64
source "$(dirname "$0")/../../../../scripts/ci/common.sh"
ci_module() {
  ci_native native bunko/kiso/aot/x86_64
}
ci_main "$@"
```

相邻 `ci-module.json`：

```json
{
  "module": "kiso/aot/x86_64",
  "engine": "native",
  "targets": ["macos-arm64"],
  "suites": ["quick", "unit", "full"],
  "required_checks": ["native"],
  "skip_reason": "Mio native test execution requires macOS ARM64 and verified GF4 seed"
}
```

这些入口完成原生单元层接入，**不表示关键模块的独立验收已经完成**。不要给新模块设置 `covered_by` 来掩盖缺失的独立层。独立层实现后，在 manifest 的 `required_checks` 加入相应检查名并在入口使用 `ci_native_and_crosscheck`。如果已声明必需独立层却未实现，调度器会补记 NOT_RUN 并返回非零。

必须补齐的独立证据：

- x86_64：PR 已有 `python3 bunko/kiso/aot/x86_64/check_with_objdump.py`。它检查 56 组固定序列及显式反汇编预期，不能证明所有编码器行为。应作为 Linux 补充独立检查注册；GNU objdump 缺失/版本不兼容应明确报环境 NOT_RUN，不能当作原生 PASS。脚本当前缺工具退出 3，直接作为普通 command 会被记为 FAIL；接入时需先声明工具依赖并验证 GNU 版本，不能吞掉退出码。
- ELF：新增独立 reader/生成夹具入口，检查头、段权限、BSS、entry offset，并在 Linux 执行至少 bss=0、bss>0、非零 entry 三种真实生成镜像，对照退出码/输出。PR 所述手工执行尚未自动接入。此层 NOT_RUN。
- CPU/OS：#5 已有 `TestLinuxAMD64PureMioRuntimeChainExecutesNatively`；在 Linux 独立模块中用下面入口运行，严格禁止因宿主不符而悄悄 SKIP。它通过参考 VM 生成、执行 ELF；属于补充交叉验证，不代替 macOS 上的 Mio 原生单元层。

#5 新增 `internal/aot/linux-runtime-reference/test.sh` 可使用：

```bash
#!/usr/bin/env bash
CI_MODULE=linux-runtime-reference
source "$(dirname "$0")/../../../scripts/ci/common.sh"
ci_module() {
  ci_check go-required runtime-chain go test -json -p 1 ./internal/aot \
    -run '^TestLinuxAMD64PureMioRuntimeChainExecutesNatively$' -count=1 -timeout 2m
}
ci_main "$@"
```

对应 `ci-module.json`：

```json
{"module":"linux-runtime-reference","engine":"reference","targets":["linux-amd64"],"suites":["quick","unit","full"],"required_checks":["runtime-chain"]}
```

合入前检查 macOS 原生层与 Linux 独立层两份报告。#5 单独叠加而没有 #4 时属于依赖缺失导致的编译失败，不属于 Runner 故障。

## #6：已有独立入口

已核对 head `6f27416`：`bunko/kiso/aot/pe/{test.sh,ci-module.json}` 已存在，声明 macos-arm64、quick/unit/full、native 和 independent。没有 covered_by，可直接被新框架发现。

建议将入口中顺序调用改为下面形式，使原生层失败后仍收集独立层；在 #6 中由贡献者实施，本分支不添加 PE 包：

```bash
ci_module() {
  ci_native_and_crosscheck native bunko/kiso/aot/pe independent \
    "$PYTHON" tests/pe-writer/run.py --mio "$MIO_CI_MIO" \
    --mode native --output "$MIO_CI_MODULE_DIR/pe-images"
}
```

当前 Windows 执行夹具是额外显式检查，不在统一原生矩阵中。PR 自报的 VM/Windows PASS 不是本次执行证据；本次原生 Seed 验收 **NOT_RUN**。当前 draft 状态及未满足的原生证据需维护者处理。

## #7：参考 AOT 单独注册

已核对 head `d593e3e`：没有独立 test.sh/manifest。现有 `go-reference quick` 的包列表不包含 internal/aot 或 cmd/mochi-aot；`go-aot-reference` 仅 macOS。Linux Full 的 `go test ./...` 会递归包含它，但 PR Quick 会漏掉新 Linux AOT 测试。

在 #7 内新增 `internal/aot/linuxamd64/test.sh`：

```bash
#!/usr/bin/env bash
CI_MODULE=linux-aot-reference
source "$(dirname "$0")/../../../scripts/ci/common.sh"
ci_module() {
  local result=0
  ci_check go backend go test -json -p 1 ./internal/aot/... ./cmd/mochi-aot \
    -count=1 -timeout 30m || result=$?
  local name
  for name in TestEmitterScalarInstructionsMatchObjdump \
      TestEmitterHeapInstructionsMatchObjdump TestEmittedScalarCodeDecodesWithoutGaps \
      TestRuntimeBlobsRecordCurrentSourceHashes TestRuntimeBlobsMatchSources; do
    ci_check go-required "$name" go test -json -p 1 ./internal/aot/linuxamd64 \
      -run "^${name}$" -count=1 -timeout 5m || result=$?
  done
  return "$result"
}
ci_main "$@"
```

对应 `ci-module.json`：

```json
{
  "module":"linux-aot-reference",
  "engine":"reference",
  "targets":["linux-amd64"],
  "suites":["quick","unit","full"],
  "requires":["go","gcc","objdump","objcopy","nm","python3","sh"],
  "required_checks":["backend","TestEmitterScalarInstructionsMatchObjdump","TestEmitterHeapInstructionsMatchObjdump","TestEmittedScalarCodeDecodesWithoutGaps","TestRuntimeBlobsRecordCurrentSourceHashes","TestRuntimeBlobsMatchSources"]
}
```

`go-required` 对空测试、失败及任何 SKIP 返回非零。普通 go 检查保留现有平台跳过明细；五项必需检查分别执行，不能靠另一个 PASS 隐藏缺失测试。GNU objdump、gcc 14.2.0 等实际要求需匹配开发环境；默认 ubuntu-24.04 不保证满足 blob 重建版本。没有固定工具链时该必需检查应为 NOT_RUN，不能宣称验证完成。不要把本参考实现标成 engine=native。

还应在 macOS 执行受影响 internal/aot 与 cmd/mochi-aot 的回归。#7 包含实际嵌入的 C runtime/blob；它是否符合项目正式实现边界需要维护者独立架构决定，CI 审计不能替代此决定，也不将它加入正式运行时。本方案未执行、未批准或合并该实现。
