# 证据目录、状态和自举合同

## 目录规范

建议在本工作树内使用独立的新目录：

`build/m19ef-evidence/e3-<run-id>/`、`e4-<run-id>/`、`e5-<run-id>/`、`e6-<run-id>/`。

`<run-id>` 可由时间/构建标识产生，**路径存在即拒绝覆盖，不能删除旧结果**。所有失败、超时、负向测试均保留。禁止把已发布的 GF4/GF5/M19b/c 证据改写成新的 PASS。

## 每次运行至少保存

1. `source-manifest.json`：有序源码相对路径、字节 SHA256、文件数、Git HEAD/分支、dirty/untracked 清单、平台与 target、工具版本，必须覆盖真实编译输入。
2. `seed.json`：可信纯 Mio Native Seed 的路径、哈希、签名验证方式与结果；外部本地路径只是 audit 信息，不能暗示二进制已上传。
3. `commands.json`：逐进程 argv、cwd、环境中有用的非秘密变量（注意脱敏）、wall/CPU/peak RSS、退出码、timeout，stdout/stderr 文件路径与 hash。
4. `results.json`：每 Gate 的 `PASS / FAIL / BLOCKED / NOT_RUN`、证据路径、重复次数、确切断言及源 Manifest hash。
5. 原生 Mach-O、未签名像、签名像、结构/签名验证输出及其 SHA256，按需保存。
6. 实际 mutator/collector 活动时段、Stop/Resume epoch、Root 检查、SATB 入/出队和溢出、sweep/quarantine 与 LOS 事件的**来源于真实运行时**的计数或 trace。
7. 失败最小复现及隔离失败原因，不因最终通过而删除先前失败。
8. `final-source-unchanged.json`：验收前后 Source Manifest 是否完全一致；变更后必须重新冻结并复验。

## 测试证据语义

- 真正通过由 native 退出码、stderr、结构化测试结果、精确 assert 和目标进程观察共同证明。不能只依赖 stdout 的 `PASS` 文本。
- 预期失败（例如无法唤醒超时、错误平台、CAS mismatch）必须独立记 `expected_exit`；不可把普通 `exit != 0` 当作成功。
- 数字示例：`64` 次真实堆、`64,128` 次 Minor、`256` 次 Major、`32` 原生、`11` GF4 镜像是**前次报告数据**，需要按新源码实际复核；不作为不变门槛硬编码或新产物直接计数。
- 旧 GF4 `signed witness` 完全相等是 ABI 兼容证据，不等于最新编译器的完整 `.mio` 自举通过。
- 不能用 mock 计数构造 Mutator/Collector 重叠，必须观测真实托管执行和 GC 真实阶段。

## GF4 同源原生自举（E6）

1. 从可信原生 Mio Seed，编译**完整统一 Mio CLI/Compiler 源码**为 A；A 编译自身源码为 B，B→C，C→D。每代实际执行前必须核对机器码签名、路径和产物有效性。
2. 由该代自身的正常源码→原生编译路径工作，禁止共享一个预先生成的 `.mochi` 当作每代输入；无生产 Go/Clang/LLVM/Python 编译阶段。
3. **最终 B=C=D 的完整未签名字节一致**；如采用确定性 ad-hoc 签名，**已签名全文件也一致**；不省略代码签名差异来伪造固定点。
4. 至少 A、B、C 必须实际生成下一代并执行必要自测；D 按验收目标执行最终 suite。每代时间、RSS、错误、SHA256 分开记录。
5. 编译器固定点不是正确性充分条件，必须对相同源码快照进行 GCStress、语言语义、Bunko/LSP/CLI 和多线程实测。
6. 新源码改变生成代码时新 hash 变化正常；禁止把旧 hash 强制写进新验收预期。

## 状态流转

- 每阶段检查完毕才修改状态；产物/源码证据不一致则置 `BLOCKED` 或 `NEEDS_REVALIDATION`，不能保留旧 PASS。
- 总状态 `NOT_ACCEPTED` 直到 E3/E4/E5/E6 及已有 E0/E1/E2 全部正式验收。
- 不授权远端发布；正式 v2.1.0 另需独立版本决策、平台与发行检查。
