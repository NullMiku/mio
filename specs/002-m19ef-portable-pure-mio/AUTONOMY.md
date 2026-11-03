# 七、Codex 自动实施工作方式

本规范授权 Codex 对隔离的 M19ef Worktree 自主审计、修改纯 Mio 源码、执行非破坏性测试、修复失败、生成本地验证产物并在 E0–E6、F0–F4 间连续推进。

## 安全与工作树

1. **先调查再行动**：`git status --porcelain=v1`, `git rev-parse HEAD`, `git worktree list --porcelain`, `git branch --show-current`；确认 `Mio-2.1` 最新 HEAD。用户已有更高优先级更改应冻结/记录，不准覆盖。当前参考分支 HEAD 见 README，实际以远端/本地核实为准。
2. 禁止动 `Mio-2`、GF5 冻结编译器 worktree、M19d/Race 其他 worktree。若需独立 worktree，先安全创建新的 `EXP/m19ef-portable-gc`，确保目标路径不存在，不使用 `reset --hard` / `clean` / `stash` 来清理用户状态。
3. 不在未经审查的情况下把 Git Worktree 的 HEAD 视为包含另一个工作树的未提交源码。已有未提交 M19d/E 补丁需要逐项审计才可选择合入。
4. 禁止 Commit、Push、Tag、Release、force push、重写历史；也不要修改 GitHub 默认分支、保护/CI 配置或删除证据。
5. 在隔离 Worktree 可修改相应 `.mio` 源码、必要 `.mio` 测试和该 Spec 下的报告；不要新增 Go/C/Rust 编译器生产依赖。Python/shell 仅允许作为不会进入生产构建链的审计/测试工具，且优先用纯 Mio native 运行器。

## 严格自主执行顺序

- E0→E1→E2→E3→E4→E5→E6→M19e PASS，然后 F0→F1→F2→F3→F4→M19f PASS。
- 若早期任务可以低风险平行研究，只允许并行阅读、轻量测试；不要与 GF5/M19 的重型完整自举争抢 CPU，不要并行多个重型跑批。
- 每一步必须实际落地源码和测试、确认最新 source snapshot，不能只在报告里写『已设计』。
- 失败时自动缩小最小复现、锁定 target semantics/CPU/OS/GC core 中对应层、修复并在同一最终源码重跑受影响 Gate；不能假装成功。
- 需要重大平台能力（例如 Darwin 线程桥 ABI）时，先设计和实机原型，再融合到 GC；不能用单线程假并发替代。
- 每轮将状态与证据写到独立 `build/m19ef-evidence/<phase>-<unique-run-id>/` 或安全目录（需新路径），附 Manifest/hash/命令/退出码。失败和旧候选均保留。
- `status.json` 只能按事实更新；可为每阶段记录 PASS / IN_PROGRESS / BLOCKED / NOT_RUN；不可预填 PASS。
- 稳定运行环境可自行连续推进，不需在每一阶段向用户请求确认。遇到权限、硬件、时间或必需资源不可用时，停在可复现 BLOCKED 状态，给出已完成成果与准确原因，不能保证异步后续完成。

## 最终交付

- 一套真实纯 Mio 源码改动，portable GC core 与 Darwin ARM64 backend 分离。
- M19e、M19f 的源码/证据/测试/性能报告与最终状态。
- 未来 Linux ARM64 / Linux AMD64 / Windows AMD64 backend 的可执行接口和缺口清单，而不是伪装已适配。
- 固定点可复现 Native 自举证据，不把历史 GF4/GF5 PASS 自动当作新源码 PASS。
