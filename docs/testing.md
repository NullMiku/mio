# Mio Native Testing First：测试架构

**Mio's native testing framework is the primary testing mechanism. External tools and other programming languages are permitted for supplementary testing and independent cross-validation only.**

本分支为 `Mio-2.1`。普通模块、标准库、Core、AOT 和 GC 首先使用 Mio 原生测试；关键模块再运行具有独立判断能力的检查。Go 参考实现及 Python/Shell 仅用于补充测试、交叉验证和基础设施自检。框架不支持的类型应记录限制，不能因外部语言方便而替换 Mio 测试。

## 结构

```text
scripts/ci/
  run.sh / runner.py           发现模块、环境检查、日志与 JSON 汇总
  common.sh                   模块协议及 ci_native / ci_check
  selftest.sh / selftest.py    负向自检
  verify_native.py            独立原生输出、ABI、GC 遥测
  release_isolation.py        发布源码与包清单隔离检查
  test.sh                     quality 基础设施检查
  legacy/test.sh              保留历史 BCD/M18 检查
selfhost/cli/test.sh           core：Mio 测试 → 独立原生验证
selfhost/test.sh               selfhost：原生测试全集
selfhost/bootstrap/test.sh     Mio 测试 → 原生 ABCD 固定点及复核
bunko/kiso/aot/test.sh          AOT：Mio 测试 → 原生产物/ABI 检查
bunko/kiso/runtime/gc/test.sh   GC：Mio 测试 → 实际 GC 遥测
bunko/kiso/**/test.sh           各个已有 Mio 测试的标准库包
internal/test.sh               go-reference，补充参考实现
internal/aot/test.sh           go-aot-reference，补充后端/race 检查
tools/native-ci/test.sh        原生 archive 测试 → 既有生产流水线 → 独立清单检查
```

每个入口旁的 `ci-module.json` 是注册信息。调度自动发现 internal、bunko、selfhost、tools 和 scripts/ci 下的清单，无需修改中央模块列表。源码目录不迁移。Actions 负责调度、依赖安装和证据上传，测试业务由仓库脚本负责。

## 使用接口与平台

```bash
bash scripts/ci/selftest.sh
bash scripts/ci/run.sh macos-arm64 core quick
bash scripts/ci/run.sh macos-arm64 aot unit
bash scripts/ci/run.sh macos-arm64 gc quick
bash scripts/ci/run.sh macos-arm64 all quick
bash scripts/ci/run.sh macos-arm64 all full
bash bunko/kiso/math/test.sh macos-arm64 unit
bash scripts/ci/run.sh linux-amd64 go-reference quick
# 需要原有生产 Seed、冻结输入和可用的 macOS 沙箱：
bash scripts/ci/run.sh macos-arm64 native-release release
```

参数为 `<target> <module> <suite>`，`all` suite 等价于 `full`。模块单独调用为 `<target> [suite]`，默认 quick。脚本内部切换到仓库根目录。示例是已实现的接口；本次 Windows 环境未执行 macOS/Linux 流程，实际状态见 [审计记录](testing-audit.md)，不能把示例视为通过声明。

| target | 实际主机 | 能力 |
| --- | --- | --- |
| macos-arm64 | Darwin arm64 | Mio 原生框架、AOT、ABI、GC、自举及辅助检查 |
| linux-amd64 | Linux x86_64 | 现有 Go/VM 补充参考测试；无 Mio 原生后端验收 |

会核对真实 OS 和架构。Linux ARM64、macOS AMD64、Windows 尚未接入统一原生入口。交叉编译不等于原生执行。Windows 可以独立运行基础设施自检及部分 Go 补充测试。

开发驱动要求 Bash、Python 3.9+、Git；参考测试另需 Go（版本见 go.mod）。原生测试使用已有、由主机提供的 `MIO_NATIVE_SEED`，其 GF4 SHA256 必须为：

```text
4c3f7dcbea536d756c3c4a93c18a999412625184bd5c90123f1c16a0cd9e36da
```

该约定来自现有 `tests/m19ef/README.md`、ABCD 和生产流水线，不新增 Go Seed，也不下载不明原生产物。所有 Mio 原生测试显式传递当前 `--bunko-root`，避免读到 Seed 内嵌的历史库。缺少 Seed 或哈希不符返回 NOT_RUN/2，不降级到 Go 冒充原生。系统 `codesign` 只用于签名验证；真正的原生代码生成、链接、签名由现有 Mio 实现负责。

## 模块与等级

