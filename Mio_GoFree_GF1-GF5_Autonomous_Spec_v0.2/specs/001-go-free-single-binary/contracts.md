# Unified Toolchain Contracts — GF1～GF5 跨阶段接口约定

本文件定义 GF1～GF5 必须共同遵守的可验证协议。接口名字是概念性签名，Codex 应对照现有纯 Mio 类型系统落地，**不得把伪代码当成现有 Mio API**。

## A. 前端编译与诊断

```text
CompileSource(ProjectRoot, Entry, CompileOptions, ResourceResolver)
    -> Result<MochiBytes, DiagnosticList>

Diagnostic:
    code, severity, file, start/end span, message, optional cause
```

- 输入不能硬编码为 `selfhost/bootstrap` 或当前工作目录 `.`；需支持单文件、多文件模块和 Bunko 导入。
- 错误必须从词法、解析、名称解析、类型检查、Codegen 一直传播到 CLI；禁止只向 stdout 打印 `decode failed` 然后 exit 0。
- 诊断至少包括源文件位置、稳定代码/类别、明确错误原因、非零退出码；stdout 用于程序标准输出，stderr 用于编译错误。
- 原生前端通过相同源码差分，不要求错误文字逐字照搬 Go，但错误类别、位置与成功/失败边界必须一致；无法一致的地方要作为兼容决策记录。

## B. 后端内存契约

```text
BuildNative(MochiBytes, Target=darwin-arm64, RuntimeOptions)
    -> Result<UnsignedMachOBytes, DiagnosticList>
SignAdHoc(UnsignedMachOBytes) -> Result<SignedMachOBytes, SignError>
```

- `MochiBytes` 由同一进程的内存 buffer 传输，无 `.mochi` 临时文件与第二个编译器进程。
- GF2 允许使用现有 Decoder 路径而不复制实现，但数据布局、类型指针分类、NativeFS binding ID/hash、GC Root/Shadow Frame、ABI 必须通过差分。
- 未签名输出用于固定点，签名输出用于用户执行。GF3 起普通构建自己签名，`codesign` 只作为测试校验工具。
- 任何失败不得生成看似成功的旧文件：每次成功验证输出必须属于本次构建，可用临时文件 + 原子重命名保护目标文件。

## C. Bunko 资源契约

资源清单包含规范化导入路径、模块版本、源码字节长度、SHA256、稳定排序序号；资源构建输入必须可追溯到 GF0/GF4 冻结源快照。优先内嵌源字节或可靠编码内容，不允许编译时暗中读取本机仓库路径。外部覆盖是显式、可追踪、确定性诊断的开发功能。

## D. 统一 CLI 契约

| 命令 | 新目标默认行为 | 失败条件与退出 |
| --- | --- | --- |
| `version` | 打印真实版本与目标平台 | 无法读取元数据非零退出 |
| `help` | 列出实际可用 Native 能力 | 未知命令使用错误码 |
| `check file.mio` | 原生前端静态诊断 | 源码无效非零退出 |
| `build file.mio -o file` | 原生 Source→Mach-O＋本地签名 | 前端/后端/签名错误均非零且不保留陈旧产物 |
| `run file.mio -- args` | 原生编译后启动刚构建的用户程序 | 编译错误不启动用户程序；用户退出码可正确传播 |
| `test ./...` | Native 测试发现与执行、汇总 | 任一失败或测试基础设施错误非零 |
| `exec file.mochi` | 纯 Mio Native 编译并执行 Mochi | 不解释执行 VM、不偷用 Go |
| `disasm file.mochi` | 由纯 Mio 解码器反汇编 | 不调用旧 Go 工具 |
| `lsp` | 在同一个原生 `mio` 中以正确 JSON-RPC 提供服务 | stdout 必须只有协议报文；无 Go 子进程 |

前几个既有命令在 GF0 仍使用 Go VM 或输出 `.mochi`。**不得声称新行为向后完全兼容**；按版本管理，保留显式 Mochi 产出选项，提供 README/迁移说明和回归。

## E. 测试语义及可观察输出

- 同一源码与输入、已定义行为必须一致，包括整数溢出、`float32` 与负零、数组/Map/Cell 共享语义、错误状态、模块可见性。
- 原生二进制的无符号固定点比较不经过随意正则化，不对外宣称未执行 Stage 已执行。
- Release `mio` 本身和编译产物都必须检查无 Go Runtime 符号/buildinfo，且构建/运行轨迹中不启动 Go 编译器或 VM。
- 环境/argv/stdin/stdout/stderr、错误码、文件读取/关闭、无 Bunko 文件系统状态和中文路径至少有真实回归。

## F. 有界安全与原生内存

- 保留 M19c 的稳定地址、16 字节对象头与 16 字节 Payload 对齐、精确引用分类、Young/Old/LOS、Side Metadata 预算与 OOM。
- 保留独立的 Major/Minor、跨代 Remembered Set、GCStress 和 Shadow Frame 验收；不把 M19d 未合入代码作为 GF 必需组件。
- 不跨线程读取 M19c 单线程 Snapshot 并宣称原子安全；需要真实线程同步时必须实现合规发布协议并另验收。
