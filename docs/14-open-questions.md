# 14. 开放问题

这些问题未被当前讨论完全解决。它们是后续研究和实验输入，不应被实现者静默猜测。

## 首个纵向切片已经部分回答

- Desktop saved project 可以作为 task 控制入口，brief 指定同一 common-dir 下的 permanent worktree 作为 execution workspace；它在记录条件下可行，但仍不等于 Desktop-managed worktree 已验证。
- `DONE`、parent `ACCEPTED`、Git `INTEGRATED`、Reviewer `APPROVED` 和 sealed `PASSED` 必须分别取证；Run10 已实际走过这些状态。
- 一个新 Reviewer 在 public Gate 已绿后仍发现四个 high defect，说明 review 不能折叠为测试摘要。
- recovery 必须保留 predecessor status，只携带 exact candidate 和新事实；ordinary clean 与 ignored clean 必须分开。
- 以上是一次 lineage 的观察，不是长期可靠性答案。详见 [OutputGuard 实录](research/outputguard-vertical-slice-2026-08-15.md)。

## `team-plan` v0.1 已经部分回答

- 规划阶段已有一个 canonical `run-manifest` v0.1；base identity、task project、workspace policy、frozen contract、lanes、parallel groups、integration order、Gate 和 stop condition 都由同一文档承载。
- task brief 不再人工复制身份，而是由通过校验的 manifest 投影，并携带同一个 canonical SHA-256。
- validator 已能拒绝未知依赖、DAG 环、并行写入重叠、workspace 逃逸/别名、错误 Reviewer 拓扑、非法 projection 和非 canonical Git/timestamp。
- `team-plan` 成功后必须停止，不创建任务或 worktree；因此它只回答“计划是否结构上可执行”，没有回答真实 Desktop dispatch 是否成功。
- no-skill baseline 读取了历史 solution refs，不能用于计算 skill 提升。详见 [`team-plan` v0.1 实录](research/team-plan-v0.1-2026-08-15.md)。

## P0：继续实现剩余入口前必须回答

1. `team-plan` 已冻结 manifest → brief 的最小字段；preregistration、freeze、handoff、Gate receipt 和 acceptance 中哪些字段继续由 manifest 派生，哪些允许人工叙述？
2. manifest → brief 已冻结 UTF-8、sorted keys、无空白分隔和 SHA-256；后续 preregistration、Gate/recovery/cleanliness receipt 如何复用同一 canonical identity 和字节规则？
3. `team-plan` 已能拒绝依赖或所有权结构不成立的 fan-out；协调成本阈值、“只适合 subagent”与“应当串行”的选择规则如何通过第二 benchmark 验证，而不是写成未经测试的常数？
4. `team-run` 如何统一创建/验证 artifact、pytest、cache、dist root，并让 parent 与真实 Desktop task 分别完成 preflight？
5. `team-status` 如何把 Desktop read/wait/message、artifact timeline 和 Git state 合并为事实视图，既不相信单一自报，也不无理由重复昂贵命令？
6. `team-integrate` 如何生成可验证 Gate receipt；review、sealed authorization 和 public Gate 的责任边界怎样编码？
7. `team-recover` 如何约束 predecessor、candidate、旧 proof、唯一新事实和预算，防止恢复任务顺手扩大 scope？
8. 第一批 skills 如何打包共享 schema/scripts，才能在安装后保持相对路径稳定又不复制大量资源？
9. Desktop 未显式暴露 effective model/thinking 或 token 时，run artifact 应怎样保留 `unknown` 并维持可解释的对照？

## P1：第二个 blind 纵向切片中回答

1. 第一轮 3–5 条 worker session 中，真正同时 ready 的 lane 有多少，多少 worker 会因为依赖而空等？
2. 在相同 Desktop 任务拓扑下，不同 model/thinking 在 planner、implementer、reviewer、integrator 上分别出现什么失败；提高 thinking 是否比重派/重切任务更有效？
3. 何种结构化 brief 能让 worker 不读完整项目历史仍正确使用共享 contract？
4. Worker `DONE`、主编排者 `ACCEPTED` 与 Git `INTEGRATED` 怎样分别取证？
5. affected tests 如何选择，worker evidence 何时失效，合并后哪些 Gate 必须重跑？
6. Worker 阻塞、任务拆分错误、接口变更或所有权冲突时，怎样安全暂停、重派或回到 plan？
7. 一次性任务接收后怎样归档；worktree 保留、清理和 branch 处理怎样分别授权？
8. workflow 相对 native single/native multi-task baseline 的缺陷、返工、等待、冲突、wall time、token 和用户介入怎样变化？
9. skill 来源、revision、license、兼容范围、脚本副作用与权限如何记录和验证？
10. 如何证明 baseline Git object store、可见 refs、task history、run artifacts 和 evaluator 没有泄漏已见 solution？

## P2：扩展范式前回答

1. Codex `create/fork/message/wait/handoff/archive` 在所有 workspace 和 active/dirty/failure 状态下的完整行为矩阵是什么？
2. Hub-and-spoke 何时因主编排者瓶颈需要二级 coordinator？
3. 不建 daemon 的前提下，work queue、lease、心跳、orphan worker 和 crash recovery 能可靠做到什么程度？
4. Blackboard 如何避免并发写冲突和信息膨胀？
5. Competing prototypes 的统一 benchmark 如何防止选择偏差？
6. Maker-checker 是否需要不同模型、不同上下文或独立输入顺序来减少确认偏差？
7. 哪些项目可以安全自动 merge，哪些只能生成集成建议？
8. 如何量化 UI 冗繁、任务找回时间和用户认知负担？
9. 哪些 pattern 已经产生足够独立行为和证据，应从 reference/profile 晋升为 skill？
10. 如何在不破坏 auth、rules 和 sandbox 的前提下优化 memory/plugin/skill discovery、compaction 和长期 owner 轮换？
11. 同一 workflow 在 Desktop 的 Windows/macOS/Linux 环境中如何标 unknown、unsupported 或 observed；CLI 历史兼容数据如何保持独立而不污染 active 结论？

## 暂不做的问题

- Claude Code 的兼容实现或 adapter；允许继续把官方能力与实验作为 prior art 调查；
- 跨平台 Agent adapter；
- 完整 A2A 网络互操作；
- 无边界自治发布；
- 在没有 telemetry 的情况下猜测 token 数据。

## 解决流程

每个开放问题关闭时应留下：来源或实验、原始证据、结论适用范围、被替代的假设、对应 decision ID，以及对 docs/schema/skills 的影响。

候选 skill 的问题关闭还应留下 no-skill baseline、兼容 snapshot、触发/非触发结果和失败注入结果；没有正向结果也要保存，不能只发布成功案例。
