> 最高优先级修订（用户 2026-10-26）：遵守 [PURE_MIO_ARCHITECTURE.md](PURE_MIO_ARCHITECTURE.md)。正式组件、构建、自举、发行链必须全部由 Mio Native 实现；其他语言仅限隔离参考审计。未经授权禁止 Commit、Push、Tag、Release。旧条款冲突时以此修订为准。

# GF1～GF5 自动执行清单

**初始：** GF0 `PASS`（基于外部审计）；GF1～GF5 `NOT_RUN`。本清单不因“计划存在”自动打钩。

## 初始化与恢复

- [ ] 对照 `gf0/AUDIT.md` 和当前 Git/worktree 源码清单。
- [ ] 建立独立 GF 工作树，不改源树；安全导入全部必要 staged/unstaged/untracked 源码与 Spec。
- [ ] 记录 GF0 基线 SHA、M19d/Race 工作树状态，设置证据目录与 `status.json`。
- [ ] 安排避免大测试并发的资源窗口。

## GF1 — Native Frontend 完整性

- [ ] 在真实冻结 GF0 Corpus 中复现 Cases 9、10、13、14、15。
- [ ] 修复 `int8`、`uint32` 等窄整数回绕的静默错并覆盖 signed/unsigned 边界。
- [ ] 实现 Map 的纯 Mio Native decode/lowering/runtime路径（Op 41/42/43），覆盖 GC 指针布局。
- [ ] 根因定位并修复顶层函数值 decoder 与函数索引问题，保留 Closure/Cell。
- [ ] 修复泛型 identity `int64` / `string` 表示和 UnsafeType(1025)，避免过度合并。
- [ ] 修复 `float32`/`float64`/-0.0/转换 UnsafeType(1622)及相关精度行为。
- [ ] 把固定 selfhost bootstrap driver 泛化为指定源码/目录/Bunko 的原生 frontend。
- [ ] 修复缺 config/decode/lower/类型失败 `exit 0` 误报；输出准确诊断。
- [ ] 16/16 + 扩大差分 corpus、完整 selfhost/Bunko 原生前端测试、GF1 provenance。
- [ ] **GF1 PASS 后立即开展 GF2，无需再问用户。**

## GF2 — 进程内统一编译

- [ ] 定义前端 Mochi bytes 与后端 decoder 的一致性、类型/ABI/NativeFS 绑定接口。
- [ ] 纯 Mio 原生单进程串接 `source → frontend → Mochi in memory → Native AOT → Mach-O`。
- [ ] 验证无 Go VM、无中间编译器子进程、无外部 linker，失败不留陈旧输出。
- [ ] 执行 Hello/Map/泛型/数值/数组/Nullable/Cell/模块/错误处理完整纵切。
- [ ] GCStress、LOS、签名及真实 Mach-O 执行；GF2 provenance。
- [ ] **GF2 PASS 后立即开展 GF3。**

## GF3 — 仅安装一个 mio

- [ ] 纯 Mio CLI version/help/check/build/run/test，支持真实 argv/stdout/stderr/退出码。
- [ ] 完成 exec（原生 AOT）、disasm（原生 Decoder）、lsp（原生 JSON-RPC）迁移及版本兼容说明，不能以删除旧命令过关。
- [ ] 内嵌 Bunko 清单/资源与哈希；移除工作树磁盘 Bunko 后正常编译。
- [ ] Mach-O 内建 ad-hoc 签名；普通编译不要求用户手动 codesign。
- [ ] 验证发行 `mio` 和生成应用均不含 Go Runtime/buildinfo，也不执行 Go/VM。
- [ ] 干净离线安装只需一个 `mio`，成功 check/build/run/test；GF3 provenance。
- [ ] **GF3 PASS 后立即开展 GF4。**

## GF4 — 从 `.mio` 全源自举

- [ ] 冻结可信原生 Seed 与 compiler source/Bunko/ABI manifest。
- [ ] 在禁 Go、禁其他编译器的隔离环境从 Seed 编译完整 `.mio` 得 A。
- [ ] A→B→C→D 同样读取完整 `.mio`；真实执行必要各代，签名验证。
- [ ] B=C=D **未签名完整 Mach-O 逐字节一致**，每代记录 SHA、退出码、工具/进程来源。
- [ ] 执行 GCStress/Root/LOS/OOM/NativeFS/Nullable/Cell 真实自编译见证。
- [ ] GF4 provenance；**GF4 PASS 后立即开展 GF5。**

## GF5 — Go-free 生产构建与发行准备

- [ ] 单文件发行构建、测试、版本、来源追踪、签名验证、SHA256SUMS。
- [ ] 在无 Go 的受控环境实际从种子/源码重建发行 `mio`；文件/进程/符号审计。
- [ ] 实现和验证 Go-free Release CI 候选，最小权限、失败阻断、dry-run 无远端发布。
- [ ] 保留 Go 历史测试路径，但从 Native Release 构建硬依赖中移除，记录 M19 历史 Race 状态与覆盖差异。
- [ ] 最终全量 A1～A12 复验，记录兼容性与性能。
- [ ] 输出一个可由人未来推 Tag 的 Release 工作流，不自动 Push/Tag/Release。

## 纯 Mio 架构修订硬门禁

- [ ] 全部正式组件、CLI、Frontend/IR/Backend、Runtime/GC 生成、标准库、测试运行器、工具链服务均为 Mio Native。
- [ ] 正式构建、执行、自举、离线安装和发行链移除 Go/Python/C/Clang/LLVM 等外部工具链。
- [ ] 原生打包、SHA、provenance 和资源生成；历史指令表生成工具不构成正式重建依赖。
- [ ] 外部参考审计环境与正式依赖链隔离；不得以参考工具产物替代正式源码多代自举。
- [ ] 不执行未经另行授权的 Commit、Push、Tag 或 Release。

## 最终交付

- [ ] 单个真正的纯 Mio `mio`（不是把 Go CLI 换名）。
- [ ] 可审计 Seed→A/B/C/D 源码级固定点与全部哈希。
- [ ] 当前最终源码下全部 GF/A Gate PASS 的日志和报告；不通过则 `NOT_ACCEPTED` 并列出阻塞。
- [ ] 只提供本地补丁/构建/CI 待审；保留原始工作树与历史证据。
