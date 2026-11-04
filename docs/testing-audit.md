# Mio CI V2 审计与验收

日期：2026-11-04；实施分支：`Mio-2.1`。开始时在 `windows-amd64/pe-writer`，确认无跟踪文件修改及 PE 路径冲突后，按用户要求切换到已有 `Mio-2.1`。本任务开始时分支提交为 `0884282367c713722cc0a9087f629853f5a98f5f`。本任务未执行 commit、push、创建 PR 或远端 workflow dispatch。

开始时未跟踪的 `bunko/kiso/aot/pe/` 原样保留。期间观察到独立的 Issue/PR 模板暂存及提交变化，没有重置或纳入本任务；最终变更列表只列本任务拥有的文件。已有测试源码、测试数据及发布工作流保留。

## A：旧工作流分类与删除

| 原路径 | 分类 | 处理 |
| --- | --- | --- |
| `.github/workflows/ci.yml` | 普通 CI：Go 质量、Linux 参考实现、macOS AOT/race/固定点 | 删除，由仓库模块入口及新 Quick/Full 调度取代 |
| `.github/workflows/native-tests.yml` | 普通 CI：原生模块及 Linux 补充测试 | 删除，新 PR/Full 统一调度 |
| `.github/workflows/release.yml` | 原生发布/打包/签名流水线 | 保留，内容未改 |
| `.github/workflows/release-candidate.yml` | 发布策略手动验证 | 保留，内容未改 |

当前 `.github/workflows/` 没有单独安全检查或其他独立自动化。`.github/legacy-workflows/` 下的历史发布与 CI profile 是非激活历史资料，原样保留。删除前逐个读取并确认用途，没有递归删除目录。

