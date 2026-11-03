# Mio WebAssembly V1 Playground

在浏览器 Worker 中运行真实 Go 编译器和 Mochi VM。静态 HTTP 服务只分发资源，用户源码不会发送到服务器。

## 构建与运行

需要 Go（本轮验证为 go1.25.9 darwin/arm64）、Bash、Python 3。

```sh
./scripts/serve-wasm.sh       # 构建并监听 http://127.0.0.1:8787
# 可选端口：./scripts/serve-wasm.sh 8788
```

在浏览器中打开上述地址即可编辑、Run、Check 和 Stop / Reload。单独构建：

```sh
./scripts/build-wasm.sh
```

产物是 `build/playground/`，可整体部署到静态 HTTP(S) 服务器。不要用 `file://` 打开。
构建脚本从当前 GOROOT 复制匹配的官方 `wasm_exec.js`，并写入 `toolchain.txt`；请一起部署同一次构建的文件，勿混用工具链 runtime。
首次构建会生成忽略的 `cmd/mio-wasm/library/`，因此直接 `GOOS=js GOARCH=wasm go build ./cmd/mio-wasm` 前须先运行脚本。模块闭包来自当前检出的源码，不依赖开发者绝对目录。

## 自动化验证

保持静态服务运行，在另一个终端执行：

```sh
# 需要可解析的 playwright 包及其 Chromium。也可以使用已有的 Chrome：
MIO_BROWSER_CHANNEL=chrome ./scripts/check-wasm.sh
# 非默认端口：MIO_PLAYGROUND_URL=http://127.0.0.1:8788
# 非项目内的 Playwright：MIO_PLAYWRIGHT=/absolute/path/to/playwright
```

可在测试环境中 `npm install --no-save playwright` 并 `npx playwright install chromium`，然后不设置 channel。
脚本构建 Wasm、运行 Go 回归、导出 native baseline，再使用真实无头浏览器测试 UI 和 Worker。
不需要向运行中的 Playground 安装任何 JS 框架或 npm 依赖。

```sh
go test ./...  # 全库回归；含较慢的原生 AOT 测试
```

测试证据在忽略的 `build/wasm-report/`，含 `browser-results.json`、桌面及手机截图；native oracle 在 `build/playground/native-results.json`。浏览器测试比较输出与诊断原文，而不是仅确认 wasm 文件存在。本地 Go 测试另外使用原有 `mio.Environment.CompileFile/Run` 与磁盘加载器验证样例和类型诊断一致性。

## 执行架构

`textarea → main-thread controller → classic Web Worker → official Go runtime → Go js/wasm bridge → Bunko loader → lexer/parser → constant folding → resolver → type checker → compiler → Mochi encode/decode → VM → capped stdout → result`

- `internal/playground` 使用真实 Go 实现，没有 JavaScript 语言解释器。
- Run 经过现有 Mochi 编解码器，支持截至 v14 的格式。编码器依照现有规则选择能表达程序的最低格式版本，简单程序不强行标为 v14。
- Check 完成解析、检查及编译，不运行 VM。
- 每次请求创建新的编译器、空 MMA 注册表和 VM。
- 共享改动仅在 `internal/bunko/loader.go`、`program.go`：增加 `LoadSourceFS` 和只读 `fs.FS` 分支，复用现有导入合并逻辑。磁盘、symlink、overlay 和 CLI 路径继续使用原入口。`fs_test.go` 验证拒绝目录穿越、忽略测试源码、无磁盘回退及 nil FS。
- 未修改 Compiler、VM、Mochi 格式规则、原生 ARM64 代码生成、GC、对象布局、M18 固定点脚本、M19 或发行工作流。

## 消息协议和生命周期

主线程发 `{operation:"init", id}`；初始化返回 `{operation:"ready", id, initMs}`。
Run/Check 发 `{operation:"run"|"check", id, source}`。
结果返回 `{operation:"result", id, status, stdout, diagnostics, error?, compileMs, runMs, elapsedMs}`。
异常返回 `{operation:"error", id, error}`。
状态包括 `ok`、`checked`、`diagnostic`、`error`、主线程产生的 `cancelled` 和 `timeout`。
`compileMs` 是 Go 前端编译耗时；`runMs` 仅 VM；`elapsedMs` 包括桥接与 Mochi 编解码，不含初始化、主线程消息往返和 Worker 重建。Check 的 VM 时间为 0。没有独立 stderr 语言通道，因此不虚构 stderr；诊断和运行错误在单独字段显示。当前诊断是编译器错误文本，尚未提供编辑器行内标注。

