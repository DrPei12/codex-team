# `team-status` v0.1 只读派生层实录

## 结论

`team-status` v0.1 已交付一个可执行的只读状态派生层。它不调用 Codex
task/list/read/wait/message，也不读取或修改 live workspace；它只消费
canonical manifest、`team-run` 准备产物、worker-preflight receipts 和一份
不可变 `status-facts`，校验 identity/hash/事实一致性后生成新的
`status-snapshot` 与每 lane 下一动作。

当前成熟度为 `incubating`。它证明“持久事实 → 派生显示状态”可以用标准库
helper 确定性实现；没有证明真实 Codex Desktop observation、消息可靠性、长期
轮询、自动重派或 live 状态准确率。

## 两个命令

```text
python scripts/team-status.py init-facts MANIFEST --run-dir RUN_DIR --out FACTS
python scripts/team-status.py render MANIFEST --run-dir RUN_DIR --facts FACTS --out SNAPSHOT
```

`init-facts` 从已准备 run 生成一个“尚未创建 task”的事实快照。未来获授权的
Codex-native observation adapter 只能创建更新的 facts 文件，不能把显示状态
写回旧 facts。

`render` 验证 manifest、preregistration、parent receipt、dispatch bundle、
Prompt/Brief hash、worker receipt、task binding、report/evidence hash、acceptance、
integration、review、blocker、archive 和 workspace observation，再派生状态。

## 状态规则

高风险事实优先于乐观活动信号。主要 lane 状态包括：

- `preparation-failed` / `preflight-failed` / `blocked` / `changes-requested`；
- `needs-input` / `needs-evidence` / `no-signal`；
- `preflight` / `working`；
- `handoff-ready` / `accepted` / `integrating` / `integrated` /
  `review-pending` / `reviewed`；
- `waiting-dependency` / `ready-for-dispatch` / `planned` / `archived`。

依赖是否满足只看持久事实 `acceptance_state=accepted`，不看显示状态。
因此未验收任务即使被归档，也不会错误解锁 Integrator；已验收任务后来归档，
依赖仍保持满足。

Worker 完成边界若 `ordinary_status` 非空，不能显示 `handoff-ready`。report 与
evidence 必须位于当前 run directory 并通过 SHA-256，另一次 run 的文件不能
满足本次 handoff。

## AO、CCPM 与本项目的映射

- Agent Orchestrator 的核心原则被实现为“facts 永久、display snapshot 可重建”；
- CCPM 的依赖解锁思想落到 manifest DAG，但是否 ready 只由已验收前驱决定；
- Gas Town 的 integration/review/recovery facts 只作为输入枚举，本 skill 不
  执行 merge、retry 或重派；
- Parallel Code/Conductor 的卡片语义由 snapshot 中 lane status/reason/
  next_action 提供数据基础，当前没有 UI。

## 回归结果

实现 commit `08892eb628aeaaeb473d5d9f14af44fdf2083e43` / tree
`5de613b4a7f4bb2ae47dc1ec5c8fea832beb2266`。

`tests/test_team_status.py` 复用 `team-run` 的临时真实 Git repository 与三个
worktree fixture，最终 `18 passed, 0 failed`，覆盖：

- 初始 Core/CLI ready、Integrator/Reviewer waiting dependency；
- parent preparation failure；
- task 已绑定但缺 worker receipt；
- active + passed receipt、failed receipt；
- completed 缺 evidence、valid handoff、handoff dirty；
- report/evidence 跨 run 污染；
- accepted 后 archive 仍解锁、未 accepted archive 不解锁；
- review changes 与 archive 优先级；
- manifest/facts/dispatch identity 篡改；
- 矛盾 integration facts；
- facts 路径逃逸和 snapshot 不覆盖。

初始与 handoff 两组四份 `status-facts/status-snapshot` 通过当前环境 Draft
2020-12 schema 校验。`team-run` 11 项和 `team-plan` 19 项旧回归保持通过。

## 尚未证明

- 没有调用 Codex list/read/wait，也没有真实 thread/project ID；
- 没有实现 live facts collector、消息发送、重派、handoff、archive 或 merge；
- 没有验证 task 状态与 Git/report 事实的长期时序、重复/延迟消息或 cursor；
- repo-local helper 路径、安装后共享资源、Windows junction/submodule/LFS 仍未知；
- 没有独立 fresh Reviewer、第二 blind benchmark 或公平 skill 边际效用。

## 下一步

先审查并接收 stacked branch。随后实现独立的 Codex-native observation adapter：
它只读取 list/read/wait 与 Git/artifact，写新的 `status-facts`；仍不发送消息。
完成该只读 adapter 后，再由用户单独授权两条真正独立 lane 的 live pilot。
