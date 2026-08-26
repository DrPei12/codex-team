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

## `team-run` v0.1 准备层已经部分回答

- preregistration、parent/worker preflight、Prompt/dispatch bundle 继续引用同一 manifest digest；brief 还绑定自身 raw SHA-256，不产生第二份任务真相。
- cache、dist、logs、pytest root 在 dispatch 前初始化为空并写入 preregistration；ordinary dirty 触发 parent/worker fail closed，ignored inventory 单独记录。
- Prompt 已区分可信项目规则/brief/runtime binding 与不可信 Issue、评论和粘贴背景；bundle 不包含虚构的 thread/task ID。
- 正确输入生成 `ready_for_authorized_dispatch` 后立即停止，不创建 Codex task/worktree/message；因此它仍没有回答真实 Desktop dispatch、worker runtime context 或 task binding 是否成功。
- 11 项临时真实 Git/worktree 回归通过，但没有独立 fresh Reviewer、安装后运行、第二 blind benchmark 或公平 no-skill 对照。详见 [`team-run` v0.1 实录](research/team-run-v0.1-2026-08-24.md)。

## `team-status` v0.1 只读派生层已经部分回答

- facts 与 display status 已分离；snapshot 可重建，不把 `DONE`、消息或 UI 标签写回项目真相。
- 初始 Core/CLI 可显示 `ready-for-dispatch`，依赖它们的 Integrator/Reviewer 显示 `waiting-dependency`；依赖只由 `acceptance_state=accepted` 解锁。
- parent/worker preflight、Manifest/dispatch/Prompt/Brief、task binding、report/evidence 和 current-run path/hash 均在派生前交叉验证；dirty handoff、跨-run evidence、矛盾 integration facts 与 identity 漂移 fail closed。
- 当前 facts 仍由文件输入模拟；没有 Codex list/read/wait collector、消息送达、cursor 或长期状态准确率证据。详见 [`team-status` v0.1 实录](research/team-status-v0.1-2026-08-24.md)。

## Team v0.1 离线闭环已经部分回答

- `team-integrate` 已把 report/evidence/receipt/commit/tree/changed files 绑成 candidate，按 manifest 顺序生成 plan；Git mutation 和 Gate command 分别需显式旗标，非零 Gate 立即停止。
- `team-finish` 已把 approved review、exact Gate target、ordinary/ignored/operation residue、run inventory 和 milestone result 分开；不自动 archive/cleanup。
- `team-recover` 已约束 immutable predecessor、exact commit/dirty candidate、same-manifest proofs、一个新事实和命令/路径/预算；不创建 successor task。
- 统一 `team` 路由只读 canonical artifact 名称，不从多个同类历史文件猜测权威版本，也不把路由建议当成授权。
- 该轮当时八组共 90 项回归与 16 份端到端 schema artifact 通过；尚无可移动打包或 live Codex 生命周期证据。详见 [Team v0.1 验收](research/team-v0.1-2026-08-25.md)。

## Plugin packaging v0.1 已经部分回答

- 当前官方分发单位是 plugin，一个 skills-only plugin 可包含一组相关 skill，无需为纯本地 workflow 强行增加 MCP server。
- `build-team-plugin.py` 已将源码中唯一 runtime/schema 注入 bundled `team` skill，其他 phase 从 `<TEAM_SKILL_DIR>` 定位，不在仓库里维护七份重复 runtime。
- 两次构建 bytes 一致，输出不覆盖；bundle manifest/self-check 绑定 37 份文件和 7 个 runtime entrypoint。
- 生成包在源码仓库外的临时目录实际运行全流程，通过官方 plugin validator 和 7/7 skill validator。详见 [plugin packaging v0.1 验收](research/team-plugin-packaging-v0.1-2026-08-25.md)。
- 仍未回答的是真实 marketplace/UI 安装后的 discovery、触发、更新和卸载，不是包内路径。

## P0：进入实际安装/live 验证前必须回答

1. 需用户单独授权的 local/personal marketplace 方案中，应使用临时测试来源还是 repo-scoped marketplace？如何预注册 rollback 和不触碰现有用户 plugin 的边界？
2. 新会话是否同时发现 7 个 skill？统一 `team` 的显式/隐式触发、phase 路由与非触发对照是否可靠？
3. Plugin 升级、cachebuster、重装、禁用和卸载后，旧会话与新会话各使用哪个版本，怎样取证？
4. `team-run` 准备层已完成 root 初始化与 parent/worker helper；真实 Desktop task 如何消费 dispatch bundle、写入 thread/project binding，并在真实回合运行同一 worker preflight？
5. `team-status` renderer 已完成；Codex-native observation adapter 如何把 Desktop list/read/wait、Git state 和 artifact timeline 写成新 immutable facts，处理重复/延迟/cursor，同时不发送消息或无理由重复昂贵命令？
6. `team-plan` 已能拒绝依赖或所有权结构不成立的 fan-out；协调成本阈值、“只适合 subagent”与“应当串行”的选择规则如何通过第二 benchmark 验证，而不是写成未经测试的常数？
7. Desktop 未显式暴露 effective model/thinking 或 token 时，run artifact 应怎样保留 `unknown` 并维持可解释的对照？
8. 项目应采用什么 LICENSE 与 NOTICE 策略，才能在未来确有必要时合规复用 MIT/Apache-2.0 prior-art 源码，同时保持来源 revision 与本地改写可追溯？

## P1：第二个 blind 纵向切片中回答

1. 第一轮经用户单独授权的最小 live pilot 中，真正同时 ready 的 lane 有多少，多少 worker 会因为依赖而空等？
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
