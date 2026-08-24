# `team-run` v0.1 准备层实录

## 结论

`team-run` v0.1 已交付一个可执行但非 live 的准备层。它消费通过
`team-plan` 校验的 canonical manifest 与机器投影 brief，在创建任何
Codex task 之前初始化 run-local runtime roots，生成 preregistration、
parent preflight receipt、分层 prompt 和 dispatch bundle，并提供必须由
未来真实 worker 在 assigned workspace 内执行的 preflight 命令。

当前成熟度为 `incubating`。它证明准备产物可以在临时真实 Git
worktree fixture 上 fail closed；没有证明 Codex Desktop task 创建、消息、
等待、handoff、真实实现、集成或长期状态管理。

## 冻结边界

用户选择的 v0.1 范围是“准备但不派发”。因此 skill 和 helper 均禁止：

- 创建、fork、message、handoff 或 archive Codex task；
- 创建 lane worktree；
- 修改目标产品代码或冻结 contract；
- 把 requested model/thinking 写成 effective；
- 覆盖或清理失败 run 的 evidence 目录。

`prepare` 通过后只输出 `ready_for_authorized_dispatch`。另一个已获得明确
授权的后续 orchestrator 才能消费该 bundle；“准备成功”不等于“Desktop
dispatch 已验证”。

## 产物与数据流

命令：

```text
python scripts/team-run.py prepare MANIFEST --briefs BRIEF_DIR --out RUN_DIR
python scripts/team-run.py worker-preflight MANIFEST --brief BRIEF --receipt RECEIPT
```

通过路径生成：

1. `preregistration.json`：绑定 manifest canonical digest、raw bytes hash、
   每份 brief hash、计划 lane、停止条件，以及四个明确为 false 的执行授权；
2. `runtime/cache|dist|logs|pytest/`：创建为空的 run-local 输出根目录；
3. `parent-preflight-receipt.json`：记录 task project 与每条 lane 的 Git
   root/common-dir、branch、HEAD、tree、ordinary status 和 ignored inventory；
4. `prompts/<lane>.prompt.md`：把可信 manifest/brief、workspace/preflight
   绑定与“不可信外部上下文”规则分层；
5. `dispatch-bundle.json`：引用 prompt/brief SHA-256、依赖、workspace 和
   requested/effective runtime，但不包含 thread/task ID；
6. `worker-receipts/`：未来真实 worker 的独占 receipt 目录。

输入 manifest 或 brief 错误发生在 output 创建前。Git/workspace preflight
失败则保留 preregistration 和 failed parent receipt，不生成 prompt 或
dispatch bundle。worker preflight 无论通过或失败都写独占 receipt，已有
receipt 永不覆盖。

## Prior art 组合如何进入本切片

- CCPM 的依赖、并行和冲突思想由现有 manifest 的 `depends_on`、
  `parallel_groups` 与 ownership validator 承担，没有新增第二套任务真相；
- Agent Orchestrator 的 Prompt 分层进入每条 lane prompt：项目规则、可信
  brief、runtime/preflight 绑定与不可信外部上下文分开；
- Gas Town 的 durable integration/recovery 状态机留给后续
  `team-integrate` / `team-recover`，本切片没有超前实现 daemon、lease 或
  batch merge；
- Parallel Code / Conductor 的“一任务一 workspace、集中显示事实”留给
  后续 `team-status` 投影；当前不启动外部 Agent CLI 或自建看板。

## 回归结果

最终代码身份：commit `c5ead87fd311d6223a9a10712fd6e1e3f357bd61` /
tree `8589357fe8eb75d265c20b9c6af4f7f82633702b`。

`tests/test_team_run.py` 使用标准库 runner，每个行为测试创建临时 Git
repository、task project 和 Core/CLI/Integrator 三个真实 worktree；Reviewer
复用 Integrator workspace。最终结果为 `11 passed, 0 failed`，覆盖：

- 正向准备及四类 schema artifact；
- brief 内容篡改和 symlink 逃逸；
- dirty workspace 阻塞和 ignored inventory 分层；
- global `require_clean_start` 覆盖 lane 自己的宽松设置；
- 已存在 run root 拒绝覆盖；
- worker 正确/错误 cwd；
- worker receipt 不覆盖。

旧 `team-plan` 回归仍为 `19 passed, 0 failed`；三份 capability contract、
五类原有 workflow artifact、两个 skill validator 和全部本地 JSON 解析均
通过。使用当前环境已有的 `jsonschema` 对一次生成的 preregistration、
parent receipt、dispatch bundle 和 worker receipt 做 Draft 2020-12 校验，
四份均通过。

## 尚未证明

- 没有创建真实 Codex Desktop task，也没有验证 thread/project/worktree 绑定；
- 没有运行 live prompt dispatch、消息、wait、handoff、archive 或恢复；
- repo-local 显式 helper 路径尚未证明安装后稳定；
- 未做 Windows junction、Git submodule/LFS、detached HEAD 或 Git operation
  residue 的完整矩阵；
- 没有独立 fresh Reviewer、第二 blind benchmark 或公平 no-skill 边际效用；
- 项目仓库尚无 LICENSE，当前只独立实现 prior-art 思想，未复制外部源码。

## 下一步

先对本 commit 做主编排者自审并同步项目状态。后续先实现 read-only
`team-status` 的“持久事实 → 派生状态”最小投影，再由用户单独授权一个两条
真正独立 lane 的 Desktop live pilot；不为了展示并发而固定四条任务。
