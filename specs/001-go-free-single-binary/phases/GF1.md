> 最高优先级修订（用户 2026-10-26）：遵守 [PURE_MIO_ARCHITECTURE.md](../PURE_MIO_ARCHITECTURE.md)。正式组件、构建、自举、发行链必须全部由 Mio Native 实现；其他语言仅限隔离参考审计。未经授权禁止 Commit、Push、Tag、Release。旧条款冲突时以此修订为准。

# GF1 — Native Frontend Semantic Completion

**目标：** 纯 Mio 编写、作为原生 ARM64 运行的 Lexer/Parser/Resolver/TypeChecker/Codegen，能处理真实 `.mio` 工程并输出可信 Mochi v14，完全不通过 Go VM 解释执行前端。

## 第一步：建立定位矩阵，不预设错误层

对 GF0 Corpus 同源输入分别记录：
1. Go frontend 编译得到的 Mochi 和诊断。
2. 纯 Mio frontend 原生编译得到的 Mochi 和诊断（必要时先从已验证 bootstrap 变体出发）。
3. 相同 Mochi 的 Go VM 运行结果。
4. 相同 Mochi 的纯 Mio Native AOT decode/lower/执行结果。

必须区分是前端 Codegen、Mochi Decoder、Native lowering、Runtime/ABI 还是 GC 布局问题。不允许一律写成“前端不支持”。对每个失败构造**最小且忠于原语义**的回归，再扩展复杂输入。

## 五项必修缺口（GF0 真实案例）

### 14：窄整数静默错误（最高优先级）

- `int8(127)+1` 期望 `-128`；`uint32(4294967295)+1` 期望 `0`，原 Native 错为 `128` 与 `4294967296`。
- 对照整数 width/type descriptor、算术结果截断、符号扩展/零扩展、常量折叠、函数参数/返回、数组 load/store、类型转换、负值边界。
- 检查 Go 与纯 Mio AOT 是否一致执行，保留所有整数/引用布局与 ABI。

### 9：Map Opcode 41/42/43

- GF0 Map 创建/写/读遭遇 `lowering failed / 2 / 41`；不得将 Map 语法从 Mio 移除。
- 实现或正确连接 Map Native lowering、对象布局、键值相等/哈希、引用/非引用值的精确 GC Root 与写屏障，处理 Nullable 查找结果。
- 测试 empty、insert、update、missing、GCStress、字符串键、整数值与包含托管引用的 Map。

### 10：顶层无捕获函数值 `add`

- GF0 表现为 `decode failed`；先查字节码常量池、函数索引、闭包类型/绑定、调用约定，缩减复现。
- 覆盖无捕获函数值、闭包捕获、函数值参数/返回及错误调用；不改变已有 Closure Cell 语义。

### 13：泛型 identity 的 int64/string 实例化

- GF0 `lowering failed / 8 / 1025`（UnsafeType）。调查单态化实例区分、类型 arena、引用分类、相同 generic 函数多实例数据布局。
- 不可通过合并整数与 boxed/reference 类型、关闭 pointer safety 或跳过 Root 验证解决。

### 15：float32/float64

- GF0 `lowering failed / 8 / 1622`（UnsafeType）。最小化 `float32`、`float64 -0.0`、转换、比较、函数传值/返回和格式化案例。
- 检查精度舍入、NaN/±Inf（在语言既定语义可用范围内）、有符号零、bitcast与算术/转换路径。
- 若文本表示引起差异，区分格式化差异与数值位模式差异；不能无依据改测试期待。

## 通用原生前端入口

- 从固定 `selfhost/bootstrap`、硬编码 `.` 和 `input.config/output.config` 中抽象出真实 `CompileSource` 入口；支持入口文件、项目目录、多模块依赖、Bunko 导入路径和错误诊断。
- 初期允许读取源码和模块文件，但不依赖 Go VM、Go CLI 或运行第二个编译器；与 GF3 的 Bunko 内嵌分开推进。
- 缺 config、decode/lower、文件不存在、语法/类型错误必须 **exit != 0**；验证错误发生时绝不复用旧输出文件。
- 正确比较 `Mochi v14`：确定性部分要求字节相等；明确允许的差异必须有布局/结构/执行等价的充分证据，不得无条件宽松比对。

## 测试计划

- GF0 原样 16 例全部通过（5 项不能跳过）。
- 新增覆盖：整数极值/宽度、泛型多个实例、Map 参照/GC、函数值/Closure、float32/float64、错误诊断、模块依赖、NativeFS。
- 历史 bootstrap 固定输入仍输出 120707 bytes 与已知 Golden（仅用于相同输入/相同旧语义构建路径；若源变化，证明差异来源）。
- 在禁运行 Go/VM 的沙箱内**实际运行原生前端**，从 `.mio` 源文件生成 Mochi。单靠 Go 测试驱动编译 Native 不能证明前端原生执行。
- 回归 M19c 精确 GC、LOS、Shadow Frame 与 OOM；记录 stage 产物变化。

## 性能

GF0 测得原生前端固定任务约 11.256 秒，Go 前端约 0.074 秒（不同阶段、主机有 Race 负载），不得直接宣称提速。GF1 记录完整任务 CPU、RSS、wall、编译单位数量，并进行多样本重复。若仍显著慢，Profiling 确定热点，先修复语义而不是牺牲类型检查换速度。

## GF1 PASS

只有通用原生前端实际正确运行、16/16 和新增广泛语义/错误/模块测试全通过、M19c GC 行为未回退、错误非零、无 Go VM 执行路径且证据可复现，才能标记 GF1 PASS，并**自动继续 GF2**。
