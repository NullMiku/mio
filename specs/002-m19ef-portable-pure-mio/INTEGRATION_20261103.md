# M19e 源码集成报告 — 2026-11-03

本次完成源码集成，不授予 E6、M19e、M19f 或 Mio v2.1.0 Release Ready。历史 Full30 FAIL 永久保留。

## 仓库与分支

- 源：`/Users/hatsunemiku/.codex/worktrees/m19ef-portable-gc/mio`，`EXP/m19ef-portable-gc`。
- 目标：`/Volumes/Sector0/AppData/Mio/mio`，实际分支 `Mio-2.1`，不切换分支。
- 双方 HEAD、Merge Base 均为 `f8410f48ee69eb2bcd228eafe423b92fc1dd7d2f`，双向祖先检查成立。
- 共同 Git 目录为 `/Volumes/Sector0/AppData/Mio/mio/.git`；双方独有提交均为 0。
- 源码成果实际位于未提交和未跟踪文件，未用单独 merge 分支历史冒充集成。
- 原源树 14 个 tracked 修改、209 个 untracked 路径；双方 staged patch 均为空。
- 目标原有 6 个 tracked 用户修改以及全部 untracked TCP/测试/Spec/配置均以真实工作目录为基线保留。

## 保护、清单与 SHA256

完整独立归档：[/Volumes/Sector0/AppData/Mio/m19e-integration-20261103-01](/Volumes/Sector0/AppData/Mio/m19e-integration-20261103-01)，位于双方工作树之外，目录权限 0700，归档 0600。

- source-full.tar SHA256：`109957396dfdb9e4ae1c33b23e1e520a4505b897790936319882e93848866432`。
- target-full.tar SHA256：`6af209c051784fae0053bea9bce80417b7cc51d1d3e49d9ba27a185dc8d76a18`。
- source/full-manifest.json SHA256：`f532a7f8840f0fd25e6102f385db9b537e2afb36e05ff50508cc40b00143742a`。
- target/full-manifest.json SHA256：`3d4226c7752b67bb2420ff72c119c681cf2ac07bb5a7134b2519fb8f2eff69d0`。
- 完整 tar 保留权限、目录、符号链接、ACL/xattr、Git 信息和忽略目录中的历史验收证据；备份前后所有内容稳定。
- 原始 porcelain -uall/-z、binary unstaged/staged patch、index --stage、tracked/untracked/ignored、HEAD、worktree 和祖先检查在归档 source/、target/ 与 repository-check.json。
- [所有 223 个 M19e 来源路径及 SHA256](/Volumes/Sector0/AppData/Mio/m19e-integration-20261103-01/m19e-source-presence.json)。
- [最终实际新增/修改/删除逐文件清单](/Volumes/Sector0/AppData/Mio/m19e-integration-20261103-01/publish-plan.json)。
- [完整合入源码 Manifest](/Volumes/Sector0/AppData/Mio/m19e-integration-20261103-01/integrated-source-manifest.json)；其 SHA256、精确文件数及最终变更数见 [publish-result.json](/Volumes/Sector0/AppData/Mio/m19e-integration-20261103-01/publish-result.json)。Manifest 在同步前生成，同步后逐文件核对内容和 mode。
- [同步后 Git 状态](/Volumes/Sector0/AppData/Mio/m19e-integration-20261103-01/after-status-porcelain.bin)、[binary diff](/Volumes/Sector0/AppData/Mio/m19e-integration-20261103-01/after-unstaged.patch)、[staged diff](/Volumes/Sector0/AppData/Mio/m19e-integration-20261103-01/after-staged.patch)、[index](/Volumes/Sector0/AppData/Mio/m19e-integration-20261103-01/after-index.bin)；不新增暂存、不修改 HEAD。
- 原开发树全部原始文件及忽略证据逐 SHA256 复查结果见 [source-preservation.json](/Volumes/Sector0/AppData/Mio/m19e-integration-20261103-01/source-preservation.json)。

## 合并内容和冲突

临时副本 `/Volumes/Sector0/AppData/Mio/m19e-integration-20261103-01/integration` 是独立 Git clone，以主项目真实 tracked/untracked 内容和 mode 为基线，未复制主项目工作区 Git 索引覆盖原树。采用共同祖先三方状态比较：目标等于祖先时应用源 delta，双方相同时保留；无整个文件 source-wins/target-wins。

223 个来源路径：212 个目标未修改路径应用源 delta，10 个已相同路径保留，1 个 add/add 冲突进行结构化合并。没有来源删除或重命名，没有待合入独有提交；完整原始清单在 integration-plan.json。

