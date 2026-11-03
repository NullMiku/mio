# Portable GC / Runtime / ABI 强制合同

## 目标架构

```text
普通用户 .mio / 纯 Mio CLI / Frontend / Mochi IR
                 ↓
        Native AOT lowering（纯 Mio）
                 ↓
        Target-neutral GC semantics（纯 Mio）
        ├── precise roots / shadow maps / mutator state
        ├── STW handshake / epochs / safepoints
        ├── SATB / remember set / mark termination
        ├── Old sweep / free-lists / LOS reclamation
        └── memory snapshot + observability
                 ↓ RuntimeOperation semantic interface
       CPU adapter                  OS adapter
       ARM64 首先实现               Darwin 首先实现
       AMD64 后续                   Linux/Windows 后续
                 ↓
        Native executable backend (Mach-O/ELF/PE)
```

### 无条件约束

1. `bunko/kiso/runtime/gc/` 不导入 `kiso/aot/arm64`、Mach-O 或 Darwin 子模块；不包含 pthread 具体函数名、Darwin SVC 编号、固定页面尺寸、A64 LDAR/LDAXR/DMB 编码；这些属于 adapter。GC core 只使用跨平台语义操作（例如 `PauseAllMutators`, `PublishRoots`, `AtomicPublish`, `SATBRecordOld`, `DeferFree`）。
2. 新增平台时不得复制并改名整套 GC mark/sweep 实现。暂不支持的 Linux/AMD64/Windows 必须 `UNSUPPORTED` 或 fail closed，不得伪报可运行。
3. 纯 Mio 是生产核心唯一源语言；允许通过公开系统 ABI 使用 libSystem 等系统库，也允许测试协调器用 Python/Shell **仅在编译器生产路径之外**读取日志或启动程序；不得由 Go/C/Python 实现 GC 或重建编译器的必要阶段。
4. 保持非移动对象地址、对象级晋升、16B 对象头、16B 对齐、Side Metadata 和 Shadow Frame 的精确指针布局；LOS 默认 128KiB，独立映射并可属于 Young/Old；M19c 预算/四级压力规则不应退化。
5. 用户程序的 `int64` / `float` 数值载荷不可按位模式保守猜成地址；Nullables、泛型、Cell、Closure、Struct/Enum、Map/Array、Storage、LOS 均按类型与布局数据精准扫描。窄整数溢出与浮点语义不能因插桩被改变。
6. M19d Admission 控制器独立，不自动整合。M19f High/Balanced/Low 的策略改动超出 E3～E6 授权；E6 只要求现有压力/内存协议并发一致、安全不退化。

### 共享对象与同步语义表

| 数据 | 典型拥有者 | 并发访问规则 | 必须保证 |
|---|---|---|---|
| Mutator TLS context / Shadow chain | 对应 mutator | 在握手确认后的 safepoint 内读，或使用证明正确的同步快照 | frame 节点存活、Root 不丢失 |
| GC epoch / phase | Coordinator | 明确 Acquire/Release 原子发布 | 不读到未来阶段的过期 Root |
| Threads registry | Registry owner | 注册/退出与遍历串行化或安全快照 | 不访问退出线程状态 |
| SATB 队列 | Producer / Collector | 无锁或锁协议必须线性化 | 无丢项，无无限溢出 |
| Remembered Set | Mutator / Minor GC | 原子或 STW 同步 | Old→Young 不遗漏 |
| Mark bits / age / generation | Collector + mutators | 原子/协作所有权明确 | 不误扫、不重复提升 |
| Free bins / recycled objects | Sweeper / Allocator | 同步、epoch/quarantine | 不在仍可访问时复用 |
| LOS mapped list | GC + allocator + threads | 延迟 unlink/unmap、失败持有所有权 | 不 use-after-unmap |
| `memory.snapshot` 8 字段 | GC/pressure 发布者 | 一致性快照协议（双缓冲/锁/原子） | 8 字段来自同一版本 |

### 真实编译器接入界面（不得保留手工-only）

- 纯 Mio Codegen/Lowering 在每个普通函数入口/退出正确建立和销毁所属线程的 Shadow Frame；GC 线程不使用 Mutator 栈；程序启动/线程创建自动附加 context。
- 每个调用/分配、循环回边和适当的耗时热点，以安全性证明选择 Safepoint，不能在对象半初始化/未正确 root/published 状态中断。需要记录未 root 的中间值和调用参数的寄存器溢出语义。
- 运行时进入阻塞 OS ABI 之前必须声明阻塞模式并发布所需根，返回后正确重新进入可运行状态；不可无协议扫描外部系统线程栈。
- GC 协议中 CPU 平台相关寄存器约束属于 target adapter，不能将当前 Darwin ARM64 x24 状态当作 Portable GC 公共合同。
- 未来其他 CPU/OS 后端可在独立模块实现同一 RuntimeOperation 并重用相同 semantic tests。

### 写屏障与回收边界

- E4 默认 SATB pre-write 记录旧引用，同时继续 Old→Young post-write Remembered Set。不可直接用后者替代 SATB。
- E4 标记开始/结束、并发分配/晋升、队列终止、异常中止需要形式化线性化时点；可选择可靠的多轮 Remark，不能静默丢项。
- E5 只有在证明无活动读者访问时才能释放；非移动并不自动安全，LOS 的 `munmap` 与复用必须等 epoch/quarantine；没有证明时不允许 E5 PASS。
