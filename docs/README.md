# 文档导航

这套文档采用“先建立共同语言，再进入运行规则，最后进入实现与评测”的顺序。读者无需一次加载全部内容。

最后同步：2026-08-24。`team-plan` 已在 `main`；`team-run` 非 live 准备层最终代码身份为功能分支 commit `c5ead87`，下一步是审查该切片并实现 read-only `team-status`，真实 Desktop dispatch 仍需单独授权。

## 第一层：五分钟了解项目

- [项目章程](00-project-charter.md)：目标、边界、成功标准。
- [概念模型](01-conceptual-model.md)：角色、编排范式、历史来源、workspace 和生命周期为什么不能混为一谈。
- [默认运行架构](04-default-operating-model.md)：大白话版默认团队和默认混合流程。
- [当前状态](16-project-status.md)：当前完成了什么、下一步是什么。

## 第二层：准备设计或运行一个项目

- [Worker 分类](02-worker-taxonomy.md)
- [编排范式](03-orchestration-patterns.md)
- [Codex 任务与 worktree 机制](05-thread-and-worktree-mechanics.md)
- [Codex Capability Contract](18-capability-contract.md)
- [OutputGuard 首个 Desktop 纵向切片计划](19-outputguard-vertical-slice-plan.md)
- [任务与消息模型](06-task-and-message-model.md)
- [交接与验收](07-handoff-and-verification.md)
- [模型与上下文策略](08-model-and-context-policy.md)
- [生命周期与治理](09-lifecycle-and-governance.md)

## 第三层：准备实现 skills 或开展评测

- [Skills 套件架构](10-skill-suite-architecture.md)
- [成熟标准复用](11-standards-reuse.md)
- [评测路线](12-evaluation-roadmap.md)
- [决策日志](13-decisions.md)
- [开放问题](14-open-questions.md)
- [讨论记录](15-conversation-record.md)
- [术语表](17-glossary.md)
- [官方与研究来源](research/official-sources.md)
- [Prior art 与能力上限调查](research/prior-art-and-capability-limits.md)
- [大型 Skill 套件的工程方法提炼](research/large-skill-suite-engineering-methods.md)
- [Capability 行为实验计划](research/capability-experiment-plan.md)
- [2026-08-12 隔离会话 Pilot](research/capability-pilot-2026-08-12.md)
- [2026-08-12 Worker Profile 对照](research/profile-comparison-2026-08-12.md)
- [2026-08-15 OutputGuard Desktop 纵向切片实录](research/outputguard-vertical-slice-2026-08-15.md)
- [OutputGuard 纵向切片机器 evidence](../evidence/experiments/2026-08-15-outputguard-vertical-slice.json)
- [2026-08-15 team-plan v0.1 实录](research/team-plan-v0.1-2026-08-15.md)
- [team-plan v0.1 机器 evidence](../evidence/skills/2026-08-15-team-plan-v0.1.json)
- [2026-08-24 team-run v0.1 准备层实录](research/team-run-v0.1-2026-08-24.md)
- [team-run v0.1 机器 evidence](../evidence/skills/2026-08-24-team-run-v0.1.json)
- [模板目录](templates/README.md)

## 文档状态标签

专题文档中的关键陈述可按下面五类理解：

- **已确认事实**：由当前产品行为、官方文档或本地可复现实验支持。
- **实验观察**：在特定时间、版本和环境中观察到，不能自动外推为长期保证。
- **已接受决策**：本项目当前采用，未来可以通过新决策替代。
- **设计提案**：方向明确但尚未经过系统对照实验。
- **待验证假设**：必须通过研究或实验解决，不能作为自动化默认值。

## 更新规则

- 核心决策变化：更新对应专题、`13-decisions.md` 和 `16-project-status.md`。
- 新实验完成：把方法与结果写入评测记录，并更新相关假设状态。
- 模板字段变化：同步更新消息模型、验收模型和模板版本。
- 未来实现某个 skill：其 `SKILL.md` 保持精炼，深入解释链接到按需 references；项目级原理仍保留在本目录。
