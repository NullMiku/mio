# GF5 — Go-free CI、测试体系与单文件发行准备

**目标：** 将正式 `mio` 生产构建、主要正确性测试与可重现发行链迁移到原生工具链，不再依赖 Go 编译器、Go Runtime、Go VM 或独立编译器程序。

## 本地发行物

- 唯一**必需**工具链可执行文件为 `mio`，可在发行压缩包中附带 LICENSE/README/SHA 文本，但不能要求用户另外安装独立编译器、标准库目录或动态 Runtime。
- 生成 `mio-<version>-darwin-arm64.tar.gz`、`SHA256SUMS`、`release-provenance.json` 和实际可用的安装测试结果。
- 发行 `mio` 由 GF4 可信 Native 来源链从完整 `.mio` 源码构建，并在干净环境独立复核。不得复制历史 RC4 的 Go CLI 作为最终产物。
- ad-hoc 签名可用于本地可执行交付，但不等于 Developer ID 或公证；凭据不足不能伪称 notarized。

## Go-free CI

- 使用受控 macOS ARM64 Runner，显式验证 Darwin 与 `arm64` 及资源要求。检查 Tag、Commit、编译器版本、源码/内嵌资源 Manifest 与 Release Notes 关系。
- 流程：Preflight → Native source build / trusted Seed → Native unit/integration tests → Go-free source self-bootstrap → Package → Isolated install smoke → Verify SHA/codesign/provenance → （将来通过维护者推 Tag 后）Publish。
- 生产构建流程不能 `go build`/`go run`/`go test`/调用 Go 二进制；脚本可用 Python/Shell/系统校验工具协调，但这些不能作为编译器核心生成器。若 CI Runner 预装 Go，须用禁用运行/进程审计/二进制检查证明不依赖它。
- 默认只读权限，发布 Job 才申请必要写入权限；RC Tag 为 prerelease，正式 Tag 为 release。同名 Release 不覆盖，必需门禁失败即停止，dry-run 不可能 Publish。
- 只准备工作流，不擅自创建远端 Tag/Release 或上传资产。若远端 Hosted CI 尚不能运行，标明 `NOT_RUN`，不可把 actionlint 静态通过冒充远端自动发布 PASS。

## 原生测试迁移与历史 Go 测试

- 原生 `mio test` 覆盖语法、类型/诊断、Mochi IR、AOT、GC/LOS、NativeFS、模块/嵌入 Bunko、CLl/运行、GF0 问题用例、各代源码自举。
- 原生测试框架应实际执行测试、分组/筛选、报告失败与退出码；必要的额外安全工具（例如 OS 诊断器）只能作为审计，不算发布编译依赖。
- 保留历史 Go 参考实现和 Go VM 测试作**独立的 Legacy/Reference CI**，不自动删除、静默跳过或将旧失败改成 PASS。
- M19b 原始 `go test -race ./... -count=1 -timeout=30m` 的 Codegen 超时仍然是**历史 M19 发布门禁阻塞**。新 GF Go-free 原生 CI 并不自动“修复”该 Race；需要源码结果或经项目审核的等价发布策略才能解除。
- 如正式的现行 V2.0.0 Release workflow 仍绑定该 Gate，不得未经说明暗中绕过以宣布其 READY。Go-free 分支验收与既有发布分支状态要分开报告。

## 隔离可复现性与安全

- 使用新目录、固定输入源清单、可信 Seed 及版本化构建选项；禁止从开发 worktree 偷用旧 `.mochi`、`mio`、Bunko 或宿主 Go 路径。
- 验证正常用户程序可离线运行，`mio build` 无外部链接/签名步骤；检查编译器自身和最终应用不含 Go buildinfo/runtime 符号。
- 在测试输出中显式保留构建版本、命令、退出码、文件哈希、环境、资源消耗与代码签名类型。
- 不使用生产签名证书/苹果账号，除非单独拥有用户明确授权。

## 性能

- 对完整 `.mio` → Mach-O 流程测冷进程、热缓存、CPU、RSS、真实编译吞吐、长任务/多模块。与 GF0 的 Go frontend、Go VM 自托管及旧 Go AOT 分别比较，不混淆不同工作负载/阶段。
- 用户目标是摆脱解释 VM 缓慢路径。优化实际热点，但不得宣称新原生前端在没有实测时必然快于 Go 前端。
- 对性能显著退化提供解释或修复，不以删除慢样本或降低语义覆盖为代价。

## GF5 PASS 与最终确认

实际存在 Go-free CI 构建、测试、发行候选；A1～A12 基于最终源码已验证，单文件真正离线安装可用，源码多代自举固定点稳定，发布链可由维护者未来推 Tag 触发且不要求 Go 才能构建。

**远端 Release 是否已公开**为独立 `NOT_RUN`/待维护者动作，不得自行发布。GF5 PASS 不得自动改写 M19b 历史 Race 状态。
