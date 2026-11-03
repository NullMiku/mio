# TypeChecker 第一轮索引优化测量

生产代码仅修改 `selfhost/typecheck/environment.mio`，使用已有动态数组 API。
`TypeCheckResult` 的生产结构、序列化和结果顺序不变。

## 重现

使用新的、尚不存在的输出目录。先把同一份优化前源码（包括未提交修改）冻结到
`EVIDENCE/baseline`，保存 Git diff、未跟踪文件和 SHA-256 清单。不要使用 HEAD
代替含有本地修改的基线。`prepare.py` 从当前主项目工作树复制优化后源码，生成固定
800 组函数/泛型调用输入和独立的 profiling 副本。脚本拒绝覆盖已有测量目录。

```sh
python3 tests/typechecker-perf/prepare.py EVIDENCE
go build -o EVIDENCE/native-builder ./tests/typechecker-perf/builder
export MIO_PERF_SEED=/absolute/path/to/existing/native/mio
EVIDENCE/native-builder EVIDENCE/baseline EVIDENCE/baseline/harness.mio EVIDENCE/baseline-observed.native
EVIDENCE/native-builder EVIDENCE/after EVIDENCE/after/harness.mio EVIDENCE/after-observed.native
python3 tests/typechecker-perf/measure.py EVIDENCE --repeats 5
EVIDENCE/native-builder EVIDENCE/baseline-profile EVIDENCE/baseline-profile/harness.mio EVIDENCE/baseline-profile.native
EVIDENCE/native-builder EVIDENCE/after-profile EVIDENCE/after-profile/harness.mio EVIDENCE/after-profile.native
```

Builder 在各自冻结源码目录中运行相同 native seed 的 `build --emit=mochi`，再在 Go VM
执行各自的同一份 Mio lowering 源码 `compile_with_observation`，生成并签名原生程序。
Go VM 只用于构建，所有测量运行均为 native，不涉及性能回退或新 Runtime API。
固定 managed capacity 为 256 MiB、关闭 GC stress。输入和输出路径以绝对路径编码。

测量执行一次预热，再交错运行两组各 5 次。`typecheck_ms` 是原生单调毫秒时钟包围
`check_program` 的时间，包含 environment/index 初始化。解析、resolver、输出不在该
计时区间。RSS 来自 Darwin `wait4`；GC 来自生成程序的现有 telemetry，覆盖整个
进程（包含解析、resolver 和输出），不是 TypeChecker 独占 GC 时间。

Profiling 只修改生成副本：在副本 TypeCheckResult 加入调用私有计数数组，统计五个函数
调用次数、实际逐项检查次数和累计毫秒。正式结果结构不变，主测量二进制没有这些插桩。
`profile-schema.json` 给出最后 15 行的下标。毫秒时钟较粗，0 ms 不表示零成本；插桩时间
含计数/时钟开销，不能与未插桩时间相加或用于精确分摊。`symbol_type` 扫描包括 facts。
索引初始化对 bindings 的一次扫描不计入“查询线性扫描”计数。

精确语义与 Codegen 字节比较：

```sh
MIO_TYPECHECK_BASELINE_ROOT=/absolute/EVIDENCE/baseline \
MIO_TYPECHECK_EVIDENCE=/absolute/EVIDENCE \
go test ./selfhost/typecheck -run FrozenSnapshot -count=1 -v
```

该测试比较 12 个正/负案例的原始 wire 输出，覆盖类型记录顺序、所有诊断的错误码、
位置、详情、顺序、泛型替换、常量、NodeType 及 Codegen 生成的完整 Mochi 字节。
其他实际执行结果由 `selfhost/codegen` 差分测试和原生 TypeChecker 测试验证。

2026-11-03 的实际结果见当前工作树 `build/typechecker-round1/REPORT.md`。
未完成全量源码编译性能复测和新源码 ABCD 固定点；不代表 M19e/E6 通过。
