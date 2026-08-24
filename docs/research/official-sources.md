# 官方与研究来源

本页记录 Phase 0/M1 用于建立 baseline 的来源。初始条目访问于 2026-08-09，prior-art 扩展条目访问于 2026-08-10，三套大型 skill 工程源码在 2026-08-12 再次核验。产品文档、论文和仓库会更新，实施前应重新核验；完整 claim/evidence 关系和查询日志见 [prior-art 与能力上限调查](prior-art-and-capability-limits.md)，工程方法提炼见 [大型 Skill 套件的工程方法提炼](large-skill-suite-engineering-methods.md)。

## Codex / OpenAI

### Codex App

- 来源：[OpenAI — Introducing the Codex app](https://openai.com/index/introducing-the-codex-app/)
- 用途：确认官方把 App 描述为并行 threads、worktrees、skills 和 automations 的多任务工作面。
- 限制：产品介绍不是组合语义或稳定 API 契约；行为仍需 capability test。

### Git worktrees

- 来源：[OpenAI — Git worktrees](https://developers.openai.com/codex/environments/git-worktrees)
- 用途：确认 Codex 环境下 worktree 的目的、隔离思路和工作方式。
- 本项目推论：worktree 提供工作目录隔离，但 Git 和语义集成风险仍需本项目治理；后半句是工程推论，不是官方保证。

### Subagents

- 来源：[OpenAI — Subagents](https://developers.openai.com/codex/subagents)
- 用途：建立父任务内部短生命周期委派的能力 baseline。
- 注意：具体可见性、并发、模型和 workspace 行为应以实施时工具 schema 为准。

### Skills

- 来源：[OpenAI — Build skills](https://learn.chatgpt.com/docs/build-skills)
- 用途：建立 `SKILL.md`、references/scripts/assets、plugin 分发和渐进式披露 baseline。
- 注意：skill 进入发现上下文不等于会正确触发或带来正向边际效用。

### Harness 与 Agent 选择

- 来源：[OpenAI — Harness engineering](https://openai.com/index/harness-engineering/)
- 用途：repo knowledge base、短入口、按需文档、execution plan 和机械检查。
- 来源：[OpenAI — A practical guide to building agents](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf)
- 用途：先最大化单 Agent，再按实际需要增量引入多 Agent；manager 与 decentralized pattern baseline。
- 限制：二者是工程实践/通用指南，不是本项目在 Codex 上的实测结论。

### Compaction

- 来源：[OpenAI API — Compaction](https://developers.openai.com/api/docs/guides/compaction)
- 用途：理解长运行 Agent 如何压缩上下文，以及为何硬 context window 不等于无限有效记忆。
- 注意：API compaction 与 Codex 桌面任务的具体自动行为不能未经验证直接等同。

## Claude Code prior art

Claude Code 不在实现和兼容范围，但其原生协作能力是重要 prior art。

### Agent Teams

- 来源：[Anthropic — Orchestrate teams of Claude Code sessions](https://code.claude.com/docs/en/agent-teams)
- 用途：lead、独立 teammate、shared task list、dependencies、claim locking、direct message、hooks、shutdown/cleanup 和 token/coordination 限制。
- 关键限制：experimental；in-process teammate 不可 resume；状态可能滞后；无 nested teams；lead 固定；teammate 默认不使用 worktree 隔离。

### Parallel agents 与 worktrees

- 来源：[Anthropic — Run agents in parallel](https://code.claude.com/docs/en/agents)
- 来源：[Anthropic — Worktrees](https://code.claude.com/docs/en/worktrees)
- 用途：区分 subagent、Agent Teams、多 session worktree 和 batch，以及各自适用场景。
- 限制：只用于机制比较，不导入 Claude adapter。

## 社区开源近邻

以下仓库链接固定到 2026-08-10 通过 `git ls-remote HEAD` 取得的 revision；gstack、Superpowers 和 oh-my-codex 又在 2026-08-12 以本地 clean 源码快照核验，HEAD 未变化：

- [oh-my-codex @ b30127a](https://github.com/Yeachan-Heo/oh-my-codex/tree/b30127a0979c96046c8cd6312a8cd922c3516cad)：Codex workflow、team、goal/ledger、checkpoint、review/QA 和 model routing。
- [gstack @ 94993f7](https://github.com/garrytan/gstack/tree/94993f74012782fd94416dd44b8314f6363a13a4)：端到端 sprint、context save/restore、health、benchmark 和专业 workflow skills。
- [Superpowers @ 44c9b2d](https://github.com/obra/superpowers/tree/44c9b2d6e889982ac18c27d05a19fefe335194e1)：worktree、TDD、subagent-driven development、两阶段 review 和 skill 行为测试。
- [Gas Town @ 649b832](https://github.com/gastownhall/gastown/tree/649b832b7672bc7a2dbef26f5983aba6198b819b)：git-backed ledger、mail、handoff、watchdog、merge queue、scheduler 和 telemetry。

2026-08-21 又按用户提供的并行开发系统清单核验以下当前 HEAD，用于 D-032 的 Codex 原生组合设计：

- [Agent Orchestrator @ 52fde02](https://github.com/Untrivial-ai/agent-orchestrator/tree/52fde027975fdeacd49b98d13c172ed30b79042e)：长期 orchestrator/worker、SQLite/CDC、持久事实派生状态、Prompt 分层、CI/review 反馈路由和一任务一 worktree；Apache-2.0。其 daemon 与 Agent adapter 不是本项目运行目标。
- [CCPM @ 7d7e462](https://github.com/automazeio/ccpm/tree/7d7e4623bc6d4c0c9ba66ca6bfecd7e5261dc697)：PRD→Epic→Task、`depends_on`、`parallel`、`conflicts_with`、GitHub sync 与确定性状态脚本；MIT。Epic 内多个 stream 可共享 worktree，因此只复用规划语义。
- [Parallel Code @ 9b47562](https://github.com/johannesjo/parallel-code/tree/9b47562c4ccf6c22680dda884935750c1d63d4de)：一任务一 branch/worktree、集中终端/diff/CI 和人工 merge/discard；MIT。它启动外部 Agent CLI，不替代 Codex Desktop 原生 task。
- [Conductor worktree 文档](https://www.conductor.build/docs/concepts/git-worktrees)：workspace 绑定文件、branch、commands、chat 和 review flow 的界面参照；只学习交互模型。

这些仓库是机制、规模与失败处理的参照，不是竞品，也不是兼容目标。文档或源码存在不能替代安装后的黑盒复现。

## 长时与多 Agent 能力研究

### 长时 coding harness

- 来源：[Anthropic — Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- 来源：[Anthropic — Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)
- 用途：structured feature/progress artifact、fresh context + handoff、planner/generator/evaluator 分离。
- 限制：特定模型和任务；不能外推为 Codex 默认最佳结构。

### Parallel compiler stress test

- 来源：[Anthropic — Building a C compiler with a team of parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler)
- 用途：高成本、多周、多 session 能力上限，以及独立失败项易并行、单一 kernel bottleneck 难并行的直接观察。
- 限制：研究原型和压力测试，不是普通项目的成本收益证明。

### 多 Agent scaling 与失败

- 来源：[Kim et al., Towards a Science of Scaling Agent Systems](https://arxiv.org/abs/2512.08296)
- 用途：任务可并行性、固定预算、协调开销、拓扑和错误放大的量化假设。
- 来源：[Cemri et al., Why Do Multi-Agent LLM Systems Fail?](https://arxiv.org/abs/2503.13657)
- 用途：specification/system design、inter-agent misalignment、verification/termination failure taxonomy。
- 限制：不是当前 Codex 软件工程专项 benchmark；论文数值只作条件化 baseline。

## Skills 实证、维护与安全

### 边际效用

- 来源：[Han et al., SWE-Skills-Bench](https://arxiv.org/abs/2603.15401)
- 用途：有/无 skill 的成对、确定性验收设计；专业 skill、无收益 skill 和版本冲突负例。
- 限制：很新的预印本；本轮无法通过 `git ls-remote` 复核论文所列仓库，不能把论文结果当作当前 Codex 总体结论。

### 复用与维护

- 来源：[Gao et al., From Registry to Repository](https://arxiv.org/abs/2607.00911)
- 用途：把 skill 看作会被复制、定制、积累和漂移的软件 artifact。
- 限制：观察性生态研究，不证明某种目录结构必然更优。

### 供应链与权限

- 来源：[Yang et al., SkillGate](https://arxiv.org/abs/2607.25619)
- 来源：[Pan et al., SkillGuard](https://arxiv.org/abs/2606.03024)
- 用途：恶意 skill、context influence、脚本/工具 side effect、permission manifest 和运行时监控的威胁输入。
- 限制：两项均为很新的预印本；项目需要独立 threat model 和当前 Codex 实验。

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
- 社区仓库引用尽量固定 revision，机制声明区分“文档写明”和“已在本项目复现”；
- 社区反馈可用于发现场景和失败模式，但不能单独确定默认阈值；
- 搜索未发现某个官方能力不等于证明它不存在；
- 每次冻结产品行为或数值结论，都应记录版本、日期、环境和复现步骤。
