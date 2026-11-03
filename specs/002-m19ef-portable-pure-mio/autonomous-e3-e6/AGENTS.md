# Local directives — E3～E6 autonomous work

- 阅读本目录 `CODEX_START.txt`，再阅读上级 002 规范。此目录是补充规约，不允许覆盖上级的安全约束。
- 保持所有 E3/E4/E5/E6 状态证据真实；默认 E3 IN_PROGRESS、E4/E5/E6 NOT_ACCEPTED。测试专用手工 Root 无法证明 E3 普通程序自动接入。
- GC core target-neutral；正式编译/Runtime/GC 纯 Mio；平台实现隔离；无 Go/C/Python 生产阶段。
- 当前 worktree 之外不可写；不 commit/push/tag/release/reset/clean/stash；保存所有源码、未提交改动与历史证据。
- 一个阶段通过才连续推进下一阶段；所有并发安全与新原生 fixed point 必须是真实运行验证，不得伪报。
