# 实际测试矩阵与最低可观测要求

## E3 自动插桩 / 精确根

| 维度 | 正向 | 负向 / 边界 |
|---|---|---|
| TLS | main + 2～4 Mutator 分别附加 Root 链 | 创建失败、重复注册、线程退出/Join 失败 |
| 过程调用 | 深层递归/嵌套调用/函数值/闭包捕获 | leaf/尾调用/错误退出，Shadow Frame 不泄漏 |
| Safepoint | 长循环回边、分配慢路径、用户函数调用 | 半初始化对象/未发布寄存器临时值时不得安全点 |
| 跨线程 Root | A 分配 B 持有，GC 后地址、字段不变 | 双方解除 Root 后可确认回收；不解引用死亡对象 |
| 分代 | Young、晋升 Old、Old→Young 与循环对象图 | remembered 元数据失效、重复晋升、不正确扫描 |
| 多形态对象 | Array/Map/Struct/Enum/Closure/Cell/Nullable/LOS | 数值/浮点伪指针、泛型布局、空容器、空 nullable |
| 阻塞/退场 | native blocking call 发布 Root，park/wake/re-register | 退出同时扫描、超时、无限等待保护 |

**E3 特有失败判据**：需要调用测试专用的 `publish_root_vector` 才不崩、普通 Mio 用户函数不自动建立 Roots 或 Safepoint，均不能 PASS。

## E4 并发 Mark / SATB

| 维度 | 验证 |
|---|---|
| 指针覆盖 | Old 黑对象覆写指向白对象旧值，SATB 保活；没有 SATB 时确实复现可达性危险 |
| 双屏障 | Old→Young postwrite + Old→Old/Young→Old 的 prewrite 适用规则 |
| 暴露路径 | Globals、Map/Array 槽、Cell、Closure、Struct、Nullable、LOS、泛型/资源对象 |
| 分配/晋升 | 并发标记开始后新分配，Young 晋升 Old，二次 Minor 发生在 Mark 时有安全协调 |
| 队列 | 单生产者、多生产者、满队列、失败背压/同步兜底、Remark 耗尽，终止无在途项 |
| Epoch | 线程新注册、退出、阻塞、恢复、再次 GC，没有过期黑白标记串代 |
| 时间重叠 | Collector 标记期间至少一个 Mutator 能持续取得进展，trace 使用真实可比较时钟和 Epoch |

## E5 Sweep / LOS

| 维度 | 验证 |
|---|---|
| 核心 | Sweeper/Allocator 读写同一 free bin，重复回收、ABA、循环复用 |
| Epoch | 活跃读者延迟复用；所有读者退出后 eventual reclaim；任意周期不会永久卡住 |
| LOS | 有根不能 unmap、无根但有读者不能 unmap、失败 munmap 保留 owner；后续重试安全 |
| 并发 Minor | Old Sweep 期间 Young Minor/晋升/记忆集合，阶段互斥或同步契约 |
| 失败 | OOM、HardCap、进程退出、GC Abort、worker error、无限等待负向样例 |
| 时间重叠 | Sweep 期间真实 Mutator 仍能进行与对象生命周期相容的安全操作 |

## E6 完整回归

- 原 M19b/c：精确 Root / Shadow Frame、Old→Young、LOS 128KiB、heap budget、Pressure Normal/Elevated/High/Critical/Unknown、GCStress、OOM、对象稳定地址、存活/死亡统计。
- 纯 Mio 工具链：原生 CLI，Bunko、Frontend/Resolver/TypeChecker/Codegen、RPC/LSP（取消、overlay、路径）、NativeFS、ARM64/Mach-O、Native runtime、签名。
- 新并发：可重放调度（种子+决策序列）、不同 mutator 数量和对象类型图、长时运行、争抢、资源失败、SATB、LOS 等。
- 自举：最终同源 Seed→A→B→C→D，完整已签名与未签名字节固定点，真实执行代际与测试。
- 性能只报告真实结果，不承诺相对旧 STW 一定快；GC 暂停、mutator 进度和 collector 时间的真实 p50/p95/p99、CPU、wall、RSS、峰值堆和碎片率（能测则记录）；无足够样本时明确 N/A。

执行脚本和真实测试包应由 Codex 对照仓库实际命令/CLI 自动发现，不得虚构不存在的 `mio` 命令、工具路径或 87 项固定测试数量。必须优先调用已有可复现测试入口。
