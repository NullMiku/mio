# GF3 — One Native `mio` CLI + Embedded Bunko

**目标：** 普通用户只需安装**一个可执行文件 `mio`**，从源码检查到构建、运行、测试均在本地原生完成。

## 统一命令

实现和验证：

```text
mio version
mio help [command]
mio check path.mio
mio build path.mio -o name
mio run path.mio -- [program args...]
mio test ./... [known test options]
```

由真实 CLI 命令表/测试确认错误码、help 和 stdout/stderr。`run` 必须传递用户程序 args/exit code；`test` 遵守 `_test.mio`、`test_` 函数、包发现/筛选/汇总、正反测试和失败状态，不可拿单个运行示例冒充整个 test runner。

### 已发布接口兼容

GF0 确认旧版 `mio build` 输出 `.mochi`，`mio run/exec` 使用 Go VM，`disasm/lsp` 由 Go 提供：

- 采用明确 **v2 原生默认行为迁移**，发布说明和版本/CLI 回归记录 breaking changes。
- 以显式 `--emit=mochi`（或等价的正式标志）保留必要 Mochi 导出能力。
- `exec` 必须用纯 Mio Native AOT 编译 Mochi 后执行，不得运行 VM；`disasm` 必须用纯 Mio Decoder；`lsp` 必须移植为原生 Mio JSON-RPC 语言服务器，并对 initialize、诊断、文件同步及项目既有重要能力建立回归。任何一项未实现，GF3 保持 `NOT_ACCEPTED`，不能将 Go LSP 打包成隐藏二进制。
- 完整功能宣称以最终实际命令和测试为准；任何非平凡移除须显式人工可见的兼容性记录，不能在无人值守模式下静默抹除。

## 内嵌 Bunko

建立包含规范导入路径、字节长度、模块版本、SHA256 的确定性生成 manifest。把 Bunko 内容作为可解析资源编进 `mio`；导入 `yobu "kiso/math"`、array/string/fs 等有效模块时不依赖磁盘目录；保留一个**明确覆盖开关**用于源码开发，且拒绝意外从原仓库路径隐式回退。

覆盖项目模块、相对/绝对路径、同名覆盖优先级、符号链接行为、中文路径、错误诊断。当前 GF0 `MIO_BUNKO` 等查找规则需明确迁移，不能静默删除开发能力。

## 自带 Mach-O ad-hoc 签名

- 纯 Mio Writer 补充满足 macOS ARM64 原生执行的 ad-hoc CodeDirectory/LC_CODE_SIGNATURE 等必要结构与页面哈希。
- `mio build` 输出即可执行、可经 `codesign --verify --strict` 验证，测试可用系统 `codesign`，但**普通构建不得靠外部 `codesign` 成功**。
- 区分本地 ad-hoc 与 Developer ID/notarization，不能用 ad-hoc 宣称正式苹果公证。

## 运行时及发行单文件

`mio` 本身及生成应用都不得包含 Go Runtime/buildinfo/隐藏 Go 工具；用户程序包含其所需 Native Runtime/GC/LOS/Shadow Frame。用户没有 `mio` 时生成程序仍能启动。

使用隔离临时目录，仅放一个 `mio` 和项目源码；物理 Bunko、Go、编译工具不在可访问路径；离线测试 CLI、多个模块、GC/NativeFS、错误码。文件访问和进程追踪不能显示工作树/Go/编译器隐藏依赖。PATH 为空不是充分条件，必须额外静态查二进制及执行来源。

## GF3 PASS

单一纯 Mio `mio` 可执行文件、内嵌 Bunko、单进程核心编译、内建本地签名、Native check/build/run/test 和已声明的兼容命令全部验收；用户只装 `mio` 的离线真实测试成功。生成报告后**自动继续 GF4**。
