# Mio-2.1 测试架构审计与验收记录

日期：2026-11-04。基准提交：`11820c116df1904c575e0ca576a67a7f4177a62f`。最终工作分支：`Mio-2.1`，跟踪 `origin/Mio-2.1`。未提交、未推送、未创建 PR。

## 审计结论与复用

最初检出的是干净的 `Mio-2`；用户指定 v2.1 后，保留本次新增文件，切换到已有远端 `Mio-2.1` 并重新审计。旧分支测试结果不作为本分支验收证据。切换前中止了旧分支完整 Go 测试，标记 NOT_RUN；其临时 bootstrap.config 已恢复，最终没有配置文件改动。

可复用：现有 `*_test.mio`、原生 `selfhost/testrunner`、Native Seed、Go 参考测试、`tests/m19ef/bootstrap-abcd.sh`、受限堆 automatic-roots builder，以及纯 Mio `tools/native-ci` 的构建/打包/安装流程。新增统一调度、模块协议、分层结果、独立 oracle、负向自检、隔离检查和贡献文档。

不应替换：正式 `.github/workflows/release.yml`、`tools/native-ci/*.mio`、`production.sb`、现有 ABCD/E5/E6 验证器和全部语言核心实现。本次没有修改这些文件，也没有改变 go.mod、LICENSE、ABI、GC 或语言语义。旧参考 CI 的重要检查改为通过仓库入口调用，保留其历史 artifact 上传。

当前真正有原生执行路径的是 macOS ARM64。Linux AMD64 仅有 Go/VM 参考实现验证；Linux ARM64、macOS AMD64、Windows 均未宣称支持原生 AOT。Windows 本地检查不能替代 macOS/Linux Runner 的实测。

## 实现与关键规则

主入口：`bash scripts/ci/run.sh <target> <module> <suite>`。共注册 26 个模块，清单和结构见 [测试架构](testing.md)。原生模块先执行 Mio 测试；Core、AOT、GC、自举、发布分别具有独立检查定义。原生层与独立层各自保存状态，缺 Seed 或中途未执行的层记为 NOT_RUN。Go 明确列为补充参考实现。

Core/AOT 独立验证覆盖基本源程序编译、9 参数内部调用约定、Mach-O、签名和实际输出，并核查故意失败的原生断言。GC 独立验证复用现有纯 Mio builder，检查输出、真实 minor collection 和根/资源生命周期遥测。ABCD 使用现有原生脚本构建和独立 verify。以上路径已经实现，但本环境未实际运行，不能称为“已验证通过的双重覆盖”。

CONTRIBUTING.md 明确维护者主导、尊重贡献者并说明决策理由、提前讨论重大设计、沿用 Conventional Commits 风格、配套回归测试、如实提供平台证据、MIT 与角色图像许可分开、允许 AI 辅助但由提交者负责。测试通过不承诺合并。文档包含要求的英文原生测试优先原则，以及外部工具与 Core 完全隔离的规则。

## 实际验证结果

| 检查 | 状态 | 证据及范围 |
| --- | --- | --- |
| 30 个 Shell 脚本语法 | PASS | 实际 Git Bash `-n` |
| 测试基础设施负向自检 | PASS | 18 项全部通过，实际经 `selftest.sh` 执行；本次无 SKIP |
| 真实成功/故意失败/空模块调度 | PASS | 分别产生 PASS/0、FAIL/1、NOT_RUN/2；检查实际 JSON 和日志文件 |
| 失败命令经 tee 管道 | PASS | Bash pipefail 保留退出码 7 |
| Windows 冒充 macOS 原生执行 | PASS | 真实入口拒绝主机不匹配，返回 2；被请求的原生测试本身为 NOT_RUN |
| Python 语法及 26 项注册发现 | PASS | 标准库 AST 和实际 discover |
| 两份修改/新增 workflow YAML | PASS | PyYAML 6.0.3 解析；无 continue-on-error |
| 发布隔离源码检查 | PASS | 三文件 allowlist、空 PATH、生产执行沙箱、导入方向、嵌入资源检查 |
| 污染发布包的负向检查 | PASS | 故意混入 runner.py 的 tar.gz 被拒绝；不是实际 Release 验证 |
| Go 参考 CLI 构建，无测试工具 PATH | PASS | PATH 只保留 Windows 系统目录；不代表正式 Native Release |
| go vet ./... | PASS | Windows，Go 1.22.2 |
| Go 补充测试，沙箱外复跑 | FAIL | `./internal/... ./cmd/... ./mma`：1403 PASS、147 SKIP、6 FAIL（含父/子测试节点） |
| selfhost 差分测试基线 | FAIL | resolver/typecheck/codegen 的 SelfAndBunkoSources 均报告 kiso/string resolve errors=1 |
| Windows 统一原生后端 | SKIP | 未支持，不提供伪通过入口 |
| macOS ARM64 Mio 原生层 | NOT_RUN | 当前机器是 Windows；无受信任 Native Seed |
| macOS ARM64 独立 Core/AOT/ABI/GC | NOT_RUN | 同上，不能以交叉编译替代执行 |
| 原生 ABCD 固定点 | NOT_RUN | 需要 macOS ARM64 和既有 Seed |
| Linux AMD64 Runner | NOT_RUN | 本次未连接或触发 Linux 运行环境 |
| 实际 Native Release 构建/安装/包审核 | NOT_RUN | 无 macOS Seed；生产冻结 fixture 也有基线缺失，见下文 |
| 远端 GitHub CI 红/绿状态 | NOT_RUN | 未推送、未触发 workflow；仅完成本地失败传播实测 |

