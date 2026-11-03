# GF2 — In-process Source-to-Native Pipeline

**目标：** 同一个纯 Mio ARM64 原生进程里完成 `.mio → Mochi v14（内存）→ Native AOT → Mach-O`。

## 起点

- GF1 已 PASS，纯 Mio Frontend 对真实源码可用。
- M18/M19c 已有纯 Mio Native Backend，含 Decoder、Lower、ARM64 Encoder、Mach-O Writer、精确 GC/LOS。
- GF0 当前 frontend API 给出编码 bytes/layout，backend 吃 `mochi.File`；不能假装二者有现成公共对象模型。

## 最小可行整合（明确允许）

可先使用 GF1 前端产生的 **Mochi v14 内存字节 buffer**，直接交给同进程纯 Mio Decoder，再运行 Native AOT。只要没有中间编译器进程/外部 `mochi` 文件，此方案满足 GF2 单进程要求。

尽量复用已有 Parser、Codegen、Decoder、Lower/Types、Mach-O Writer、Runtime，对共享 ABI、NativeFS binding、类型布局、常量池/函数索引和对象所有权做契约测试。不要因“更优雅”而全盘重写 IR。

## 最小纵切顺序

1. Hello World：源码文件 → 单进程 Mach-O → strict 签名验证 → 实际执行。
2. 多模块 + Bunko math，正确导入与依赖顺序。
3. 整数窄位回绕、float32/-0.0、泛型多实例、函数值/Closure、Map。
4. Nullable、Cell、数组/引用存储、struct/enum、错误诊断。
5. NativeFS 实际文件 I/O、复杂项目、大输入与内存压力回归。

## 可观测行为

- 监控 `fork/exec`/子进程、输出路径、依赖访问；正常 `build` 中不允许启动 Go/VM/第二 AOT/Clang/LLVM/外部 linker。
- 不要求此阶段就解决 `codesign` 内嵌；GF2 可通过测试工具进行验签和签名以便执行，但必须把这一外部签名依赖记录为 GF3 待清事项。
- 编译失败时非零、stderr 有可定位错误、不得留下声称成功的旧输出。
- 一次编译跨越多个 AST/IR/GC 分配周期，必须正确追踪所有中间资源与 Shadow Frame；验证无幽灵 Root、悬挂引用或地址搬迁。

## 性能测量

分开记录编译前端、IR encode/decode、Native AOT、Mach-O 写入和最终端到端时间与 RSS。Mochi 内存缓冲不得未经证明就调用大型内存复制；内存不足应明确 OOM，不能悄悄退回磁盘临时文件或 Go VM。

## GF2 PASS

真实 `.mio` 输入在**同一个已执行的纯 Mio 原生程序**中生成并执行有效 ARM64 Mach-O，主语义纵切与错误流全部通过，没有外部编译子进程或解释器回退。保留证据并**自动继续 GF3**。
