# Mio GF1～GF5 自动开发 Spec v0.2

这是可以直接交给 Codex 的多文件 Spec 包，**不是编译器二进制，也没有实际完成 GF1～GF5**。

## 在你的 Mac 上

1. 解压 ZIP 到任意目录。
2. 在该目录执行（或直接请 Codex 执行）：

```bash
python3 install_spec.py --repo /Volumes/Sector0/AppData/Mio/mio
```

- 安装器只覆盖 `specs/001-go-free-single-binary/` 中同名 Spec 文件，提前备份到仓库的 `build/gofree-spec-backup-<timestamp>/`；**不会删除或覆盖 `gf0/`**。
- 不会执行 Git Commit、Push、Tag、Release，也不会修改其他 Worktree。
- 想先看要变更什么，可以执行：

```bash
python3 install_spec.py --repo /Volumes/Sector0/AppData/Mio/mio --dry-run
```

3. 在 Mio 仓库根目录打开 Codex，发送 `specs/001-go-free-single-binary/CODEX_START.txt` 的全文。Codex 会使用项目已有 GF0 审计及本包连续实施 GF1～GF5。

**权限与能力边界：** 该 Spec 让 Codex 在已授权的隔离工作树内自行开发和测试，不要求每阶段都等人确认；远端强制推送、发布 Tag/GitHub Release、苹果签名凭据等不可逆/敏感动作仍保留给维护者。复杂工程可能因为真实实现缺口、机器资源或单次会话限制而无法一口气完成，因此必须保留状态和日志可恢复，不得假报全部 PASS。

## 文件说明

- `START_HERE.md`：导览。
- `AGENTS.md`、`autonomy.md`：不逐阶段追问的实施协议和安全边界。
- `GF0_BASELINE.md`：GF0 已知事实摘要。
- `spec.md`、`contracts.md`：最终产品与跨阶段 API/CLI 规则。
- `worktree.md`、`plan.md`、`tasks.md`：开发隔离、连续推进与待办。
- `acceptance.md`：A1～A12 和 GF1～GF5 独立验收。
- `phases/GF1.md` 至 `GF5.md`：各阶段实施细节。
- `status.json`：恢复/验收状态索引。
- `CODEX_START.txt`：只需复制一次的启动指令。
