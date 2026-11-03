# Implementation Plan — GF1～GF5 无需逐阶段人工指导

## 0. 安全启动

- 读取 GF0 报告和冻结证据，确认当前源码 SHA 与 HEAD/未提交状态。建立新的隔离 GF worktree，完整导入当前必要的未提交源码与 `specs/`。
- 保留 GF0、M18、M19b/c、M19d 与 Race 工作树不受影响。不要合并 `mio-wt-m19d` 或 `mio-wt-m19-race` 未经审核的改动。
- 创建 `status.json`、每阶段的 `baseline/`、`logs/`、`results/`；记录从 GF0 到新工作树的差异和来源。

## 1. 实施顺序（完成即自动进下阶段）

| 阶段 | 关键纵切 | 进入下一阶段的条件 |
| --- | --- | --- |
| GF1 | 修复 Case14 窄整数静默错、Case9 Map、Case10 函数值、Case13 泛型、Case15 浮点；通用原生 Frontend `.mio→.mochi`，非零诊断 | 16/16 原 corpus 和新增错误、模块、Selfhost/Bunko 差分通过，真实原生执行无 Go VM |
| GF2 | `CompileSource`→内存 Mochi→`BuildNative`→ Mach-O；不启动其他编译器 | 同一 Native 进程完成源码到 Mach-O，真实 Hello/数值/数组/Nullable/Cell/模块/错误纵切与来源监测通过 |
| GF3 | 单原生 CLI、Bunko 内嵌、本地 ad-hoc 签名、Native test runner 与兼容命令 | 只安装 `mio`、移走物理 Bunko、无 Go PATH、离线完成 check/build/run/test；静态/进程证据无 Go Runtime/VM |
| GF4 | 可信纯 Mio Seed 从完整 `.mio` 编译器源码生成 A；A→B→C→D | 实际运行 Seed/A/B/C 及需要的验证，B=C=D 完整 unsigned Mach-O 逐字节一致，GC/LOS/源来源正确 |
| GF5 | Go-free 生产 CI/发行门禁、发行物唯一 `mio`、文档和 provenance | 确切源码/Seed在 Go-free 隔离构建中可复现；所有 A1～A12 门禁通过，CI 本地/可用环境实测，远端发布保留人工 Tag |

## 2. 自动循环

每个阶段：inspect → design in small steps → implement → targeted tests → repair → phase gate → append provenance → next phase。

- **不要只完成 GF1 后停止问“是否继续 GF2”。** 用户明确授权连续完成 GF1～GF5。
- 不允许先跳过 GF1 失败去声称 GF2 PASS；可以并行做不依赖前置条件的准备，但阶段验收仍严格顺序。
- 对耗时诊断优先采样/profiling 后修复，避免机械地把 Race 超时从 30m 调到 120m 再更久。
- 每次测试失败先区分代码缺陷、环境/沙箱、资源竞争、超时及测试本身错误，保留原样证据。修复不能改坏历史规范。
- 对破坏性 CLI 行为采用确定的版本化迁移说明，不主动修改已发行版本的远端包。

## 3. 与其他工作线的资源协调

轻量开发和针对性测试可以与 M19d/Race 并行，但 GF 自举与全仓 Race/大基准须在单机独占重型时段执行。先检查工作进程和负载，必要时先做非重型任务。不能终止无关进程以获取资源。

## 4. 开发任务完成后的整合验收

在 GF 独立工作树中确认相对于 GF0/当前 M19c 的真实修改；审查任何共享文件覆盖/编译器版本变更。若后来要整合到 Mio-2 主线，应另外开展源差异审查和合并后测试，不得直接通过覆盖原目录完成“合并”。

## 5. 输出

独立工作树中维护 `status.json`，报告和证据放 `build/gofree-evidence/GF1` … `GF5`、`build/gofree-evidence/final`。保留每次失败记录。最后汇总 A1～A12、所有阶段的实际状态、唯一发行物 SHA、Seed→A/B/C/D 哈希、性能数据、Go/Race 遗留范围、远端需要的人工步骤。
