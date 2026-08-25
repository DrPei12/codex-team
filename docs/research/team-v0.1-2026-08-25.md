# Codex Team v0.1 离线完整工作流验收

## 结论

Team v0.1 的 repo-local、Codex-only、artifact-driven 第一版已实现：

`team-plan -> team-run -> team-status -> team-integrate -> team-finish`

任一阶段出现可定位的 failed/blocked 事实时，由 `team-recover` 冻结旧
结果并准备一个有界 successor。统一 `$team` 入口只读 canonical run
artifact，选择下一个 phase skill，不取代各 phase 的身份、hash、所有权
和前置条件校验。

这里的“完整”仅指离线 workflow 代码和产物协议闭环。它不表示已经用
这些 skill 创建真实 Codex 多任务、发送 prompt/message、wait/handoff/archive，
也不表示已证明比单任务更快或更便宜。

## 统一路由的职责

`scripts/team.py route` 只读 canonical 文件名，生成 `team-route`，其中包含：

- 当前 state；
- `next_skill` 与 `next_action`；
- 支持该判断的文件 SHA-256；
- 该动作是否仍需单独授权；
- 恒为 false 的 task/Git/command/cleanup 授权字段。

路由器不从多个同类历史文件猜测“最新真相”。需要自动路由时，已接收
产物必须提升为 reference 中声明的 canonical 文件名；其他文件仍可作为历史
evidence 保留。

## 验收证据

代码基线为 branch `codex/team-v01` commit
`e497188d27b5531aeb553d852d0a80a546e3bbdd` / tree
`9930abfce6d637167f8dc907df1cd9d58ace94f0`。`main` 当时仍为
`db3b81001b970d0b0be00cd41eb75c805dfde629`，本轮没有合并 main。

八组标准库回归全部通过，共 `90 passed, 0 failed`：

- team-plan 19；team-run 11；team-status 18；
- team-integrate 12；team-finish 11；team-recover 10；
- team router 8；离线端到端主链 1。

端到端用例在临时 Git repository/worktrees 中执行：准备 run、初始化 facts、
写入模拟任务事实与真实 commit、冻结候选、真实合并、显式授权离线
Gate、review、audit 和 finalize。16 份主链产物通过对应 Draft 2020-12
schema。7 个 skill 通过 skill validator，9 份 schema 通过元校验，3 份
capability contract 与 5 类原有 workflow artifact 继续通过。

## 成熟度和下一阶段

七个 skill 都保持 `incubating`。下一阶段不是继续增加离线字段，而是：

1. 验证 skill 安装后共享 helper/schema 的定位与隐式触发；
2. 实现只读 Codex-native observation adapter，把 list/read/wait + Git/artifact
   转成新 facts，不发消息；
3. 由用户单独授权一次最小 live pilot，再根据证据决定是否开启默认
   prompt dispatch、wait/handoff/archive；
4. 转向第二个未见 benchmark 做 no-skill/native single/native multi-task/
   skill-assisted 公平对照。
