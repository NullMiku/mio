# E5 late-11：真实事件诊断与约束冲突

2026-10-30（Asia/Tokyo）。E5 **IN_PROGRESS / NOT_ACCEPTED**，E6 **NOT_RUN**。
本轮没有启动下一轮完整矩阵，没有修改正式 Runtime/GC/测试源码。
Sample 24 的覆盖失败**尚未修复**，也没有建立满足全部原约束的确定性协议。

证据：`build/m19ef-evidence/E5-event-diagnostic-20261030-06/`。
`analysis.json`、`late-0.events.json`～`late-3.events.json`、原始 stdout/stderr、
`commands.json`、`source-snapshot/`、`final-integrity-review.json` 均已保存。
这是 late-only 最小路径的定向诊断，不是完整矩阵或 E5 验收。

## 原生运行和不可替代的证据边界

同一冻结诊断副本预先固定运行 4 次，保留原始 late 源码、2400000 死 Node、
256 MiB 堆、8 次请求 Minor、全部 17 个原始输出和真实线程/精确 Root 路径。
4 次原生退出均为 0；所有原始其余功能、对象回收/LOS 与资源计数检查通过。
原始 Join 后 Phase=2 断言：**1 通过 / 3 失败**，全部失败保留。
每次 8 次请求 Minor 的实际开始/结束均处于 Epoch 1 / Sweep Phase 2。
这 4 次覆盖不能修复或抹去历史 Sample 24，也不能证明将来必定覆盖。

诊断由可信原生 Mio Seed 编译；代码生成、链接、签名仍为纯 Mio。
签名验证通过；重新生成的 signed 和 unsigned 全文件分别逐字节相等。
正式输入 257 个 .mio 文件全部仍与 Full30 字节一致：
`e09017b6038169ea77975996c0f002481e23367740d4db836b4a01a71d7cebe7`。
诊断 Manifest：
`665de3070774b02cd474ba443806c4d866746ffcec050eb95490ceb654f08a5e`。
原生命令、资源/耗时、产物/日志 hash 均已逐项核验。

## 事件顺序协议

独立 native 数据区记录真实 Collector 开始、Phase3 发布前/后、Worker 注册后启动、
实际用户函数调用/返回、thread_leave 前/后、registry unlink、回调返回前最后事件、
Main Join 入口、completion wait 前/后、底层 pthread_join 前/后、gc_block_leave
前/后、真实 STW owner 等待/恢复、实际 Phase load 返回值、Minor 请求/开始/结束。

序号由 LDAXR/STLXR AcqRel RMW 分配，随后 DMB；每条 payload 写完后以 STLR
提交序号。500 条上限检查，实际 168～226 条，无丢失/溢出。报告在所有真实
Worker/Collector join 后输出。顺序结论依据操作两侧事件与原子序号，不靠时钟
大小推导 happens-before。时间是记录调用内的真实 monotonic 读数，不是内核事件。
Epoch/Phase/owner 的独立 Acquire 采样不是复合一致快照；Phase load 和 park 原因
另外保存实际返回值/实际检查的 owner。四次 Phase 值都与原始程序输出一致。

**实际线程终止没有伪造一个“线程内终止后事件”。** 实际终止 T 被回调最后事件和
成功 pthread_join 返回夹定。Sample 0/2 的 join 成功发生在 Collector 发布 Phase3
之前，因此原生线程确实已在 Sweep 内终止；Sample 1/3 的终止区间跨越 Sweep
结束，不能声称其实际终止必定在 Sweep 内。精确内核终止瞬间仍未直接观测。

## 最小反例：Sample 2 的同一 Epoch 1

| 原子序号 | 真实事件 |
|---|---|
| 88 | B 从 registry 摘除，Phase2 |
| 90～91 | thread_leave 返回；native 回调最后事件，Phase2 |
| 92 | Main 进入 Join，Phase2 |
| 97～98 | 底层 pthread_join 调用/成功返回 0，Phase2，约 10 µs |
| 99～100 | Main 进入 gc_block_leave，实际检查到 owner=A 并等待 |
| 101～102 | Collector 发布前事件 → Release Phase3 → 发布后事件 |
| 103～104 | Main 恢复并从 gc_block_leave 返回，约 136.838 ms |
| 107 | Main 实际 Acquire 读取 Phase=3 |

