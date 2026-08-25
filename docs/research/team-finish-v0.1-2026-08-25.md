# `team-finish` v0.1 非破坏性收尾实录

## 结论

`team-finish` v0.1 已实现“Gate target → 独立 review → final audit →
milestone result”。它将功能通过、审查通过、Git 现场无普通污染、
Git operation 无残留和 run artifact 可定位分开记录。

当前成熟度为 `incubating`。完成结果只列出归档候选和 workspace
建议；它不归档 Codex task，不删 worktree，不清理 ignored 文件。

## 关键语义

- review receipt 绑定通过的 Gate receipt bytes、target commit/tree、reviewer
  lane 和 findings hash；`changes-requested` / `rejected` 是有效事实，但不能收尾。
- audit 区分 ordinary status、ignored files、merge/rebase/cherry-pick/bisect
  residue 和 run inventory。ordinary 或 operation residue 阻断；ignored residue
  可被报告为 `completed-with-ignored-residue`。
- finalize 会重验 Gate/review/audit hash 和 target，并确认 audit 之后
  workspace 没有变化。

## 回归证据

实现 commit `95b8567ccaa4716cffe76b97c4b5ae64e30dc583` / tree
`94562bc309d053003908055d1b62bba32ca812e0`。`tests/test_team_finish.py`
结果为 `11 passed, 0 failed`，覆盖 Gate/review 绑定、findings 篡改、
ordinary/ignored/operation residue、非批准 review、audit 后 workspace 变化和
产物不覆盖。三份生成产物通过 Draft 2020-12 schema 校验。

## 尚未证明

- 没有调用真实 Codex archive/handoff 或验证 UI 任务生命周期；
- 没有执行清理，因此不能证明 worktree/cache 清理策略的安全性；
- sealed authorization 仍属项目/评测策略，不由 `team-finish` 自动触发。
