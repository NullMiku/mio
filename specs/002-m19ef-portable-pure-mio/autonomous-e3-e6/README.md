# Mio M19e — E3～E6 纯 Mio 自主实施补充规范 V0.2

**任务性质**：现有 `002-m19ef-portable-pure-mio` 规范的续接实施包，不是新建 GC 或替换上游规范。仅覆盖 E3、E4、E5、E6；**不自动开发 M19f**。E6 最终 PASS 后应交接已有 `M19F.md`，是否继续 M19f 依据 Codex 当时收到的任务授权；本包只授权 E3～E6。

**已有进度（由用户报告，需在工作树用证据核实）**：E3 真实堆接入层完成 64 次原生运行（64,128 次 Minor、256 次 Major、192 次线程 Create/Join）、32 项原生回归与 11 个历史 GF4 GC 见证；跨线程保活/死亡、地址稳定、对象级晋升、Old→Young、LOS、阻塞持根、注册、溢出拒绝和受控复用已有局部证据。**E3 仍 IN_PROGRESS**，普通用户 Mio 函数的自动 TLS/Shadow Frame/Safepoint 接入未证明；E4～E6 NOT_ACCEPTED。历史见证签名镜像一致不等于新编译器完整自举。

## 位置与入口

- 已存在工作树：`/Users/hatsunemiku/.codex/worktrees/m19ef-portable-gc/mio`
- 开发分支：`EXP/m19ef-portable-gc`
- 上游基础分支：`Mio-2.1`
- 原始规范：当前目录上一级 `../SPEC.md`、`../ARCHITECTURE.md`、`../CONTRACTS.md`、`../M19E.md`、`../ACCEPTANCE.md`
- 近期实际状态优先参考：`../E3_REPORT.md`、`../IMPLEMENTATION_REPORT.md`、`tests/m19ef/README.md`、本地 `build/m19ef-evidence/`（可能尚未提交 Git）
- 阅读顺序：`PORTABILITY.md`、`EVIDENCE.md`、`GATES.md`、`phases/E3.md`～`E6.md`。

## 严格完成条件

- **E3 PASS**：真正的**普通 Mio 用户程序**无需手工发布测试专用 Root，自动 TLS/Shadow Frame/Safepoint 在多线程真实 GC 上安全可用。
- **E4 PASS**：Old 标记真正与 Mutator 并发；SATB 与现有分代屏障完整协同，具有终止/溢出/Remark 证明。
- **E5 PASS**：Old 清除及分配/LOS 释放和 Mutator 安全重叠，有同步与安全复用协议。
- **E6 PASS**：同一最终源码完成全部实际回归、原生多代完整源码自举、二进制固定点及可追溯证据。
- `M19e PASS` **仅在 E3 E4 E5 E6 全为 PASS、已有 E0～E2 门禁也已真实接受时**才能声明；否则仍 `IN_PROGRESS` / `BLOCKED`。

凡是未实现的 Linux/Windows/AMD64 后端保持 `NOT_IMPLEMENTED`；仅 Darwin ARM64 需要本期实机通过。

## 文件说明

- `PORTABILITY.md`：GC 核心与 CPU/OS 后端分层及对象 ABI 不变量。
- `GATES.md`：每阶段及最终可机械检查的 Pass/Fail 条件。
- `EVIDENCE.md`：结果文件、失败保存、固定点与真实性要求。
- `TEST_MATRIX.md`：类型、交错、失败注入、性能见证矩阵。
- `phases/E3.md`～`E6.md`：具体可落地任务与验收。
- `status.json`：**初始示例状态**，不能代替最新实际源码、验收报告及测试结果。

**禁止操作**：Commit、Push、Tag、Release、历史重写、`git reset --hard`、`git clean`、`git stash`、跨 worktree 写入、删除历史证据。生产 GC/编译器实现全为纯 Mio；Python/Shell 仅可为非生产审计驱动。
