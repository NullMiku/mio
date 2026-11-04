# Mio 2.1：Quick / Full / Release 调度审计

日期：2026-11-04。全部修改位于 **Mio-2.1** 工作树，起始 HEAD `0fa9e04d49967eb653e77ccd2478fc8dd59c9c4e`，开始时工作树干净。未修改 Mio-2 或其他分支、远端设置、贡献者 PR；审计后用户授权本地全量提交，提交编号以 Git 历史为准，不推送、合并或发布。

## 一、修改前的完整审计

已检查 CONTRIBUTING.md、docs/testing.md、四份激活 Workflow、scripts/ci 全部驱动及所有模块的 test.sh/ci-module.json。当前路径与祖先目录均无 AGENTS.md；specs 内两份 AGENTS.md 不在本次修改范围。共发现 26 个模块。原入口为 run.sh → runner.py → 相邻 manifest/test.sh → common.sh → 模块测试、独立检查及逐模块报告。

| 原 Workflow | 触发 | 原测试范围与问题 |
| --- | --- | --- |
| ci-pr.yml | 所有 PR 的 opened/synchronize/reopened | hosted infrastructure 自检；Linux/macOS 都跑 all quick。无变更选择；纯文档及普通测试调整也占 macOS；quality 自检与 infrastructure 重复，macOS 再跑 Linux 已跑的 Go/VM 基线 |
| ci-full.yml | Mio-2.1 push、手动、周计划 | 两平台 all full；macOS 保留 selfhost 全集、ABCD、AOT/race、GC、旧 BCD/M17/M18。外层及资源组已使用 queue: max。手动任意 ref 可请求生产 Runner |
| release.yml | 手动、v2.0.0-dev tag push | 既有纯 Mio 生产沙箱：真实源码构建、固定点、测试、打包、安装及运行。不纳入普通 PR |
| release-candidate.yml | 手动 | 历史发布策略校验入口，引用当前分支缺失的 release_automation.py/test_release_automation.py；保留，不把它算成可用的发布验收 |

Quick 原本已经不包含完整 ABCD、自举全集或 release suite，不能为“加速”删除这些本来只属于 Full/Release 的检查。主要重复在每次完整 Quick、两平台的参考/质量检查、及预构建不需要的三个 Go 工具。原生 Seed 编译器原本就按单次运行构建一次，本次保留此正确行为。

原 macOS Quick 与 Full 使用同一个 `ci-resource-macos-arm64-shared` 资源组，串行保护合理。cancel-in-progress: false 默认仍可能替换 pending；本分支上次已补 queue: max，本次不移除。Quick 外层允许同 PR 新版本取消旧版本。Full 不得因新任务等待而取消。

原 PR 直接选用 `[self-hosted, macOS, ARM64, mio-native]`，与 Release 的持久化主机标签一致。Fork 审批、contents: read、checkout 不保留凭据都不能提供宿主隔离；这是必须处理的安全边界。

### 远端事实与实际计时

只读查询 repo、最近 15 个 run、前五个 run 的 jobs，以及分支保护。记录在 `build/ci-scheduling-validation/github-snapshot.json`。

