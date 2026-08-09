# 13. 决策日志

这里记录已经接受的项目级决策。新决策只能通过新增记录替代旧决策，不静默改写历史。

## D-001：建立正式工程项目

- 日期：2026-08-09
- 状态：Accepted
- 决策：在 `D:\Desktop\Codex多任务工程系统` 建立独立 Git 项目和主任务。
- 原因：范围已经超过单份提示词或单个 skill，包含原理、范式、worker taxonomy、协议、评测和生命周期治理。

## D-002：只面向 Codex

- 日期：2026-08-09
- 状态：Accepted
- 决策：不设计平台无关核心，不加入 Codex/Claude adapter，也不做 Claude Code 预留。
- 原因：专注把 Codex 当前能力做深；未来 Claude Code 版本若有必要，单独立项。

## D-003：大型多-skill 套件

- 日期：2026-08-09
- 状态：Accepted
- 决策：产品形态参考 gstack/superpowers 的多-skill 工程，不做单一巨型 `SKILL.md`；按用户入口、编排范式和 worker 角色组织，并使用渐进式披露。

## D-004：范式与 worker 正交

- 日期：2026-08-09
- 状态：Accepted
- 决策：编排范式、角色、执行身份、历史来源、workspace、生命周期和模型策略分别建模，再按任务组合。
- 原因：`worker`、同目录 fork、worktree 和 ABC 流水线不是同一类别。

## D-005：默认混合架构

- 日期：2026-08-09
- 状态：Accepted
- 决策：默认由高能力主编排者维护目标和架构；长期任务作为模块 owner；subagent 处理局部短任务；单一 integrator 接收；CI/Gate 提供机械证据。
- 补充：默认开发流是 hub-and-spoke + contract-parallel，默认集成流是 stage pipeline，高风险点插入 maker-checker。项目不同阶段可以切换范式。

## D-006：A2A 语义复用而非重造协议

- 日期：2026-08-09
- 状态：Accepted
- 决策：复用 A2A 的 Task、Message、Part、Artifact、状态和上下文语义；第一版沿用 Codex 原生消息和 Git/artifact，不搭建完整 A2A 网络服务。

## D-007：Artifact-first 和 proof-carrying handoff

- 日期：2026-08-09
- 状态：Accepted
- 决策：消息只承载控制信息和摘要；大型内容与证据进入 artifact。昂贵测试结果绑定 revision、suite 和环境，接收方先验证证据，再运行新事实所需的 affected/integration Gate。

## D-008：模型分层先做方案，后做对照

- 日期：2026-08-09
- 状态：Accepted
- 决策：采用结构化 brief + 高能力编排者 + 按难度选择 worker 模型 + 升级机制作为初版假设。具体模型名、thinking 和阈值必须实验决定。

## D-009：Token telemetry 延后但不忽略

- 日期：2026-08-09
- 状态：Accepted
- 决策：Phase 0 不因缺少 token 记录而停滞；评测 schema 预留 token/成本字段，后续通过产品 telemetry 或外部工具记录。

## D-010：任务完成后的保留政策

- 日期：2026-08-09
- 状态：Accepted
- 决策：主编排者和活动 component owner 保留；一次性任务在产物被接收后归档；上下文老化时通过 artifact + handoff 轮换；任务归档与 worktree 删除分开处理。

## D-011：任务与 subagent 采用混合模式

- 日期：2026-08-09
- 状态：Accepted
- 决策：不把两者做成互斥方案。任务承担长期身份、历史、workspace 和交接；subagent 承担父任务内部短工作。

## D-012：先文档，后实现

- 日期：2026-08-09
- 状态：Accepted
- 决策：立项阶段先保存完整讨论、形成设计和评测基线；未确认第一阶段计划前不直接生成全部 skills。