原始日志保存在本地 `build/ci-validation/`、`build/v21-go-windows-unsandboxed.jsonl`、`build/v21-baseline-go-windows.jsonl`。机器可读汇总为 `build/ci-validation/summary.json`。完整文件清单在本记录末尾。

## 已有基线问题与环境限制

沙箱内测试额外出现 Windows 临时文件 rename 权限失败，不能误判为语言回归；沙箱外复跑后，相关大批失败消失。残留 6 项分别为：

- `TestM14NativeStatSemantics`、`TestM14NativeMkdirSemantics`：Windows 创建符号链接缺少权限。
- `TestM14NativeSocketCompilesPureMioTCP`：现有 Go 参考测试找不到 `mio/sys/socket` 模块。
- `TestRendererUnicodeGolden`：当前 CRLF checkout 的 golden 文本与实际 LF 输出不匹配。
- `TestPathFromURI`：Windows 路径与测试的 POSIX 路径假设不一致。
- `TestRunWritesNativeExecutable`：Windows 文件执行位与 POSIX 测试假设不一致。

现有 selfhost 的 3 个源码差分失败均在未修改的 Go/Mio 源码上出现；未为这些基线问题修改编译器。macOS/Linux 上是否有同样失败仍为 NOT_RUN。

`Mio-2.1` 的旧 CI 仍引用已不存在的 `scripts/check-native-bootstrap.sh` 和 `scripts/check-native-aot-fixed-point.py`；legacy candidate workflow 同样引用已不存在的 release_automation 脚本。新入口保留 BCD/M17/M18 gate，缺脚本时如实失败，不删除重要验证，也不伪造历史产物。

正式 `tools/native-ci` 的 component manifest 引用 `tests/gofree/runtime_metadata.mio.fixture` 和 `tests/gofree/unsigned_image_audit.mio.fixture`，但当前 checkout 缺少这些文件。生产固定 source hash、内嵌资源、Seed 的一致性也需要在对应主机上按既有流程验证。本次不改生产 pin 来使流程变绿。

GitHub 连接器在最初查询旧分支提交时返回的 PR-triggered workflow 列表为空；这不能证明历史 CI 已通过。本分支的远端 CI 状态未声称已知。

本次新增基础设施未发现尚未修复的本地语法/自检失败；原生路径尚未实跑，因此仍存在待对应平台验证的集成风险。

## 发布隔离证据与限制

新增外部依赖只安装在开发环境：Go 工具链和 YAML 校验包位于忽略的 `.cache/`，检查结果和参考工具位于忽略的 `build/`。未引入正式依赖文件，未把测试工具链接或嵌入编译器。

正式生产 workflow、Mio 打包代码和生产沙箱保持原样。静态检查确认打包仅包含 `mio`、`LICENSE`、`README.txt`；生产 workflow 不安装 Python/Go 测试依赖，空 PATH 由原有沙箱限制执行范围。新增 native-release 模块在沙箱外收集证据，生产输出按原流程置于 checkout 外，避免 SOURCE 写禁令冲突，并保留路径记录。

