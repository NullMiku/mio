[English](../CONTRIBUTING.md) | [简体中文](CONTRIBUTING.zh-CN.md) | [日本語](CONTRIBUTING.ja.md)

---

# 为 Mio 做贡献

欢迎 Bug 报告、文档修订、测试补充、Bunko 标准库扩展、编译器优化、平台移植和架构建议。Bug 报告请附最小复现、版本、操作系统及架构、预期行为和实际输出。

## 治理与设计

Mio 采用维护者主导（Maintainer-led Governance）模式。贡献者可以提出方案、参与讨论并提交实现；维护者负责最终的语言设计、技术路线及 PR 合并决定。维护者应提供清晰、合理且尊重贡献者的审查反馈和决策理由。设计未获接受，不能成为否定贡献者技术能力的理由。

审查优先考虑语言设计一致性、长期可维护性和架构完整性。目前的方向包括原生 AOT、自举、清晰严格的类型系统和模块化架构。应控制核心复杂度，谨慎处理 ABI、运行时、GC 及平台兼容性，避免为单个功能增加不必要的全局复杂度。这些原则为探索提供方向，并不排除未来的技术方案。

## 开始贡献

在 GitHub Fork 仓库，克隆自己的 Fork，在当前开发分支基础上创建主题分支。完成后向上游对应分支提交 PR，并填写模板。下面的 Fork 名称和分支名是示例，需要替换为自己的值：

```bash
git clone https://github.com/YOUR-NAME/mio.git
cd mio
git switch -c fix/topic
```

本分支为 `Mio-2.1`。正式源码构建沿用已有受信任 Native Seed 和纯 Mio 自举架构；macOS ARM64 上的命令接口为：

```bash
"$MIO_NATIVE_SEED" build selfhost/cli --bunko-root "$PWD/bunko" -o /absolute/new/path/mio
```

受信任 Seed 的版本及 SHA256 约定见测试说明。Go（版本见 `go.mod`）仅用于参考前端/VM、补充测试，以及无受信任 Seed 时生成 go-hosted Stage A；没有任何 Go 程序生成原生代码（Go AOT 后端已删除）。统一测试驱动使用 Bash、Python 3.9+ 和 Git，原生签名检查使用 macOS 系统 `codesign`；它们都不是正式 Mio 的新增依赖。日常命令为：

```bash
bash scripts/ci/selftest.sh
# 在具备受信任 Seed 的 Apple Silicon Mac 上：
bash scripts/ci/run.sh macos-arm64 all quick
# Linux 上仅运行补充参考实现，不能替代上面的原生验收：
bash scripts/ci/run.sh linux-amd64 go-reference quick
```

命令的验证范围和实际状态见 [测试说明](testing.md) 与 [审计记录](testing-audit.md)。本次实现环境是 Windows；文档不会把未执行的平台命令描述为已通过。

## 提前讨论的变更

语言语法、类型系统、核心运行时、GC、ABI、编译器主要架构、新后端及大规模依赖变更，建议先开 Issue 说明问题、备选方案、兼容性与验证方法。提前讨论有助于减少方向不一致带来的实现成本，同时欢迎正常的技术探索和实验。

## Commit 与 PR 范围

现有历史使用 `feat(bootstrap): ...`、`fix(aot): ...`、`docs: ...`、`chore: ...` 等简洁前缀，可继续使用 `feat`、`fix`、`test`、`docs`、`refactor`、`ci`、`chore`，按需注明 scope。描述具体变化及原因，中英文均可；不要求重写历史。

每个提交应是可审查的逻辑单元。将无关修复、广泛重构与功能变化拆为不同 PR；相关测试和文档随实现提交。避免夹带格式化、构建产物、个人配置或无关源码改动。

## 测试证据

**Mio's native testing framework is the primary testing mechanism. External tools and other programming languages are permitted for supplementary testing and independent cross-validation only.**

所有贡献者应优先使用 Mio 原生测试框架。普通模块、标准库以及 Core、AOT、GC 首先运行 Mio 编写的测试；关键模块再运行独立验证。两层分别记录状态。只有框架尚不支持的测试类型，才应说明限制并采用辅助方案。其他语言测试工具不构成正式实现的一部分。

独立可测试模块应提供自己的 `test.sh` 和相邻 `ci-module.json`；现有尚无独立入口的包在测试说明中记录，新增模块应遵守此接口。共用环境检查、日志与报告代码，不复制整套框架。

代码 PR 应附实际运行的命令、目标平台、结果和日志。使用 `PASS / FAIL / SKIP / NOT_RUN` 区分状态，并说明跳过原因。不得将未运行、空测试或仅交叉编译写成通过。

