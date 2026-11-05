# kiso/aot/winconsole

最小纯 Mio Windows AMD64 控制台镜像生成链路：

```text
exit_executable / stdout_executable
  -> kiso/aot/x86_64 指令编码器
  -> kiso/aot/pe 写入器
  -> Windows AMD64 PE32+ bytes
```

返回 `BuildResult {bytes,error}`；失败返回空 bytes 和非空错误。调用者保存成功结果。正式模块没有进程调用、C、Go、Python 或外部链接器依赖。

- `exit_executable(exit_code)`：通过 IAT 调用 `ExitProcess`，退出码限 0..255。
- `stdout_executable(message,exit_code)`：输出最多 1 MiB 原始字节，再退出；不补换行，不转换编码，支持内嵌 NUL。空消息生成 exit-only 镜像。
- 非空输出使用继承的同步 stdout，经 `GetStdHandle` / `WriteFile` 写入。检查 NULL/INVALID_HANDLE_VALUE、API 失败、零进度和异常字节数；部分成功写入会推进指针并继续。I/O 错误以 111 退出（调用者应避免用 111 表示应用成功）。不支持异步句柄。
- 只使用易失寄存器；32 字节 shadow space、第五参数及局部状态分别占用独立栈位置。exit-only 分配 40 字节，stdout 分配 72 字节，调用点保持 16 字节对齐。全部指令来自共享编码器；绝对 IAT/数据操作数交给 PE writer 修补并登记 DIR64。
- 函数只执行一次栈分配，不保存其他非易失寄存器，符合 PE writer 已有的受限 unwind 模型。生成匹配的 pdata/xdata；实际异常展开仍为 NOT_RUN。

这是参数化的最小代码生成模块；尚未把普通 Mio 源码接入 Windows lowering，也未增加 CLI Windows target、通用 Win64 FFI、OS Adapter、GC、线程或自举支持。

## 开发验证

原生模块入口：

```bash
bash bunko/kiso/aot/winconsole/test.sh macos-arm64 unit
```

需要受信任 Native Seed，先执行 Mio 模块测试，再独立检查 Mio builder 生成的 PE；不降级参考 VM。Windows 产物执行必须显式请求。

Windows 补充验证（Go/Python 仅为开发工具）：

```text
go build -o build/pe-writer/mio-reference.exe ./cmd/mio
python tests/pe-writer/run.py --mio build/pe-writer/mio-reference.exe --mode reference --execute
python tests/pe-writer/test_driver.py
```

驱动保留原有 6 个结构镜像、7 个损坏输入拒绝检查及 4 个执行夹具，另生成 4 个编码器镜像。新增独立检查核对导入、数据、栈分配、展开字节、全部绝对操作数和重定位；5 个负向检查破坏 payload、栈分配、展开、IAT 调用和重定位，必须全部拒绝。真实 Windows 执行精确比较退出码、stdout 和 stderr；另继承只读 stdout 句柄验证 WriteFile 错误路径。报告及执行输出保存在 `build/pe-writer`，包含源码/编译器/执行镜像 SHA256。

2026-11-05 Windows AMD64 实测：参考 VM 的 PE 测试 14 项、winconsole 测试 3 项 PASS；原有验证全部 PASS；新增 4 个镜像结构及真实执行 PASS，退出 47/48/49/50，文本输出为 `Mio Windows AMD64\n`，二进制输出为 `4d 69 6f 00 ff 0a`；只读 stdout 返回 111，5 个负向检查及 8 个驱动测试 PASS。

`examples/windows-amd64/hello.mio` 经参考 VM 运行可生成 hello-windows.exe，本机执行退出 48，精确输出上述文本，stderr 为空。`runner.py inventory` 正确发现新 native 模块；shell 语法及发布隔离静态检查 PASS。重跑 CI 框架自检为 FAIL：59 项中 57 项通过，`test_timeout_kill_survives_macos_eperm_for_zombie_only_groups` 因 Windows 无 `os.killpg` 报错，`test_timeout_kills_descendants` 检测到超时后子进程仍创建 marker；这两个框架检查均未修改或跳过，日志在 build/pe-writer/ci-selftest.log。此结果不能写为 CI 全部通过。

受信任 Mio 原生生成/模块测试、强制部分写入/零进度注入、NULL/INVALID_HANDLE_VALUE 路径注入、实际异常展开、强制非首选基址加载、macOS/Linux 原生回归、完整 Windows 源语言 AOT、自举与发布验收均为 NOT_RUN。四个新 PE 的实际执行是 Windows 原生执行；生成器的参考 VM PASS 不代表生成器原生 PASS。

依据：[Win64 调用约定](https://learn.microsoft.com/en-us/cpp/build/x64-calling-convention)、[函数序言/尾声](https://learn.microsoft.com/en-us/cpp/build/prolog-and-epilog)、[WriteFile](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-writefile)、[GetStdHandle](https://learn.microsoft.com/en-us/windows/win32/api/processenv/nf-processenv-getstdhandle)。
