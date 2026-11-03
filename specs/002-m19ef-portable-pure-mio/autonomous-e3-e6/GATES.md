# E3～E6 必须通过的验收门禁

所有 Gate 使用 **当前同一份最终源码 Manifest**，记录测试执行的 native Mio 版本、hash、目标平台和证据目录。旧结果是 provenance，不是新源码的 PASS。

## 总门禁规则

- **E3 PASS** 当且仅当 G3.1～G3.7 实际 PASS；必须有「未使用手动 Root 发布 API 的普通 `.mio` 程序」证据。
- **E4 PASS** 当且仅当 G4.1～G4.7 实际 PASS；必须观察 Old 标记线程与至少一个正常执行的 Mutator 时间重叠。
- **E5 PASS** 当且仅当 G5.1～G5.6 实际 PASS；必须观察 Sweep 与 Mutator 重叠，或对未并发 Sweep 明确 `BLOCKED`（不能将 STW Sweep 标为本阶段 PASS）。
- **E6 PASS** 当且仅当 G6.1～G6.9 实际 PASS；完整源码级 Native 自举 Seed→A→B→C→D 的原生二进制与所有必需运行均被实测。
- **M19e PASS** 还需已有 E0～E2 已验收，且当前 Darwin ARM64 真实并发能力开启并证明；未来 target 依旧 NOT_IMPLEMENTED。
- 无法完成则 `IN_PROGRESS / BLOCKED / NOT_RUN`，不得虚构性能优势、额外 CPU 支持或不存在的签名/固定点。

## E3 Gate

| ID | 验收必须证明 |
|---|---|
| G3.1 | 普通用户 Mio 函数自动附加/分离线程 TLS context，包含用户线程、main、返回、线程退出/重新注册、阻塞调用 |
| G3.2 | Native lowering 自动维护精确 Shadow Frame + liveness/pointer layout，包含调用链、临时值、逃逸/闭包、全局、复合类型 |
| G3.3 | Safepoint 在分配/调用/必要回边真实轮询；每 Epoch 的多线程 stop→root snapshot→resume 正确且无死锁 |
| G3.4 | ≥2 真实 Mutator + 正式分配器，正常 Mio 源码执行 Young/Old Minor/Major，跨线程 Root 存活与死亡正确 |
| G3.5 | 非移动晋升、Old→Young、LOS、阻塞持根、退出时注册表内存安全、重复握手测试不退化 |
| G3.6 | 精确 Root 不误认整数/浮点为指针，不出现 register spill/temporary 漏根；GCStress、OOM/失败注入可观察且安全 |
| G3.7 | 完整 affected CPU/OS/ARM64/Mach-O/Lower/GC 回归，同一源码建立新证据；无测试专用 bypass |

## E4 Gate

| ID | 验收必须证明 |
|---|---|
| G4.1 | 纯 Mio target-neutral Core 实际运行 Old Mark 状态机、调用 RuntimeOperation；平台无关审核通过 |
| G4.2 | Init/Remark 真正 STW handshake 并取得全体 Mutator 精确 Root，注册/退出/阻塞竞态受控 |
| G4.3 | SATB pre-write 覆盖每一类指针更新，仍兼容 Old→Young remembered-set；静态写路径清单与动态测例两种证据 |
| G4.4 | SATB 队列发布、溢出、终止检测、标记对象出生/晋升、Minor 与 Major 协调正确 |
| G4.5 | 真实 GC 线程与 Mutator 在 ConcurrentMark 有时间交集；不允许纯标记模拟器或 STW-only 假并发 |
| G4.6 | 黑→白、覆写风暴、LOS/Array/Map/Cell/Closure/Globals、Generic/Nullable 和整数伪指针测试通过 |
| G4.7 | abort/failure/OOM 安全回退且目标线程安全保证和 metrics 不退化 |

## E5 Gate

| ID | 验收必须证明 |
|---|---|
| G5.1 | Sweeper/Allocator 同步所有权、free bins、Side Metadata 不发生竞争/重复释放/ABA |
| G5.2 | Epoch/quarantine 保护旧对象直到已确认所有读者离开；对象地址稳定，复用只发生在安全 epoch |
| G5.3 | LOS unlink/unmap、失败回收、Reader-safe release 在真实多线程下通过；默认 128KiB 阈值不退化 |
| G5.4 | STW Minor 与 Concurrent Major/Sweep 协调，晋升/Remembered Set/young LOS 无错回收 |
| G5.5 | OOM、Hard Cap、Shutdown、Worker abort、二次 GC、线程退出不会泄漏所有权或死锁 |
| G5.6 | 真实 Sweep 与 Mutator 活动区间重叠 + 完整源/原生程序对抗测试，未证明则保留不启用 concurrent capability |

## E6 Gate

| ID | 验收必须证明 |
|---|---|
| G6.1 | 最终源码 Manifest、dirty changes、trusted Seed、native compiler 与所有运行产物 hash 完整 |
| G6.2 | 全量 E3/E4/E5 检查与真实并发压力在同一冻结源码真实重跑，不拼凑旧候选 |
| G6.3 | M19b/c、GCStress、LOS、OOM/Hard Cap、压力、观测协议、NativeFS 等全部规定回归通过 |
| G6.4 | Bunko、Frontend/Codegen、统一 CLI、LSP、Mach-O、ARM64、Thread/Atomic 回归通过；只用原生 Mio 正常编译 |
| G6.5 | Memory.snapshot 8 字段并发一致，Sequence 可解释，系统压力未知可表示 Unknown；日志数据真实 |
| G6.6 | 多种调度交错、内存上限、退出与故障注入、长时间 GC 压力、各类型对象图覆盖，所有失败保留 |
| G6.7 | `.mio` 完整源码 Seed→A→B→C→D；实际执行必要代际且 B=C=D 完整已签名/未签名字节一致 |
| G6.8 | Portable Core 无 Darwin/ARM64/Go 生产依赖，非 Darwin target 不声称可运行；产物无 Go Runtime，原生 source-to-native 无外部 compiler/VM |
| G6.9 | 审计报告列出暂停 p50/p95/p99（够样本才计算）、CPU/wall/RSS、并发重叠与限制；PASS 与 v2.1.0 发布分别判定 |

## 失败策略

- 若改变 M19b/c 对象 ABI，必须先设计兼容迁移证据；未经批准直接 `BLOCKED`。
- 若 GC 无法安全做到并发而采取 STW fallback，保留运行稳定但相应 E4/E5 `BLOCKED`。
- 原生自举新哈希可以不同于 GF4 旧哈希；同源新 B/C/D 必须完全一致。
- 一项测试 PASS 不等于相关其他门禁 PASS；只有明确观测结果、产物和来源可复核才可记通过。