唯一冲突 `specs/002-m19ef-portable-pure-mio/status.json`：目标为初始 NOT_RUN，源为开发检查点，且无已提交共同文件祖先。双方原文分别留在 conflicts/，同时嵌入最终 integration_history。当前工作树/分支改为主项目，E3/E4/E5 标为需要新集成源复验，E6 IN_PROGRESS，总体 NOT_ACCEPTED。未解决合并冲突：0。详见 [conflict-resolution.json](/Volumes/Sector0/AppData/Mio/m19e-integration-20261103-01/conflict-resolution.json)。

主项目 TCP 的 6 个 tracked 修改和已有新增文件不与 M19e 生产源码重叠，逐字节保留。未移除或降低其功能；本次验证不声称已完成它们的全部旧 Go/Native socket 兼容验收，完整新 E6 仍会运行 Bunko suite。

纳入全部有效纯 Mio GC Core、RuntimeOp、CPU/OS Adapter、精确 Root/Shadow Frame/Safepoint、SATB/Concurrent Mark/Sweep/LOS、Native AOT/Runtime、LSP 修复及相关测试/Spec/必要配置。生产实现按来源内容保留；集成适配限于测试路径、执行 cwd、分支检查、串行锁、状态/续接文档，以及新增 resume.py。来源与集成 SHA 差异逐项列在 m19e-source-presence.json。

7 个 Mio 测试 fixture 的旧工作树绝对 IO 路径改为当前执行目录相对路径，配套控制器执行 native 时 cwd 指向当前 checkout；不会写回旧工作树。原始测试仍完整保存在源树和 tar，包括旧错误断言及历史 Full30 FAIL。

不向源码集成编译缓存、重复二进制、大型运行日志、.DS_Store 和 pycache；它们仍完整保留在原树及独立完整归档。未执行 reset、clean、stash、commit、push、tag、release，未改远端或删除原树。

## 实际新集成源码验证

编译器为已验签的原生 Mio `mio-current`，SHA256 `0225cb1296f08af147e491ae1f5f17e31d2ed79b3ad0208737f86cb039c3bad8`。这是编译工具来源，不是新集成源码 ABCD PASS。所有本次测试均显式使用临时集成副本的当前 Bunko；未借旧候选日志宣布新源码通过。重型工作串行，未停止主项目已有 LSP。

新增正式模块由其所在 package 的真实原生编译和测试覆盖导入/类型检查，包含 Runtime IR、GC、Target、CPU/OS adapter 与 Lower/Pipeline。负向 fixture、包私有 audit 按专门 builder 组织运行，不将它们错误地当作独立普通应用。

| 原生 package | Passed | Failed | Exit |
|---|---:|---:|---:|
| bunko-kiso-aot-arm64 | 7 | 0 | 0 |
| bunko-kiso-aot-lower | 9 | 0 | 0 |
| bunko-kiso-aot-macho | 3 | 0 | 0 |
| bunko-kiso-runtime-cpu-aarch64 | 4 | 0 | 0 |
| bunko-kiso-runtime-gc | 5 | 0 | 0 |
| bunko-kiso-runtime-os-darwin | 2 | 0 | 0 |
| bunko-kiso-runtime-target | 1 | 0 | 0 |
| selfhost-lsp-rpc | 36 | 0 | 0 |
| selfhost-pipeline | 1 | 0 | 0 |

原生实际执行还包括：线程/TLS/Atomic/park-wake/join 见证；1000 保活轮次、1002 Minor、4 Major、131088 LOS 回收字节的托管图；普通程序 check/build/native execute；真实 Concurrent Mark/SATB/Minor/LOS 普通 mutator 见证；E5 v2.1.1 same-Epoch 生命周期、真实 Join、8 次 owned Minor/Sweep 握手、fatal abort 和 oracle 负向回归。它们是定向证据，不能替代完整 E3/E4/E5/E6 或新固定点。

