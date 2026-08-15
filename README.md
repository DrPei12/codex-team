# Codex 多任务工程系统

一个面向 Codex 的社区开源研究与 skills 工程：调查多任务、subagent、Git worktree、直接任务通信、验收证据与生命周期治理已经能做到什么，再把可复现的方法、失败边界和工具化实践分享出来。

它不是商业产品，也不以“发明新范式”作为成立条件。项目可以广泛吸收、复现和组合已有实践，但只有经过当前 Codex 环境实测的能力才会晋升为稳定 skill。当前已经有首个可执行但仍属 `incubating` 的 `team-plan`，尚未形成完整可安装套件。

## 项目要解决什么

单个 Codex 任务可以完成复杂工程，但大型开发仍会遇到四类上限：

1. 功能没有按依赖和共享契约正确拆分，可并行工作被迫串行，或错误并行造成返工；
2. 多条 session 缺少清楚的文件/资源所有权、任务状态和集成顺序；
3. 多任务之间靠自由文本交接，证据、责任和状态容易丢失；
4. 并行数量增加后，Git 冲突、重复测试、等待、任务堆积和上下文干扰抵消收益。

本项目不把“多开几个 Agent”当作答案，而是研究、验证并逐步工具化下面这套方法：

- 一个高能力主编排者负责目标、架构、切分、风险和最终整合；
- 若干长期任务像项目成员一样拥有独立历史和可隔离的工作环境；
- 每个任务内部可以使用短命 subagent 搜索、分析或实现小单元；
- Git、测试报告和结构化 artifact 承担事实传递，任务消息只负责协调；
- 验收按风险分层，避免昂贵测试机械地执行两遍；
- 完成的临时任务归档，长期职责任务保留，老化任务可通过 handoff 轮换。

## 范围

只面向 Codex。不会设计“平台无关核心”、adapter 层或 Claude Code 兼容预留。如果未来需要 Claude Code 版本，应作为独立项目重新设计。

Claude Agent Teams、oh-my-codex、gstack、Superpowers、Gas Town 和相关论文可以作为 prior art 与实验参照，但不是本项目要兼容的运行目标，也不是需要击败的竞争对象。项目规模可以随可靠能力累积而扩大；边界来自 Codex plugin/skills 能承载什么，而不是预先规定一个最小目录。

## 当前成果

- 项目章程、概念模型和术语体系；
- worker 角色、执行环境与历史来源的分层分类；
- 多种编排范式及默认混合工作流；
- 基于 A2A 语义的任务、消息和 artifact 模型；
- proof-carrying handoff 与分层验收策略；
- 模型、thinking、上下文和任务生命周期策略；
- 大型 skills 套件的信息架构与渐进式披露原则；
- 评测路线、决策日志、开放问题和完整讨论记录；
- 对原生产品、社区实践、长时多 Agent 实验和 skills 实证研究的 [prior-art 与能力上限调查](docs/research/prior-art-and-capability-limits.md)；
- 对 gstack、Superpowers、oh-my-codex 固定源码快照的 [大型工程方法提炼](docs/research/large-skill-suite-engineering-methods.md)；
- 区分声明与行为观测的 [Codex capability contract](docs/18-capability-contract.md)、静态环境快照、只读探针和 validator；
- 首轮隔离行为 [pilot](docs/research/capability-pilot-2026-08-12.md)：两个外部 worktree、三个会话、idle message/wait 与 same-directory fork；
- 首个 worker profile [对照](docs/research/profile-comparison-2026-08-12.md)：粗暴关闭用户配置不仅未降本，还使 verifier 失败并把输入放大约 5.2 倍；
- 已冻结的 OutputGuard JSONL benchmark、反作弊边界和失败记录；第一次 CLI 混合试跑因真实 worker 环境与 Git preflight 失败而停止，没有形成对照结论；
- D-023 Desktop-first 执行规则；Desktop local 任务已完成只读、Git index/ref 写入、完整 public pytest、Ruff、mypy 外置缓存、离线 package build 和 assigned worktree marker commit 资格检查；
- 已冻结并实际执行的 [OutputGuard 首个 Desktop 纵向切片计划](docs/19-outputguard-vertical-slice-plan.md)，以及 session plan、roster、task brief、worker report、integration queue 的最小 JSON Schema、样例和 fail-closed validator；
- [Run02–Run10 全流程实录](docs/research/outputguard-vertical-slice-2026-08-15.md)：最终 exact tree 通过 public Gate、fresh Reviewer 和单次 sealed evaluator `37/37`，同时保留每个 blocked run、一个 low finding 和 29 个 ignored bytecode 残留的限制。
- 首个 `incubating` workflow skill：[`team-plan`](skills/team-plan/SKILL.md)、canonical manifest schema、标准库 validator/projector 和 19 项边界回归；一次 fresh forward test 生成 1 份 manifest 与 4 份 digest-bound task brief，详见 [team-plan v0.1 实录](docs/research/team-plan-v0.1-2026-08-15.md)。

## 从哪里开始读

1. [项目章程](docs/00-project-charter.md)
2. [概念模型](docs/01-conceptual-model.md)
3. [默认运行架构](docs/04-default-operating-model.md)
4. [文档导航](docs/README.md)
5. [当前状态](docs/16-project-status.md)
6. [Prior art 与能力上限](docs/research/prior-art-and-capability-limits.md)

## 当前阶段

`M1.1 — Turn the accepted manual lineage into incubating skills`

首个功能 OutputGuard JSONL streaming 已完成一条真实 Desktop recovery lineage。最终 commit `b67c8e` / tree `41de967` 通过 affected tests `64 passed`、完整 public suite `2093 passed / 28 skipped`、Ruff、mypy、离线 build、新 Reviewer 和唯一一次 sealed evaluator `37 passed`。这不是一次无中断四任务成功，也没有证明多任务比 single 更快、更省或更可靠；最终结果复用了前序 run 已验收的 CLI commit 和精确 Core candidate。

Run02–Run10 暴露的 canonical identity、artifact root、所有权和 review target 约束，已经先进入 `team-plan` v0.1；但 Gate receipt、recovery link、cleanliness receipt、安装/隐式触发和实际 dispatch 仍未完成。下一步实现 `team-run` 的最小 Desktop dispatch/preflight 切片，再接 `team-status`、`team-integrate`、`team-finish` 与候选 `team-recover`。OutputGuard 只继续作为 failure corpus；skill 的主要边际效用必须转到第二个未见 benchmark。参见[评测路线](docs/12-evaluation-roadmap.md)。