控制器：loading → ready → running → result → terminate → loading → ready。
每次请求结束都终止并重新创建 Worker，回收整套 Go/Wasm 内存。首次及每次重建初始化都有 15 秒上限。执行请求自发出起有 5 秒上限（也覆盖编译）。Stop 在主线程直接调用 `Worker.terminate()`，无需等待 Go 返回；随后重建。无法通过发送 stop 消息中断正同步运行的 Go，因此这里刻意不依赖 Worker 内的 stop 消息。
唯一递增 request ID 配合 generation 检查，丢弃已终止 Worker 的延迟消息。页面离开时清理 Worker。Worker 异常会显示错误，Stop / Reload 可重新初始化。

## 支持与限制

嵌入经过测试的纯源码模块：`kiso/math`、`kiso/array`、`kiso/string`、`kiso/bytes`、`kiso/utf8`（string 的传递依赖）。样例验证 gcd/sqrt、数组 make/push、Unicode 拼接及 rune count、bytes.contains。其他现有语言能力通过相同前端和 VM 执行；未宣称每一能力均做了浏览器覆盖测试。

未打包模块统一报 `unsupported Bunko package`，包括 `kiso/fs`、`kiso/io`、原生模块、AOT 包以及未审查的其他纯计算模块；不会伪造结果。没有 stdin、用户自定义多文件包、文件上传、网络模块或宿主 JavaScript 调用接口。MMA 注册表为空，不能获得文件系统等原生能力。Go runtime 自身拥有启动 Wasm 所需 JS 接口，但不向 Mio 程序注册这些接口。

资源限制：

- 源码最多 65,536 UTF-8 字节（UI 和 Go 均验证）。
- stdout 缓冲最多 65,536 字节，超出立即返回真实 VM 输出错误；只返回上限内的部分输出。
- VM 每请求最多 5,000,000 条指令；主线程另外控制 5 秒期限。
- 停止和每次运行后销毁 Worker，避免跨请求累计保留 Go 堆。
- 没有可配置的 Go Wasm 堆硬上限。单条大分配、编译峰值、字符串格式化中间量仍受浏览器/Go/操作系统限制，可能导致 OOM 或浏览器终止 Worker。Worker 隔离不能视为完整的恶意代码安全沙箱；输出限额也不是内存限额。
- 当前每次运行都重新初始化，代价是额外启动时间；在取得更多测量前保留此简单回收策略。

## 本轮验收（2026-10-21）

真实 Chrome 155.0.8059.85（macOS ARM64、Playwright）通过 18 组检查：加载、5 个正常示例与 native 对比、类型错误对比、3 次重复执行、Check、状态隔离、不支持能力/路径检查、输出限额、VM 指令预算、无限循环 Stop/恢复、外部超时与旧消息隔离、真实 Worker 异常显示/恢复、控制台健康以及桌面/手机布局。桌面 1200×1000，手机 390×844。自动化的异常和 1 ms 超时测试为故障注入；正常 UI 默认超时仍是 5 秒。

本轮 Wasm 未压缩约 5.86 MB。具体字节数和每次运行的时间以 `build/wasm-report/REPORT.md` 和 `browser-results.json` 为准；本机无头浏览器、HTTP localhost、同时运行 Go 回归的结果不代表性能目标。尚未验证 Safari、Firefox、Edge、真实移动设备或低内存环境。Go 官方 runtime 需现代浏览器的 WebAssembly、Worker、TextEncoder/Decoder、crypto 等基础接口。

已满足本轮 Chrome WebAssembly V1 PoC 的交互验收；适合下一步在文档官网集成前做浏览器矩阵和静态资源发布测试。正式官网为同级独立仓库，本任务没有修改它。M18 完整自举固定点需原有单独验收流程，不能用浏览器测试代替；M19 未提交修改不包含在独立 worktree 中。

全库回归补充：本轮 `go test ./...` 中 `internal/aot`（468.985 s）、`internal/aot/darwinarm64`、CLI、Compiler、VM、Bunko、Mochi、selfhost 的 lexer/parser/resolver/typecheck 等包通过；`selfhost/codegen` 的 `TestCodegenSelfAndBunkoSources` 在默认 10 分钟测试时限超时，命令退出 1。因此没有宣称全库回归全绿，也没有通过修改超时或黄金哈希来掩盖该结果。堆栈显示该测试仍在既有 `VM.RunWithOptions` 执行，其 VM 和自托管代码本任务均未改动；本轮没有断言它在更长时限下的结果。完整日志保存在 `build/wasm-go-tests.log`。