因此，即使**原生线程终止和底层 Join 成功均在 Sweep 内**，原断言仍可失败。
等待的对象是 A 的 STW registry ownership，不是 Sweep collector。

另一个反例 Sample 1：B 的最后 native 事件 #114；Collector 完成 #116～117；
Main 从启动 B 的 gc_block_leave 返回 #119；Main 才在 #122 进入 Join。
启动返回的 blocked leave 区间约 179.546 ms，底层 Join 仅约 6 µs。
不能把这个延迟误归因为 Join 自身等 Sweep。

## Runtime / 精确 Root / 退出与回收审计

`worker_roots.mio` 的 Join 路径先把 Main 转为 blocked，再等自然用户完成，随后
实际 thread_close / pthread_join，最后 gc_block_leave；没有调用 Sweep finish/join。
gc_block_leave 在 Main mutex 内检查 registry owner，只在外部 STW owner 存在时
通过 condition wait 保持 Root 固定；其后恢复可运行。条件等待会释放 mutex，
协调者能够确认该线程。Sweep Phase2 与另一个 Mutator 的 STW Minor 可以共存，
所以不能凭 Phase2 绕过该等待，否则 Main 可在外部精确扫描时改变 Shadow Frame。

registry 退场与扫描串行；bootstrap/shadow 清理晚于摘除；回调退场后不再访问
托管对象；native context/stack/condition/mutex 的释放晚于实际 join。
Sweep 只消费完整 Remark 捕获的闭合死对象集合。这些现有安全路径本轮未改。
没有发现足以支持跳过该同步的内存安全缺陷；这不是无缺陷或全量安全性证明。

还发现额外 STW 流量的具体来源：原始 `first` 的每轮有两个 opcode49 局部
初始化、两个 opcode66 类型标记。当前 lowering 的 heap_step 从 opcode>=30
开始，未将它们豁免；其中 opcode66 在当前 native lowering 中没有用户操作。
opcode49 的 captured-cell 情形又必须独立保留。这个源码级过度同步候选见
`protocol-audit.md`；本轮没有借此做未经定向 Root/GCStress 验证的正式改动。
即使修掉这些额外握手，也不会建立下面缺失的全局顺序。

## 无法同时兑现的约束

实际保证：用户执行 → registry 退出 → 原生终止 → Join 返回 → Main 读取 Phase。
Collector 的 Sweep 完成没有依赖最后那次 Main 读取；Acquire 也不能回看过去状态。
所以“无额外同步时 Join 后 Phase 必须为2”**逻辑上不受保证**。

阻止 Collector 完成直到 Main 读取的测试门闩会人为延长 Sweep；固定 Sleep、
加负载或筛选重试同样不能建立合法顺序。允许读取3则改变原始断言。本轮均未采用。
同理，Sweep 内注册/发出 Minor 请求不能保证该线程获得 CPU、STW ownership 和
heap lock 之后仍有未完成 Sweep；Sample24 必须独立保留 COVERAGE_FAILURE。
当前没有不改变这些约束、又能确定性保证迟到 B 的8次 Minor/退出和 Join 后读取
全部位于有限 Sweep 窗口的实现；不能将约束冲突包装为 Runtime 已修复。

本轮停在可审阅的约束冲突：**未完成根因修复或 Sample24 确定性交错修复**。
完整原始 fixed32 的前置条件未满足，故没有运行；E5 未 PASS，故没有进入 E6。
后续需要明确版本化的观察合同，或允许实际资源依赖的 Epoch 协议；在仍要求
原断言且禁止延长 Sweep 的条件下，不能给出保证 PASS 的恢复命令。

## 诊断设施失败也保留

01/02：设置脚本的替换次数校验失败，未构建原生程序。
03：native builder 成功；日志区超过链接布局上限，生成退出68。
04：静态发现后续 Mach-O 上限后，仅中断本轮自身 builder，退出-15。
05：4 次 native exit0，但辅助 value 字段保存偏移错误，明确禁止作为完整证据。
06：修正该诊断偏移，重新构建/签名/逐字节复现并完成预设4次。
所有原目录、失败和快照仍在，没有替换旧源、隐藏失败或改写 Full30 结果。

无 Commit/Push/Tag/Release；无其他 Worktree 写入。