| 实际命令标签 | Exit | Expected | Timeout |
|---|---:|---:|---|
| `compiler-signature` | 0 | 0 | False |
| `test-bunko-kiso-runtime-target` | 0 | 0 | False |
| `test-bunko-kiso-runtime-cpu-aarch64` | 0 | 0 | False |
| `test-bunko-kiso-runtime-os-darwin` | 0 | 0 | False |
| `test-bunko-kiso-runtime-gc` | 0 | 0 | False |
| `test-bunko-kiso-aot-arm64` | 0 | 0 | False |
| `test-bunko-kiso-aot-macho` | 0 | 0 | False |
| `test-bunko-kiso-aot-lower` | 0 | 0 | False |
| `test-selfhost-pipeline` | 0 | 0 | False |
| `test-selfhost-lsp-rpc` | 0 | 0 | False |
| `thread-smoke-build` | 0 | 0 | False |
| `thread-smoke-generate` | 0 | 0 | False |
| `thread-smoke-signature` | 0 | 0 | False |
| `thread-smoke-execute` | 0 | 0 | False |
| `managed-roots-build` | 0 | 0 | False |
| `managed-roots-generate` | 0 | 0 | False |
| `managed-roots-signature` | 0 | 0 | False |
| `managed-roots-execute` | 0 | 0 | False |
| `ordinary-check` | 0 | 0 | False |
| `ordinary-build` | 0 | 0 | False |
| `ordinary-execute` | 0 | 0 | False |
| `mark-build` | 0 | 0 | False |
| `mark-generate` | 0 | 0 | False |
| `mark-signature` | 0 | 0 | False |
| `mark-execute` | 0 | 0 | False |
| `sweep-lifecycle-directed` | 0 | 0 | False |

完整 argv/cwd/wall/stdout/stderr/hash 见 [validation/commands.json](/Volumes/Sector0/AppData/Mio/m19e-integration-20261103-01/validation/commands.json)、[directed/commands.json](/Volumes/Sector0/AppData/Mio/m19e-integration-20261103-01/directed/commands.json)；E5 内部每个原生进程见 [/Volumes/Sector0/AppData/Mio/m19e-integration-20261103-01/integration/build/m19ef-evidence/integration-E5-directed/commands.json](/Volumes/Sector0/AppData/Mio/m19e-integration-20261103-01/integration/build/m19ef-evidence/integration-E5-directed/commands.json)。同步后在主项目执行 `git diff --check`、普通程序 check/build、codesign 与 native execute；其实际退出码见 [post-sync/commands.json](/Volumes/Sector0/AppData/Mio/m19e-integration-20261103-01/post-sync/commands.json)，最终状态见 [post-sync/summary.json](/Volumes/Sector0/AppData/Mio/m19e-integration-20261103-01/post-sync/summary.json)。

## 状态和从主项目继续 E6

原 E6-accept-20261103-02 因本次用户集成请求在 snapshot 编译阶段受控中断，真实 -15/exit1 和 USER_INTEGRATION_HANDOFF.json 原样保留；不是新 Runtime 失败，也不是 PASS。已完成 E4 与 SATB-negative 原证据保留为历史。

当前 E6 IN_PROGRESS、M19e NOT_ACCEPTED、M19f NOT_RUN；本次不冻结为 Release Ready。新增主项目入口按全新输出目录执行完整 E3，然后完整 E6/E4/E5 fixed32/owned snapshots/seeded stress/pressure/native suites/CLI-LSP 与 NEW ABCD，禁止旧源码 PASS 替代。

```sh
cd /Volumes/Sector0/AppData/Mio/mio
python3 tests/m19ef/e6/resume.py \
  --out build/m19ef-evidence/E6-main-integration-20261103-01 \
  --compiler /Users/hatsunemiku/.codex/worktrees/m19ef-portable-gc/mio/build/m19ef-evidence/E6-LSP-policy-repair-20261103-01/mio-current \
  --compiler-sha256 0225cb1296f08af147e491ae1f5f17e31d2ed79b3ad0208737f86cb039c3bad8
```

以上为本轮同步后实际使用的唯一全新输出入口；目录已存在或仍运行时不要重复启动。实时状态见该目录 active-process.json、commands.json 及子目录 stdout/stderr。失败候选保留，修复后用新目录和新快照复验；修改编译器/Runtime 后必须重新验证新源码固定点。只有 E6 全部门禁真实通过后才依用户授权进入 M19f。

## 同步后续接入口修复

首次启动退出 1：主项目尚无 build/m19ef-evidence 父目录，尚未启动任何 native 子进程。已将 resume.py 输出创建改为 mkdir(parents=True)，仍拒绝已有输出目录。生产源码未变化；失败和补丁 SHA 见 [continuation-first-launch.json](/Volumes/Sector0/AppData/Mio/m19e-integration-20261103-01/continuation-first-launch.json)。同步快照原始 Manifest 不重写；修复后主项目最终 Manifest 与 SHA 见 [main-final-source-manifest.json](/Volumes/Sector0/AppData/Mio/m19e-integration-20261103-01/main-final-source-manifest.json) 和 [main-final-state.json](/Volumes/Sector0/AppData/Mio/m19e-integration-20261103-01/main-final-state.json)。
