# 00. 项目章程

## 项目名称

**Codex 多任务工程系统**

这是工作名称。名称可以以后调整，但范围不会因此变成跨平台项目。

## 背景

Codex 中的长期任务已经更接近独立工程成员：它们有独立历史，可以在独立 worktree 中工作，可以收发任务消息，也能在内部调用 subagent。官方产品、Claude Agent Teams、oh-my-codex、gstack、Superpowers、Gas Town、Agent Orchestrator、CCPM、Parallel Code/Conductor 和长时 Agent 实验已经分别展示了这些机制的不同组合，但没有替代针对当前 Codex 环境的系统复现与边界研究。

但“任务数量翻倍”不等于“产出翻倍”。没有系统治理时，并发会带来新的损失：重复探索、契约漂移、同文件冲突、合并失败、重复测试、上下文老化、消息噪声、无人回收的任务和无法审计的完成声明。

## 愿景

形成一个社区可阅读、可安装、可复现的 Codex 多任务实践库：既分享如何用主任务、长期任务、subagent、worktree、Git 和验证证据完成工程，也公开这些组合何时无效、退化或应当停止。

“工程队伍”是解释角色关系的运行模型，不是产品定位。项目不追求商业化或创新性证明；有价值的已有机制可以直接复现、组合和改进，只要来源、条件与验证清楚。

## 核心目标

1. 建立一套可按项目特征选择的多任务编排范式，而不是固定一种流程。
2. 建立角色、执行环境、历史来源、权限和生命周期彼此正交的 worker 模型。
3. 建立结构化任务、artifact、消息、handoff 和验收约定。
4. 用 worktree、所有权和集成闸门控制并行风险。
5. 用分层验证和证据复用减少昂贵测试的重复执行。
6. 建立模型能力、thinking、上下文容量、轮换和成本的可测策略。
7. 形成类似 gstack / superpowers 的多-skill Codex 工程，并做到成熟的渐进式披露。
8. 对每个自动化承诺给出可复现评测，明确边界和失败模式。
9. 持续调查官方与社区 prior art，把“已实现、已观察、合理推测、尚未验证”公开分层。
10. 让每个候选 skill 接受 no-skill baseline、版本兼容和失败注入，而不是用目录数量证明价值。

## 非目标

- 不开发平台无关协议核心。
- 不开发 Codex adapter 或 Claude Code adapter。
- 不在本项目内实现 Claude Code 版本。
- 不重新发明完整的 Agent-to-Agent 网络协议。
- 不把全部工作塞进一个巨型 `SKILL.md`。
- 不承诺完全无人监督地自动合并、部署或执行破坏性操作。
- 不以线程数、消息数或并发数作为成功指标。
- 不做商业产品定位、市场验证或竞争差异化论证。
- 不把“必须创新”设为收录条件，也不把 prior art 已经做过某项能力视为停止研究的理由。
- 不为了看起来轻量而预先限制长期 skills 数量；同时不把尚未验证的分类项冒充稳定 skill。

## 核心用户

首要读者和使用者是希望研究、复现和分享 Codex 多任务工程方法的社区开发者，也包括用 Codex 完成中大型软件工程的个人或小团队。他们既需要可运行的方法，也需要知道哪些结论只来自特定版本、模型、仓库或实验。

## 成功标准

项目成熟时至少应证明：

- 能根据依赖图和风险选择合适编排范式；
- 并行 worker 不会默认争抢同一文件或共享未声明状态；
- 任务输出可以被另一个任务无歧义接收；
- 长测试在证据充分时不会被机械重复，证据失效时又能正确重跑；
- worker 的模型档位和 thinking 可按任务难度调度，并有升级机制；
- 长期任务在上下文衰减前可通过可验证 handoff 轮换；
- 临时任务完成后可归档，主任务仍能从仓库恢复项目状态；
- skills 能被按需发现和加载，不要求每次注入整个方法论；
- 与单任务、纯 subagent 和无规范多任务基线相比，在质量、吞吐、成本或等待时间上有可测优势。
- prior-art 来源、查询、代码 snapshot、实验 artifact 与结论关系可追溯；
- 某个 skill 没有正向边际效用或出现版本冲突时，项目能如实降级、改写或废弃它；
- 社区能够仅凭仓库中的说明和固定输入复现至少一个完整纵向切片及其失败案例。

## 当前阶段边界

Phase 0 已完成项目目录、Git 基线、文档体系、prior-art 调查和设计基线。M1 已用 OutputGuard Run02–Run10 建立一条保留失败历史的 Desktop recovery lineage，并通过 public、fresh review 和单次 sealed Gate；它不是一次无中断多任务成功，也没有证明多任务优于 single。

截至 2026-08-24，项目进入 M1.3：`team-plan` v0.1 已在 `main`；stacked feature branches 已实现 `team-run` v0.1 非 live 准备层和 `team-status` v0.1 只读派生层。前者生成 preregistration、runtime roots、preflight、Prompt/dispatch bundle但不创建 task；后者从 durable facts 派生状态但不读取 live task。下一步是审查/接收两层并实现 Codex-native 只读 observation adapter，再由用户单独授权最小 Desktop live pilot；`team-integrate`、`team-finish` 与 `team-recover` 仍待实现。只有 workflow 依赖未知产品语义时才补最小 capability probe，未实测部分继续标为 `unknown`。
