# Windows AMD64 AOT：阶段 A 审计与实施边界

审计日期：2026-11-04（Asia/Shanghai）。本记录是源码审计及设计建议，不是 Windows 支持声明。

## 工作树与依赖

- 实际分支：`Mio-2.1`，HEAD `0884282367c713722cc0a9087f629853f5a98f5f`。
- 修改前 `git status --short --branch` 仅输出分支行，工作树干净。
- origin：`https://github.com/mio-kobo/mio.git`。未切换分支、抓取或应用 PR、合并、提交或推送。
- 主机：Microsoft Windows 10.0.26200，X64。Windows 执行环境可用；尚无本任务生成的 PE 可供执行。
- 通过 GitHub REST API 只读查询 PR 元数据；连接器调用不可用，已使用只读 HTTPS 后备路径。

| 本地缺少的模块 | 来源 | 查询时状态 |
| --- | --- | --- |
| `bunko/kiso/aot/x86_64` | [PR #4](https://github.com/mio-kobo/mio/pull/4)，head `015b0f80208235ab070fd77e09fa430db3a08521` | OPEN，merged=false |
| `bunko/kiso/aot/elf` | PR #4 | OPEN，merged=false |
| `bunko/kiso/runtime/cpu/amd64` | [PR #5](https://github.com/mio-kobo/mio/pull/5)，head `2347ce6a8b518ab8d60c8f4cb8d6aeb2b30f5731` | OPEN，merged=false |
| `bunko/kiso/runtime/os/linux` | PR #5；其说明明确依赖 #4 | OPEN，merged=false |

以上 PR 描述和作者报告不是本次执行证据，也没有对 PR 源码作完整审查。不得将其中测试数字计入本次结果。任务明确要求基础依赖未合并时报告并等待维护者决定，因此本次不导入或重新实现这些模块。

## 已有源码架构

正式纯 Mio 原生路径为：

```text
selfhost/cli
  -> selfhost/frontend（Mochi）
  -> selfhost/pipeline/compiler.mio
  -> kiso/aot/lower（直接生成 ARM64 words 和 Mach-O AddressPatch）
  -> kiso/aot/macho -> kiso/aot/sign
  -> macOS ARM64 原生镜像
```

`selfhost/pipeline/compiler.mio` 的 `build_file` 调用 `lower.compile_with_heap` 和 `macho.executable`，签名入口再调用 `sign.adhoc`。`lower/LowerResult` 含 `[]uint32` words 与 `[]macho.AddressPatch`，因此完整语言 lowering 尚不是通用多 CPU 后端。

另一条运行时生成路径是：

```text
kiso/runtime/gc 的平台无关操作/算法
  -> kiso/runtime/ir 的标量 Step / Function / Binding
  -> kiso/runtime/cpu/aarch64/program.mio
  + kiso/runtime/os/darwin 的 bindings / 平台程序 / 链接
```

Runtime IR 使用虚拟原生字寄存器、符号函数/标签、原子操作和 OS binding；它不是完整 Mio 源语言 IR，也没有浮点调用签名。AArch64 consumer 的运行时内部 ABI 是 x0..x6 参数、x7 imports、x0 返回；寄存器及机器码由 CPU Adapter 决定。Darwin Adapter 将公开 libSystem 符号绑定至 Mach-O 数据槽，不能照搬到 Windows。

已存在 ARM64 编码器、Mach-O writer、其 Mio 单元测试及模块 CI 注册。当前本地没有 ELF writer，无法按已落地 ELF 接口对齐 PE writer；待 #4 合并后再审查其实际接口和错误类型。

### ABI、根与 GC

- `runtime/gc/layout.mio` 冻结 Object ABI v1：16 字节对象头、16 字节对象对齐、独立 metadata，默认 LOS 阈值 128 KiB。没有 CPU 寄存器或 OS 页大小混入此契约。
- `aot/lower/lower.mio` 的 `emit_shadow_push/pop` 维护精确根；现有 ARM64 实现以 x24 保存 Shadow Frame 链。`attached_roots.mio` / `worker_roots.mio` 把链发布到线程上下文。Windows 需要新 CPU 映射，不能照抄 x24 编号或省略发布协议。
- GC Core 已有 mark/sweep、分代、SATB、safepoint、线程生命周期和 LOS 等模块。模块存在不等于所有平台上的并发正确性均已验收。
- `runtime/target/target.mio` 默认所有能力关闭；`concurrent_error` 检查完整能力契约。Windows descriptor 当前不会通过该契约。
- 连 Darwin `thread.mio` 的局部能力描述也明确不声明 precise_roots 或 concurrent_collector；不得通过新增 Windows 平台名称推断 GC 支持。

### CLI、自举与测试

- 纯 Mio CLI 当前只有 `build ... [-o ...] [--emit=mochi] [--bunko-root ...]` 等接口，没有已实现的通用目标选择参数。不能声称存在 `--target=windows-amd64`；目标选择的最小扩展需在基础后端落地后设计。
- 正式源码构建使用已有受信任 Native Seed。`MIO_NATIVE_SEED` 在本次 shell 未设置；文档规定的正式 Seed/原生测试主机是 macOS ARM64。
- `build/ci-validation` 中有历史 Windows `.exe`，其存在不能证明是受信任纯 Mio Seed，本次没有拿它们替代原生工具链。
- `scripts/ci/run.sh` / `runner.py` 已提供统一入口，自动发现 `test.sh` 和 `ci-module.json`，区分 native / independent / supplementary 层。
- runner 当前只接受 `macos-arm64` 和 `linux-amd64`；后者是 Go/VM 补充检查，并非已验收的 Linux 原生后端。
- `.github/workflows/native-tests.yml` 保留 macOS ARM64 原生 job 和 Linux 补充 job；没有 Windows 原生 job。本次未修改既有 CI。

## Windows 方案（尚未实现）

### B：独立纯 Mio PE32+ Writer

可先独立开发 `bunko/kiso/aot/pe`，而不接入编译器或复制 AMD64 编码器。建议接受原始 text/rdata/data、入口偏移、命名导入及显式 fixup，返回 bytes、layout 和结构化错误；输入机器码的生成由调用者负责。该阶段是否先行，等待维护者决定。

按 [Microsoft PE/COFF](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format) 实现 DOS/PE/COFF/PE32+ headers 和 section table，明确区分 RVA、VA 与文件偏移。布局集中计算：建议 FileAlignment=512、SectionAlignment=4096、ImageBase=0x140000000；值是待实现的选择，不是仓库既有 ABI。

`.text` RX、`.rdata` R、`.data` RW，导入描述符、名称和 ILT 可放只读节，IAT 放可写节并发布对应目录。布局必须处理空节、零填充、字符串 NUL、终止项、整数溢出、目录/节边界和越界入口。绝对 VA fixup 使用 DIR64 base relocations；仅使用 RVA/相对地址时不凭空生成重定位项，也不虚报 ASLR。为非叶函数提供 `.pdata` / `.xdata` 数据入口，并验证范围、对齐和排序。

配套 `pe_test.mio`、`test.sh`、`ci-module.json`、README；先用当前受支持的 Mio 原生测试主机测 writer，再用独立 PE parser 验证。外部 parser 仅属测试依赖。未运行的测试始终写 NOT_RUN。

### C/D：最小原生程序与 Windows ABI

待共享编码器可用后生成调用 ExitProcess 的最小程序，随后加入 stdout；在当前真实 Windows X64 主机执行并检查退出码、精确 stdout/stderr。必须由 Mio writer 生成，不能用其他语言 writer 替代正式实现。

复用 AMD64 encoder 和运行时内部调用约定，仅在 OS 调用边界使用 Win64 ABI。PR #5 描述的内部寄存器约定只是待审查输入，不在本次冻结。共享 consumer 需要将外部 ABI 策略与 CPU 指令选择分离，不能复制整套 emitter 或改坏 Linux。

按 [Microsoft x64 calling convention](https://learn.microsoft.com/en-us/cpp/build/x64-calling-convention) 使用 RCX/RDX/R8/R9，浮点按参数位置使用 XMM0..3，预留 32 字节 shadow space，额外参数上栈，调用处满足 16 字节栈对齐，保存需要保留的非易失状态。Runtime IR 缺少浮点类型时明确拒绝未经建模的浮点外部调用。shadow space 是 Windows ABI 栈区域，与 GC Shadow Frame 是不同概念。

按 [Microsoft x64 exception handling](https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64) 为分配栈空间或调用其他函数的函数生成匹配序言/尾声的 unwind 数据；不能以“最小示例能运行”代替展开正确性。

### E/F：OS Adapter 与完整源语言 AOT

Windows Adapter 使用公开 API：ExitProcess、GetStdHandle/WriteFile、VirtualAlloc/VirtualFree/VirtualProtect、QueryPerformanceCounter/QueryPerformanceFrequency。适配层负责句柄错误、部分写入、计数器换算及溢出、内存大小/对齐、MEM_RELEASE 大小为零等语义。具体 API 细节实施时再逐项对照官方参考并测试；不使用 Linux syscall 编号。

初期 threads/TLS/park-wake/precise-roots/concurrent-collector 都保持 false。实现并测试单项服务后才逐项声明能力。复用平台无关 GC，保持对象和精确根语义。

完整语言 AOT 仍需把当前 ARM64 专用 lowering 的相关职责抽出或增加受限共享 lowering 层；这是 #4/#5 之外的工作，不能把 Runtime IR 最小链路当成完整编译器。先覆盖 int/bool/分支/循环/函数/多参数/递归/输出/内存和非法操作；不支持的 opcode、类型或 native operation 显式失败。保留 macOS 路径和历史引导编译器。

### G：验收和拆分

推荐审查顺序：独立 PE writer 与测试；共享 AMD64 外部 ABI 策略和 unwind；Windows OS Adapter 与真实执行；受限源语言 AOT；Windows runner 接入与回归；后续单独 GC/线程及 Windows 自举验收。不要一次引入全后端和 GC 的巨大改动。

Windows CI 应扩展已有统一入口的主机映射，先运行可用的 Mio 原生模块测试，再运行独立 PE 检查与 `.exe` 原生执行，并保留 macOS/Linux jobs。在 Windows Seed 尚不可用时，可拆分 macOS 上 writer 的 Mio 原生测试与 Windows 上产物执行，但需记录产物来源和各层状态；不得空测试变绿。

## 本次结果与停止点

| 项目 | 结果 | 说明 |
| --- | --- | --- |
| Git / 本地模块审计 | PASS | 执行只读命令并核查源码 |
| PR 依赖状态查询 | PASS | #4/#5 均 open、未合并；不等于源码或功能验证通过 |
| PE writer、Windows ABI、OS Adapter | 未实现 | 等待基础依赖处理/独立阶段范围决定 |
| PE 结构 / 独立交叉验证 | NOT_RUN | 没有本任务生成的产物 |
| Windows 原生执行 | NOT_RUN | 主机可用，但没有待测产物 |
| Mio 原生模块测试 | NOT_RUN | 没有新增模块，当前未配置受信任原生 Seed |
| Windows CI | NOT_RUN | 尚无对应 job，未触发远端工作流 |
| macOS/Linux 回归 | NOT_RUN | 本次只有 Windows 源码审计 |
| Windows GC / Selfhost | 未支持、未验证 | 不变更现有能力描述或验收结论 |

阶段 A 只新增此文档，没有修改正式实现、ABI 或 CI。依据任务中“基础依赖仍在未合并 PR 中……报告并等待维护者决定”的要求，阶段 A 后暂停了实现，没有自动合并或叠加 PR。

## 维护者后续决定

2026-11-04：维护者明确授权先独立实现 PE Writer，并要求创建 PR 供贡献者参与修改。工作分支为 `windows-amd64/pe-writer`，目标为 `Mio-2.1`。阶段 B 不引入 #4/#5，不新增 AMD64 编码器、OS Adapter 或完整语言 AOT 接入。上述测试矩阵记录阶段 A 当时状态，后续实测结果随阶段 B 更新。