- [旧 Quick 41813398201](https://github.com/mio-kobo/mio/actions/runs/41813398201)：Linux 10:19:30Z–10:21:06Z，约 96 秒；macOS 未分配 Runner，后因旧运行取消而 cancelled。
- [旧 Quick 41813714786](https://github.com/mio-kobo/mio/actions/runs/41813714786)：Linux 10:22:18Z–10:23:59Z，约 101 秒；macOS pending，没有执行证据。
- [Full 41811793218](https://github.com/mio-kobo/mio/actions/runs/41811793218)：macOS 自 10:05:06Z queued、runner_name 为空；查询期间 Linux 仍 in_progress。到 10:46Z 观察窗口，原生任务已等待约 41 分钟，没有原生运行时长。
- [Full 41814856989](https://github.com/mio-kobo/mio/actions/runs/41814856989)、[41815108934](https://github.com/mio-kobo/mio/actions/runs/41815108934) 位于外层 pending，尚无 job；不能描述为测试失败或通过。
- Quick 总耗时、Full 总耗时、原生执行耗时：**NOT_RUN / 尚无完整计时数据**。不从虚填的 queued started_at 推算原生耗时，不编造提升百分比。
- 当前仓库默认分支为 **Mio-2**。读取该分支 `.github/workflows/ci-full.yml` 得到 404；[GitHub schedule 规则](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)要求 Workflow 存在于默认分支。因此 Mio-2.1 中写 cron 和显式 checkout 并不足以让周计划自动生效。默认分支/工作流部署需要维护者另行决定；本次严格不修改 Mio-2。
- `/branches/Mio-2.1/protection` 返回 403 `Resource not accessible by integration`。远端 required checks、Runner group ACL、机器在线状态及仓库变量配置均未验证，标为 **NOT_RUN**。

已知 Core Resolver/Typechecker/Codegen 基线失败见先前 `ci-reliability-audit.md`。本任务没有再次运行这些完整语言回归，也没有将它们归咎于本次调度变更或放宽断言。

## 二、优化后的三级设计

| 等级 | Workflow / 触发 | 执行内容 |
| --- | --- | --- |
| Quick | ci-pr.yml；目标为 Mio-2.1 的 PR 创建、提交更新、重新打开 | hosted 生成计划并运行 quality；按计划运行原生模块及 Linux 参考基线；固定名称 gate 核验 job 和执行报告 |
| Full | ci-full.yml；Mio-2.1 push、手动、原每周 cron | hosted policy 拒绝非 Mio-2.1 的手动 ref；两平台仍执行 all full，不使用 PR 裁剪计划 |
| Release Validation | 原 release.yml；维护者手动、原 tag | 原生产沙箱、Seed/签名规则、真实构建与固定点、安装/运行及包依赖检查，原样保留。也保留现有 native-release release 模块接口 |

Full cron 仍为周日 19:19 UTC；实际 schedule 生效依赖上一节的默认分支部署。新增 hosted policy 不改变 Seed 或构建实现，只约束 Full 调度来源。Release 与历史 candidate 工作流内容逐字核对未变。

### Quick 的保守影响范围

调度策略位于 `scripts/ci/plan.py`，测试业务仍由模块入口负责：

1. 只有 README.md、CONTRIBUTING.md 或 docs/*.md 变化：运行 quality，包括 gofmt/vet、自检和发布隔离静态检查。语言模块为明确的 SKIP，文档 gate 成功不代表语言测试 PASS。
2. 只有普通 Bunko 包的现存 `*_test.mio` 改动，可夹带文档：运行 Core、受影响包、Linux Go/VM 基线及 quality。Core 的原生与独立检查均保留。owner 必须由相邻清单唯一确认。
3. 任意实现代码、selfhost/Core/ABI、GC/runtime、AOT、清单、Workflow、脚本、Go、未知路径、已删除测试、无法读取或不可靠的 diff：完整 Quick。即使普通库实现看似局部，也不使用不完整的依赖图推断来缩减。
4. 注册发现错误直接失败；缺少 Core/quality/go-reference 基线不能变成文档成功。新模块清单由 discover 自动加入完整 Quick，无需维护中央模块列表。

计划绑定 base/head/source SHA，并记录每个模块 NOT_RUN（已调度待执行）或 SKIP（范围/等级未选中）及原因。单次统一入口支持 `core,kiso/math` 这样的多模块选择；先验证全部 ID，保持原生优先顺序、逐模块报告、编译器复用和失败传播。委托只有在父模块也被选中时生效，不会因裁剪丢失 required independent。

### Full 的覆盖完整性

所有原 full suite 与 required_checks/suite_checks 保持不变：Core、Bunko、selfhost 全集、AOT/ARM64/Mach-O 独立 oracle、实际 GC 遥测、原生 A→B→C→D、Go 全量/VM 差分、macOS AOT/race、历史固定点全部保留。Linux 仍是适用的参考实现与辅助检查，不能冒充 Linux Mio Native 验收。native-release 仍仅在显式 release suite 调用。

Full 中某个关键编译器构建或原生层失败时，后续依赖层可为 NOT_RUN，总结果不会因此成功。这里保留原有测试；未在 Windows 执行这些层，不宣称 Full 已通过。

## 三、并发与 Runner 安全边界

| 位置 | 分组 | 策略 |
| --- | --- | --- |
| Quick 外层 | ci-quick-pr-PR_NUMBER | cancel-in-progress: true；不同 PR 的可取消组不同 |
| Quick macOS / Full macOS | ci-resource-macos-arm64-shared | cancel-in-progress: false，queue: max；共享串行保护 |
| Full 外层 | 原 ci-full-REF | cancel-in-progress: false，queue: max；不替换等待中的 Full |
| Full Linux | 原含 run_id 的资源组 | 独立 hosted 执行，不占 macOS 资源组 |
| Release | 原 native-candidate-REF | 未修改正式调度；其主机配置由维护者管理 |

[GitHub 官方并发文档](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)支持 queue: max，最多 100 个等待项，且不可与 cancel-in-progress: true 混用。扩展队列不解决离线 Runner，也不是无上限队列。未取消任何已有远端运行。

PR native 现在只指定 **mio-native-pr Runner group + mio-native-pr label**。部署前 `MIO_PR_RUNNER_READY` 默认未启用，作业不会进入生产队列；代码 PR 的 gate 必须为 NOT_RUN。所有 PR 原生代码都应在一次性隔离机器执行，而非仅对 fork 做条件判断后让其他 PR 使用生产机。

维护者必须在启用变量前完成并验证：

- 创建专用 Runner group，worker 每个 job 销毁并重建；不得挂载生产磁盘、工作目录、签名凭据、云凭据、生产 token 或跨 PR 可写缓存。不能只在持久化生产机上添加新 label。
- 只向隔离 worker 提供相同固定 GF4 摘要的只读测试 Seed 副本；哈希不匹配仍由 runner 拒绝，不能下载任意 PR 提供的 Seed。
- 限制生产 Runner group 的仓库/Workflow/ref 授权，使不可信 PR 修改 YAML 也不能访问生产组。YAML、审批或 readiness 变量本身无法证明宿主隔离；此项是仓库外的安全前提。
- 保留正常 fork Workflow 审批；审批不替代隔离。确认专用 worker 与必要开发工具可用后，再将仓库变量 `MIO_PR_RUNNER_READY=true`。

这些设置均 **NOT_RUN / 未完成**。没有设置默认分支、创建 Runner、访问生产凭据、改分支保护，或声称已部署安全环境。

## 四、结果与 Artifact 的可信链

保留检查名 `CI infrastructure`、`Quick / linux-amd64`、`Quick / macos-arm64`、**`Mio CI / required`**。维护者应将最后一个设为必需合并门槛；其他逐平台状态可用于诊断。当前规则是否如此配置未获权限确认。

gate 始终尝试运行，读取同 run/attempt 的计划和小型报告 artifact，要求：

- 被计划要求的 job 成功；其 skipped/cancelled/pending/未执行均不能成功。
- 必须存在该 commit、该平台、quick suite 的唯一 report.json；选定模块集合与计划完全一致，exit_code=0、总状态 PASS。
- 模块必须 PASS；仅允许已选父模块实际承担的既有递归委托 SKIP。缺少、过期、不同 SHA、漏模块或必需项跳过均为 NOT_RUN。

每个完整日志 artifact 和 report artifact 使用用途、run ID、attempt、platform 命名；路径也隔离。gate 只下载报告，不重复传输 compiler/tool 二进制。完整日志、逐 check stdout/stderr、build 证据仍单独保留。Full Artifact 名称也增加 run/attempt，ABCD 目录隔离不变。

PASS / FAIL / SKIP / NOT_RUN 的模块协议未改。Go 记录 reference/supplementary；原生模块仍必须由固定 Seed 构建当前源码编译器并执行 Mio 测试。没有 Native Seed 或 Runner，不能通过 hosted VM 成功补齐原生状态。

## 五、优化前后与资源成本

| 场景 / 优化 | 修改前 | 修改后 | 预期资源与覆盖影响 |
| --- | --- | --- | --- |
| 纯文档 PR | 两平台 all quick，占原生编译/库测试队列 | hosted quality；语言明确 SKIP | 不申请 macOS；不声称语言回归已测 |
| 普通 math 测试文件修改 | 完整 Quick | core + kiso/math；Linux Go/VM；quality | macOS 选中 2 个模块；完整 Quick 选中 19 个原生模块，其中 2 项原有递归委托。所有受影响测试与 Core 独立 oracle 保留 |
| Core/GC/AOT/实现或未知修改 | 完整 Quick | 完整 Quick | 不缩减原生覆盖 |
| Quick 参考/quality 重复 | macOS 与 Linux 都跑；基础设施又单跑自检 | hosted quality 一次，参考基线 Linux 一次 | 移除 macOS 上相同的辅助工作；跨平台 Go 全量差异仍由 Full 保留 |
| Quick 驱动预构建 Go 工具 | macOS/Linux 各构建 mio/mochi-aot/mochi-aot-audit | 当前配置仅 Linux 预构建 mio | 顶层驱动预构建命令由 6 次降为 1 次；不计 Go 测试内部自建工具，不是运行时间比例 |
| Native compiler | 每次运行构建一次 | 保持一次，多模块共同使用 | 不共享跨提交的测试结果或可执行产物 |
| Full 工具 | 每个参考组预建全部 | 按 reference_tools 懒构建，同次运行每个工具最多一次 | Linux go-reference 不再预建不使用的 AOT 工具；macOS 后续有需求时再构建，保留原默认三工具兼容新模块 |
| 大型自举 | 每次 Full；Quick 无 | 不变 | 保留 push/manual/weekly 的验收频率与固定点规则 |
| 汇总可信度 | 主要检查 job 结果 | 计划 + 精确报告核验 | 增加 hosted gate、少量报告上传/下载成本，以拒绝缺失或旧证据 |

没有新增跨 job/PR/提交缓存。setup-go 的依赖缓存仍关闭（仓库无 go.sum）；当前原生 Quick 不需要 Go 时不安装，但 hosted quality 需要 Go。Full 的两平台回归存在必要的 OS 差异，未为节省资源删除。

配置预算不等于实测耗时：Quick hosted infrastructure 15 分钟、reference 30 分钟、native 180 分钟、gate 5 分钟；Full 原测试 job 360 分钟，policy 5 分钟。无原生/Full 完成数据，不能给出总耗时或加速百分比。过去 push/PR 相同源码的重复验收有不同合并职责，不按 SHA 缓存一个 PASS 来跳过 Full。

## 六、本次实际验证

环境：Windows AMD64、Python 3.14.5、已有 Git Bash/Git、Go 1.22.2、actionlint 1.7.7；YAML 验证使用原 .cache/ci-python 中的 PyYAML，没有新增正式依赖。

可复现驱动：`python build/ci-scheduling-validation/validate.py`。完整 argv、退出码、日志及计划示例保存在同目录的 validation.json、*.stdout.log、*.stderr.log、plan-examples.json 与 results/。此目录是忽略的本地开发证据；本报告与源码可提交，二进制/缓存不纳入源码。

按用户隐私要求，本地审计记录中的个人目录和带地区偏移的本地时间已脱敏。脱敏不修改命令退出码、测试结果或源码内容；原始机器路径不作为可分享报告的一部分。

| 实际执行 | 结果 |
| --- | --- |
| bash scripts/ci/selftest.sh | PASS：47 项，0 SKIP；保留旧负向检查，新增范围回退、自动注册、多模块失败、工具复用、job/证据缺失/过期等检查 |
| actionlint 四份 Workflow，原始调用 | 未通过兼容性验证：退出 1，仅三个 concurrency.queue 未识别；**不标 PASS**。没有忽略未知标签，已提供明确自托管 label 配置 |
| actionlint -ignore 'unexpected key "queue" for "concurrency" section' 四份 Workflow | PASS；只兼容该已受 GitHub 支持的新字段，未屏蔽其他语法或表达式错误 |
| PyYAML BaseLoader 解析全部四份 YAML，并逐个检查 concurrency.queue 枚举、cancel 冲突、PR group、Full 触发/保护、Artifact 唯一性 | PASS；为旧 lint 不支持的新字段独立补充结构验证 |
| hosted Full policy 的真实 Bash 测试 | Mio-2.1 手动返回 0；其他 ref 手动返回 NOT_RUN/2；schedule + 默认分支上下文可进入显式 Mio-2.1 checkout |
| python scripts/ci/runner.py inventory 与 Quick 计划示例 | PASS（静态）：26 模块；docs/test-only/GC/unknown 范围符合上表；Full 所需 Core/AOT/GC/selfhost/bootstrap/历史与参考模块均保留 |
| python scripts/ci/plan.py plan --base HEAD~1 --output ...；不存在 base 的回退用例 | PASS（调度协议）；错误 diff 回退完整 Quick，不变成文档成功。语言状态仍 NOT_RUN |
| python scripts/ci/plan.py gate：必需 native skipped、缺 plan | 正确返回 NOT_RUN/2；成功 job 缺报告/错 SHA/漏模块的负向自检同样拒绝 |
| 故意 assert False 的 Bash/Python 检查，经统一 negative,positive 多模块入口 | 真实失败退出 1；第二模块仍 PASS，最终 report FAIL。仅注入宿主/模块发现用于协议夹具，不冒充 Linux 或 Mio 原生验证 |
| bash -n CI/module 脚本；Python AST | PASS：30 个 Shell 脚本与 scripts/ci/*.py |
| bash scripts/ci/quality.sh | PASS：临时副本 gofmt、go vet ./...、git diff --check；未改语言源码或 golden |
| python scripts/ci/release_isolation.py | PASS（静态）；不等于真实发布构建 |
| release.yml / release-candidate.yml 与 HEAD 内容比较 | PASS：未变 |
| Windows 请求 run.sh macos-arm64 core,kiso/math quick | 正确 NOT_RUN/2；没有运行原生测试 |

**NOT_RUN**：真实 macOS Quick/Full、GF4 构建与签名、Mio 负向断言、Linux 真机 Quick/Full、当前 Core 全量回归、ABCD、真实 GC/AOT/ABI、Release 构建/安装/包审计、新 Workflow 远端调度/Artifact 往返、Runner/ACL/变量/分支保护部署。既有 Core 基线不改为 PASS，也不认定为本次新增回归。

## 七、改动文件与管理员后续

本次源码/文档变更：

- `.github/workflows/ci-pr.yml`：Quick 计划、分工、专用 PR group、按计划与报告验收。
- `.github/workflows/ci-full.yml`：可信 ref policy、Artifact 名称隔离；保留全量范围与 queue。
- `.github/actionlint.yaml`：声明实际使用的自托管标签，没有全局忽略检查。
- `scripts/ci/plan.py`：保守选择与 gate 证据校验。
- `scripts/ci/runner.py`：多模块选择、选定集合记录、工具按需构建/复用。
- `scripts/ci/selftest.py`：新增回归与负向用例，保留旧测试。
- `internal/ci-module.json`：声明 Go/VM 辅助验证只需预构建 mio。
- `CONTRIBUTING.md`、`docs/testing.md`、本报告及 `.gitignore` 文档白名单。

管理员后续：首先部署并验证隔离 PR Runner、安全 ACL 与 Seed 副本，再启用 readiness 变量；配置 `Mio CI / required` 为 Mio-2.1 合并门槛；处理默认分支缺少 Full Workflow 导致的 schedule/手动入口部署问题；检查已有 Runner 在线状态、队列与权限；在真机运行 Quick/Full 和既有 Release 验证并检查原生/独立/参考三种证据。发布策略缺失脚本属于独立既存问题，本次按限制保留。

所有设置与默认分支变更只作报告，不在本任务执行。工作仅在 Mio-2.1，未修改 Core/GC/正式 AOT/Object ABI/Runtime IR/自举架构，未新增正式运行时依赖。

## 后续变更：GitHub-hosted macOS 与 Native Verification 暂缓

本文第三节关于 `mio-native-pr` Runner group、`MIO_PR_RUNNER_READY` 和共享 macOS 资源组的描述已被取代：Quick/Full 的 macOS 作业改用 GitHub-hosted `macos-15`，并因 Native Seed 不可用而暂缓 Native Verification（NOT_RUN）。当前行为、限制和重新启用条件见 [测试架构](testing.md) 的“暂行措施”。Release 工作流未变。
