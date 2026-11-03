# 三、GC 算法/并发硬约束

## 3.1 保留现有对象布局

- Ordinary heap：16 字节对象头、16 字节对齐、独立 Side Metadata；对象级 Young→Old 晋升**只更新对象 metadata，不移动地址**。年龄阈值遵从既有自适应边界（复核实际常量，不能假设被某个编译优化折叠）。
- LOS：默认从 128 KiB 开始，独立映射，Young/Old LOS 使用同一代际与写屏障协议。释放不能在其他线程尚能读取时直接 unmap。
- GC Root 必须精确：Storage、TypedArray、nullable、struct、enum、Closure/Cell、Map、泛型实例、全局与各 mutator shadow frame；纯数值 payload 不可以保守猜测成指针。
- 老 ABI 与生成程序的运行时调用约定需验证；新增 metadata 应版本化或明确占用经核实的未使用空间，杜绝与现有 3072B metadata 区、LOS prefix、GC/pressure counters 相互踩踏。

## 3.2 并发阶段机

建议明确状态：`Idle` → `InitHandshake(STW)` → `ConcurrentMark` → `RemarkHandshake(STW)` → `ConcurrentSweep` → `Idle`。如需多次 remark 或阶段并发重叠，先用协议图和不变量证明安全。

- GC worker 与 mutator 是**不同执行线程**。工作集由 epoch、颜色和同步发布规则约束；标记栈/队列不可丢项。
- Init 必须对所有已注册 mutator 建立 safepoint，快照每线程 Shadow Frames、全局、TLS/运行时 roots；禁止跨线程无同步遍历正在修改的 frame。
- 默认采用 **SATB pre-write barrier（保存被覆盖旧引用）** 保护并发 Old 标记，配合现有 Old→Young post-write remembered-set barrier；设计前先证明必要 Root / Global / allocation 发布路径的覆盖。若选择 incremental-update，则须在验收报告中给出等价三色不变量与完整写路径证明，不能混用但缺少任何一边。
- SATB worker 队列必须有并发可见性、背压、overflow 修复与 termination detection。Overflow 不得静默丢引用；可触发有界 STW drain/remark。
- 期间新建对象与从 Young 晋升的对象有明确黑/白/灰定义；若 Minor 与 Old 标记冲突，设计显式互斥/握手/epoch handoff，而非同时自由修改对象头或 remembered list。
- Remark 必须消费在途 SATB、处理新旧 Roots 和线程注册/退出，然后才能进入 Sweep。
- Sweep 必须只清除**已经确证不可达且无并发读者**的 Old 对象。Allocator 与 sweeper 的自由链/对象头/side metadata 操作必须同步；必要时采用 epoch/quarantine 延迟重用。
- 线程失败、join 失败、超时、OOM、队列耗尽必须进入可验证安全退出/保守回退，不能无锁直接回收。

## 3.3 原子、压力与采样

- M19c 的 `memory.snapshot` 奇偶序列只是在单线程下观测版本，**不等于原子发布**。M19e 必须用 Acquire/Release 或经证明等效同步改造，让另一个线程读取 8 个字段时观察到一致快照。
- GC 状态字段、记忆集合标志、标记颜色、队列 head/tail、已提交页预算和 LOS 链接皆属于并发共享内存，逐项给出 owner、读写线程、同步规则。
- 压力等级 Normal/Elevated/High/Critical、reason 位和 hysteresis 继续由 GC 原生策略维护；系统内存压力输入缺失时表示 Unknown，不得假定 Normal。
- GC 只提供压力和 telemetry。M19d Admission Controller、HTTP 503、请求排队属于**外部消费方**，不得通过 GC 直接实现。

## 3.4 安全边界

- 禁止把 `int64`、`float64`、packed nullable 或未证明带 pointer layout 的字段当作指针；必须使用类型/布局标记。
- 不得为了并发提高吞吐关闭 GCStress、Shadow Frame、边界检查、全量精确回归、LOS/压力预算。
- 禁止未经过生命周期/回收协议就扫描指向已释放的对象；禁止在 STW 中调用任意用户回调。
- CPU-specific barrier 指令只能在 target backend 中；不可将 LL/SC/DMB 等放进公共 GC 模块。
- 如平台无法可靠提供 safepoint / atomic / worker thread，禁止启用并发 Old GC；明确错误或回到兼容 STW，验收仍 BLOCKED。

## 3.5 M19b/M19c 同源性

现有 `generational.mio`、`large_objects.mio`、`memory_runtime.mio`、`observation.mio` 等需保留功能和指标同源。重构过程中用元数据布局检查、差分测试和 native witnesses 证明 Young/Old/LOS 行为一致。

`memory_policy.mio` 目前为 Go 生成的指令序列；M19f 将策略的**权威维护源码**改成纯 Mio，并保留与旧压力语义的差分证据。历史 Go 脚本可作只读参考，不可作为新版本更新 policy 的必需生成器。