实际发布验证命令是 `bash scripts/ci/run.sh macos-arm64 native-release release`：原生 archive 测试 → 原有生产构建/自举/安装烟测 → 外部真实 archive 清单和运行时标记检查。该命令的实际执行状态是 NOT_RUN，静态检查不能替代它。

## 尚未覆盖与下一步

部分基础库没有独立 Mio 测试包，未创建空 test.sh；selfhost 的独立验证未逐阶段拆分，完整外部 FFI/ABI、长期/并发 GC、多 mutator 及其他架构仍未验收。E5/E6 原有控制器含固定路径、fixture 和分支约束，保留原状，没有冒充已集成。

下一步应在现有 `mio-native` macOS ARM64 Runner 上提供已验证 GF4 Seed，运行原生 Quick/Full，分别审查两层报告；补齐原有冻结生产输入后运行显式 release suite；随后在 Linux Runner 复现补充检查并处理上述基线问题。全部命令与协议见 [测试架构](testing.md)。

## 新增和修改文件

- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/workflows/ci.yml`
- `.github/workflows/native-tests.yml`
- `.gitignore`
- `CONTRIBUTING.md`
- `README.md`
- `bunko/kiso/aot/arm64/ci-module.json`
- `bunko/kiso/aot/arm64/test.sh`
- `bunko/kiso/aot/ci-module.json`
- `bunko/kiso/aot/lower/ci-module.json`
- `bunko/kiso/aot/lower/test.sh`
- `bunko/kiso/aot/lower/types/ci-module.json`
- `bunko/kiso/aot/lower/types/test.sh`
- `bunko/kiso/aot/macho/ci-module.json`
- `bunko/kiso/aot/macho/test.sh`
- `bunko/kiso/aot/test.sh`
- `bunko/kiso/crypto/sha256/ci-module.json`
- `bunko/kiso/crypto/sha256/test.sh`
- `bunko/kiso/encoding/binary/ci-module.json`
- `bunko/kiso/encoding/binary/test.sh`
- `bunko/kiso/encoding/json/ci-module.json`
- `bunko/kiso/encoding/json/test.sh`
- `bunko/kiso/encoding/mochi/ci-module.json`
- `bunko/kiso/encoding/mochi/test.sh`
- `bunko/kiso/io/ci-module.json`
- `bunko/kiso/io/test.sh`
- `bunko/kiso/math/ci-module.json`
- `bunko/kiso/math/test.sh`
- `bunko/kiso/net/tcp/ci-module.json`
- `bunko/kiso/net/tcp/test.sh`
- `bunko/kiso/path/ci-module.json`
- `bunko/kiso/path/test.sh`
- `bunko/kiso/regexp/ci-module.json`
- `bunko/kiso/regexp/test.sh`
- `bunko/kiso/runtime/cpu/aarch64/ci-module.json`
- `bunko/kiso/runtime/cpu/aarch64/test.sh`
- `bunko/kiso/runtime/gc/ci-module.json`
- `bunko/kiso/runtime/gc/test.sh`
- `bunko/kiso/runtime/os/darwin/ci-module.json`
- `bunko/kiso/runtime/os/darwin/test.sh`
- `bunko/kiso/runtime/target/ci-module.json`
- `bunko/kiso/runtime/target/test.sh`
- `docs/testing-audit.md`
- `docs/testing.md`
- `internal/aot/ci-module.json`
- `internal/aot/test.sh`
- `internal/ci-module.json`
- `internal/test.sh`
- `scripts/ci/ci-module.json`
- `scripts/ci/common.sh`
- `scripts/ci/legacy/ci-module.json`
- `scripts/ci/legacy/test.sh`
- `scripts/ci/quality.sh`
- `scripts/ci/release_isolation.py`
- `scripts/ci/run.sh`
- `scripts/ci/runner.py`
- `scripts/ci/selftest.py`
- `scripts/ci/selftest.sh`
- `scripts/ci/test.sh`
- `scripts/ci/verify.py`
- `scripts/ci/verify_native.py`
- `selfhost/bootstrap/ci-module.json`
- `selfhost/bootstrap/test.sh`
- `selfhost/ci-module.json`
- `selfhost/cli/ci-module.json`
- `selfhost/cli/test.sh`
- `selfhost/test.sh`
- `tools/native-ci/ci-module.json`
- `tools/native-ci/test.sh`
