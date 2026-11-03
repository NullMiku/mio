# 二、可移植性架构（强制）

## 2.1 建议层次

```text
Pure Mio user source
      │
Native Mio Frontend / IR / Native AOT
      │
Target-independent Runtime/GC semantics (纯 Mio)
  ├── Object/Root/Layout/Generational rules
  ├── Concurrent mark + sweep protocol
  ├── SATB + Old→Young barrier semantics
  ├── Safepoint, thread/root registry protocol
  ├── Allocation/LOS/quarantine/epoch protocol
  └── Profiles / Pressure / Telemetry
      │
GC Runtime-Op IR / explicit target capability contract (纯 Mio)
      ├──────────────────────┐
CPU-specific codegen       OS-specific Runtime bridge
  ├── ARM64                  ├── Darwin (syscalls / libSystem)
  ├── AMD64 (later)          ├── Linux (syscalls / supported ABI)
  └── future CPU            └── Windows (system DLL / supported ABI)
      │
Native executable writer / target ABI
  ├── Mach-O / Darwin ARM64 [first real backend]
  ├── ELF / Linux targets [future]
  └── PE / Windows targets [future]
```

**GC 核心禁止**：直接导入 `kiso/aot/arm64`、`macho`、依赖 Darwin SVC 编号/页面大小、调用 OS 私有 API、假设仅一个执行线程、把 AArch64 原子内存序当通用语义。

**目标后端允许**：用纯 Mio 生成专属 CPU 指令和调用 OS ABI；Darwin 首个实现可复用现有 AArch64 emitter 与 Mach-O Writer，不为了表面平台无关把一切先推倒重来。

## 2.2 两阶段分离改造，防止大重写

1. 先把**语义协议和 policy**整理成独立 Mio 数据结构、编译期规则与可单独测试的 target-neutral operations。由当前 ARM64 实现承担第一个 backend adapter。
2. 再逐步把 `generational.mio` 中的标记/清除和 barrier 生成逻辑改为通过抽象 Runtime-Op API 发射。不能在核心目录只包装一个 `arm64.Assembler` 然后宣称可移植；接口应描述**行为**（AtomicLoadAcquire、WriteBarrier、SafepointPoll、ProtectMemory），而非仅改名 `movz`/`str`。
3. 目前自托管 Mio 语言若尚无 trait/interface，不要求先实现 trait；可以使用显式 `TargetInfo`、`RuntimeOperation` 枚举、可验证 dispatch 和后端模块函数。避免为 GC 引入不必要的语言特性。
4. Runtime-Op IR 与平台代码生成分离后，构建一个**mock target**，只做正确性/指令协议验证（不声称能执行）。未来加 CPU 后端只写 target emitter / ABI，不复制 GC 状态机。

## 2.3 Target contract（先建立再实现并发）

每个 target 必须声明：

- `os`、`arch`、`abi`、pointer width、endianness、page-size 获取方式。
- Atomic 64 位 Load/Store/CAS/FetchAdd/RMW 与 Acquire/Release/AcqRel/SeqCst 的明确 memory-order 语义；支持相应栅栏。
- Thread create/join、Thread Local Storage/thread identity、park/wake/safepoint handshake、monotonic timer。
- Reserve/Commit/Decommit/Release、OS pressure hint（允许 Unknown）、系统内存上限（允许不可用）。
- 精确 Shadow Frame 访问及各线程 Roots 枚举机制、跨线程对象发布可见性。
- 原生函数调用约定、栈对齐、寄存器使用、机器码缓存维护（如必要）、失败报告协议。

平台能力缺失时**构建期或启动时明确 NOT_SUPPORTED**；正常默认单线程 GC 可以保留兼容回退，但此目标上 M19e 并发验收必须标记 BLOCKED，不能说全平台 Concurrent PASS。

## 2.4 不同层的原子归属

CPU 层实现 LL/SC 或 CAS 机器指令、Acquire/Release 和内存屏障；OS 层提供线程和睡眠/唤醒；GC 核心只表达语义要求。不要把 OS thread API 和 CPU atomics 混成 Darwin-only GC 核心。

Darwin ARM64 可通过系统库公开 ABI 实现线程能力，系统库 ABI 调用不等于引入 C 编译/Runtime 源码；若链接/动态加载尚不支持，在 backend 中先补安全、可审计的 OS bridge。不能用 undocumented/private kernel thread API 假装可移植。

## 2.5 未来目标矩阵

| 目标 | M19ef 责任 | 状态要求 |
|---|---|---|
| Darwin ARM64 / Mach-O | 真正实现并执行并发 GC/Profile | 完整 PASS 必须基于实机 |
| Linux ARM64 / ELF | 保持 target contract，可在未来实现 | NOT_IMPLEMENTED，绝不伪报 |
| Linux AMD64 / ELF | 保持 target contract，可在未来实现 | NOT_IMPLEMENTED，绝不伪报 |
| Windows AMD64 / PE | 保持 target contract，可在未来实现 | NOT_IMPLEMENTED，绝不伪报 |
| 其他目标 | 后端能力声明，失败即失败 | 未实现时 fail closed |

**约束**：不要求 v2.1.0 支持所有目标，但禁止为了当前 Darwin ARM64 方便而将未来平台处理写进公共 GC 核心。
