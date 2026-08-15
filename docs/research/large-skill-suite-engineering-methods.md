# 大型 Skill 套件的工程方法提炼

## 这轮调查要回答什么

本轮不再重复证明 Codex 能创建任务、发送消息或进入 worktree。主问题改为：面对一个中等偏大的软件功能，怎样把它拆成若干条可并行的 session，怎样分配责任、控制依赖、检查进度、处理失败，并把结果安全地集成回来。

调查对象是三个当前较成熟、路线明显不同的开源项目：

- [gstack @ `94993f7`](https://github.com/garrytan/gstack/tree/94993f74012782fd94416dd44b8314f6363a13a4)
- [Superpowers @ `44c9b2d`](https://github.com/obra/superpowers/tree/44c9b2d6e889982ac18c27d05a19fefe335194e1)
- [oh-my-codex @ `b30127a`](https://github.com/Yeachan-Heo/oh-my-codex/tree/b30127a0979c96046c8cd6312a8cd922c3516cad)

源码快照保存在 `D:\Desktop\Codex多任务工程系统实验场\prior-art`。三份 checkout 的 HEAD 与上述固定 revision 一致。oh-my-codex 初次 checkout 曾受 Windows 长路径影响，随后改为 sparse checkout 并恢复为 clean；这只是本地取证问题，不计作项目能力结论。

## 先给结论

三套项目分别补上了大型工程的不同部分：

1. **gstack 解决一条 session 该怎样像成熟研发流程一样工作。** 它把澄清、计划、工程审查、实现、代码审查、QA、发布和复盘串成阶段，并让上一步 artifact 成为下一步输入。但它宣传的多 sprint 并行主要由 Conductor 等外部 session/workspace 管理器承载，gstack 自身并不是任务调度器。
2. **Superpowers 解决一个计划怎样拆成可实现、可复查的小任务。** 它要求精确文件、接口、测试步骤、独立 worktree、逐任务审查和最终整体验收。它的最新 `subagent-driven-development` 明确禁止多个实现者并行改代码；只有真正独立、没有共享状态的问题调查才使用并行 fan-out。
3. **oh-my-codex 解决耐久并行运行所需的控制面。** 它已经拥有任务图、依赖、worker 分配、认领 token、mailbox、ACK、状态、心跳、worktree、重分配、集成状态和 shutdown。但这些能力依赖 tmux、CLI、hooks、状态目录和大量 runtime 代码，已经超出纯 skills 的边界。

因此，本项目不应照抄任意一套。我们的合理组合是：

- 用 gstack 的阶段化研发流程定义“一条 session 做到什么程度才算交付”；
- 用 Superpowers 的任务规格、文件边界、审查和停止规则定义“每条 session 怎样工作”；
- 借 oh-my-codex 的 task graph、认领、状态、消息和集成语义，但由 Codex 原生 task 工具、Git worktree 和仓库 artifact 承载，不另建 tmux/runtime。

## 三套项目到底做对了什么

### gstack：让每条 session 有完整研发流程

固定快照中的主流程是：

```text
Think -> Plan -> Build -> Review -> Test -> Ship -> Reflect
```

其价值不在“扮演 CEO、设计师、工程经理”等角色名称，而在以下工程约束：

- 前一阶段写出的设计、计划和测试 artifact 会被后一阶段读取；
- 根据改动范围路由必要审查，不让所有变更机械经过同一套昂贵流程；
- `/review` 可以并行调用互不干扰的专项 reviewer，主 reviewer 负责合并和去重；
- `/ship` 在发布前重新核对测试、覆盖、计划完成度、审查状态和文档；
- skill 的公共 preamble、命令表和模板由生成器维护，并用静态检查、真实 Agent E2E 和 LLM judge 分层验证；
- checkpoint、review record 和恢复 artifact 让跨 session 工作有可追踪依据。

对本项目最重要的反面结论是：gstack 的“10–15 parallel sprints”是作者在 Conductor 隔离 workspace 中的实践描述，不是 gstack 自己提供了跨 session 排程，也不是可直接迁移的并发上限。我们应该学习其工作流一致性和按阶段验收，不复制数字。

### Superpowers：把执行单元做小，把审查做硬

Superpowers 的计划任务不是一句“实现模块 A”，而是一个可独立执行和拒收的工作包：

- 写明创建、修改和测试的精确文件；
- 写明 consumes/produces 接口，防止相邻任务各自发明类型和名称；
- 每个任务包含失败测试、运行命令、最小实现、通过测试和 commit；
- 任务大小以“值得一次独立 reviewer Gate”为准，而不是按目录或技术层硬切；
- 执行前建立或确认 worktree，并先跑干净 baseline；
- 每个任务由实现者完成，再做 spec compliance 与 code quality 审查，最后做 whole-branch review；
- 修复循环有上限，达到上限后必须裁决或上报，不能无限续跑；
- progress ledger 绑定 plan 和 commit，避免 compaction 后重复派发已经完成的任务。

它对并行的态度很有参考价值：

- 多个互不相关的故障、不同子系统的只读调查，可以一域一 Agent 并行；
- 有共享文件、顺序依赖或需要完整系统理解时，不并行；
- 计划型实现默认逐任务推进，避免多个实现者在同一代码树上互相踩踏；
- reviewer 使用独立上下文，但接收的是 task brief、report 和 diff package，不是主任务全部聊天历史。

这说明“管理多 session”首先不是多开窗口，而是先判断哪些 lane 真正独立。

### oh-my-codex：完整控制面的高水位，也是范围警示

oh-my-codex 的 Team 已经接近一个专用调度 runtime。固定快照包含：

- repo-aware DAG、符号依赖到 runtime task ID 的映射；
- worker count 的来源和有效 ready lane 计算；
- 同文件/同领域尽量交给同一 owner；
- claim token、依赖就绪检查、lease/release/reclaim；
- worker inbox、leader/worker mailbox、启动 ACK 和 dispatch queue；
- worker status、liveness、heartbeat、dead worker 和 reassignment 建议；
- worker 独立 worktree、commit、leader incremental integration；
- `pending -> notified -> delivered/failed` 等投递状态；
- 只有 Git containment/leader HEAD 证据成立才标记 `integrated`；
- status、resume、await、shutdown 和 stale state recovery。

这些机制说明了并行工程真正会遇到的坑：重复领取、依赖尚未完成就开工、worker 死亡、消息到了但任务状态没变、worker 完成但 commit 未集成、过早 shutdown、旧状态干扰新运行、共享文件被不同 owner 同时修改。

但它也画出了本项目边界。上述能力需要 tmux、后台 hook、CLI API、状态机和长期 runtime 测试。本项目交付是 Codex skills/plugin，不建设第二个 oh-my-codex runtime。我们只采用可以落到 Codex 原生任务、Git 和 artifact 上的语义；需要后台 lease、自动心跳或 daemon 才可靠的功能，先保留为限制或人工 runbook。

## 对本项目主线的修订

### 主线问题

第一主线正式收敛为：

> 给定一个中等偏大的软件功能，主编排任务先理解仓库和需求，冻结共享契约，再把可并行部分分配给若干条独立 Codex session；每条 session 在独立 worktree 中按明确 brief 工作并提交证据；主编排任务持续管理依赖、消息和状态，最后由单一 integrator 按顺序接收、审查和集成。

上下文裁剪、自动 compaction、长期 owner 轮换和 skill discovery 优化仍然有价值，但现在都是后续优化，不再阻塞第一条工程闭环。

### 第一批用户入口

第一版不需要先做十几个入口。最小但真实的闭环是：

| Skill | 用户在什么时候用 | 核心产物 |
|---|---|---|
| `team-plan` | “把这个功能拆成多条任务并行完成” | 任务图、共享契约、session 数量与角色、文件所有权、依赖、worktree 和验收计划 |
| `team-run` | 用户接受计划后要求开始 | 创建/选择 session 与 worktree，派发 task brief，记录 task/thread identity 和起始 revision |
| `team-status` | 用户问进度，或编排者等待/收到阻塞时 | 当前 roster、任务状态、依赖变化、阻塞、证据引用和下一动作 |
| `team-integrate` | worker 交付后 | handoff 校验、commit 接收顺序、review、affected/integration Gate 和集成结论 |
| `team-finish` | 里程碑完成后 | 最终状态、临时任务归档候选、保留的 worktree、未决风险和恢复入口 |

`team-recover`、`team-review`、`team-benchmark` 等可以继续建设，但不作为第一条纵向切片的前置条件。Capability probe、schema validator、worktree preflight 和 evidence collector 优先做共享脚本/reference，而不是抢占用户入口。

### `team-plan` 必须解决的核心判断

`team-plan` 的价值不只是生成任务清单，而是做出以下决定：

1. 哪些工作必须先串行完成，例如公共 schema、迁移顺序或基础接口；
2. 哪些 lane 在契约冻结后可以并行；
3. 哪些文件或可变资源只能有一个 owner；
4. 哪些工作适合长期 task，哪些只需当前任务内 subagent；
5. 每个 lane 的输入、输出、acceptance Gate 和上报条件；
6. 集成顺序以及合并后才会出现的组合测试；
7. 并行收益是否足以覆盖 briefing、review 和 merge 成本。

如果不能画出清楚的依赖图、所有权和集成点，`team-plan` 应建议串行或先做探索，而不是为了展示多任务强行 fan-out。

### 最小持久状态

第一版不建 mailbox server 或 lease daemon，但至少保存以下 artifact：

- `session-plan`：目标、DAG、共享契约、worker 数、模型、worktree 和集成顺序；
- `session-roster`：task/thread ID、角色、worktree、branch、起始 HEAD、所有权和当前状态；
- `task-brief`：单 lane 的目标、范围、文件、输入、输出、Gate、禁止事项和升级条件；
- `worker-report`：commit、diff 摘要、测试证据、风险、对其他 lane 的影响；
- `integration-queue`：接收顺序、evidence 状态、review 结论和合并状态。

消息只通知“有新任务、需要输入、已阻塞、已交付”；完整内容放 artifact。Codex 原生 task 状态与 Git 是事实源，Markdown/JSON ledger 是可恢复视图，不能凭聊天摘要覆盖实际状态。

### 当前 Desktop 与模型政策

从 D-023 起，实验场的执行、审查和集成回合只通过 Codex Desktop 原生任务工具创建。用户没有明确指定 model/thinking 时不覆盖 Desktop 默认配置；明确指定后才把它冻结为该 run 的控制变量。运行记录同时保存 requested/effective model 与 thinking，产品未暴露的值记为 `unknown`。配置不符时停止，不改用 CLI 或在看到结果后换模型。

2026-08-12 的 `gpt-5.6-luna + high` 是已经发生的 CLI 历史实验条件，不再是未来 Desktop task 的自动默认。首个 Desktop 闭环不做跨模型对照；模型分层仍在流程稳定后单独研究。

## 第一条实战评测应长什么样

不再继续做消息 nonce、idle fork 或加载项裁剪作为主实验。第一个 benchmark 应是一个真实、可验收、能暴露依赖和集成成本的功能：

1. 一个共享 contract 或公共接口先由主编排者/单一 owner 冻结；
2. 两到三个实现 lane 在不同模块和 worktree 中并行；
3. 一个独立 review/verification lane 检查 task brief、diff 和证据；
4. 单一 integrator 按依赖顺序接收 commit；
5. 最后运行合并后才有意义的 integration Gate；
6. 至少注入一次现实问题，例如接口理解偏差、同文件所有权冲突、worker 阻塞或证据缺项。

第一轮可观察地限制在 3–5 条 worker session，是为了让失败可定位，不是项目并发上限。验收重点不是“同时开了多少任务”，而是：拆分是否正确、等待是否减少、冲突是否被阻止、交付能否被另一任务无歧义接收、最终代码是否通过同一 Gate。

## 暂时不做

- 不实现 tmux、daemon、watchdog、自动 heartbeat 或自建 mailbox runtime；
- 不把剩余 create/fork/handoff 边角行为全部测完才开始工程闭环；只在 workflow 真正依赖某个未知语义时做最小 probe；
- 不把上下文裁剪、memory/plugin 开关或长期轮换当作 M1 的首要优化；
- 不在首个 Desktop 闭环中同时做跨模型对照；
- 不实现 Claude Code adapter 或平台无关层。

## 下一步

1. 使用已经冻结的 OutputGuard JSONL streaming benchmark，不根据无效试跑结果修改公开 task 或 sealed Gate；
2. 先解决 Desktop saved project 与实验根目录约束，并通过一个明确授权的只读 Desktop-native preflight；
3. 根据本报告重写 `team-plan`、`team-run`、`team-status`、`team-integrate`、`team-finish` 的 spec；
4. 只冻结这条闭环需要的 session plan、roster、brief、report 和 integration queue schema；
5. 通过 Desktop 原生 task 在批准的 workspace 完成第一轮端到端运行和 single baseline；
6. 根据实际失败再决定是补 skill、script、reference，还是承认需要原生/runtime 能力。
