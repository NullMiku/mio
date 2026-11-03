# 六、M19e/f 验收（强制 Gates）

Codex 不可凭旧阶段 PASS 或代码静态检查推断新阶段成功。每个 Gate 在同一目标源码 Manifest 上记录：输入/主机/target/backend/版本、原生 mio 二进制 SHA256、实际命令、退出码、stdout/stderr、超时、内存、见证/重复次数、状态。

| Gate | 要求 | 失败或未运行 |
|---|---|---|
| G0 基线/保护 | 目标 worktree 从已确认 `Mio-2.1` 出发，GF4/GF5/M19 历史证据均可追踪；无外部树改动 | BLOCKED |
| G1 纯 Mio | 新生产代码全部 `.mio`，没有 Go/C/Clang/LLVM runtime/compiler/构建器必要依赖；历史 Go 代码仅做参考 | BLOCKED |
| G2 目标无关 Core | Portable GC 核心不包含 CPU asm、Darwin/Linux/Windows syscall 号码、可执行格式；Mock RuntimeOp 契约通过 | BLOCKED |
| G3 原子 + 线程 | ARM64 原子编码正确，真实线程、TLS、join、park/wake、内存序测试，独立 worker 观测到 | BLOCKED |
| G4 精确根 + 并发屏障 | 多线程 root、SATB/等价 barrier、Old→Young、LOS、global、closure、Map、泛型等完整交错测试 | BLOCKED |
| G5 Concurrent Mark-Sweep | mutator 在 Old mark/sweep 期间真实执行；无内存损坏、重复释放、死锁、数据竞态（有证据的可用检测器） | BLOCKED |
| G6 历史兼容 | GCStress、16-byte headers、LOS threshold、晋升对象地址、自动 heap/pressure、NativeFS、Bunko/Frontend/CLI/LSP 关联回归 | BLOCKED |
| G7 4 级压力 | 正常/升高/高/危急/未知输入，滞后恢复和原子 snapshot 一致性 | BLOCKED |
| G8 Profile | High/Balanced/Low 策略各独立可达、效果可测、内存上限优先、无安全回退 | BLOCKED |
| G9 性能 | 固定样本 workload，记录 p50/p95/p99、wall/cpu/rss、GC pause、吞吐、噪音；不得只写主观“更快” | BLOCKED |
| G10 Native fixed point | 当前最终源码完成完整 `.mio` → Native compiler Seed→A→B→C→D，真实运行各必要阶段，B=C=D 完整未签名/签名固定点 | BLOCKED |
| G11 CI/平台 | 正式 Native Mio 构建/测试路线通过；macOS ARM64 真实验证；未实现的 Linux/Windows 不得列为通过 | BLOCKED |
| G12 release readiness | 是否发布由用户授权；本阶段不自动 Commit/Push/Tag/GitHub Release | NOT_RUN |

## 推荐边界样本

- 同一对象 Young→Old 晋升后再次被跨线程旧对象引用，地址不变。
- Old 黑对象的字段被两个 mutator 反复覆盖（SATB），同时一个线程建新 Young，另一个触发 Minor。
- Closure/Cell/Map/[]T/Nullable/generic、全局指针、非指针 int64 为类似对象地址的位型。
- LOS 在 Minor/Old Concurrent Sweep 中存活/死亡/重新分配；OS munmap 失败注入。
- worker 创建失败、线程退出途中 safepoint、无限等待保护、queue overflow、多轮 GC 交错、heap OOM/硬上限/压力恢复。
- `memory.snapshot` 同时双线程反复读取，同一个 sequence 的 8 字段要一致且观测到真实递增发布。
- 压力预测高但短寿分配有效回收时不得持续虚警 Critical。
- 单线程用户程序与跨线程 Native workload 都要验证；启用 GCStress 与禁用 GCStress 都要验证。

## 状态转换

- E0/E1/.../E6 逐项 `PASS` 后才可宣布 M19e PASS。
- F0/F1/.../F4 逐项 `PASS` 后才可宣布 M19f PASS。
- M19e 改动如污染 GF4/GF5 原生 compiler fixed point，相关阶段要重跑，不沿用上一个候选的哈希。
- 若平台后端只支持 STW 回退，该目标上只能标记 `FALLBACK_STW`；不能给 Concurrent PASS。
- 任何 BUG 未修复，测试失败不能通过跳过、删测试、改变期待值、忽略 race/timeout 来获得 PASS。
