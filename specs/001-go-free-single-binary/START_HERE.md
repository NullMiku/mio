> 最高优先级修订（用户 2026-10-26）：遵守 [PURE_MIO_ARCHITECTURE.md](PURE_MIO_ARCHITECTURE.md)。正式组件、构建、自举、发行链必须全部由 Mio Native 实现；其他语言仅限隔离参考审计。未经授权禁止 Commit、Push、Tag、Release。旧条款冲突时以此修订为准。

# Mio Go-free Single Binary — GF1～GF5 自动实施包

**版本：** Spec v0.2 / Autonomous Execution Edition  
**范围：** macOS ARM64，Mio-2 开发线，GF1、GF2、GF3、GF4、GF5  
**状态：** GF0 有审计 PASS 证据；GF1～GF5 均待实际实现和验收。本包是规范，不是已实现成果。

## 使用方式

1. 将本包的 `specs/001-go-free-single-binary/` **合并**到 Mio 仓库同名目录。不要覆盖已有的 `gf0/` 审计源码、`gf0/AUDIT.md`、历史证据或用户修改；若同名文件在本地已被修改，先比较并备份其内容。
2. 在 Mio 仓库根目录打开 **Codex 的可执行工作会话**，向它发送 `CODEX_START.txt` 中的指令。
3. Codex 应先审计、冻结、创建**独立 GF 工作树**，然后按 GF1 → GF2 → GF3 → GF4 → GF5 连续实施。每个阶段验证结束后**自动进入下一阶段**，不要每一步都请求维护者确认。
4. 运行状态记录在独立工作树的 `specs/001-go-free-single-binary/status.json`；每个阶段的真实日志和证据放在专用 `build/gofree-evidence/`。上下文中断时从状态文件与实际证据恢复，不得仅依赖旧对话内容。
5. 唯一保留的人工批准边界是：**强制推送、重写远程 Git 历史、真正创建并推送发布 Tag、正式 GitHub Release、使用私钥/生产凭据、不可逆外部动作**。Codex 可以自动准备这些步骤和对应 CI，但不得替维护者执行。

## 目标产品

最终用户只需一个原生 `mio` 可执行文件：

```sh
mio version
mio help
mio check hello.mio
mio build hello.mio -o hello
mio run hello.mio -- arg1
mio test ./...
```

- `mio` 内含纯 Mio 原生前端、Mochi v14 内存中间表示处理、纯 Mio Native AOT、ARM64 Mach-O 生成和必要的 Bunko 资源。
- 正常编译和运行不调用 Go、Go VM、Go Runtime、独立 `mio-front`/`mio-aot`、Clang、LLVM 或外部链接器。程序执行时允许由 `mio run` 启动**刚构建的用户程序**，但不允许启动第二个编译器。
- 生成的程序内嵌所需原生 Runtime 与 GC，自身不依赖安装 Mio。
- 可信原生 Seed 允许存在；从 Seed 开始 `.mio` 源码多代自举和发行构建不依赖 Go。

## 必读文件（次序）

1. 仓库现有 `gf0/AUDIT.md`（如缺失，使用此包 `GF0_BASELINE.md`，并核对原始快照/证据）。
2. `AGENTS.md`、`autonomy.md`、`spec.md`。
3. `contracts.md`、`worktree.md`、`plan.md`、`tasks.md`、`acceptance.md`。
4. `phases/GF1.md` … `phases/GF5.md`。

## 重要现状

GF0 已确认源码版 `mio build` 默认生成 `.mochi`、`mio run` 使用 Go VM，纯 Mio 原生前端仅在固定 bootstrap 输入上成功；16 个差分用例为 11 PASS、4 BLOCKED、1 FAIL。GF1 必须先处理五处语义缺口，不能把 M18/M19 的 **Mochi → Native** 固定点当作完整 **`.mio` → Native** 的验收。M19b 历史 Full Race 仍 `NOT_ACCEPTED`，即使 GF1～GF5 全部通过也不可替它改成 PASS。

**本包不执行任何构建，不会自动运行 Codex，也不是保证 Codex 在单次受限会话中一定能够完成庞大的 GF1～GF5 工程。它定义了可恢复、可自驱和不可伪造验收的实施协议。**
