# `team-recover` v0.1 有界恢复实录

## 结论

`team-recover` v0.1 已将 OutputGuard 恢复链的核心约束做成可执行工具：
保留旧结果，冻结 exact candidate，复用经验证 proof，只声明一个新
事实，并绑定允许命令、路径和命令数预算。

当前成熟度为 `incubating`。输出的 plan/brief 都是非 live；不创建
successor task，不执行恢复命令，不修改 predecessor 状态。

## Candidate 两种模式

- `commit`：只接受 ordinary-clean、从 lane base 派生、有实际变更的
  commit；绑定 commit、tree 和 changed files。
- `dirty`：对未提交但属于 lane ownership 的文件，生成 tracked
  binary patch 和固定 timestamp/permission/order 的 ZIP snapshot。越权路径
  在写入 patch/snapshot 前就停止。

`prepare` 只接受 failed/blocked/changes-requested/preparation-failed/
preflight-failed predecessor，校验所有 proof 属于同一 manifest，并生成新
successor run ID。`project` 在生成 brief 前重验 predecessor、candidate 和
proof bytes，防止 plan 之后替换证据。

## 回归证据

实现 commit `32927d0983df5fe74909cce56feb939f90681097` / tree
`ee2b0e93972f3abc7378a77644afa1f6d6995896`。`tests/test_team_recover.py`
结果为 `10 passed, 0 failed`，覆盖 dirty/commit candidate、所有权、无半成品、
blocked predecessor、wrong-manifest proof、budget/authorization、不覆盖和计划后
candidate 篡改。三份生成产物通过 Draft 2020-12 schema 校验。

## 尚未证明

- 没有真实 successor Codex task 或恢复命令执行；
- dirty snapshot 只冻结当前存在的普通文件，对 symlink、submodule、LFS、
  超大文件和复杂 rename 的政策仍需扩展；
- “一个新事实”当前只有结构约束，其实质性仍需人工审查。
