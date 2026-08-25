# 17. 术语表

| 术语 | 本项目含义 |
|---|---|
| Task / 任务 | 可独立存在、具有历史和状态的 Codex 会话；在 schema 中也可能指其中一项工程工作，需看上下文 |
| Thread | 底层工具对 Codex task 的常见命名；用户文档统一称任务 |
| Session / 会话 | 本项目讨论并行执行单元时的历史泛称；active workflow 落到 Codex Desktop 时对应 task/thread。CLI session 只出现在历史兼容证据中，不是后续执行后端 |
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
| Filesystem boundary | worker 的 cwd、允许根目录和可写路径边界 |
| Git boundary | worker 使用的 repository、branch、HEAD、dirty 状态和所有权边界 |
| Runtime context boundary | Codex 会话加载的 user config、memory、skills、plugins、MCP、模型设置和上下文预算 |
| 编排范式 | 多个执行者在一个阶段如何分工、通信和交接的工作拓扑 |
| Artifact | 可持久化、可引用和可校验的任务产物 |
| Evidence | 把完成/测试声明绑定到 revision、命令、环境和结果的证据 artifact |
| Proof-carrying handoff | 携带可验证证据而非仅有自然语言声明的交接 |
| Canonical run manifest | 一次 run 中 revision、tree、路径、hash、命令、预算和授权的单一机器事实源；其他 brief/preregistration/receipt 是它的 projection |
| Projection | 从 canonical manifest 机器生成或验证的角色/阶段视图，不独立拥有重复身份事实 |
| Preregistration | 在 dispatch 或实验前冻结 manifest/brief identity、输入 hash、runtime roots、授权与停止条件的机器记录；用于防止看到结果后移动条件 |
| Dispatch bundle | `team-run` 准备的每 lane Brief/Prompt/workspace/runtime/preflight 绑定集合；不含尚未创建的 thread/task ID，也不等于已派发 |
| Parent preflight receipt | 在创建真实 worker 前，由主编排者记录 task project 与计划 workspace Git 身份、cleanliness 和边界检查的机器回执 |
| Worker preflight receipt | 由真实 worker 在 assigned workspace 内再次验证 cwd/common-dir/branch/HEAD/clean 与 Brief 后写出的独占回执 |
| Status facts | manifest-bound 的持久观察：task/workspace/report/evidence/acceptance/integration/review/blocker/archive；不保存派生 UI 状态 |
| Status snapshot | 从一份 status facts 和当前 run receipts 确定性生成的可重建状态视图，包含 lane/run status、reason、blocking dependencies 和 next action |
| Derived status | 根据持久事实按风险优先级计算的显示状态；不能反向当作新事实或依赖完成证明 |
| Integration candidate | 一条 lane 的 exact 集成候选；绑定 manifest、worker receipt、report/evidence hash、workspace base/HEAD/tree、ordinary status 和 ownership 内 changed files |
| Integration plan | 按 canonical manifest 顺序排列已验证 candidates 的非 mutation 计划；本身不授权 Git 合并或 Gate 命令 |
| Integration apply receipt | 记录指定 plan 在 integrator workspace 的 before/after commit/tree、每个 merge 结果和错误的回执 |
| Recovery lineage | 多个 append-only run 通过 predecessor 与 exact candidate/evidence 连接的恢复链；后继成功不改写前驱失败 |
| Recovery candidate | 用 clean descendant commit/tree 或 dirty patch + deterministic snapshot 冻结的 exact 恢复输入 |
| Recovery plan | 绑定 immutable predecessor、candidate、复用 proof、一个新事实、allowed commands/paths、命令预算和 stop rule 的非 live successor 计划 |
| Recovery brief | 对 recovery plan 的非 live 投影；不含 thread ID，不授权创建 task、修改 workspace 或执行命令 |
| Gate receipt | 绑定 target identity、命令、环境、exit、摘要和 artifact hash 的机器可验收记录 |
| Review receipt | 将 reviewer lane、decision、findings bytes 和 passed Gate exact target 绑定的审查事实 |
| Finish audit | 在 milestone 前重验 Gate/review target，并分开记录 ordinary、ignored、Git operation residue 和 run inventory 的审计 |
| Milestone result | 对 passed Gate、approved review 和 ready audit 的非破坏性收尾结论；只列出 archive/cleanup 候选，不执行它们 |
| Team route | 统一 `team` 入口从 canonical run artifact 派生的下一 phase 建议；包含证据 hash 和授权提示，但不是执行授权 |
| Gate | 进入下一阶段前必须满足的机械或人工验收条件 |
| Affected Gate | 只覆盖某次组合变更所引入新风险的测试/检查 |
| Active roster | 当前活跃任务、角色、workspace、状态和唤醒条件清单 |
| Integration queue | 记录 worker 交付的接收顺序、revision、证据、review 和集成状态的持久 artifact；不是后台 merge daemon |
| Context rot | 上下文仍在硬限制内，但因长度、噪声、位置或旧信息干扰而表现下降 |
| Artifact-first | 大输出与事实进入 artifact，消息只发摘要、状态和引用 |
| Fail closed | 不能证明操作安全或证据有效时停止，而不是猜测继续 |
| Ordinary clean | tracked/untracked 的普通 Git porcelain 无变化；不自动包含 ignored 文件或 Git operation residue |
| Ignored clean | 单独审计 Git ignored 文件后没有新增残留；与 ordinary clean 是两个事实 |
| Prior art | 官方、社区或研究中已经公开的机制、实现、实验与失败证据；用于复现和约束设计，不等于本项目已验证能力 |
| Capability contract | 在固定 Codex 客户端、工具 schema、OS、Git 和日期下，由可复现实验确认的能力与失败行为快照 |
| Pattern profile | 供 `team-plan` 选择编排拓扑的按需 reference；只有形成独立触发、行为和验收后才晋升 skill |
| Skill marginal utility | 相同任务与环境中，加载 skill 相对 no-skill baseline 带来的质量、成本、时间或失败变化 |
| Research maturity | 只有来源、假设或实验设计，不能声称稳定可用 |
| Incubating maturity | 已有可执行实现和初步证据，但兼容范围与失败模式仍在收敛 |
| Stable maturity | 在声明的环境与版本中通过触发、行为、错误、恢复和回归验收 |
| Deprecated maturity | 已被产品变化、协议或新证据替代，不再默认路由但保留迁移和历史记录 |
