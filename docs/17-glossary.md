# 17. 术语表

| 术语 | 本项目含义 |
|---|---|
| Task / 任务 | 可独立存在、具有历史和状态的 Codex 会话；在 schema 中也可能指其中一项工程工作，需看上下文 |
| Thread | 底层工具对 Codex task 的常见命名；用户文档统一称任务 |
| Worker | 领取有边界工程责任的执行者通称，不等于某种 workspace |
| Subagent | 父任务内部创建的短生命周期 Agent |
| 主编排者 | 维护目标、架构、计划、分配、风险和最终验收的主任务 |
| Component owner | 跨多轮持续负责某个模块的长期任务 |
| Integrator | 接收 worker 产物、控制合并顺序并运行集成 Gate 的角色 |
| Fork | 从已有任务历史分叉新任务；不自动等于 Git branch 或新 worktree |
| Handoff | 执行责任和工作状态从一个任务移交给另一个任务 |
| Rehydrate | 新任务从仓库文档、状态和 artifact 恢复，而非复制完整旧聊天 |
| Checkout | 一个 Git 工作目录及其 index/HEAD 状态 |
| Worktree | Git 提供的附加工作目录，使同一仓库可同时检出多个状态 |
| Managed worktree | Codex 为任务管理的 worktree |
| Permanent worktree | 项目长期维护的既有 worktree |
| 编排范式 | 多个执行者在一个阶段如何分工、通信和交接的工作拓扑 |
| Artifact | 可持久化、可引用和可校验的任务产物 |
| Evidence | 把完成/测试声明绑定到 revision、命令、环境和结果的证据 artifact |
| Proof-carrying handoff | 携带可验证证据而非仅有自然语言声明的交接 |
| Gate | 进入下一阶段前必须满足的机械或人工验收条件 |
| Affected Gate | 只覆盖某次组合变更所引入新风险的测试/检查 |
| Active roster | 当前活跃任务、角色、workspace、状态和唤醒条件清单 |
| Context rot | 上下文仍在硬限制内，但因长度、噪声、位置或旧信息干扰而表现下降 |
| Artifact-first | 大输出与事实进入 artifact，消息只发摘要、状态和引用 |
| Fail closed | 不能证明操作安全或证据有效时停止，而不是猜测继续 |
