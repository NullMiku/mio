# 一、范围与完成定义

## 1.1 正式目标

1. M19e：在同一个 *非移动式* Young/Old/LOS GC 上增加真正的并发 Old Mark-Sweep；Young Minor 可维持短暂停顿 STW。必须证明 mutator 与 collector 曾实际同时运行，不得把分批 STW、单线程循环或轮询称为并发。
2. M19f：在同一个 GC 上加入 **High（吞吐优先）/ Balanced（默认）/ Low（p99 延迟优先）** 自适应策略。Low 不等于最小内存；不允许缩减类型安全、精确 Root 或 GC 可达性。
3. *算法无关目标平台*：GC 协议、状态机、追踪/晋升/回收规则、预算及 profile 在独立纯 Mio 模块中定义。Darwin、Linux、Windows 和 ARM64、AMD64 的差异只在 target backend 中实现。
4. 完整保持 M19b/M19c 的：对象级非移动晋升、16-byte header、独立 Side Metadata、精确 Shadow Frame、Old→Young remembered-set、128 KiB LOS 阈值、压力分级和堆预算；变更任何 ABI 必须有版本和迁移验证。
5. 仅使用 **Mio 编写** 新的正式 GC、目标接口、测试/构建所需生产组件；不要引入 Go/C/Rust 作为正式 Runtime、代码生成器或维持代码生成的必经程序。使用必要 OS ABI / 系统库是允许的。历史 Go 参考代码和独立证据脚本可只读存在。
6. 以已验收的原生 `mio` 为编译器 seed，正常编译和最终自举不经过 Go VM、Go CLI、Clang、LLVM、独立 C 编译器或 Python 编译阶段。

## 1.2 非目标

- M19e/f 不要求一次性实现 Linux ARM64、Linux AMD64、Windows AMD64 完整原生后端；必须使各后端**有清晰可实现的接口**并在 unsupported target 明确失败。
- 不在本阶段加入移动式 Copying GC、Mark-Compact、Region 级晋升、用户可见所有权系统、全新语言语法、JIT 或 LLVM。
- 不借 M19ef 重写 Frontend/LSP/Parser、另造 GC 版本、引入自动 Admission/HTTP 503 行为。
- 不把当前 `Mio-2.1` 研发候选伪称已经发布为稳定 v2.1.0；GF5 或 v2.0.0 发布状态以最新证据为准。

## 1.3 完成门槛

`M19e PASS` = 并发正确性 + 真实并发见证 + 安全回收 + 目标接口审计 + 现有 GC 回归 + Native 自举全部通过。

`M19f PASS` = 三配置真实生效 + 性能趋势有有效测量 + 压力策略/回退正确 + 兼容性与自举全部通过。

`M19 GLOBAL PASS` = 在最终相同源码、相同目标平台与一致证据口径上 E/F/M19b/c 必要回归全过，M19d 是否纳入需独立明确记录。不能由独立旧 PASS 拼接。发布是额外步骤。
