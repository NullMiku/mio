# GF1～GF5 真实验收标准（禁止假 PASS）

**有效状态：** `PASS | FAIL | BLOCKED | NOT_RUN | IN_PROGRESS`。不能用“没有看到警告”代替 PASS。每次 PASS 必须绑定**最后一次修改后的源码 Manifest**。

## 全局 A1～A12 验收矩阵

| Gate | 验收动作（必须实际执行） | PASS 的最低证据 |
| --- | --- | --- |
| **A1 单文件** | 隔离空环境中只安装目标 `mio` | `check/build/run/test` 与声明的保留入口都不依赖额外 Mio 工具/Bunko；产物列表证明仅一个必要编译器可执行文件 |
| **A2 无 Go Runtime** | 查看 `mio` 与生成程序符号/build info/依赖/进程日志 | 无 Go Runtime/buildinfo 与 Go 可执行文件/Go VM调用，真实构建来源可追溯；PATH 隐藏不足以单独通过 |
| **A3 原生前端** | `.mio` 单文件、多模块、错误样例、完整自托管源码的原生编译差分 | GF0 16/16 修复并增加足够覆盖，字节/行为与批准的参考一致，诊断非零 |
| **A4 同进程** | 监测正常 `mio build` 进程及中间 IR | 不执行第二个编译器/链接器/VM；从源码到 Mach-O 同一进程完成 |
| **A5 内嵌 Bunko** | 移走物理 Bunko、清除开发路径、离线构建 `yobu "kiso/..."` | 内嵌清单及哈希通过、使用真实模块成功 |
| **A6 CLI** | version/help/check/build/run/test/exec/disasm/lsp 全部原生迁移及兼容决策 | 真实命令和错误路径、`--`、退出码/输出正确；破坏性默认变更有版本化迁移 |
| **A7 独立应用** | 移除 Mio 安装，运行编译好的 Hello、数组/Nullable/Closure/NativeFS | 程序直接运行，包含原生 Runtime 与精确 GC，无 Go 或 Mio runtime 安装 |
| **A8 源码自举** | 无 Go 的可信 Native Seed → A → B → C → D `.mio` 构建 | Seed/A/B/C 实际执行；B=C=D **完整未签名 Mach-O 字节相等**，每代 SHA/输入来源准确 |
| **A9 内存安全** | GCStress、Minor/Major、跨代引用、LOS、OOM、Shadow Frame、地址稳定、数组/Cell/Map | 不漏扫或误扫描，不隐藏崩溃/失败，针对性和端到端回归真正执行 |
| **A10 语义回归** | VM 参考与原生参考差分、错误码、函数 ABI、精度、模块导入 | 已定义行为一致；任何有意兼容变化单独标记和测试 |
| **A11 性能证据** | 相同源码/硬件/输入的普通、原生链对照 | 提供冷启动/热缓存耗时、CPU、峰值 RSS、样本分布；不无证据宣称快多少倍 |
| **A12 Go-free CI/发行** | 在不使用 Go 的可审计隔离流程从精确来源/Seed 产生单文件发布候选 | 构建、测试、签名、SHA、provenance、安装 Smoke 实际通过；发布步骤可由未来 Tag CI 自动运行 |

## 阶段硬门禁

### GF1

- Case 9/10/13/14/15 的五个缺口真正修复；Case 14 必须输出 `-128`、`0`，并覆盖边界算术与类型转换。
- 原生 Frontend 不写死 bootstrap/config；能够读取任意有效入口、模块，并正确拒绝错误代码。缺 config / decode / lower 失败非零，不得单靠 stdout marker 判成功。
- 从`.mio` 到 `.mochi` 的原生执行可证无 Go VM；16 个 GF0 用例全部通过、扩大差分及错误输入回归通过；历史 Compiler-B 字节证明保留。

### GF2

- 单个**实际原生进程**接收 `.mio` 并输出可执行 Mach-O，不启动其它编译器。
- Hello、模块、Map、泛型、浮点、溢出、Closure/Cell、Nullable、数组及错误输入纵切实际通过。
- IR 版本、绑定、类型布局、GC 和运行时一致，编译失败不产生陈旧或错误标称成功的输出。

### GF3

- 用户安装目录只需要一个 `mio` 原生可执行文件；Bunko 必要资源内嵌；成功编译不依赖外部 `codesign`。
- `check/build/run/test/exec/disasm/lsp`在隔离无 Go/无仓库目录环境中真正运行；用户程序可独立运行。
- 明确处理现有 build 默认 Mochi/run VM 的向后兼容；不偷偷改变旧稳定发布的行为。

### GF4

- 可信 Seed 的来源、二进制哈希可复核；在可审计无 Go 环境中全源码 `.mio` 输入生成 A，A→B、B→C、C→D；每代必要执行与签名验证完整。
- B/C/D **未签名完整字节**和 SHA256 一致，不替换历史黄金以掩盖差异。
- 真实 GC/LOS/OOM/NativeFS/Shadow Frame见证通过；原生编译链不能调用 Mochi VM、Go AOT 或外部链接器。

### GF5

- 生产发布候选从提交/manifest 和可信 Seed 由 Go-free 路径重新构建；同机隔离安装验证、版本与 provenance 正确。
- CI 原生门禁真实执行；不能用只校验 YAML 的静态检查替代远端/本地构建与执行测试。
- 旧 Go/Race 测试保留历史报告。若新发布政策对 Go 原有 Full Race 仍作硬门禁，未解则**仍有独立发布阻塞**，不得静默删除该门禁并报告整个 M19 PASS。

## 证据规格

每个阶段保留：`phase`、状态、基线 Manifest、最终 Manifest、实际运行命令 argv、exit code、日志绝对或仓库相对路径、日志 SHA256、每个输出 SHA256、平台/编译器信息、真实耗时/RSS、覆盖、未执行项、异常复现和下一步；同一证据目录不可覆写旧成功或失败。

**单文件 Go-free 终验：** GF1～GF5 均 PASS，A1～A12 全部绑定最终源码 Manifest 实际 PASS，且无需额外安装 Go 或 Mio 工具。远端正式发布仍需维护者授权，未推 Tag/未发布不能被写成已发布。