新功能通常应配套测试；Bug 修复尽可能增加能重现原问题的回归测试。编译器、代码生成、AOT、ABI、运行时、GC 和自举等关键路径应具备正式测试和独立结果判断两条验证路径。再次执行 `mio test` 不构成独立验证。测试基础设施也应运行负向自检，确认故意错误能导致非零退出。

## 外部工具与 Core 隔离

Go、Shell、Python 或其他外部工具只能作为 Development / CI Dependencies，用于补充验证、证据收集和基础设施自检。它们可独立调用 Mio；Mio Core、标准库和正式编译器不得反向导入、链接或在运行时调用这些测试工具。新增测试依赖不能参与正式源码构建、运行或自举。

正式发行包不得包含测试驱动及其专用依赖。现有 `tools/native-ci` 由 Mio 实现，生产构建保留空 PATH 和原有执行沙箱，使用既有 Native Seed；新增的 `scripts/ci` 仅在沙箱外运行。代码 PR 涉及打包时应附源码依赖检查、实际 archive 清单及无测试工具环境下构建/运行的证据。无法运行的发布检查应标为 NOT_RUN。

历史 Go 引导/参考实现与本次新增的测试工具依赖必须分开描述；不得为了测试而替换现有纯 Mio Native Seed 构建架构，或将测试工具加入发行包。

## 审查标准

维护者综合评估功能正确性、回归风险、架构一致性、性能、平台兼容性、测试充分性、可维护性、文档及长期方向。**测试通过是合并的必要依据之一，不是自动合并承诺。** 请如实说明基线失败和已知限制，不能删除重要检查或掩盖失败来使 CI 变绿。

## 许可与归属

程序代码及相关文档遵循仓库现有 [MIT License](../LICENSE)，保留其版权及许可声明。贡献者应有权提交贡献，并说明第三方代码的来源和许可。本项目未在此引入 CLA 或版权转让要求。

`assets/mascot/` 中 Mio 与 Mochi 的角色插画不在代码 MIT 许可范围内，其版权及使用许可另行适用；不要依据代码许可推定可使用这些资产。

## AI 辅助开发

允许 AI 辅助开发，请在 PR 中说明是否使用。提交者必须理解所提交代码，并对正确性、安全性、许可合规及测试结果负责。AI 生成的测试报告不能替代实际运行证据。


## CI V2 测试入口

普通 PR 由 `ci-pr.yml` 先生成保守的 Quick 计划，再调用 `bash scripts/ci/run.sh <target> <modules> quick`；`Mio-2.1` push、手动及定期 Full 由 `ci-full.yml` 调用同一入口的 `all full`。修改单一模块时可直接运行其 `test.sh <target> [quick|full]`。正式发布工作流保持独立。

原生测试先由受信任 Seed 构建当前工作树编译器，再复用产物运行模块；只运行 Seed 的历史内嵌实现不能证明当前源码通过。新增独立模块应提供相邻 `ci-module.json`、`test.sh` 和真实 Mio 测试，关键模块同时提供固定输出、字节、退出码或参考实现 oracle。使用公共 `ci_native_and_crosscheck` 可在原生层失败时继续收集独立层结果，最终仍返回非零。

提交验证材料时附命令、平台和 `report.json`；分别说明 PASS、FAIL、SKIP、NOT_RUN。全跳过或没有实际检查不能写成成功。CI 基础设施变更请运行 `bash scripts/ci/selftest.sh`，并检查工作流语法。当前已知 Core 失败不得通过改预期、放宽断言或跳过测试隐藏。详见 [测试架构](testing.md) 和 [本次审计](testing-audit.md)。

涉及编译器、后端、运行时或 GC 的修改须通过 `.github/workflows/native.yml` 的三平台原生验证（`Native / required`），并在 [Runtime ABI 契约](runtime-abi.md) 变更时同步更新 `tests/runtime-abi`。只有普通标准库测试文件的局部修改才缩小 Quick；实现代码、Core/ABI/GC/AOT、清单或未知范围改动均回退完整 Quick。macOS 现使用 GitHub-hosted `macos-15`。**暂行措施：** 受信任 Native Seed 尚不可用于 GitHub-hosted Runner，Native Verification 暂时为 NOT_RUN（只有仓库变量 `MIO_NATIVE_VERIFICATION=enabled` 并提供 Seed 后才会恢复），`Mio CI / required` 此时只是补充测试 gate，其通过不代表原生测试通过。详见 [测试架构](testing.md) 的“暂行措施”与 [三级 CI 调度审计](ci-scheduling-audit.md)。