参考旧运行 [41603555344](https://github.com/mio-kobo/mio/actions/runs/41603555344) 的公开页面确认该次运行失败，并显示缺少 artifact、Go 缓存无 go.sum 等注解；日志正文需要登录，未把用户提供的全部诊断视为本次已复现结果。

## B–D：新架构与接入范围

```text
ci-pr.yml / ci-full.yml
  -> scripts/ci/run.sh -> runner.py
  -> discovered ci-module.json + adjacent test.sh
  -> common.sh / ci_native / ci_native_and_crosscheck / ci_check
  -> report.json + build/module/check logs
```

工作流只安装开发工具、调度统一入口并上传产物，使用 `contents: read`、checkout 禁止保留凭据，无 secrets、pull_request_target、自动合并或 continue-on-error。PR 使用 Quick；Mio-2.1 push、手动及周计划使用 Full，周计划显式检出 Mio-2.1。macOS 重任务在两份工作流间共享 concurrency group；模块内顺序执行。现有 `mio-native` macOS ARM64 主机需要提供受信任 Seed，外部 PR 仍服从仓库正常运行审批。

Runner 复用既有模块测试资产，新增当前源码原生编译器构建及复用、构建单独报告、显式工具依赖、整次运行零执行拒绝成功、无效协议检测、失败优先汇总、取消处理及 Windows 进程树清理。Seed 仅用于构建当前源码及既有 ABCD/生产流程，不用旧 Seed 直接冒充当前源码测试。GF4 SHA256 未放宽。

共发现 26 个模块，保留既有入口并补强关键交叉验证：

- Core：`selfhost/cli/test.sh`，原生 pipeline 测试及独立编译/输出/负向前端检查。
- AOT：`bunko/kiso/aot/test.sh`，递归原生测试及独立编码/目标文件/执行验证。
- GC：`bunko/kiso/runtime/gc/test.sh`，原生测试及实际 GC 遥测。
- Selfhost：`selfhost/test.sh`，Full 原生全集。
- Bootstrap：`selfhost/bootstrap/test.sh`，原生 codegen 测试、纯 Mio ABCD 构建与独立复核。
- 标准库 16 项：aot/arm64、aot/lower、aot/lower/types、aot/macho、crypto/sha256、encoding/binary、encoding/json、encoding/mochi、io、math、net/tcp、path、regexp、runtime/cpu/aarch64、runtime/os/darwin、runtime/target，均位于 `bunko/kiso/`，各有自己的 test.sh。
- `go-reference`、`go-aot-reference`、`legacy-bootstrap`：补充历史 Go/VM/AOT/race/BCD/M17/M18 回归。
- `quality`：格式、vet、框架自检及发布隔离。
- `native-release`：显式 release suite，保留既有生产沙箱流程及独立 archive 审核。

当前受版本控制的所有 Bunko `*_test.mio` 包都有入口。AOT 子包在 all 调度时可由父级递归覆盖，单独记录 SKIP/委托原因；显式选择时运行自己的原生和适用独立层。Full 包含历史固定点和 race，不因旧失败删除测试。

未独立接入：array、bytes、convert、fs、os、string、testing、utf8、aot/lower/nativefs、aot/sign、runtime/ir、regexp/unicode_data（没有自己的 Mio 测试包，仅部分集成覆盖）；net/tcp.before-patch 是历史副本。E5/E6 长压力、多 mutator/并发 GC、完整外部 FFI ABI 及其他平台后端尚未整体接入，不能宣称通过。PE 开发文件属于用户独立工作，本次未注册或修改。

## 独立交叉验证

- Core：编译九参数函数、数组、字符串，检查 Mach-O/签名，在空 PATH 环境运行并对照固定输出和退出码；非法词法、语法、未定义符号、类型错误必须失败；故意错误的 Mio 断言必须非零退出且 JSON failed=1。
- ARM64 编码器/Mach-O Writer：直接调用模块生成 MOVZ、负向分支和退出 syscall，Python 比较固定 words、头、768 字节入口和含 NUL 常量布局；签名后运行产物，必须退出 42。AOT、编码器和 Writer 的单独入口均可运行这个 oracle。
- Runtime CPU：原生 IR 验证加独立实际程序/ABI 输出检查。
- GC：保留现有纯 Mio 1 MiB 受限堆 builder，输出必须是 4797，64 字节遥测必须证明发生 minor GC，且根及资源生命周期计数匹配。
- Bootstrap：保留现有 ABCD signed/unsigned/resigned 字节固定点及 verify。历史 BCD/M17/M18 独立补充 gate 从 `d4a11b3^` 恢复，未改历史哈希、祖先约束或见证断言；BCD 在独立源码副本执行，两套历史 gate 复用已构建参考工具。

这些路径已实现；新增 macOS 原生 oracle 尚未在本 Windows 主机执行。不能把实现完成或模拟协议自检写成原生交叉验证通过。

## E–G：本地验证

详细日志：`build/ci-v2-validation/`，均为忽略的本地开发产物。

| 检查 | 本次状态 | 范围 |
| --- | --- | --- |
| 框架自检 | PASS | 31 项；真实 Bash 调度、日志、并行子失败、管道、重定向、0/1/2、超时及后代清理、无效模块/平台/超时参数、缺依赖、空/全跳过、损坏报告、取消、构建复用与构建失败等，无 SKIP |
| Shell 语法 | PASS | 32 个入口、ABCD 及恢复的历史脚本，实际 bash -n |
| Python 语法 | PASS | AST 解析驱动及历史 Python 脚本 |
| 新 workflow | PASS（静态） | actionlint 1.7.7；不等于 GitHub 执行通过 |
| 质量检查 | PASS | Windows CRLF 输入先在临时副本中规范换行，再 gofmt 检查；go vet 与 git diff --check；没有格式化源码 |
| 发布隔离 | PASS（静态） | 允许的 archive 文件、空 PATH 沙箱、源码依赖方向；不等于实际 release 构建 |
| 后端 oracle 补充验证 | PASS（Go VM） | 实际生成固定 ARM64/Mach-O 字节并匹配；原生签名/执行仍 NOT_RUN |
| Golden 换行修正 | PASS | Git 跟踪字节本来是 LF；声明该 fixture 固定 LF 后按原字节检出，TestRendererUnicodeGolden 复跑通过，未改预期 |
| 真实统一/单模块入口 | PASS（拒绝错误主机） | Windows 请求 macOS 或 windows-amd64 均返回 NOT_RUN/2；对应语言测试没有运行 |
| Windows Go 全量补充回归 | FAIL | 1468 PASS、9 FAIL、147 SKIP（测试节点）；另有自举包 30 分钟超时，详见下节 |
| macOS ARM64 原生 Quick/Full | NOT_RUN | 当前主机为 Windows，没有原生 Seed/执行环境 |
| Linux AMD64 Quick/Full | NOT_RUN | 本次没有 Linux 执行环境；仅配置适用参考测试，不宣称原生 Linux AOT |
| Windows 原生 CI 矩阵 | NOT_RUN | 后端尚未成熟，未制造空 job；仅验证开发基础设施和 Go 补充实现 |
| 真实生产打包/安装 | NOT_RUN | 需 macOS 与冻结生产输入，发布 workflow 未改 |
| GitHub Actions 新工作流执行 | NOT_RUN | 未推送、未触发、未宣称远端通过 |

## 配置与基础设施修复

- 删除两份旧普通 CI，重新建立 PR/Full，两平台均调用 all quick/full；修复重复旧 workflow 调度。
- Go 无 go.sum：setup-go 禁用该仓库不适用的依赖缓存。
- 补回缺失历史脚本，Full 真正调用 BCD/M17/M18 和 AOT race，保留原检查失败。
- 当前源码原生编译器只构建一次；原生构建失败本身记 FAIL，依赖该编译器的测试记 NOT_RUN，不回退 Go。
- 全跳过、空模块、损坏报告、缺必需层、取消以及缺工具均非零退出；失败不会被基础设施错误覆盖为成功。
- Shell 和逐字节比较的 Unicode golden 固定 LF，Go 格式检查在临时副本统一 CRLF，保持 Windows 可复现且不改源码或 golden 预期。Golden 的工作树规范化后逐字节等于 Git 原有 blob。

保留的 release-candidate.yml 仍依赖当前分支缺失的 release_automation 脚本，这是已有发布策略验证问题，本任务未改发布流水线。生产模块引用的冻结 fixture/源码 pin 也需要单独核实及补齐；静态隔离 PASS 不代表这些发布输入齐备。

## H：使用方式与后续

```bash
bash scripts/ci/selftest.sh
bash scripts/ci/run.sh macos-arm64 core quick
bash bunko/kiso/aot/arm64/test.sh macos-arm64 quick
bash scripts/ci/run.sh macos-arm64 all full
bash scripts/ci/run.sh linux-amd64 all quick
bash scripts/ci/run.sh linux-amd64 all full
```

新增模块、test.sh 写法、suite_checks/requires、状态与报告解读见 [测试架构](testing.md)。CONTRIBUTING.md 已同步 CI V2 规则，保留维护者主导方式。

下一步：在受信任 macOS ARM64 主机运行 Quick/Full，分别审查两层及当前源码构建报告；在 Linux Runner 执行补充 Quick/Full；按下节真实失败报告修复 Core 前先确认具体实现变更范围。完整 FFI、长期/并发 GC 和 E5/E6 可作为后续分批接入，不能勾选已完成。

## 本任务文件清单

删除：`.github/workflows/ci.yml`、`.github/workflows/native-tests.yml`。

新增：`.github/workflows/ci-pr.yml`、`.github/workflows/ci-full.yml`、`scripts/check-native-bootstrap.sh`、`scripts/check-native-aot-fixed-point.py`、`scripts/ci/legacy_bootstrap.py`、`scripts/ci/format_go.py`。

修改：`.gitattributes`、`CONTRIBUTING.md`、`docs/testing.md`、`docs/testing-audit.md`；`scripts/ci/{runner.py,selftest.py,common.sh,quality.sh,test.sh,verify_native.py,ci-module.json,legacy/test.sh,legacy/ci-module.json}`；`internal/{test.sh,ci-module.json,aot/test.sh,aot/ci-module.json}`；`selfhost/cli/test.sh`、`selfhost/bootstrap/{test.sh,ci-module.json}`；`tools/native-ci/{test.sh,ci-module.json}`；`bunko/kiso/aot/test.sh`、`bunko/kiso/aot/{arm64,macho}/{test.sh,ci-module.json}`、`bunko/kiso/runtime/gc/test.sh`、`bunko/kiso/runtime/cpu/aarch64/{test.sh,ci-module.json}`。

没有修改 Go/Mio 编译器实现、GC 或 ABI 源码，未新增正式运行依赖。

## 当前复现的 Core 失败与分类

- C / Resolver：`selfhost/resolver/resolver_diff_test.go:474`，`TestMioResolverSelfAndBunkoSources`：`package kiso/string resolve errors=1`。
- C / Typechecker 前置解析：`selfhost/typecheck/typecheck_diff_test.go:836`，`TestMioTypecheckerSelfAndBunkoSources`：`package kiso/string resolve errors=1 type errors=0`。
- C / Codegen：`selfhost/codegen/codegen_diff_test.go:427`，`TestCodegenSelfAndBunkoSources`：`field owner is not a struct`、`jump references an undefined label`。产生诊断的实现位于 `selfhost/codegen/compiler.mio:459`、`selfhost/codegen/emitter.mio:92`。本任务未改这些实现。
- `old_sweep_enabled undefined` 及 `AOT M7 static string data exceeds __const limit` 未在此次 Windows 环境重新复现；需要对应 macOS AOT 路径，不标为已修复。
- Windows 补充测试还报告 `TestRunWritesNativeExecutable`（POSIX 执行位假设）、`TestM14NativeStatSemantics`/`TestM14NativeMkdirSemantics`（创建 symlink 缺权限）、`TestM14NativeSocketCompilesPureMioTCP`（找不到 mio/sys/socket）、`TestPathFromURI`（POSIX 路径假设）。这些没有通过改实现或放宽断言规避。
- `TestRendererUnicodeGolden` 首轮失败来自 CRLF 检出，归为 B；已固定检出换行并按原 blob 复跑通过。原始全量日志仍保留初次失败，复跑日志为 `build/ci-v2-validation/golden-lf-recheck.jsonl`。

上述 Core 源码错误及平台基线继续保持失败，不能将框架自检通过误读为语言测试通过。

## 最终 Go 补充回归结果

实际命令：`go test -json -p 2 ./... -count=1 -timeout 30m`，进程退出码 1。测试节点统计 1468 PASS、9 FAIL、147 SKIP，包含条件跳过，不是原生 AOT 验收。`TestBootstrapSelfCompilation` 已运行到 Compiler C，随后达到此次复现命令的 30 分钟期限；该包为 FAIL，未宣称自举固定点通过。

9 项显式失败即上节列出的 3 项 Core 差分、5 项 Windows/参考实现基线及 1 项 golden 换行问题。Golden 修复后原测试复跑 PASS，其余 8 项没有改动或绕过；完整全量没有在修复 golden 后重跑。自举时间预算问题已经在新 Full 入口中改为 Go 包 60 分钟、检查器 6600 秒，但新的长自举预算尚未实跑验收，不能标记为通过。

Go 超时没有执行原测试 cleanup，留下了本次运行自己的临时 bootstrap.config 路径。已核对该路径属于本次测试后恢复为开始时 Git blob，并验证完全一致；没有遗留该配置改动或本次 Go/test 进程。新 Full 模块增加原配置备份与退出/信号恢复；历史 BCD 则完全在独立源码副本执行。

机器可读结果为 `build/ci-v2-validation/go-windows-summary.json`；统一验证检查为 `build/ci-v2-validation/final-checks.json`。Go 原始 PowerShell UTF-16 输出另存 `.powershell-utf16.log`，JSONL 已转为 UTF-8 便于读取；新 CI 驱动直接捕获子进程字节，不经过 PowerShell 文本转换。

验收边界：普通旧 CI 删除、新调度、模块协议、日志/JSON、失败传播及本地自检完成；macOS/Linux 真机、原生双层检查、远端 Actions、完整长压力/FFI 及实际生产发布尚未验收。现有 Core 错误仍然失败。
