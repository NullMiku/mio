# Worktree、来源冻结、恢复与整合协议

## 1. 已知仓库与位置（需在启动时重新核验）

```text
源仓库            /Volumes/Sector0/AppData/Mio/mio
GF0 外部证据       /Volumes/Sector0/AppData/Mio/mio-gf0-audit-20261026-01
推荐新工作树       /Volumes/Sector0/AppData/Mio/mio-wt-gofree
推荐本地分支       EXP/go-free-single-binary
其他工作树         mio-wt-m19-race / mio-wt-m19d
```

GF0 记录的 HEAD `a96d83ca0ee30239026b9ba27d5a5d547349f647` 和源码 Manifest SHA256 只能作为**历史身份**。当前启动时应再次读取工作树真实状态。

## 2. 执行前只读审计

在源仓库读取 `git status --porcelain=v1 -z`、`git rev-parse HEAD`、`git branch --show-current`、`git worktree list --porcelain`，枚举 staged、unstaged、untracked（含必要被忽略源码）以及符号链接和文件权限。识别本 Spec 包、`gf0/`、M19 证据。禁止仅凭 `git diff` 忽略 untracked 文件。

从 GF0 外部 `source-manifest.json` 建立基准与当前清单的差异报告；不要把历史证据中 6162 个文件完整复制到新源码树，它们是**不可修改的历史证据**，可通过路径与哈希读取。

## 3. 冻结与创建专用 Worktree

- 优先使用本地 Git `worktree add` 创建全新未占用路径/分支；若已有目标则停下做身份校验，绝不覆盖。
- `worktree add` 会更新共享 `.git` 的 worktree 注册元数据，**不会**改变源工作树内容。禁止 Reset、Clean、Stash。
- 在 worktree 初始化后，以受审计的安全复制方式导入源树**已暂存、未暂存、未跟踪**必要源码和已删除文件状态；不得复制 `.git` 文件夹或凭据。
- 对源树与新树相关源码生成独立 SHA256 Manifest，验证对应快照一致。Manifest 要处理换行、NUL 路径、软链接目标和文件模式；导入过程要做拒绝路径穿越校验。
- 将新开发输出放在独立 worktree 的 `build/gofree-evidence/` 或工作树外安全目录。旧 M18/M19、GF0 原证据全部只读。
- 若 GF0 快照落后于现在已接受的 M19c 新版本，先以实际当前可信源码和清单为基线，再由 Codex 核对差异；不得默默回退 M19 GC。

## 4. 开发隔离与检查点

GF1～GF5 只修改 `mio-wt-gofree`。其分支和工作树独立。保存每次自举/修复前后的源码清单及 Patch，不从其他实验 worktree 盲目 cherry-pick。

可以采用本地、可复核的阶段检查点文件和 patch 存档。默认**不自动提交原仓库、不推送远端**；若为安全恢复确需在隔离 worktree 本地建立 Commit，先以本 Spec 的禁止远端规则和实际 Codex 权限为准，并记录每个 Commit SHA，不得触碰用户原分支。

阶段性结果通过 `status.json` 及日志恢复。Git SHA/Manifest 变化时重新审核哪些测试证据适用于最终源码，过时测试不能复用为当前 PASS。

## 5. 最终整合方式

- 输出 GF 独立基线到最终实现的 patch/diff、文件清单及冲突风险。
- 合并到正式 `Mio-2` 前先审查 GF 与 M19 Race/M19d 分支的共享接口；未经人工远端授权，不推送也不自动合并原工作树。
- 若允许本地自动整合，仍必须在新的**隔离 integration worktree** 进行，而不是修改源仓库；执行全量回归并区分 GF 和 M19 各自验收。
- 不允许以 GF 原生测试成功覆盖历史 M19b Full Race `NOT_ACCEPTED`；历史状态更改需相应实际结果和项目验收决策。

## 6. 运行资源与沙箱

- 不在其他 M19 worktree 的重型 Race、自举、性能基准运行时，同时启动竞争 CPU/内存的 GF 重型验收。可先编写/运行轻量测试、进行静态审计。
- 不能使用 `pkill` 或向不相关 PID 发送信号来释放资源；仅能终止自己启动的测试进程组，并保留失败日志。
- GF4/5 Go-free sandbox 要**阻止或记录**所有子进程执行，包括直接绝对路径调用；PATH 为空只是辅助证据。GF3 的 `mio run` 启动用户生成的可执行文件是允许行为。
- 在 macOS ARM64 中必须区别 ad-hoc codesign 与 Developer ID/notarization，不将严格签名验证等同于正式分发公证。
