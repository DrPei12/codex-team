# 官方与研究来源

本页记录 Phase 0 用于建立 baseline 的来源。访问日期均为 2026-08-09。产品文档可能更新，实施前应重新核验。

## Codex / OpenAI

### Git worktrees

- 来源：[OpenAI — Git worktrees](https://learn.chatgpt.com/docs/environments/git-worktrees)
- 用途：确认 Codex 环境下 worktree 的目的、隔离思路和工作方式。
- 本项目推论：worktree 提供工作目录隔离，但 Git 和语义集成风险仍需本项目治理；后半句是工程推论，不是官方保证。

### Subagents

- 来源：[OpenAI — Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- 用途：建立父任务内部短生命周期委派的能力 baseline。
- 注意：具体可见性、并发、模型和 workspace 行为应以实施时工具 schema 为准。

### Compaction

- 来源：[OpenAI API — Compaction](https://developers.openai.com/api/docs/guides/compaction)
- 用途：理解长运行 Agent 如何压缩上下文，以及为何硬 context window 不等于无限有效记忆。
- 注意：API compaction 与 Codex 桌面任务的具体自动行为不能未经验证直接等同。

## A2A

### 官方规范

- 来源：[A2A Protocol specification](https://github.com/a2aproject/A2A/blob/main/docs/specification.md)
- 用途：Task、Message、Part、Artifact、Agent Card 和状态语义。

### Task 生命周期

- 来源：[A2A — Life of a Task](https://a2a-protocol.org/latest/topics/life-of-a-task/)
- 用途：长任务、状态转换、输入请求和 artifact 交付的概念 baseline。

本项目只采用语义对齐的本地 profile，不声称实现完整 A2A wire protocol。

## 长上下文研究

### Lost in the Middle

- 来源：[Liu et al., Lost in the Middle, TACL 2024](https://aclanthology.org/2024.tacl-1.9/)
- 用途：支持“信息在长上下文中的位置与检索表现有关”的研究 baseline。
- 限制：论文模型和任务不等于当前 Codex 工程任务，不能直接给出 worker 的轮数阈值。

### Context Rot

- 来源：[Chroma Research — Context Rot](https://www.trychroma.com/research/context-rot)
- 用途：形成“上下文长度增加可能导致有效表现逐步下降”的实验假设。
- 限制：这是外部研究，不是 Codex 官方保证；具体模型、指标与当前版本必须复测。

## 工程证据标准

### SARIF

- 来源：[OASIS SARIF](https://www.oasis-open.org/committees/sarif/)
- 用途：静态分析与安全 finding 的标准化输出候选。

### in-toto

- 来源：[in-toto specification](https://github.com/in-toto/docs/blob/master/in-toto-spec.md)
- 用途：未来 proof-carrying handoff、命令/材料/产物 provenance 的参考。

### OpenTelemetry semantic conventions

- 来源：[OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/)
- 用途：未来关联主任务、worker、工具、测试和 handoff 的 telemetry 候选。

## 来源纪律

- 官方产品事实优先官方文档和当前工具 schema；
- 研究只能提供假设与 baseline，不替代本项目实测；
- 社区反馈可用于发现场景和失败模式，但不能单独确定默认阈值；
- 每次冻结产品行为或数值结论，都应记录版本、日期、环境和复现步骤。
