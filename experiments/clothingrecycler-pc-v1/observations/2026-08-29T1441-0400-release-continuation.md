# 正式发布续跑观察

## 用户授权与模型政策

- 用户要求继续到“全部验收完成、可以正式发布”，并允许并行改进 Team。
- 产品规划、分析、集成与验收继续请求 `gpt-5.6-sol/high`。
- 产品开发执行继续请求 `gpt-5.6-luna/max`。
- Effective model/reasoning 仍不可独立观测，不能由 requested 推成 confirmed effective。

## 产品 release-retention lineage

正式发布前唯一已知 P3 是 restore-preview evidence 缺少有界保留/回收。产品主编排者使用一条开发 subagent 和一条独立 reviewer subagent，多次 append-only successor 后形成最终候选：

- Developer task path：`/root/release_retention`。
- Reviewer task path：`/root/review_release_retention`。
- Final commit：`5afdb683813b235bef57ea14483d3f9b663d26e5`。
- Final tree：`922166ffca380b79543509cbaf645307c617ec33`。
- Predecessor：`22d1fa17d5223796ff34eb791e7b145b98f52aa1`。
- Branch：`codex/pc-v1-release-retention`。
- Worktree：worker/reviewer 均报告 clean。

Worker 报告：retention focused `14/14`、ApplicationHandlers `14/14`、full Release `102/102`、Release app build `0 warnings / 0 errors`、`git diff --check` exit 0。Final reviewer 对 exact `5afdb683…` 独立重跑 focused `14/14`，结论 `approved`，无 P0–P3。

该结论关闭 retention P3 candidate，但尚不等于 release candidate 已集成。主编排者仍需把 exact commit 接入 integration/release branch，并在变化后的 product tree 上重跑 required release Gates。

## Team 0.1.1 并行改进

- Branch：`codex/team-v011-live-fixes`。
- Commit：`85baabe4ba187c0bff8e95f435c9abf7ba5c7ad4`。
- Tree：`a4f019cd4df78a89f0fa654e802184ac8bef45ac`。
- Final tests：九组 `130/130`，在同一最终工作树上通过。
- Skill quick validation：team-plan/team-run/team-status 通过。
- Independent adversarial review：五轮，最终 `approve`，无剩余 P0–P2。
- Candidate plugin：version `0.1.1`，37-file/7-entrypoint self-check 通过；packaged `integrate → Gate → reviewer-preflight → finish` 通过。
- Bundle manifest SHA-256：`384f230c70e74cb32f6466cbabe1d5a8a4443cacede68a1478b154d8c841e58b`。
- 临时 package：`C:\Users\lenovo\AppData\Local\Temp\codex-team-forward-b517777f19cd4febb9adc48d35286a17\codex-team`。

当前 installed plugin 仍为 `codex-team 0.1.0`；没有安装、cache overwrite 或 marketplace mutation。Team source 修复不能被写成产品当前 task 已使用 0.1.1。

## 当前发布状态与外部 Gate

产品主编排任务 `01a0467a-1f94-73c2-a4fe-cd560a146baf` 已收到 final retention identity，并处于 `active/inProgress`。截至本观察时间，新 turn 仍未暴露 assistant message 或 tool marker，因此这里只确认任务已唤醒，不能确认 release integration 已开始。

完成“全部验收、正式发布”至少仍需：

1. 把 `5afdb683…` 集成到 exact release candidate；
2. 在新 product tree 上重跑 Release tests/build、contract、secret、WinUI、package/install/launch；
3. 使用用户重新配置的新 DeepSeek Key 完成 live Gate；旧/泄漏 Key 仍禁止；
4. 完成真实 200% scaling、High Contrast runtime、screen-reader、keyboard focus restoration和当前 screenshots，或由用户对明确边界作发布决策；
5. 独立 final release review；
6. default branch merge、可分发产物和 clean install/launch receipt；
7. 记录 archive/cleanup candidates，且不自动删除 evidence/worktree。

若新 Key 尚未配置，DeepSeek live 是必须用户完成的外部状态，不得由任务生成、读取旧值或 mock 为 PASS。若无障碍 Gate 必须改变系统显示/辅助功能设置，也必须先给出可回滚步骤并由用户参与。