| ID | suites | 内容 |
| --- | --- | --- |
| core | quick, unit, full | `selfhost/pipeline` 原生 Mio 测试；独立编译/执行、9 参数内部 ABI、输出和错误断言检查 |
| aot | quick, unit, full | `bunko/kiso/aot/...` 原生测试；独立 Mach-O、签名和输出检查 |
| gc | quick, unit, full | `bunko/kiso/runtime/gc` 原生测试；独立 1 MiB 堆容器工作负载及 GC 遥测 |
| selfhost | unit, full | 原生 `selfhost/...` 全集 |
| bootstrap | bootstrap, full | 先原生 codegen 测试，再运行并独立复核现有 `tests/m19ef/bootstrap-abcd.sh` |
| native-release | release | 原生 archive 测试，复现正式生产沙箱和构建/安装检查，再独立审核真实包 |
| quality | quick, full | gofmt/vet/whitespace、负向自检、发布隔离静态检查 |
| go-reference | quick, unit, full | 补充 Go/VM 回归；full 保留完整 `go test ./...` 和 VM 回归 |
| go-aot-reference | unit, full, race | 原有 Go AOT 全集与 race；仅 macOS ARM64 |
| legacy-bootstrap | bootstrap, fixed-point | 原有 BCD/M17/M18 调用；当前分支引用的旧脚本缺失，保留失败以便定位基线问题 |
| kiso/* | quick, unit, full | 每个已有 `*_test.mio` 包的原生测试；实际清单见各模块注册文件 |

标准库已接入 aot/arm64、aot/lower、aot/lower/types、aot/macho、crypto/sha256、encoding/binary、encoding/json、encoding/mochi、io、math、net/tcp、path、regexp、runtime/cpu/aarch64、runtime/os/darwin、runtime/target，以及单列的 gc。`all` 调度时 AOT 子包通过 `covered_by` 委托父级递归检查，单独报告 SKIP 和委托原因；显式选择子模块仍运行自己的入口。

Quick 包含已有库测试和 Core/AOT/GC 的基本双重验证。Full 增加完整 selfhost、原生 ABCD 和历史 Go 全量补充测试。自举是顺序执行的，Go 包并行度为 1 或 2。Go 工具只在补充检查需要时构建一次；原生路径始终使用受信任 Mio Seed。PR 运行原生 Quick，push/手动/每周运行 Full。辅助历史 workflow 仍保留完整 Go、VM、AOT、race 和旧固定点检查，不使用 continue-on-error。

`native-release release` 是显式发布验证，因生产冻结输入和较高资源需求，不加入每个 PR。正式 `.github/workflows/release.yml` 保持不变。

## 两层验证与覆盖边界

每个关键模块的 `required_checks` 声明原生层和独立层；原生层使用 `kind=mio`，报告为 `layer=native`。独立层为单独命令，报告为 `layer=independent`。某层未执行时补记 NOT_RUN，不会自动继承另一层的 PASS。补充 Go 检查为 `layer=supplementary`。

Core/AOT 独立路径调用正式 Native Seed 编译 9 参数函数、数组和字符串；验证 ARM64 Mach-O 文件头和签名，再在空 PATH 环境执行，比较固定 stdout、空 stderr 和退出码。同时构造故意失败的 Mio 测试，并独立核查非零退出及 JSON failed 计数。重复调用 Mio 测试不算独立验证；这里的输出 oracle 不调用 testing.expect。

GC 独立路径复用现有 `automatic-roots/builder.mio`，由纯 Mio 生成受限堆程序。检查容器工作负载输出 `4797`，并解码 64 字节遥测：minor collections 必须大于 0，根发布、注册/退出和资源获取/释放必须满足已有协议。这是有实际回收的有限场景，不能代表长期、多 mutator、并发 old sweep 或所有内存策略均得到验证。

ABCD 继续使用现有、带冻结源和哈希/签名复核的脚本；不重写自举算法。旧 BCD/M18 脚本已在 Mio-2.1 缺失，不能默默删掉旧 gate 或用新的 ABCD 声称其通过。

尚无独立 Mio 测试的 array、bytes、convert、fs、string、testing、utf8、部分 nativefs/sign 辅助包通过原生库/集成路径间接覆盖；不创建空入口。selfhost 阶段全集有原生测试，但尚未逐阶段配置独立 oracle。外部 FFI/完整 ABI、长期 GC 压力、新平台后端仍未覆盖。原有 E5/E6 等脚本保留，其硬编码 Seed、固定 fixture、分支或恢复要求不被本次静默改写；未接入项应明确记录 NOT_RUN。

## 模块接口

新模块只需添加相邻的 `test.sh` 和 `ci-module.json`，并保证真的有测试：

```json
{"module":"kiso/example","targets":["macos-arm64"],"suites":["quick","full","unit"],"required_checks":["native"]}
```

脚本设置 CI_MODULE，source 公共脚本，定义 `ci_module(target,suite)`，末尾调用 `ci_main "$@"`。参考 `bunko/kiso/math/test.sh`。普通模块先调用 `ci_native native <package>`；关键模块再用 `ci_check command <independent-name> <argv...>` 调用独立 oracle。Go 只能用于明确的补充检查。禁止空脚本、`true` 占位或 `|| true` 掩盖失败。

公共层提供 MIO_CI_MIO（已验证 Native Seed）、MIO_CI_TOOLS（仅开发参考工具）、MIO_BUNKO、MIO_CI_MODULE_DIR。`ci_check go` 要求 Go JSON lines，`ci_check mio` 要求 Mio JSON，且均拒绝无测试/全跳过。不使用 eval 或 Shell 字符串拼接执行用户参数。

## 报告与排错

每次创建独立 `build/ci-results/<timestamp>-<id>/report.json`。schema_version=1，含 target、module、suite、status、duration_ms、checks、artifacts；模块 checks 内分别保存两层状态、command、exit_code、stdout/stderr 路径，Go 测试还保存逐测试状态。Mio stdout 保留原始完整 JSON。

| 状态 | 含义 |
| --- | --- |
| PASS | 定义的必需检查确实执行并通过 |
| FAIL | 执行失败或超时 |
| SKIP | 明确的平台/等级策略或委托跳过，附原因 |
| NOT_RUN | 环境/参数/协议问题、空测试或必需检查未执行 |

0 为所有选定必需检查通过；1 为测试失败；2 为环境、参数或基础设施错误。显式指定不支持的组合返回 2。`all` 可以包含明确策略 SKIP，但不能把它们合并为 PASS；某个必需检查 NOT_RUN 不得成功。Go 的条件跳过保留明细，部分通过不代表覆盖所有原生路径。

先查看 report.reason，再看 module.log 和独立 stdout/stderr。Python 捕获真实退出码，避免 tee 吞掉失败；POSIX 超时杀死整个进程组。默认单检查超时 2400 秒、模块 7200 秒，支持 MIO_CI_CHECK_TIMEOUT/MIO_CI_MODULE_TIMEOUT；MIO_CI_RESULTS 可更改报告父目录。PYTHON 可指定解释器。生产环境不需要这些变量。

CI 命令可以在相同平台/架构本地原样执行，不依赖 GitHub 环境变量。受信任 Seed 由和 release.yml 相同的 self-hosted macOS ARM64 Runner 提供；没有该 Runner 时不得宣称 hosted native CI 已运行。

## 外部工具隔离与发布验证

外部工具只能作为 Development / CI Dependencies；不得加入 Core/标准库正式实现、链接进编译器或运行时、成为发行版的运行依赖。依赖方向为测试工具调用 Mio，Mio 不反向调用测试工具。新增测试驱动不参与正式源码构建或自举，也不改变历史引导架构。

`python scripts/ci/release_isolation.py` 静态检查：正式工作流无新增外部依赖安装；保留空 PATH 和 production.sb；Core 导入图不引入测试目录；嵌入资源不含外部驱动；生产 bundle 仅包含 mio/LICENSE/README.txt。这个静态 PASS 不能替代实际发布构建。

`native-release release` 先执行原生 archive 测试，再在原有生产沙箱内运行纯 Mio 流水线（PATH 为空，不能执行 Python/Go/Shell），由现有 Seed 完成源码重建、固定点、原生测试、打包、安装、已安装编译器编译和应用运行。最后在沙箱外独立验证真实 tar.gz 只含允许的三个普通文件、无外部运行时标记。外部审计脚本不会进入包。若生产冻结 fixture 或 Seed 不齐，则如实失败/NOT_RUN，不能用伪造 tar 包声称 Release 通过。

## 负向自检

`bash scripts/ci/selftest.sh` 无需 Go/Seed。Windows 可直接 `python scripts/ci/selftest.py`，若 PATH 上无 Bash 则管道及真实模块调度标为 SKIP。覆盖错误断言、错误输出、异常退出、缺工具、错误参数/平台/组合、超时、空 Go/Mio 测试、全跳过、子失败聚合、框架假阳性、混入测试驱动的包，以及失败命令经过 tee。

真实端到端用例会调用 Bash 模块和检查器，核对成功/失败/空模块的 0/1/2、最终 JSON 和日志。聚合其他分支使用注入子进程结果验证协议。Core oracle 另使用真实 Mio 框架运行故意失败断言。这样证明故意错误会返回非零；本次没有提交、推送或触发远端 CI，不能宣称已观察 GitHub 状态变红。
