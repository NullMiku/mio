# Autonomous Execution Policy — 不逐阶段请求用户操作

## 1. 无需逐阶段确认的授权范围

在**隔离的 GF 开发工作树**中，Codex 应自行：

- 实施 GF1～GF5 的源码、脚本、测试、CI 草案、文档和可复现构建工具。
- 决定内部模块划分、日志格式、资源清单和测试目录等可逆方案；遇到多个方案，选择最小修改量且不牺牲语义与复现性的一项。
- 执行构建、静态检查、目标测试、差分、Native 自举、隔离安装和性能测量；可编写自动测试调度器减少重复劳动。
- 诊断失败、迭代修复、重跑受影响测试，再按 `plan.md` 进入下一阶段。
- 生成每阶段证据、摘要和最终交接材料。不以等待维护者查看阶段报告作为阶段切换前提。

不要把每个 `TODO` 都转成提问。先读代码和既有 GF0 证据后自行决策，争议决定写入 `decisions.json`，包含备选方案、选择原因、兼容影响、测试与可回滚方式。

## 2. 自动推进逻辑

```text
CHECK_INPUT_AND_FREEZE
for phase in GF1..GF5:
    inspect source + plan vertical slice
    implement feature + regression tests
    run targeted native tests
    debug and repair until gate satisfied or truly blocked
    run phase acceptance on actual current source
    record status/evidence/manifest/decision
    if PASS: proceed immediately to next phase
    if BLOCKED: resolve cause within authorized scope; otherwise
        finish safe independent preparation, record blocker; never fake PASS
FINAL_COMBINED_VALIDATION
REPORT_WITH_EXACT_EVIDENCE
```

- 每轮测试有明示时限，超过时采样和诊断，而不是无限重启相同命令。
- 重型验收的资源窗口可自己安排：先查看 `ps`、CPU/内存，发现 M19 Race 等正在跑则改做轻量工作；不得擅自停止进程。
- 若当前会话工具时间/上下文不足，记录可恢复状态，说明未完成项；不承诺离线继续跑或未来自动送达。

## 3. 只能阻断、不能代为批准的事项

- GitHub 远端 Commit/Push（包括 force）、新 Tag、正式 Release、删除远端资源、修改保护规则。
- 生产签名密钥、Apple Developer ID 凭据、Notarization 账户、第三方账号认证或资金操作。
- 不可逆迁移、删除用户数据、实质改变生产环境或触及其他项目进程。

遇到上述事项，**继续准备相应的本地脚本、工作流与人工操作说明**，但不能声称远端已完成。GF5 的发布流水线可以在维护者未来主动推 Tag 后自动发布；本次 Codex 不推 Tag。

## 4. 预先确定的技术决策（减少对话中断）

- 只支持 macOS ARM64 首版；Linux/Windows 不纳入 GF1～GF5 必须交付。
- 保留 Mochi v14 **中间表示格式**，但不能在生产编译路径运行 Go VM/Mochi VM。
- GF2 最初允许在**同一进程内**将前端 Mochi v14 序列化为内存字节数组，再从内存解码传递给现有 Native AOT；不强迫先重写完整对象 IR。不得借此创建中间编译器进程。
- GF3 目标 `build` 默认 Native，`run` 默认 Native。因为 GF0 确认当前行为不同，必须使用显式发行兼容策略：文档写明破坏性变化，且保留 `--emit=mochi` 这样的显式输出能力（实际名称与项目架构一致）；绝不静默回退到 VM。
- 保留现有 `exec`、`disasm`、`lsp` 的公开承诺：优先纯 Mio 重建；目标是全部由纯 Mio Native 实现；默认不允许以删掉现有公开命令替代移植。若遇到确实无法移植的硬阻塞，应准确保持 GF3 NOT_ACCEPTED，不能隐藏 Go 工具或擅自删接口。
- 内建 **ad-hoc** 本地 Mach-O 签名以实现普通构建无外部 `codesign`；Developer ID 与苹果公证属于发布环节，不属于用户日常编译依赖。
- 内嵌 Bunko 资源采用有序、带版本和 SHA256 的确定性清单；允许显式开发覆盖，不需要磁盘独立 Bunko 才能正常编译。
- 在 GF4 使用可信原生 Seed，不要求从完全无编译器的裸机起步。

## 5. 输出纪律

`status.json` 是进度索引，真实日志/哈希/命令是证据。未运行的任务必须标注 `NOT_RUN`，失败为 `FAIL`，因外因无法完成为 `BLOCKED`；不能填充虚构指标。每阶段 PASS 后自动转下一阶段。M19 历史 Race 状态是独立指标，不能代 GF 验收结果。
