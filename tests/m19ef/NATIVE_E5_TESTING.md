# Mio M19e：手动原生测试

在当前工作树运行；入口会验证分支、Darwin ARM64、可信 Seed SHA256 和签名。
Python 只冻结、启动、计量和核对。编译、代码生成、链接、签名、Runtime 和 GC
全部由原生 Mio 执行。不覆盖旧证据，不执行 Commit/Push/Tag/Release。

```sh
cd /Users/hatsunemiku/.codex/worktrees/m19ef-portable-gc/mio
./tests/m19ef/run-native-e5.sh fatal
```

默认执行32次 **fatal cleanup 所有权**检查。每次运行真实普通 Mio 多线程程序，
在 Sweep 活动时触发非法 Join 参数，预期目标程序退出1；启动器核对：

- 主线程未拥有完整 stopped heap 时，语义状态85表示 cancel-only；
- Sweeper收到取消，未被此错误路径 Join，未清空待处理任务；
- 所有映射和句柄保持归属，随后由终止进程的 OS teardown 接管；
- 原生诊断包、源码与产物哈希、完整签名/未签名字节复现、退出码和性能记录。

启动器退出0、`PASS_FATAL_OWNERSHIP_SUBSET_ONLY` 仅表示这个子集通过。
目标程序的预期退出1不会被误报为启动器失败。它**不等于 E5 或 M19e PASS**。
可用 `--fresh` 强制由可信 Native Seed 重建测试编译器；默认只复用来源、签名和
编译器全部输入哈希均匹配的现有原生编译器。

快速验证入口（仅开发自测，不代替默认32次）：

```sh
./tests/m19ef/run-native-e5.sh fatal --repeat 1
```

完整 E5 严格矩阵：

```sh
./tests/m19ef/run-native-e5.sh full
```

完整矩阵固定32次，包含真实 OS 故障、Sweep/Worker 重叠、Minor/晋升、空闲块复用、
八周期取消/恢复、LOS Reader/失败重试/退场、再入、关闭、OOM 和 fatal。
八周期样本保留逐周期的 active-Sweep、取消和时间重叠要求；全量入口不允许减样。
这是长时间、串行运行的矩阵。**当前 E5 仍 IN_PROGRESS**；最近候选08在重复周期
取消前发现 Sweep 已结束，严格断言失败。这个失败不会被脚本隐藏或算作通过。
E6 和新的 Seed→A→B→C→D 尚未验收，此脚本不会代替它们或宣布 M19e PASS。

每次自动创建新的 `build/m19ef-evidence/manual-E5-…/` 并打印绝对路径。重点文件：
`summary.json`、`commands.json`、`source-manifest.json`、`fatal-observations.json`、
`final-source-unchanged.json`、各命令 stdout/stderr；完整模式另有 `matrix/`。
完整模式的实时进度位于终端打印的 `matrix-controller.stdout`，例如：

```sh
tail -f /终端打印的证据目录/matrix-controller.stdout
```

测试失败返回非0，原始失败和已执行步骤全部保留。Ctrl+C 请求停止当前测试并保留
证据。此入口通过文件锁防止自身同时启动两轮；测试期间保持候选源码不变。

## 2026-10-30 验收契约 v2

`full` 入口现在运行 `old-sweep-v2/matrix.py`，固定32次，分别验证无门闩的真实
Collector/Mutator 重叠和受控 Epoch 生命周期/Minor 交错。原 `old-sweep/run.py`、
旧 late 源码与 Full30 FAIL 保留，不将旧失败改写为 PASS。

权威契约：`specs/002-m19ef-portable-pure-mio/autonomous-e3-e6/E5_CONTRACT_V2.md`。
Main 在 Join 后读到 Phase3 是新的原生回归用例要求；验收依据同 Epoch 的真实用户
工作、真实回收批次、Registry 退出、成功 pthread_join 夹定的原生终止区间，以及
8次具备合法 STW ownership 的 Minor。Phase2 瞬时读数本身不能证明成功。
测试适配层只用于独立镜像，不修改正式 GC 状态机；无门闩镜像继续证明实际并发。

开发定向入口（不能代替 full32）：

```sh
python3 tests/m19ef/old-sweep-v2/run.py build/m19ef-evidence/E5-v2-directed-NEW directed
```

所有输出目录必须尚不存在；源码、适配层、契约与控制器均冻结并保留哈希。
