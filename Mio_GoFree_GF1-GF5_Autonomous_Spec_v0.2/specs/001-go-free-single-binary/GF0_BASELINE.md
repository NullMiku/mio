# GF0 已验收事实摘要（非 GF0 完整报告）

**信息源：** 用户 2026-10-26 提供的 `gf0/AUDIT.md`。本文件只供新 Codex 快速校对；工作时以仓库真实 `gf0/AUDIT.md`、冻结清单和代码为准。

- **GF0：PASS；最终 Single Binary：NOT_ACCEPTED；GF1～GF5 尚未实施。** 评估发生在 `/Volumes/Sector0/AppData/Mio/mio`、`Mio-2`，GF0 HEAD `a96d83ca0ee30239026b9ba27d5a5d547349f647`。后续 HEAD 可能变化，必须重新核对。
- 源码冻结 462 文件，源码 Manifest SHA256 为 `57f92e4bd36851a12aae62511e46016bd4c28ab00002db2ffaec3086d81a4ea6`；历史证据 6162 文件，Manifest SHA256 为 `aaa6e10aa344566c8ff72e2964b0c4f5c78b823591a83bff1ac31448b210f4e7`；外部证据目录为 `/Volumes/Sector0/AppData/Mio/mio-gf0-audit-20261026-01`。SHA 值只描述旧冻结版本，不能作为后续修改不变的要求。
- 当前 Go CLI 源码版本 `2.0.0`：`build` 默认 `.mochi`；`run` 和 `exec` 运行 Go VM；`check` 用 Go 前端；`test` 用 Go tester/VM；`lsp` 和 `disasm` 也由 Go 提供。独立 Go `mochi-aot` 与纯 Mio `native-aot` 分开存在。
- 固定输入的纯 Mio Native Frontend 在无 fork/exec 的沙箱内能读源码生成 `compiler-B.mochi`，120707 字节 / 477 函数 / 497 常量 / SHA256 `b44a55bf3f9020e6b0ff83ad137b25774814a32dfe8acaf070abcd167bfd1465`。它依赖现有固定 bootstrap config，**缺 config 报错却 exit 0**。
- **16 个 corpus：11 PASS、4 BLOCKED_NATIVE、1 FAIL。**
  - Case 9 `Map[string,int64]`，OpMap（41/42/43）Native lowering 缺失。
  - Case 10 顶层无捕获函数值 `add`，`decode failed`，精确原因尚未确定。
  - Case 13 泛型 identity 在 `int64` 与 `string` 上实例化，UnsafeType `1025`。
  - Case 14 `int8(127)+1` 和 `uint32(4294967295)+1`：VM 为 `-128` / `0`，Native 错为 `128` / `4294967296`（**静默错误，优先修复**）。
  - Case 15 `float32` 精度、`float64 -0.0` 和转换，UnsafeType `1622`。
- M19c 历史 Native AOT 固定点 SHA256 `00a665b229ccb35a5ef291821865c455ad887e021ac92ee60fcf68d44c79c833`；该链是共同 `.mochi` 输入生成原生镜像，不是 Go-free 源码自举。
- 性能快照（GF0 受其他进程负载影响，非同一端到端流程）：Go 前端构建固定 bootstrap 约 0.074 秒；纯 Mio 原生前端约 11.256 秒；纯 Mio Native AOT 构建 bootstrap Mochi 约 1.647 秒。不能由此声称原生前端已比 Go 前端快。
- 编译器需要磁盘 Bunko；纯 Mio Native 目前经 config 文件读入路径；Mach-O 需外部 `codesign` 才能在 macOS 下正常执行；`exit 0` 不等于成功。
- M19b 历史全仓 Go Race 超时（Codegen），仍 `NOT_ACCEPTED`；M19c 独立功能 PASS；M19d 独立 Admission Core 在另一 worktree PASS、未并入本任务。
- GF0 报告明确各阶段顺序：GF1 先补语义/诊断与任意源码前端；GF2 进程内前后端；GF3 内嵌 Bunko/单 CLI/签名；GF4 完整 `.mio` 源码自举；GF5 无 Go CI/发行。

当本文件与实际 GF0 报告或冻结文件冲突时，先保存差异和来源，再以实际可复现证据为准；不要默默改变用户给定的基线。
